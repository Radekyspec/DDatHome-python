from __future__ import annotations

import asyncio
import threading

from dm import BiliDM
from logger import Logger


class WSLive(threading.Thread):
    rooms: dict[int, BiliDM]
    lived: set

    def __init__(self):
        super().__init__(name="WSLive", daemon=True)
        self.started = False
        self.logger = Logger(logger_name="bili-ws").get_logger()
        self.rooms = {}
        self.lived = set()
        self.ws = None
        self.loop = None

    def set_ws(self, ws_client):
        self.ws = ws_client
        [self.rooms[room_id].set_ws(ws_client) for room_id in self.rooms]

    async def startup(self):
        self.started = True
        while self.started:
            await asyncio.sleep(.1)

    def watch(self, room_id):
        if room_id and room_id not in self.rooms:
            self.rooms.update({room_id: BiliDM(room_id, self.ws)})
            self.logger.debug(f"WATCH: {room_id}")
            self.add(room_id)

    def add(self, room_id: int):
        self.logger.debug(f"OPEN: {room_id}")
        self.rooms[room_id].start()
        self.lived.add(room_id)

    def run(self) -> None:
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.loop = asyncio.get_event_loop()
            self.loop.run_until_complete(self.startup())
        except KeyboardInterrupt:
            print("exit with keyboard")

    async def close(self):
        self.started = False
