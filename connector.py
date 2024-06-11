from __future__ import annotations

import asyncio
import platform
from socket import AF_INET, AF_INET6
from uuid import uuid1

from websockets import ConnectionClosed
from websockets.sync.client import connect
from urllib.parse import quote

from config_parser import ConfigParser
from job_processor import JobProcessor
from logger import Logger


class Connector:
    VERSION: str = "1.3.0"
    DEFAULT_INTERVAL: int = 1000
    DEFAULT_SIZE: int = 10
    DEFAULT_LIMIT: int = 1000

    def __init__(self) -> None:
        self.parser: ConfigParser = ConfigParser()
        self.closed: bool = False
        self.runtime: str = "Python" + platform.python_version()
        self.logger = Logger(logger_name="ws")
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
        self.parser.save(section="Settings", option="name", content=name)
        return quote(name.encode("utf-8"))

    @property
    def uuid(self) -> str:
        default_uuid = str(uuid1()).upper() + "infoc"
        dd_uuid: str = self.parser.get_parser().get("Settings", "uuid", fallback=default_uuid)
        if not dd_uuid:
            dd_uuid = default_uuid
        self.parser.save(section="Settings", option="uuid", content=dd_uuid)
        return dd_uuid

    @property
    def interval(self) -> int:
        interval = self.parser.get_parser().get("Settings", "interval", fallback=self.DEFAULT_INTERVAL)
        try:
            interval: int = int(interval)
        except ValueError:
            self.parser.save(section="Settings", option="interval", content=str(self.DEFAULT_INTERVAL))
            return self.DEFAULT_INTERVAL
        else:
            if interval > 0:
                self.parser.save(section="Settings", option="interval", content=str(interval))
                return interval
            self.parser.save(section="Settings", option="interval", content=str(self.DEFAULT_INTERVAL))
            return self.DEFAULT_INTERVAL

    @property
    def max_size(self) -> int:
        max_size: str = self.parser.get_parser().get("Settings", "max_size", fallback=self.DEFAULT_SIZE)
        try:
            max_size: int = int(max_size)
        except ValueError:
            self.parser.save(section="Settings", option="max_size", content=str(self.DEFAULT_SIZE))
            return self.DEFAULT_SIZE
        else:
            if max_size > 0:
                self.parser.save(section="Settings", option="max_size", content=str(max_size))
                return max_size
            self.parser.save(section="Settings", option="max_size", content=str(self.DEFAULT_SIZE))
            return self.DEFAULT_SIZE

    @property
    def ws_limit(self) -> int:
        limit = self.parser.get_parser().get("Settings", "ws_limit", fallback=self.DEFAULT_LIMIT)
        try:
            limit = int(limit)
        except ValueError:
            self.parser.save(section="Settings", option="ws_limit", content=str(self.DEFAULT_LIMIT))
            return self.DEFAULT_LIMIT
        else:
            if limit >= 0:
                self.parser.save(section="Settings", option="ws_limit", content=str(limit))
                return limit
            self.parser.save(section="Settings", option="ws_limit", content=str(self.DEFAULT_LIMIT))
            return self.DEFAULT_LIMIT

    @property
    def network(self) -> int:
        net = self.parser.get_parser().get("Network", "ip", fallback="both")
        if net not in ("ipv4", "ipv6", "both"):
            self.parser.save(section="Network", option="ip", content="both")
            return 0
        if net == "ipv4":
            return AF_INET
        elif net == "ipv6":
            return AF_INET6
        else:
            self.parser.save(section="Network", option="ip", content="both")
            return 0

    def connect(self) -> None:
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
        reconnect = False
        # t = False
        self.processor = JobProcessor(
            interval=self.interval,
            max_size=self.max_size,
            ws_limit=self.ws_limit,
            network=self.network
        )
        while True:
            with connect(url) as self.aws:
                if reconnect:
                    self.logger.info("重连成功")
                    reconnect = False
                self.logger.info(url)
                try:
                    self.processor.startup(self.aws)
                except ConnectionClosed:
                    # t = True
                    self.processor.close()
                    if not self.closed:
                        self.logger.warning("与服务器的ws连接断开, 正在重新连接...")
                        reconnect = True
                        continue
                    break

    def close(self) -> None:
        """Close all connection
        Including websockets and https
        """
        self.closed = True
        self.logger.info("Shutting down, waiting for tasks to complete...")
        self.logger.info("You may press Ctrl+C again to force quit")
        if self.processor is not None:
            self.processor.close()
        if self.aws is not None:
            self.aws.close()
