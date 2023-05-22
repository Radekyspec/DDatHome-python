from __future__ import annotations

import asyncio
import hashlib
import json
import queue
import time
from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError
from async_timeout import timeout
from functools import reduce
from random import random
from urllib.parse import urlencode, urlsplit, parse_qsl

from logger import Logger
from ws_live import WSLive


class JobProcessor:
    _HEADERS = {
        "cookie": "buvid3=bili",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/102.0.0.0 Safari/537.36",
    }

    def __init__(self,
                 interval: int,
                 max_size: int,
                 ws_limit: int):
        self.INTERVAL: float = interval / 1000.0
        self.MAX_SIZE: int = max_size
        self.WS_LIMIT = ws_limit
        self.websockets = None
        self.queue: queue.PriorityQueue = queue.PriorityQueue()
        self.logger: Any = Logger(
            logger_name="job", level="DEBUG").get_logger()
        self.closed: bool = False
        self.client: Any = None
        self.bili_ws = WSLive(self.WS_LIMIT)

    def set_ws(self, websockets):
        self.websockets = websockets
        self.bili_ws.set_ws(websockets)
        if not self.bili_ws.started:
            self.bili_ws.start()

    async def pull_task(self) -> None:
        """Pull a task from websockets server
        Send string "DDDhttp" to server
        It is able to pull another task before the last task finished
        """
        while not self.closed:
            if self.queue.qsize() < self.MAX_SIZE:
                await self.websockets.send("DDDhttp")
                self.logger.debug("Send \"DDDhttp\"")
            await asyncio.sleep(self.INTERVAL)

    async def receive_task(self) -> None:
        """Receive a task from websockets server
        Check the type and put it into queue
        """
        while True:
            receive_text: str = await self.websockets.recv()
            text: Any = json.loads(receive_text)
            self.logger.debug("Receive a task from server.")
            self.logger.debug(receive_text)
            if "data" in text:
                task_type = text["data"].get("type", None)
                if task_type == "http":
                    self.queue.put(
                        (str(time.time_ns())[:14], text["key"], text["data"]["url"]), block=False)
                elif task_type == "query":
                    result = text["data"].get("result", None)
                    if self.bili_ws.started:
                        self.bili_ws.watch(result)

    @staticmethod
    async def fetch(client, url):
        async with client.get(url) as resp:
            return await resp.text(encoding="utf-8")

    @staticmethod
    def get_mixin_key(ae):
        oe = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39,
              12,
              38, 41,
              13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
              36,
              20, 34, 44, 52]
        le = reduce(lambda s, i: s + ae[i], oe, "")
        return le[:32]

    async def enc_wbi(self, params: dict):
        async with self.client.get("https://api.bilibili.com/x/web-interface/nav") as resp:
            resp = json.loads(await resp.text(encoding="utf-8"))
        wbi_img: dict = resp["data"]["wbi_img"]
        img_url: str = wbi_img.get("img_url")
        sub_url: str = wbi_img.get("sub_url")
        img_value = img_url.split("/")[-1].split(".")[0]
        sub_value = sub_url.split("/")[-1].split(".")[0]
        me = self.get_mixin_key(img_value + sub_value)
        wts = int(time.time())
        params["wts"] = wts
        params = {new_key: params[new_key] for new_key in sorted(params.keys())}
        query = urlencode(query=params, encoding="utf-8")
        w_rid = hashlib.md5((query + me).encode(encoding='utf-8')).hexdigest()
        return w_rid, wts

    async def process(self):
        """Process http task and send back to server
        """
        async with ClientSession(headers=self._HEADERS) as self.client:
            while True:
                if self.queue.empty():
                    await asyncio.sleep(self.INTERVAL)
                    continue
                text: tuple = self.queue.get(block=False)
                key, url = text[1:]
                try:
                    with timeout(10):
                        # resp = await self.fetch(client, url)
                        url_split = urlsplit(url)
                        if "wbi" in str(url_split.path):
                            query = dict(parse_qsl(urlsplit(url).query))
                            query = {new_key: query[new_key] for new_key in sorted(query.keys())}
                            w_rid, wts = await self.enc_wbi(query.copy())
                            query.update({
                                "w_rid": w_rid,
                                "wts": wts
                            })
                            url = "".join([url.split("?")[0], "?", urlencode(query, encoding="utf-8")])
                            self.logger.debug(f"New url: {url}")
                        resp: asyncio.Task = asyncio.create_task(
                            self.fetch(self.client, url))
                        resp: str = await resp
                except asyncio.TimeoutError:
                    continue
                except (OSError, ClientError):
                    continue
                result: dict[str, str] = {
                    "key": key,
                    "data": resp,
                }
                result: str = json.dumps(
                    result, ensure_ascii=False, separators=(",", ":"))
                await self.websockets.send(result)
                self.logger.debug("Proceeded a task and send back.")
                self.logger.debug(result)
                await asyncio.sleep(self.INTERVAL)

    async def pull_ws(self):
        """Pull a live room ws task from server."""
        while not self.closed:
            await asyncio.sleep(5)
            if self.bili_ws.rooms == len(self.bili_ws.lived) and self.bili_ws.rooms < self.WS_LIMIT:
                key = str(random())
                payload = {
                    "key": key,
                    "query": {"type": "pickRoom"}
                }
                result = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":"))
                await self.websockets.send(result)

    async def close(self):
        """Close connection pool
        Stop pulling task from server
        """
        self.closed: bool = True
        self.bili_ws.close()
        while True:
            if self.client is not None and self.queue.empty():
                await self.client.close()
                break
            await asyncio.sleep(1)

    async def monitor(self):
        while True:
            await asyncio.sleep(60)
            self.logger.info(
                "HTTP: " + str(self.queue.qsize()))
            self.logger.info(f"OPEN: {str(self.bili_ws.rooms)} | LIVE: {len(self.bili_ws.lived)} | "
                             f"LIMIT: {self.WS_LIMIT}")

    @staticmethod
    async def test_crash():
        await asyncio.sleep(10)
        import websockets

        raise websockets.ConnectionClosed(None, None)
