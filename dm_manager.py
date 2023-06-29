from __future__ import annotations

import asyncio
import threading

from dm import BiliDM
from typing import Optional


class DManager(threading.Thread):
    _loop: Optional[asyncio.AbstractEventLoop]
    _size: int
    _LIMIT: int
    _rooms: set[BiliDM]
    manager_started: bool

    def __init__(self, index: int, size_limit: int = 5) -> None:
        super().__init__(name=f"DManager-{str(index)}", daemon=True)
        self._size = 0
        self._LIMIT = size_limit
        self._rooms = set()
        self.manager_started = False

    def set_ws(self, ws_client) -> None:
        [room.set_ws(ws_client) for room in self._rooms]

    def watch(self, room_id: int, ws_client) -> None:
        room = BiliDM(room_id, ws_client)
        self._rooms.add(room)
        self._size += 1
        asyncio.run_coroutine_threadsafe(room.startup(), asyncio.get_event_loop())

    def is_available(self) -> bool:
        return self._size < self._LIMIT

    def get_rooms(self) -> list[int]:
        return [int(room.room_id) for room in self._rooms]

    def _clean_dead_rooms(self) -> None:
        dead_rooms = []
        for room in self._rooms:
            if room.closed:
                self._size -= 1
                dead_rooms.append(room)
        [self._rooms.remove(d_room) for d_room in dead_rooms]

    async def startup(self) -> None:
        self.manager_started = True
        while self.manager_started:
            self._clean_dead_rooms()
            await asyncio.sleep(.5)

    def run(self) -> None:
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            asyncio.get_event_loop().run_until_complete(self.startup())
        except KeyboardInterrupt:
            print("exit with keyboard")
