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
    VERSION: str = "1.0.4"
    DEFAULT_INTERVAL: int = 1000
    DEFAULT_SIZE: int = 10
    parser: ConfigParser = ConfigParser()

    def __init__(self):
        self.closed: bool = False
        self.runtime: str = "Python" + platform.python_version()
        self.platform: str = "win64" if platform.architecture()[0] == "64bit" else "win32"
        self.logger = Logger(logger_name="ws").get_logger()
        self.aws = None
        self.processor = None

    @property
    def name(self) -> str:
        name: str = self.parser.get_parser()["Settings"]["name"]
        if name:
            return name
        name: str = "DD"
        self.parser.save(option="name", content=name)
        return quote(name.encode("utf-8"))

    @property
    def uuid(self) -> str:
        uuid: str = self.parser.get_parser()["Settings"]["uuid"]
        if uuid:
            return uuid
        digits: list[str] = [
            "".join(random.sample(string.hexdigits, 8)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 17))
        ]
        uuid: str = "-".join(digits).upper() + "infoc"
        self.parser.save(option="uuid", content=uuid)
        return uuid

    @property
    def interval(self) -> int:
        interval: str = self.parser.get_parser()["Settings"]["interval"]
        try:
            interval: int = int(interval)
        except ValueError:
            pass
        else:
            if interval > 0:
                return interval
        self.parser.save(option="interval", content=str(self.DEFAULT_INTERVAL))
        return self.DEFAULT_INTERVAL

    @property
    def max_size(self) -> int:
        max_size: str = self.parser.get_parser()["Settings"]["max_size"]
        try:
            max_size: int = int(max_size)
        except ValueError:
            pass
        else:
            if max_size > 0:
                return max_size
        self.parser.save(option="max_size", content=str(self.DEFAULT_SIZE))
        return self.DEFAULT_SIZE

    async def connect(self) -> None:
        """Establish the websockets connection
        Create the job processor
        Check out the status of original connection
        """
        url = "wss://cluster.vtbs.moe/?runtime={runtime}&version={version}&platform={platform}&uuid={uuid}&name={name}".format(
            runtime=self.runtime,
            version=self.VERSION,
            platform=self.platform,
            uuid=self.uuid,
            name=self.name,
        )
        if self.aws is not None:
            await self.aws.close()
        reconnect = False
        async for aws in websockets.connect(url):
            if reconnect:
                self.logger.info("重连成功")
                reconnect = False
            self.aws: websockets.WebSocketClientProtocol = aws
            self.logger.info(url)
            self.processor: JobProcessor = JobProcessor(interval=self.interval, max_size=self.max_size)
            tasks = [
                self.processor.pull_task(aws),
                self.processor.receive_task(aws),
                self.processor.process(aws),
                self.processor.monitor()
            ]
            # await converse.send(bytes("DDDhttp", encoding="utf-8"))
            try:
                await asyncio.gather(*tasks)
            except websockets.ConnectionClosed:
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
