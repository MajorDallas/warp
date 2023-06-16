#!/usr/bin/env python3

"""
This is the main driver script that will run on the client.
"""

import logging
import sys
import time

import mock
import plac

from client_transfer_controller import ClientTransferController
from config import logger
from connection import Connection
from progress import WarpInterface

gui = WarpInterface()


@plac.annotations(
    tcp_mode=("TCP mode", "flag", "t"),
    recursive=("Transfer directory", "flag", "r"),
    parallelism=("parallelism", "option", "p", int),
    disable_verify=("Disable verify", "flag", "w"),
    verbose=("Enable logging", "flag", "v"),
    timer=("Time transfer", "flag", "T"),
    follow_links=("Follow symbolic links", "flag", "L"),
    copy_status=("Copy file permissions/timestamps", "flag", "s"),
)
def main(
    remote_host,
    recursive,
    file_src,
    file_dest,
    tcp_mode,
    disable_verify,
    timer,
    follow_links,
    copy_status,
    verbose=False,
    parallelism=3,
):
    if verbose:
        logger.setLevel(logging.DEBUG)
        global gui
        gui = mock.Mock()
    startTime = time.time()
    # Extract the username and hostname from the arguments,
    # the ssh_port does not need to be specified, will default to 22.
    username, hostname, ssh_port = Connection.unpack_remote_host(remote_host)

    # Start up the user interface
    gui.redraw()

    # Start an ssh connection used by the xmlrpc connection.
    # the comm_port is used for port forwarding.
    connection = Connection(
        hostname=hostname, username=username, ssh_port=ssh_port
    )
    # get the rpc channel
    channel = connection.connect()

    controller = ClientTransferController(
        channel,
        hostname,
        file_src,
        file_dest,
        recursive,
        tcp_mode,
        disable_verify,
        parallelism,
        follow_links,
        copy_status,
    )

    logger.debug("Starting transfer")
    gui.log_message("Starting transfer")

    start_thread = controller.start()

    gui.files_processed_indicator.set_update(lambda: controller.files_processed)
    gui.files_sent_indicator.set_update(
        lambda: controller.get_files_transfered()
    )
    start_thread.join()
    gui.progress_bar.set_update(
        lambda: (
            controller.transfer_size,  # expected_size / value[0]
            controller.get_server_received_size(),  # progress / value[1]
            controller.is_transfer_validating(),  # value[2]
        )
    )

    success = False
    if controller.start_success:
        gui.log_message("Start success.")
        while not controller.is_transfer_finished():
            gui.redraw()
            time.sleep(0.1)
        if controller.is_transfer_success():
            logger.debug("Done with transfer.")
            success = True
        else:
            logger.warn("Failed to send file.")

    gui.redraw()
    controller.close()
    connection.close()
    channel.close()
    logger.debug("Closed connections.")

    gui.exit()
    if timer:
        logger.info("Total time: " + str(time.time() - startTime))
    if success:
        print("Successfully transfered")
    else:
        print("Failed to transfer")
    sys.exit()


if __name__ == "__main__":
    try:
        plac.call(main)
    except RuntimeError as e:
        print(e, file=sys.stderr)
    except KeyboardInterrupt:
        gui.exit()
        logger.warn("Transfer canceled")
