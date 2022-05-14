import asyncio
import platform
import random
import string
from urllib.parse import quote

from aiowebsocket.converses import AioWebSocket

from ConfigParser import ConfigParser
from JobProcessor import JobProcessor
from Logger import Logger


class WSConnector:
    VERSION = "1.0.1"
    DEFAULT_INTERVAL = 1000
    DEFAULT_SIZE = 10
    parser = ConfigParser()

    def __init__(self):
        self.runtime = "Python" + platform.python_version()
        self.platform = "win64" if platform.architecture()[0] == "64bit" else "win32"
        self.name = self.name()
        self.uuid = self.uuid()
        self.logger = Logger(logger_name="ws").get_logger()
        self.interval = self.interval()
        self.max_size = self.max_size()

    def name(self):
        name = self.parser.get_parser()["Settings"]["name"]
        if name:
            return name
        name = "DD"
        self.parser.save(option="name", content=name)
        return name

    def uuid(self):
        uuid = self.parser.get_parser()["Settings"]["uuid"]
        if uuid:
            return uuid
        digits = [
            "".join(random.sample(string.hexdigits, 8)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 17))
        ]
        uuid = "-".join(digits).upper() + "infoc"
        self.parser.save(option="uuid", content=uuid)
        return uuid

    def interval(self):
        interval = self.parser.get_parser()["Settings"]["interval"]
        try:
            interval = int(interval)
        except ValueError:
            pass
        else:
            if interval > 0:
                return interval
        self.parser.save(option="interval", content=str(self.DEFAULT_INTERVAL))
        return self.DEFAULT_INTERVAL

    def max_size(self):
        max_size = self.parser.get_parser()["Settings"]["max_size"]
        try:
            max_size = int(max_size)
        except ValueError:
            pass
        else:
            if max_size > 0:
                return max_size
        self.parser.save(option="max_size", content=str(self.DEFAULT_SIZE))
        return self.DEFAULT_SIZE

    async def connect(self):
        url = "wss://cluster.vtbs.moe/?runtime={runtime}&version={version}&platform={platform}&uuid={uuid}&name={name}".format(
            runtime=self.runtime,
            version=self.VERSION,
            platform=self.platform,
            uuid=self.uuid,
            name=quote(self.name.encode("utf-8")),
        )
        async with AioWebSocket(url) as aws:
            converse = aws.manipulator
            self.logger.info(url)
            processor = JobProcessor(interval=self.interval, max_size=self.max_size)
            tasks = [processor.pull_task(converse), processor.receive_task(converse), processor.process(converse),
                     processor.monitor()]
            # await converse.send(bytes("DDDhttp", encoding="utf-8"))
            await asyncio.gather(*tasks)
