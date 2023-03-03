from __future__ import annotations

import time
import threading

from concurrent.futures import ThreadPoolExecutor
from dm_manager import DManager
from logger import Logger


class WSLive(threading.Thread):
    rooms: int
    lived: set

    def __init__(self, ws_limit: int):
        super().__init__(name="WSLive", daemon=True)
        self.started = False
        self.logger = Logger(logger_name="bili-ws").get_logger()
        self.managers = set()
        self.rooms = 0
        self.lived = set()
        self.pool = ThreadPoolExecutor(max_workers=ws_limit)
        self.ws = None
        self.current_loop = None

    def set_ws(self, ws_client):
        self.ws = ws_client
        [room.set_ws(ws_client) for room in self.managers]

    def startup(self):
        self.started = True
        while self.started:
            time.sleep(.1)

    def watch(self, room_id):
        if not room_id or room_id in self.lived:
            return
        is_new = False
        if self.current_loop is None or not self.current_loop.is_available():
            self.logger.debug("New manager created")
            self.current_loop = DManager(len(self.managers))
            self.managers.add(self.current_loop)
            is_new = True
        self.rooms += 1
        self.logger.debug(f"WATCH: {room_id}")
        self.add(room_id, is_new)

    def add(self, room_id: int, is_new: bool):
        if is_new:
            self.pool.submit(self.current_loop.start)
            self.logger.debug("New thread in pool")
        self.current_loop.watch(room_id, self.ws)
        self.logger.debug(f"OPEN: {room_id}")
        self.lived.add(room_id)

    def run(self) -> None:
        try:
            self.startup()
        except KeyboardInterrupt:
            print("exit with keyboard")

    def close(self):
        self.started = False
        self.pool.shutdown(wait=False)
