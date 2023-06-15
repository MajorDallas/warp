import sys
from config import *
from common_tools import *
from paramiko import SSHClient
import paramiko, getpass
import threading
from forward import *
import rpyc

hostkeytype = None
hostkey = None

# suppress paramiko logging
logging.getLogger("paramiko").setLevel(logging.WARNING)


class Connection:
    def __init__(self, hostname, username, ssh_port=22):
        self.channel = None
        self.hostname = hostname
        self.username = username
        self.ssh_port = ssh_port

    def connect_ssh(self):
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.client.connect(
                self.hostname, username=self.username, port=self.ssh_port
            )
            (sshin1, sshout1, ssherr1) = self.client.exec_command("warp-server")
            self.comm_port = int(ssherr1.read(5))
        except (
            paramiko.PasswordRequiredException,
            paramiko.AuthenticationException,
            paramiko.ssh_exception.SSHException,
        ):
            password = getpass.getpass(
                "Password for %s@%s: " % (self.username, self.hostname)
            )
            (sshin1, sshout1, ssherr1) = self.client.exec_command("warp-server")
            self.comm_port = int(ssherr1.read(5))
            try:
                self.client.connect(
                    self.hostname,
                    username=self.username,
                    port=self.ssh_port,
                    password=password,
                )
            except paramiko.AuthenticationException as message:
                logger.error("Permission denied" + message)
                sys.exit(1)

    def connect(self):
        self.connect_ssh()

        # Now we start the port forwarding
        channel = forward_tunnel(
            0, "127.0.0.1", self.comm_port, self.client.get_transport()
        )
        self.forward_thread = threading.Thread(target=start_tunnel, args=(channel,))
        self.forward_thread.setDaemon(True)
        self.forward_thread.start()

        self.channel = rpyc.connect(
            "localhost",
            port=channel.socket.getsockname()[1],
            config={"allow_public_attrs": True},
        )

        return self.channel

    def close(self):
        pass
        # self.forward_thread.exit()

    @staticmethod
    def unpack_remote_host(remote_host):
        """
        Parses the hostname and breaks it into host and user. Modified from paramiko
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
