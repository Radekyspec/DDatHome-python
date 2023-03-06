from __future__ import annotations

import asyncio
import platform
import random
import string
from urllib.parse import quote

import websockets

from config_parser import ConfigParser
from job_processor import JobProcessor
from logger import Logger


class Connector:
    VERSION: str = "1.1.2"
    DEFAULT_INTERVAL: int = 1000
    DEFAULT_SIZE: int = 10
    DEFAULT_LIMIT: int = 1000
    parser: ConfigParser = ConfigParser()

    def __init__(self):
        self.closed: bool = False
        self.runtime: str = "Python" + platform.python_version()
        self.logger = Logger(logger_name="ws").get_logger()
        self.aws = None
        self.processor = None

    @property
    def platform(self) -> str:
        return platform.system() + "_" + platform.architecture()[0]

    @property
    def name(self) -> str:
        name: str = self.parser.get_parser().get("Settings", "name", fallback="DD")
        if not name:
            name = "DD"
        self.parser.save(option="name", content=name)
        return quote(name.encode("utf-8"))

    @property
    def uuid(self) -> str:
        digits: list[str] = [
            "".join(random.sample(string.hexdigits, 8)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 17))
        ]
        default_uuid = "-".join(digits).upper() + "infoc"
        uuid: str = self.parser.get_parser().get("Settings", "uuid", fallback=default_uuid)
        if not uuid:
            uuid = default_uuid
        self.parser.save(option="uuid", content=uuid)
        return uuid

    @property
    def interval(self) -> int:
        interval = self.parser.get_parser().get("Settings", "interval", fallback=self.DEFAULT_INTERVAL)
        try:
            interval: int = int(interval)
        except ValueError:
            self.parser.save(option="interval", content=str(self.DEFAULT_INTERVAL))
            return self.DEFAULT_INTERVAL
        else:
            if interval > 0:
                self.parser.save(option="interval", content=str(interval))
                return interval
            self.parser.save(option="interval", content=str(self.DEFAULT_INTERVAL))
            return self.DEFAULT_INTERVAL

    @property
    def max_size(self) -> int:
        max_size: str = self.parser.get_parser().get("Settings", "max_size", fallback=self.DEFAULT_SIZE)
        try:
            max_size: int = int(max_size)
        except ValueError:
            self.parser.save(option="max_size", content=str(self.DEFAULT_SIZE))
            return self.DEFAULT_SIZE
        else:
            if max_size > 0:
                self.parser.save(option="max_size", content=str(max_size))
                return max_size
            self.parser.save(option="max_size", content=str(self.DEFAULT_SIZE))
            return self.DEFAULT_SIZE

    @property
    def ws_limit(self) -> int:
        limit = self.parser.get_parser().get("Settings", "ws_limit", fallback=self.DEFAULT_LIMIT)
        try:
            limit = int(limit)
        except ValueError:
            self.parser.save(option="ws_limit", content=str(self.DEFAULT_LIMIT))
            return self.DEFAULT_LIMIT
        else:
            if limit >= 0:
                self.parser.save(option="ws_limit", content=str(limit))
                return limit
            self.parser.save(option="ws_limit", content=str(self.DEFAULT_LIMIT))
            return self.DEFAULT_LIMIT

    async def connect(self) -> None:
        """Establish the websockets connection
        Create the job processor
        Check out the status of original connection
        """
        url = "wss://cluster.vtbs.moe/?runtime={runtime}&version={version}&platform={platform}&uuid={uuid}&name={name}"
        url = url.format(
            runtime=self.runtime,
            version=self.VERSION,
            platform=self.platform,
            uuid=self.uuid,
            name=self.name,
        )
        if self.aws is not None:
            await self.aws.close()
        reconnect = False
        # t = False
        self.processor = JobProcessor(
            interval=self.interval,
            max_size=self.max_size,
            ws_limit=self.ws_limit
        )
        async for self.aws in websockets.connect(url):
            if reconnect:
                self.logger.info("重连成功")
                reconnect = False
            self.logger.info(url)
            self.processor.set_ws(self.aws)
            tasks = [
                asyncio.create_task(self.processor.pull_task()),
                asyncio.create_task(self.processor.receive_task()),
                asyncio.create_task(self.processor.process()),
                asyncio.create_task(self.processor.monitor()),
                asyncio.create_task(self.processor.pull_ws())
            ]
            # if not t:
            #     tasks.append(asyncio.create_task(self.processor.test_crash()))
            # await converse.send(bytes("DDDhttp", encoding="utf-8"))
            try:
                await asyncio.gather(*tasks)
            except websockets.ConnectionClosed:
                # t = True
                [task.cancel() for task in tasks]
                if not self.closed:
                    self.logger.warning("与服务器的ws连接断开, 正在重新连接...")
                    reconnect = True
                    continue
                break

    async def close(self) -> None:
        """Close all connection
        Including websockets and https
        """
        self.closed = True
        self.logger.info("Shutting down, waiting for tasks to complete...")
        self.logger.info("You may press Ctrl+C again to force quit")
        if self.processor is not None:
            await self.processor.close()
        if self.aws is not None:
            await self.aws.close()
