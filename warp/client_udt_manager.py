from config import *
from common_tools import *
import socket
from udt4py import UDTSocket


class ClientUDTManager:
    def __init__(self, server_controller, hostname, tcp_mode):
        self.server_controller = server_controller
        self.socket = None
        self.hostname = hostname
        self.port = None
        self.nonce = None
        self.tcp_mode = tcp_mode
        self.server_udt_manager = None

    def connect(self):
        self.server_udt_manager = self.server_controller.root.get_udt_manager()(
            self.tcp_mode
        )

        self.port, self.nonce = self.server_udt_manager.open_connection()

        self.connect_to_server()
        self.send_nonce()

    def send_file(self, file_src, file_dest, block_count, file_size):
        self.server_udt_manager.receive_data(file_dest, block_count, file_size)
        self.send_data(file_src, block_count)

    def connect_to_server(self):
        """
        Connects to the provided host and port returning a socket object.
        """

        if self.tcp_mode:
            logger.debug("TCP mode")
            sock_type = socket.SOCK_STREAM

            for res in socket.getaddrinfo(
                self.hostname, self.port, socket.AF_UNSPEC, sock_type
            ):
                af, socktype, proto, canonname, sa = res
                try:
                    self.socket = socket.socket(af, socktype, proto)
                except socket.error:
                    self.socket = None
                    continue
                try:
                    self.socket.connect(sa)
                except socket.error:
                    self.socket.close()
                    # No need to log error here, some errors are expected
                    self.socket = None
                    continue
                break

        else:
            self.socket = UDTSocket()
            self.socket.connect((socket.gethostbyname(self.hostname), self.port))

        if self.socket is None:
            fail("Could not connect to" + self.hostname)

    def send_nonce(self):
        if not self.tcp_mode:
            self.socket.send(bytearray(self.nonce))
        else:
            self.socket.sendall(self.nonce)

    def get_total_recieved(self):
        if self.server_udt_manager is None:
            return 0

        return self.server_udt_manager.get_total_recieved()

    def send_data(self, file_src, block_count=0):
        """
        Opens the file at the number of blocks passed in and uses that along with
        the other parameters to send a file to the host at the specified port.
        """
        f = open(file_src, "r")
        f.seek(block_count * CHUNK_SIZE)
        data = f.read(CHUNK_SIZE)
        byteData = bytearray(CHUNK_SIZE)
        while data:
            if not self.tcp_mode:
                byteData[0:CHUNK_SIZE] = data
                self.send_chunk(byteData)
            else:
                self.socket.sendall(data)
            data = f.read(CHUNK_SIZE)
        logger.debug("Data sent.")
        self.socket.close()
        f.close()

    def send_chunk(self, data):
        size = self.socket.send(data)
        if not size == len(data):
            self.send_chunk(data[size:])

    def generate_nonce(self, length=NONCE_SIZE):
        """Generate pseudorandom number. Ripped from google."""
        return "".join([str(random.randint(0, 9)) for i in range(length)])

    def __del__(self):
        if self.socket:
            self.socket.close()
