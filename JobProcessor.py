import asyncio
import json
import queue
import time

import aiohttp
from async_timeout import timeout

from Logger import Logger


class JobProcessor:
    def __init__(self, interval, max_size):
        self.queue = queue.PriorityQueue()
        self.send_queue = queue.Queue()
        self.logger = Logger(logger_name="job").get_logger()
        self.MAX_SIZE = max_size
        self.INTERVAL = interval / 1000.0
        self.closed = False
        self.client = None

    async def pull_task(self, websockets):
        """Pull a task from websockets server
        Send string "DDDhttp" to server
        It is able to pull another task before the last task finished
        """
        while not self.closed:
            if self.send_queue.qsize() < self.MAX_SIZE and self.queue.qsize() < self.MAX_SIZE:
                await websockets.send(bytes("DDDhttp", encoding="utf-8"))
                self.logger.debug("Send \"DDDhttp\"")
                self.send_queue.put("DDDhttp", block=False)
            await asyncio.sleep(self.INTERVAL)

    async def receive_task(self, websockets):
        """Receive a task from websockets server
        Check the type and put it into queue
        """
        while True:
            receive_text = str(await websockets.receive(), encoding="utf-8")
            text = json.loads(receive_text)
            self.logger.debug("Receive a task from server.")
            self.logger.debug(receive_text)
            if "data" in text and "type" in text["data"]:
                try:
                    self.send_queue.get(block=False)
                except queue.Empty:
                    pass
                if text["data"]["type"] == "http":
                    self.queue.put((str(time.time_ns())[:14], text["key"], text["data"]["url"]), block=False)

    @staticmethod
    async def fetch(client, url):
        async with client.get(url) as resp:
            return await resp.text(encoding="utf-8")

    async def process(self, websockets):
        """Process http task and send back to server
        """
        async with aiohttp.ClientSession() as client:
            self.client = client
            while True:
                if not self.queue.empty():
                    text = self.queue.get(block=False)
                    key = text[1]
                    url = text[2]
                    try:
                        with timeout(10):
                            # resp = await self.fetch(client, url)
                            resp = asyncio.create_task(self.fetch(client, url))
                            resp = await resp
                    except asyncio.TimeoutError:
                        continue
                    result = {
                        "key": key,
                        "data": resp,
                    }
                    result = json.dumps(result, ensure_ascii=False)
                    await websockets.send(result)
                    self.logger.debug("Proceeded a task and send back.")
                    self.logger.debug(result)
                await asyncio.sleep(self.INTERVAL)

    async def close(self):
        """Close connection pool
        Stop pulling task from server
        """
        self.closed = True
        while True:
            if self.client is not None and self.queue.empty() and self.send_queue.empty():
                await self.client.close()
                break
            await asyncio.sleep(1)

    async def monitor(self):
        while True:
            await asyncio.sleep(600)
            self.logger.debug("WS | HTTP: " + " | ".join([str(self.send_queue.qsize()), str(self.queue.qsize())]))
