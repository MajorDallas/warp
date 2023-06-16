import os
import sys
from typing import AnyStr, Tuple

from common_tools import getHash
from config import CHUNK_SIZE, logger


class TransferManager:
    def __init__(self):
        pass

    def __del__(self):
        pass

    def is_file(self, filepath):
        return os.path.isfile(filepath)

    def get_file_hash(self, filepath):
        return getHash(filepath)

    def get_blocks(self, filepath: AnyStr) -> float:
        return os.path.getsize(filepath) / CHUNK_SIZE

    def create_dir(self, directory):
        if not os.path.exists(directory):
            os.makedirs(directory)

    def overwrite_file(self, filepath):
        open(filepath, "w").close()

    def get_size(self, filepath):
        if not os.path.isfile(filepath):
            return 0
        else:
            return os.path.getsize(filepath)

    def set_timestamps(self, filepath, times):
        os.utime(filepath, times)

    def set_protection(self, filepath, bits):
        os.chmod(filepath, bits)

    def get_size_and_init_file_path(self, filepath):
        if not os.path.isfile(filepath):
            output_file = open(filepath, "w")
        else:
            output_file = open(filepath, "r+")

        output_file.close()

        return os.path.getsize(filepath)

    def total_size(self, files):
        size = 0
        for path in files:
            if os.path.isfile(path):
                size += os.path.getsize(path)
        return size

    def finish(self):
        sys.exit()

    def validate_filepath(
        self, filepath: str, client_path: str, create_dirs
    ) -> Tuple[bool, str]:
        """
        Validates the filepath, and returns the correct path
        """
        (head, tail) = os.path.split(filepath)
        if not tail:
            if not os.path.exists(head):
                result = f"Directory {head} does not exist."
                logger.exception(result)
                return (False, result)
            else:
                _, client_tail = os.path.split(client_path)
                return (True, os.path.join(head, client_tail))
        elif head != "" and not os.path.exists(head):
            if create_dirs:
                try:
                    self.create_dir(head)
                except OSError:
                    pass
                return (True, filepath)
            result = f"{filepath}: No such file or directory"
            logger.exception(result)
            return (False, result)

        elif not head and os.path.isdir(tail):
            _, client_tail = os.path.split(client_path)
            return (True, os.path.join(tail, client_tail))

        return (True, filepath)
