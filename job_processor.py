from __future__ import annotations

import asyncio
import hashlib
import json
import time
from queue import Queue
from threading import Thread
from typing import Any

from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientError
from async_timeout import timeout
from functools import reduce
from random import random
from urllib.parse import quote, urlencode, urlsplit, parse_qsl
from websockets.exceptions import ConnectionClosed

from logger import Logger
from uuid import uuid1
from ws_live import WSLive


class JobProcessor:
    _img: str
    _sub: str
    _mixin: str
    TASK_TYPES = ("pull_task", "receive", "handle", "ws_send", "ws_recv")

    def __init__(self,
                 interval: int,
                 max_size: int,
                 ws_limit: int,
                 network: int):
        self.INTERVAL: float = interval / 1000.0
        self.MAX_SIZE, self.WS_LIMIT, self.NETWORK = max_size, ws_limit, network
        self.websockets = None
        self._img = self._sub = self._mixin = ""
        self.task_queue: Queue = Queue()
        self.send_queue = Queue()
        self.recv_queue = Queue()
        self.err_queue = Queue()
        self.tasks = []
        self.logger: Any = Logger(
            logger_name="job", level=Logger.INFO)
        self.closed = self.ready = False
        self.bili_ws = WSLive(self.WS_LIMIT)

    class TaskProcessor(Thread):
        _HEADERS = {
        "cookie": f"_uuid=; rpdid=; buvid3={str(uuid1()).upper() + 'infoc'}",
        "origin": "https://space.bilibili.com",
        "referer": "https://space.bilibili.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
        
        def __init__(self, task_type: str, task_queue: Queue, send_queue: Queue, recv_queue: Queue, err_queue: Queue,
                     interval: int, max_size: int, ws_limit: int, network: int, bili_ws: WSLive, logger: Logger, websockets) -> None:
            assert task_type in ("pull_task", "receive", "handle", "pull_ws", "ws_send", "ws_recv", "monitor")
            super().__init__(name=f"TaskProcessor-{task_type}", daemon=True)
            self.task_type = task_type
            self.task_queue = task_queue
            self.send_queue = send_queue
            self.recv_queue = recv_queue
            self.err_queue = err_queue
            self.INTERVAL = interval
            self.MAX_SIZE = max_size
            self.WS_LIMIT = ws_limit
            self.NETWORK = network
            self.bili_ws = bili_ws
            self.websockets = websockets
            self.logger = logger
            self.ready = self.closed = False
        
        def set_ready(self) -> None:
            self.ready = True
        
        def set_closed(self) -> None:
            self.closed = True

        @staticmethod
        async def fetch(client, url):
            async with client.get(url) as resp:
                return await resp.text(encoding="utf-8")
            
        def monitor(self):
            while not self.closed:
                time.sleep(60)
                self.logger.info(f"OPEN: {str(self.bili_ws.rooms)} | LIVE: {len(self.bili_ws.lived)} | "
                                 f"LIMIT: {self.WS_LIMIT}")

        def pull_task(self) -> None:
            """Pull a task from websockets server
            Send string "DDDhttp" to server
            It is able to pull another task before the last task finished
            """
            while not self.ready:
                time.sleep(1)
            while not self.closed:
                if self.send_queue.qsize() < self.MAX_SIZE:
                    self.send_queue.put((time.time_ns(), "DDDhttp"))
                    # self.logger.debug("Send \"DDDhttp\"")
                time.sleep(self.INTERVAL)
        
        def receive_task(self) -> None:
            """Receive a task from websockets server
            Check the type and put it into queue
            """
            while not self.ready:
                time.sleep(1)
            queue_put = self.task_queue.put
            recv = self.recv_queue.get
            while not self.closed:
                _, receive_text = recv()
                text: Any = json.loads(receive_text)
                if "empty" in text:
                    self.logger.debug(f"No job, wait.")
                elif "data" in text:
                    task_type = text["data"].get("type", None)
                    if task_type == "http":
                        queue_put(
                            (time.time_ns(), text["key"], text["data"]["url"]), block=False)
                        self.logger.info(f"Job {text['key']} received.")
                    elif task_type == "query":
                        result = text["data"].get("result", None)
                        if self.bili_ws.started:
                            self.bili_ws.watch(result)
        
        async def handle(self):
            """Handle http task and send back to server
            """
            queue_get = self.task_queue.get
            send = self.send_queue.put
            json_dumps = json.dumps
            async with ClientSession(headers=self._HEADERS,
                                     connector=TCPConnector(family=self.NETWORK)) as client:
                while not self.closed:
                    _, key, url = queue_get()
                    start = time.time()
                    try:
                        async with timeout(10):
                            # resp = await self.fetch(client, url)
                            # url_split = urlsplit(url)
                            # if "wbi" in str(url_split.path):
                            #     query = dict(parse_qsl(url_split.query))
                            #     w_rid, wts = await self.enc_wbi(query)
                            #     query.update({
                            #         "w_rid": w_rid,
                            #         "wts": wts
                            #     })
                            #     query = {new_key: quote(query[new_key]) for new_key in query}
                            #     url = "".join([url.split("?")[0], "?", urlencode(query, encoding="utf-8")])
                            #     self.logger.debug(f"New url: {url}")
                            resp = await self.fetch(client, url)
                            client.headers.update({"cookie": f"_uuid=; rpdid=; buvid3={str(uuid1()).upper() + 'infoc'}"})
                    except (OSError, ClientError, TimeoutError, asyncio.TimeoutError):
                        self.logger.info(f"Job {key} failed.")
                        continue
                    # self._HEADERS["cookie"] = f"_uuid=; rpdid=; buvid3={str(uuid1()).upper() + 'infoc'}"
                    result: dict[str, str] = {
                        "key": key,
                        "data": resp,
                    }
                    result: str = json_dumps(
                        result, ensure_ascii=False, separators=(",", ":"))
                    send((0, result))
                    self.logger.info(f"Job {key} completed in {str(time.time() - start)[:5]}s.")
        
        def pull_ws(self):
            """Pull a live room ws task from server."""
            while not self.closed:
                time.sleep(5)
                if self.bili_ws.rooms == len(self.bili_ws.lived) and self.bili_ws.rooms < self.WS_LIMIT:
                    payload = {
                        "key": str(random()),
                        "query": {"type": "pickRoom"}
                    }
                    result = json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":"))
                    self.send_queue.put((time.time_ns(), result))
        
        def ws_send(self):
            while not self.closed:
                _, msg = self.send_queue.get()
                try:
                    self.websockets.send(msg)
                except Exception as e:
                    self.err_queue.put(str(e))
                    return
                self.logger.debug(f"Send {msg}")
        
        def ws_recv(self):
            while not self.closed:
                try:
                    receive_msg = self.websockets.recv()
                except Exception as e:
                    self.err_queue.put(str(e))
                    return
                self.recv_queue.put((time.time_ns(), receive_msg))
                self.logger.debug(f"Receive {receive_msg}")
        
        def run(self) -> None:
            self.set_ready()
            if (t_tp := self.task_type) == "pull_task":
                self.pull_task()
            elif t_tp == "receive":
                self.receive_task()
            elif t_tp == "pull_ws":
                self.pull_ws()
            elif t_tp == "monitor":
                self.monitor()
            try:
                if t_tp == "handle":
                    asyncio.new_event_loop().run_until_complete(self.handle())
                elif t_tp == "ws_send":
                    self.ws_send()
                else:
                    self.ws_recv()
            except:
                return
    
    def startup(self, websockets):
        self.websockets = websockets
        self.bili_ws.set_queue(self.send_queue)
        self.tasks = [
            self.TaskProcessor(t_type, self.task_queue, self.send_queue, self.recv_queue, self.err_queue,
                               self.INTERVAL, self.MAX_SIZE, self.WS_LIMIT, self.NETWORK,
                               self.bili_ws, self.logger, websockets)
            for t_type in self.TASK_TYPES
        ]
        if not self.bili_ws.started:
            self.bili_ws.start()
        [t.start() for t in self.tasks]
        while not all([t.closed for t in self.tasks]) and self.err_queue.empty():
            time.sleep(1)
        if not self.err_queue.empty():
            raise ConnectionClosed(None, None)

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

    async def update_wbi(self):
        self.ready = True
        # await asyncio.sleep(.1)
        # while not self.closed:
        #     try:
        #         with timeout(10):
        #             async with self.client.get("https://api.bilibili.com/x/web-interface/nav") as resp:
        #                 resp = json.loads(await resp.text(encoding="utf-8"))
        #     except (OSError, ClientError, TimeoutError):
        #         continue
        #     wbi_img: dict = resp["data"]["wbi_img"]
        #     img_url: str = wbi_img.get("img_url")
        #     sub_url: str = wbi_img.get("sub_url")
        #     self._img = img_url.split("/")[-1].split(".")[0]
        #     self._sub = sub_url.split("/")[-1].split(".")[0]
        #     self._mixin = self.get_mixin_key(self._img + self._sub)
        #     self.logger.debug(f"Update mixin key: {self._mixin}")
        #     if not self.ready:
        #         self.ready = True
        #     await asyncio.sleep(300)

    async def enc_wbi(self, params: dict):
        wts = int(time.time())
        params = params.copy()
        params["wts"] = wts
        params = {new_key: params[new_key] for new_key in sorted(params.keys())}
        query = urlencode(query=params, encoding="utf-8")
        w_rid = hashlib.md5((query + self._mixin).encode(encoding='utf-8')).hexdigest()
        return w_rid, wts

    def close(self):
        """Close connection pool
        Stop pulling task from server
        """
        self.closed: bool = True
        # self.bili_ws.ws_close()
        (t.set_closed() for t in self.tasks)
        (t.join() for t in self.tasks)
        self.err_queue.queue.clear()

    @staticmethod
    async def test_crash():
        await asyncio.sleep(5)

        raise ConnectionClosed(None, None)
