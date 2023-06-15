# For now global variables and configuration will be stored in this file.
# In the future consider moving some of this to a "non-executable"
# configuration file.

# some logging setup
import logging

import __main__ as main

LOG_LEVEL = logging.INFO

if main.__file__ == "server.py" or main.__file__ == "./server.py":
    LOG_LEVEL = logging.DEBUG

logging.basicConfig(format="%(levelname)s: %(message)s", level=LOG_LEVEL)

# Just a random chunk size to send the file in pieces,
# should be the same as the chunk size used to write
CHUNK_SIZE = 4096
NONCE_SIZE = 32
PORT = 29977


def get_file_logger(logger_name, filepath="/var/tmp/warp.log"):
    """
    Returns a formatted logger that logs to a file and the console. Takes the
    logger name as a parameters and optional filepath.
    """
    l = logging.getLogger(logger_name)
    fh = logging.FileHandler(filepath)
    fh.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    l.setLevel(LOG_LEVEL)
    l.addHandler(fh)

    return l


logger = get_file_logger("warp")
