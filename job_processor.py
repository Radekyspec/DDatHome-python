import asyncio
import json
import os
import queue
import time
from typing import Any

import aiohttp
from async_timeout import timeout

from collector import Collector
from logger import Logger


class JobProcessor:
    ERROR_PATH = os.path.join(os.path.realpath(os.path.dirname(__file__)), "404.json")
    HEADERS = {
        "cookie": "buvid3=",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
    }

    def __init__(self, interval, max_size):
        self.queue: queue.PriorityQueue = queue.PriorityQueue()
        self.send_queue: queue.Queue = queue.Queue()
        self.logger: Any = Logger(logger_name="job", level="DEBUG").get_logger()
        self.MAX_SIZE: int = max_size
        self.INTERVAL: float = interval / 1000.0
        self.closed: bool = False
        self.client: Any = None
        self.error_processor: Collector = Collector(self.ERROR_PATH)

    async def pull_task(self, websockets) -> None:
        """Pull a task from websockets server
        Send string "DDDhttp" to server
        It is able to pull another task before the last task finished
        """
        while not self.closed:
            if self.send_queue.qsize() < self.MAX_SIZE and self.queue.qsize() < self.MAX_SIZE:
                await websockets.send("DDDhttp")
                self.logger.debug("Send \"DDDhttp\"")
                self.send_queue.put("DDDhttp", block=False)
            await asyncio.sleep(self.INTERVAL)

    async def receive_task(self, websockets) -> None:
        """Receive a task from websockets server
        Check the type and put it into queue
        """
        while True:
            receive_text: str = await websockets.recv()
            text: Any = json.loads(receive_text)
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
        async with aiohttp.ClientSession(headers=self.HEADERS) as client:
            self.client: aiohttp.ClientSession = client
            while True:
                if not self.queue.empty():
                    text: tuple = self.queue.get(block=False)
                    key: str = text[1]
                    url: str = text[2]
                    try:
                        with timeout(10):
                            # resp = await self.fetch(client, url)
                            resp: asyncio.Task = asyncio.create_task(self.fetch(client, url))
                            resp: str = await resp
                            await self.error_processor.process_404(resp, url)
                    except asyncio.TimeoutError:
                        continue
                    result: dict[str, str] = {
                        "key": key,
                        "data": resp,
                    }
                    result: str = json.dumps(result, ensure_ascii=False)
                    await websockets.send(result)
                    self.logger.debug("Proceeded a task and send back.")
                    self.logger.debug(result)
                await asyncio.sleep(self.INTERVAL)

    async def close(self):
        """Close connection pool
        Stop pulling task from server
        """
        self.closed: bool = True
        while True:
            if self.client is not None and self.queue.empty() and self.send_queue.empty():
                await self.client.close()
                break
            await asyncio.sleep(1)

    async def monitor(self):
        while True:
            await asyncio.sleep(600)
            self.logger.debug("WS | HTTP: " + " | ".join([str(self.send_queue.qsize()), str(self.queue.qsize())]))
