import asyncio
import threading

from dm import BiliDM
from logger import Logger


class WSLive(threading.Thread):
    rooms: dict[int, BiliDM]
    lived: set

    def __init__(self):
        super().__init__(daemon=True)
        self.started = False
        self.logger = Logger(logger_name="bili-ws").get_logger()
        self.rooms = {}
        self.lived = set()
        self.ws = None

    def set_ws(self, ws_client):
        self.ws = ws_client

    async def startup(self):
        self.started = True
        while True:
            await asyncio.sleep(0)

    def watch(self, room_id):
        if room_id and room_id not in self.rooms:
            self.rooms.update({room_id: BiliDM(room_id, self.ws)})
            self.logger.debug(f"WATCH: {room_id}")
            self.add(room_id)

    def add(self, room_id: int):
        self.logger.debug(f"OPEN: {room_id}")
        asyncio.run_coroutine_threadsafe(self.rooms[room_id].startup(), asyncio.get_event_loop())
        self.logger.debug(f"LIVE: {room_id}")
        self.lived.add(room_id)

    async def close(self):
        tasks = [self.rooms[room_id].stop() for room_id in self.rooms]
        await asyncio.gather(*tasks)

    def run(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            asyncio.get_event_loop().run_until_complete(self.startup())
        except KeyboardInterrupt:
            print("exit with keyboard")
