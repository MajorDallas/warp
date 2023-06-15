import random
import socket
import threading

from udt4py import UDTSocket

from common_tools import *
from config import *


class ServerUDTManager:
    def __init__(self, tcp_mode):
        self.tcp_mode = tcp_mode

        self.udt_sock = None
        self.conn = None

        self.sock = self.get_socket()
        self.port = self.sock.getsockname()[1]
        self.nonce = self.generate_nonce()
        self.size = 0

    def open_connection(self):
        if not self.tcp_mode:
            self.udt_sock = UDTSocket()
            self.udt_sock.bind(self.sock.fileno())
            self.udt_sock.listen()

        listening_thread = threading.Thread(target=self.accept_and_verify)
        listening_thread.start()

        return (self.port, self.nonce)

    def get_total_recieved(self):
        return self.size

    def accept_and_verify(self):
        if not self.tcp_mode:
            self.conn, addr = self.udt_sock.accept()
            logger.info("Connected by %s", addr)

            recvd_nonce = bytearray(NONCE_SIZE)
            self.conn.recv(recvd_nonce)
            recvd_nonce = str(recvd_nonce)
        else:
            self.conn, addr = self.sock.accept()
            logger.info("Connected by %s", addr)

            recvd_nonce = self.conn.recv(NONCE_SIZE)

        if recvd_nonce != self.nonce:
            fail(
                format(
                    "Received nonce %s doesn't match %s.",
                    recvd_nonce,
                    self.nonce,
                )
            )

        logger.debug("Nonce verified.")

    def receive_data(self, output_file, block_count, file_size):
        """
        Receives data and writes it to disk, stops when it is no longer receiving
        data.
        """

        def receive_data_threaded(output_file, block_count, file_size):
            logger.debug("Receiving data...")
            output_file = open(output_file, "r+")
            output_file.seek(block_count * CHUNK_SIZE)

            self.size = block_count * CHUNK_SIZE
            data = bytearray(CHUNK_SIZE)

            if not self.tcp_mode:
                while 1:
                    len_rec = self.conn.recv(data)
                    data = str(data)
                    output_file.write(data[:len_rec])
                    self.size += len_rec

                    if len_rec == 0 or str(self.size) == str(file_size):
                        break
            else:
                while 1:
                    data = self.conn.recv(CHUNK_SIZE)
                    output_file.write(data)
                    self.size += len(data)
                    if len(data) == 0:
                        break

            logger.debug("Closing file...  " + output_file.name)
            output_file.close()

        thread = threading.Thread(
            target=receive_data_threaded,
            args=(output_file, block_count, file_size),
        )
        thread.start()

        return thread

    def get_socket(self):
        """
        Opens and returns a socket on an open port.
        """

        s = None

        if self.tcp_mode:
            sock_type = socket.SOCK_STREAM
        else:
            sock_type = socket.SOCK_DGRAM

        try:
            s = socket.socket(socket.AF_INET, sock_type)
        except socket.error as msg:
            fail(msg)
        try:
            s.bind(("", 0))
            if self.tcp_mode:
                s.listen(1)
        except socket.error as msg:
            s.close()
            fail(str(msg))

        return s

    def generate_nonce(self, length=NONCE_SIZE):
        """Generate pseudorandom number. Ripped from google."""
        return "".join([str(random.randint(0, 9)) for i in range(length)])
