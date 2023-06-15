import errno
import hashlib
import os
import signal
import sys
from functools import wraps

from config import CHUNK_SIZE, logger


def getHash(file, block_count=0):
    """
    Returns a sha256 hash for the specified file.
    Eventually sent to server to check for restarts.
    """
    hash = hashlib.sha256()
    i = 0
    with open(file, "rb") as file:
        while True:
            data = file.read(CHUNK_SIZE)
            if not data or (block_count != 0 and i >= block_count):
                file.close()
                return hash.hexdigest()
            i += 1
            hash.update(data)


def fail(msg):
    """
    Simple fail function that prints and logs the error message and then exits.
    """
    logger.error(msg)
    sys.stderr.write(msg)
    sys.exit(1)


# from: http://stackoverflow.com/questions/2281850/timeout-function-if-it-takes-too-long-to-finish


class TimeoutError(Exception):
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator
