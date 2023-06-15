#!/usr/bin/env python


"""
This is the server script that will be started by client over SSH, it takes
two arguments...
"""

import os
import sys
from os.path import expanduser

import plac
from rpyc.utils.server import ThreadedServer

from common_tools import *
from config import *
from server_transfer_controller import ServerTransferController

logger.propagate = True


def main():
    os.chdir(expanduser("~"))
    server = ThreadedServer(
        ServerTransferController,
        hostname="localhost",
        port=0,
        protocol_config={"allow_public_attrs": True},
    )
    sys.stderr.write(str(server.port))
    sys.stderr.write("     ")
    server.start()


if __name__ == "__main__":
    plac.call(main)
