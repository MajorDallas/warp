import getpass
import logging
import sys
import threading
from typing import Optional, cast

import paramiko
import rpyc
from paramiko import SSHClient

from common_tools import fail
from config import logger
from forward import forward_tunnel

hostkeytype = None
hostkey = None

# suppress paramiko logging
logging.getLogger("paramiko").setLevel(logging.WARNING)


class Connection:
    def __init__(self, hostname, username, ssh_port=22):
        self.channel: Optional[rpyc.Connection] = None
        self.hostname = hostname
        self.username = username
        self.ssh_port = ssh_port

    def connect_ssh(self):
        """Initiate an SSH connection using the information passed to the
        instance constructor. Upon successful connection, run the `warp-server`
        command on the remote host.
        """
        self.client = SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.load_system_host_keys()
        except paramiko.hostkeys.InvalidHostKey:
            logger.critical(
                "A key in known_hosts could not be parsed. This likely does NOT"
                " mean there is a bad key--Paramiko's host key parser is"
                " limited to plain host keys: no commands, cert-authority,"
                " or anything other than the host list, key type, and key."
                " Check for such keys and move them into a temporary back-up"
                " file, then try again. See Github issues #771 and #386"
                " for details and, god willing, updates."
            )
            raise

        try:
            # Attempt connecting with ssh-agent or default keys, if available.
            self.client.connect(
                self.hostname, username=self.username, port=self.ssh_port
            )
        except (
            paramiko.PasswordRequiredException,
            paramiko.AuthenticationException,
            paramiko.ssh_exception.SSHException,  # type: ignore
        ):
            # Fallback to password auth.
            password = getpass.getpass(
                "Password for %s@%s: " % (self.username, self.hostname)
            )
            try:
                self.client.connect(
                    self.hostname,
                    username=self.username,
                    port=self.ssh_port,
                    password=password,
                )
            except paramiko.AuthenticationException:
                logger.exception(
                    "SSH Authentication Failed. Tried: pubkey, password."
                )
                raise
        (sshin1, sshout1, ssherr1) = self.client.exec_command("warp-server")
        if err := ssherr1.read(500):
            raise RuntimeError(
                "Execution of 'warp-server' on the remote host may have failed."
                " This message was printed to stderr (truncated to 500 bytes):"
                f"\n\n{err.decode(errors='replace')}"
            )
        self.comm_port = int(sshout1.read(5))

    def connect(self):
        """Start a UDT listener on the remote host using Connection.connect_ssh,
        establish a UDT connection to it, and return the rpyc.Connection through
        which data can be dumped into the UDT tunnel.
        """
        self.connect_ssh()

        # Now we start the port forwarding
        channel = forward_tunnel(
            0, "127.0.0.1", self.comm_port, self.client.get_transport()
        )
        self.forward_thread = threading.Thread(
            target=start_tunnel, args=(channel,)
        )
        self.forward_thread.setDaemon(True)
        self.forward_thread.start()

        self.channel = cast(
            rpyc.Connection,
            rpyc.connect(
                "localhost",
                port=channel.socket.getsockname()[1],
                config={"allow_public_attrs": True},
            ),
        )

        return self.channel

    def close(self):
        pass
        # self.forward_thread.exit()

    @staticmethod
    def unpack_remote_host(remote_host):
        """Parses the hostname and breaks it into host and user.

        Modified from paramiko.
        """
        username = ""
        hostname = ""
        # We use port 22 for ssh
        port = 22

        if remote_host.find("@") >= 0:
            username, hostname = remote_host.split("@")

        if len(hostname) == 0 or len(username) == 0:
            fail("Hostname/username required.")

        if hostname.find(":") >= 0:
            hostname, portstr = hostname.split(":")
            port = int(portstr)

        return (username, hostname, port)


def start_tunnel(channel):
    channel.serve_forever()
