import rpyc

from config import *
from server_udt_manager import ServerUDTManager
from transfer_manager import TransferManager


class ServerTransferController(rpyc.Service):
    def on_connect(self):
        logger.info("on connect")
        self.transfer_manager = TransferManager()
        self.server_udt_manager = ServerUDTManager

    def on_disconnect(self):
        logger.info("on disconnect")

    def exposed_get_transfer_manager(self):
        return self.transfer_manager

    def exposed_get_udt_manager(self):
        return self.server_udt_manager
