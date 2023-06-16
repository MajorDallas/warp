import os
import threading
from typing import Union

from common_tools import getHash
from config import CHUNK_SIZE, logger

from transfer_manager import TransferManager


# From http://theorangeduck.com/page/synchronized-python
def synchronized(method):
    outer_lock = threading.Lock()
    lock_name = "__" + method.__name__ + "_lock" + "__"

    def sync_method(self, *args, **kws):
        with outer_lock:
            if not hasattr(self, lock_name):
                setattr(self, lock_name, threading.Lock())
            lock = getattr(self, lock_name)
            with lock:
                return method(self, *args, **kws)

    return sync_method


class FileTransferAgent:
    _base_server_file_size: Union[int, float]
    _base_server_validated_size: Union[int, float]
    _file_size: int

    def __init__(
        self,
        udt,
        transfer_manager,
        file_name,
        file_dest,
        verify,
        createDirs,
        stat,
    ):
        self.file_dest = file_dest
        self.file_name = file_name
        self.verify = verify
        self.stat = stat
        self.is_transferring = False
        self.transfer_finished = False
        self.transfer_success = False
        self.is_verifying = False
        self.udt = udt
        self.transfer_manager: TransferManager = transfer_manager
        self.createDirs = createDirs
        self.block_count = 0

    def get_progress(self):
        if self.is_verifying or (
            self.is_transferring is False and self.transfer_finished is True
        ):
            return self.file_size
        elif self.is_transferring is False and self.transfer_finished is False:
            return self.base_server_validated_size
        elif self.is_transferring is True and self.transfer_finished is False:
            return self.udt.get_total_recieved()
        return 0

    @synchronized
    def get_server_file_size(self):
        if not hasattr(self, "_base_server_file_size"):
            self._base_server_file_size = (
                self.transfer_manager.get_size_and_init_file_path(
                    self.server_file_path
                )
            )
        return self._base_server_file_size

    @property
    def base_server_file_size(self) -> Union[int, float]:
        return self.get_server_file_size()

    @synchronized
    def get_server_validated_size(self):
        if not hasattr(self, "_base_server_validated_size"):
            if self.base_server_file_size > 0:
                self.block_count = 0
                if self.base_server_file_size != self.file_size:
                    self.block_count = self.transfer_manager.get_blocks(
                        self.server_file_path
                    )
                file_hash = self.transfer_manager.get_file_hash(
                    self.server_file_path
                )
                if not self.verify_partial_hash(self.file_name, file_hash):
                    logger.debug("Client and server side partial hash differ.")
                    self.transfer_manager.overwrite_file(self.server_file_path)
                    self.block_count = 0
                elif self.block_count == 0:
                    logger.debug("File already transfered")
                    self.transfer_finished = True
                    self.transfer_success = True
                    self.is_transferring = False
                    self._base_server_validated_size = (
                        self.base_server_file_size
                    )
                    return self._base_server_validated_size
            else:
                # This will create the file on the server side
                self.transfer_manager.overwrite_file(self.server_file_path)
            self._base_server_validated_size = self.block_count * CHUNK_SIZE
        return self._base_server_validated_size

    @property
    def base_server_validated_size(self) -> Union[int,float]:
        return self.get_server_validated_size()

    @synchronized
    def get_server_file_path(self):
        if not hasattr(self, "_server_file_path"):
            result = self.transfer_manager.validate_filepath(
                self.file_dest, self.file_name, self.createDirs
            )
            self.validate_success = result[0]
            self._server_file_path = result[1]

        return self._server_file_path

    @property
    def server_file_path(self) -> str:
        return self.get_server_file_path()

    @synchronized
    def get_total_size(self) -> int:
        if not hasattr(self, "_file_size"):
            self._file_size = os.path.getsize(self.file_name)

        return self._file_size

    @property
    def file_size(self) -> int:
        return self.get_total_size()

    def send_file(self):
        logger.debug("Source " + self.file_name + " Dest: " + self.file_dest)

        logger.debug("Saving to... " + self.server_file_path)

        if not self.validate_success:
            self.is_transferring = False
            self.transfer_finished = True
            self.transfer_success = False
            return

        # This will compute the block count
        if self.base_server_validated_size == self.file_size:
            return

        self.udt.connect()
        self.is_transferring = True
        self.udt.send_file(
            self.file_name,
            self.server_file_path,
            self.block_count,
            self.file_size,
        )

        if self.stat:
            stats = os.stat(self.file_name)
            self.transfer_manager.set_timestamps(
                self.server_file_path, (stats.st_atime, stats.st_mtime)
            )
            self.transfer_manager.set_protection(
                self.server_file_path, stats.st_mode
            )

        self.is_transferring = False

        if self.verify:
            self.is_verifying = True
            if self.verify_partial_hash(
                self.file_name,
                self.transfer_manager.get_file_hash(self.server_file_path),
            ):
                self.transfer_success = True
            else:
                logger.debug("File failed validation check.")
                self.transfer_success = False
            self.is_verifying = False
        else:
            self.transfer_success = True
        self.transfer_finished = True

    def file_block_count(self, file_src):
        return os.path.getsize(file_src) / CHUNK_SIZE

    def verify_partial_hash(self, file_src, partial_hash):
        """
        Takes a file source and hashes the file up to block count and then
        compares it with the partial hash passed in, fails if they do not match.
        """
        my_hash = getHash(file_src)
        return partial_hash == my_hash
