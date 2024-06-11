from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import Optional

from dm_manager import DManager
from logger import Logger


class WSLive(Thread):
    started: bool
    logger: Logger
    managers: set[DManager]
    rooms: int
    lived: set[int]
    pool: ThreadPoolExecutor
    current_loop: Optional[DManager]

    def __init__(self, ws_limit: int) -> None:
        super().__init__(name="WSLive", daemon=True)
        self.started = False
        self.logger = Logger(logger_name="bili-ws", level=Logger.INFO)
        self.managers = set()
        self.rooms = 0
        self.lived = set()
        self.pool = ThreadPoolExecutor(max_workers=ws_limit)
        self.send_queue = None
        self.current_loop = None

    def set_queue(self, send_queue) -> None:
        self.send_queue = send_queue
        [room.set_queue(send_queue) for room in self.managers]

    def startup(self) -> None:
        self.started = True
        while self.started:
            self._clean_dead_rooms()
            time.sleep(1)

    def _clean_dead_rooms(self) -> None:
        all_rooms = set()
        [all_rooms.update(manager.get_rooms()) for manager in self.managers]
        if diff := self.lived - all_rooms:
            for dead_room in diff:
                self.logger.debug(f"CLOSE: {dead_room}")
                self.lived.remove(dead_room)
            self.rooms -= len(diff)

    def managers_available(self) -> bool:
        avail = [manager.is_available() for manager in self.managers]
        if avail:
            return any(avail)
        # no manager
        return False

    def pick_avail_manager(self) -> DManager:
        for manager in self.managers:
            if manager.is_available():
                return manager

    def watch(self, room_id: int) -> None:
        if not room_id or room_id in self.lived:
            return
        is_new = False
        if self.managers_available():
            self.current_loop = self.pick_avail_manager()
            self.logger.debug(f"Reuse manager: {self.current_loop.name}")
        else:
            self.current_loop = DManager(index=len(self.managers))
            self.logger.debug(f"New manager: {self.current_loop.name}")
            self.managers.add(self.current_loop)
            is_new = True
        self.rooms += 1
        self.logger.debug(f"WATCH: {room_id}")
        self.add(room_id, is_new)

    def add(self, room_id: int, is_new: bool) -> None:
        if is_new:
            self.pool.submit(self.current_loop.start)
            self.logger.debug("New thread in pool")
        self.current_loop.watch(room_id, self.send_queue)
        self.logger.debug(f"OPEN: {room_id}")
        self.lived.add(room_id)

    def run(self) -> None:
        try:
            self.startup()
        except KeyboardInterrupt:
            print("exit with keyboard")

    def ws_close(self) -> None:
        self.started = False
        self.pool.shutdown(wait=False)
