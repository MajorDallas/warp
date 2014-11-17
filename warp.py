#!/usr/bin/env python

"""
This is the main driver script that will run on the client.
"""

from config import *
from common_tools import *
from connection import Connection
from client_transfer_controller import ClientTransferController
import plac, threading
import sys, time, logging
from clint.textui import progress
from progress import WarpInterface

@plac.annotations(
    tcp_mode=('TCP mode', 'flag', 't'),
    recursive = ('Transfer directory', 'flag', 'r'),
    parallelism = ('parallelism', 'option', 'p', int),
    disable_verify = ('Disable verify', 'flag', 'w'),
    verbose = ('Enable logging', 'flag', 'v'),
    timer = ('Time transfer', 'flag', 'T'),
    follow_links = ('Follow symbolic links', 'flag', 'L'))
def main(remote_host, recursive, file_src, file_dest, tcp_mode, disable_verify, timer, follow_links, verbose=False, custom_comm_port=PORT, parallelism=3):
  # Extract the username and hostname from the arguments,
  # the ssh_port does not need to be specified, will default to 22.
  username, hostname, ssh_port = Connection.unpack_remote_host(remote_host)

  if verbose:
    logger.setLevel(logging.DEBUG)

  startTime = time.time()

  # Start up the user interface
  gui = WarpInterface()
  gui.redraw()

  # Start an ssh connection used by the xmlrpc connection,
  # the comm_port is used for port forwarding.
  connection = Connection(hostname=hostname, username=username, ssh_port=ssh_port, comm_port=custom_comm_port)
  connection.connect()

  # get the rpc channel
  channel = connection.channel

  controller = ClientTransferController(channel, hostname, file_src, file_dest, recursive, tcp_mode, disable_verify, parallelism, follow_links)

  logger.debug("Starting transfer")
  gui.log_message("Starting transfer")


  start_thread = controller.start()

  gui.files_processed_indicator.set_update(lambda : controller.files_processed)
  gui.files_sent_indicator.set_update(lambda : controller.get_files_transfered())
  
  start_thread.join()
  gui.progress_bar.set_update(lambda : (controller.transfer_size, controller.get_server_received_size()
))


  if controller.start_success:
    gui.log_message("Start success.")
      
    while not controller.is_transfer_finished():
      # gui.log_message("Status retrieved.")
      # if(received == controller.transfer_size) and controller.is_transfer_validating():
        # bar.fill_char = 'V'

      gui.redraw()
      time.sleep(0.1)

    if controller.is_transfer_success():
      logger.debug("Done with transfer.")
    else:
      logger.warn("Failed to send file.")

  gui.redraw()
  controller.close()
  connection.close()
  channel.close()
  logger.debug("Closed connections.")

  if timer:
    logger.info("Total time: " + str(time.time() - startTime))

  sys.exit()


if __name__ == '__main__':
  try:
    plac.call(main)
  except KeyboardInterrupt:
    logger.warn("Transfer canceled")
