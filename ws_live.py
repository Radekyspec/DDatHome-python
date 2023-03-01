import asyncio
import threading

from dm import BiliDM
from logger import Logger


class WSLive(threading.Thread):

    def __init__(self):
        super().__init__(daemon=True)
        self.started = False
        self.logger = Logger(logger_name="bili-ws").get_logger()
        self.rooms = set()
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
            self.rooms.add(room_id)
            self.logger.debug(f"WATCH: {room_id}")
            self.add(room_id)

    def add(self, room_id: int):
        self.logger.debug(f"OPEN: {room_id}")
        asyncio.run_coroutine_threadsafe(BiliDM(room_id, self.ws).startup(), asyncio.get_event_loop())
        self.logger.debug(f"LIVE: {room_id}")
        self.lived.add(room_id)

    def run(self):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            asyncio.get_event_loop().run_until_complete(self.startup())
        except KeyboardInterrupt:
            print("exit with keyboard")
