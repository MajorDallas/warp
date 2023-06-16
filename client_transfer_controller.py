import os
import threading
from functools import reduce
from multiprocessing.pool import ThreadPool
from typing import List, Tuple

from client_udt_manager import ClientUDTManager
from common_tools import fail
from config import logger
from file_transfer_agent import FileTransferAgent
from rpyc import Connection


class ClientTransferController:
    def __init__(
        self,
        server_channel: Connection,
        hostname,
        file_src,
        file_dest,
        recursive,
        tcp_mode,
        disable_verify,
        parallelism,
        follow_links,
        stat,
    ):
        self.server_channel = server_channel
        self.hostname = hostname
        self.file_src = file_src
        self.file_root_dest = file_dest
        self.file_dest = file_dest
        self.recursive = recursive
        self.verify = not disable_verify
        self.tcp_mode = tcp_mode
        self.parallelism = parallelism
        self.follow_links = follow_links
        self.stat = stat
        self.transfer_agents: List[FileTransferAgent] = []
        self.start_success = None

        self.files_processed = 0

    def start(self):
        start_thread = threading.Thread(target=self._start)
        start_thread.setDaemon(True)
        start_thread.start()

        return start_thread

    def _start(self):
        if os.path.isdir(self.file_src) and not self.recursive:
            fail(str(self.file_src) + " is a directory")
        if os.path.isfile(self.file_src) and self.recursive:
            fail(str(self.file_src) + " is a file")
        if not os.path.isfile(self.file_src) and not os.path.isdir(
            self.file_src
        ):
            fail("Source file not found")

        pool = ThreadPool(processes=self.parallelism)
        transfer_manager = self.server_channel.root.get_transfer_manager()
        if not self.recursive:
            try:
                transfer_agent = FileTransferAgent(
                    ClientUDTManager(
                        self.server_channel, self.hostname, self.tcp_mode
                    ),
                    transfer_manager,
                    self.file_src,
                    self.file_dest,
                    self.verify,
                    False,
                    self.stat,
                )
                self.files_processed += 1
            except EOFError:
                logger.error("Could not connect")
                self.start_success = False
                return
            self.transfer_agents.append(transfer_agent)
            pool.apply_async(transfer_agent.send_file)
        else:
            for directory, subdirs, files in os.walk(
                self.file_src, followlinks=self.follow_links
            ):
                # Make sure the directory we use on the server starts where we
                # want it to instead of having the same path the client has.
                server_directory = os.path.relpath(directory, self.file_src)
                if str(server_directory) == ".":
                    server_directory = ""
                for f in files:
                    file_dest = os.path.join(
                        self.file_root_dest, server_directory, f
                    )
                    file_src = os.path.join(directory, f)
                    try:
                        transfer_agent = FileTransferAgent(
                            ClientUDTManager(
                                self.server_channel,
                                self.hostname,
                                self.tcp_mode,
                            ),
                            transfer_manager,
                            file_src,
                            file_dest,
                            self.verify,
                            True,
                            self.stat,
                        )
                    except EOFError:
                        logger.error("Could not connect")
                        self.start_success = False
                        return

                    self.files_processed += 1
                    self.transfer_agents.append(transfer_agent)

                    pool.apply_async(transfer_agent.send_file)

        self.start_success = True

    def get_server_received_size(self):
        pool = ThreadPool(processes=20)
        res = pool.map(lambda x: x.get_progress(), self.transfer_agents)
        pool.close()
        return reduce(lambda x, y: x + y, res, 0)

    def is_transfer_validating(self) -> bool:
        pool = ThreadPool(processes=20)

        res = pool.map(
            lambda x: (x.transfer_finished, x.is_verifying),
            self.transfer_agents,
        )

        pool.close()
        status: Tuple[bool, bool] = reduce(
            lambda x, y: x if y[0] is True else (x[0] or y[1], x[1] and y[1]),
            res,
            (False, True),
        )
        return status[0] and status[1]

    def get_total_transfer_size(self):
        if not hasattr(self, "_get_total_transfer_size"):
            pool = ThreadPool(processes=20)

            res = pool.map(lambda x: x.file_size, self.transfer_agents)

            pool.close()
            self._get_total_transfer_size = reduce(lambda x, y: x + y, res, 0)
        return self._get_total_transfer_size

    transfer_size = property(get_total_transfer_size)

    def is_transfer_finished(self):
        for i in self.transfer_agents:
            if not i.transfer_finished:
                return False
        return True

    def get_files_transfered(self):
        return reduce(
            lambda x, y: x + (1 if y.transfer_finished else 0),
            self.transfer_agents,
            0,
        )

    def is_transfer_success(self):
        return (
            reduce(
                lambda y, x: 0 + y if x.transfer_success is True else 1 + y,
                self.transfer_agents,
                0,
            )
            == 0
        )

    def close(self):
        self.server_channel.root.get_transfer_manager().finish()
