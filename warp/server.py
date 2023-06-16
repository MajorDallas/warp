#!/usr/bin/env python3


"""
This is the server script that will be started by client over SSH, it takes
two arguments...
"""

import os
import sys
from os.path import expanduser

import plac
from rpyc.utils.server import ThreadedServer

from config import logger
from server_transfer_controller import ServerTransferController

logger.setLevel("DEBUG")
logger.propagate = True


def main():
    os.chdir(expanduser("~"))
    server = ThreadedServer(
        ServerTransferController,
        hostname="localhost",
        port=0,
        protocol_config={"allow_public_attrs": True},
    )
    sys.stdout.write(str(server.port))
    sys.stdout.write("     ")
    server.start()


if __name__ == "__main__":
    plac.call(main)
