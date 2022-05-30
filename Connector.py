import asyncio
import platform
import random
import string
from urllib.parse import quote

from aiowebsocket.converses import AioWebSocket, SocketState, Converse, HandShake, DataFrames
from aiowebsocket.parts import parse_uri

from ConfigParser import ConfigParser
from JobProcessor import JobProcessor
from Logger import Logger


class WSConnector:
    VERSION = "1.0.2"
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
        self.aws = None
        self.processor = None

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
        if self.aws is not None:
            await self.aws.close_connection()
        async with WS(url) as aws:
            self.aws = aws
            converse = self.aws.manipulator
            self.logger.info(url)
            processor = JobProcessor(interval=self.interval, max_size=self.max_size)
            self.processor = processor
            tasks = [processor.pull_task(converse), processor.receive_task(converse), processor.process(converse),
                     processor.monitor()]
            # await converse.send(bytes("DDDhttp", encoding="utf-8"))
            await asyncio.gather(*tasks)

    async def close(self):
        self.logger.info("Shutting down, waiting for tasks to complete...")
        self.logger.info("You may press Ctrl+C again to force quit")
        if self.processor is not None:
            await self.processor.close()
        if self.aws is not None:
            await self.aws.close_connection()


class WS(AioWebSocket):
    def __init__(self, uri: str):
        self.logger = Logger(logger_name="ws").get_logger()
        super().__init__(uri)

    async def create_connection(self):
        """Create connection.
        Check the current connection status.
        Send out a handshake and check the result。
        """
        if self.state is not SocketState.zero.value:
            raise ConnectionError('Connection is already exists.')
        remote = scheme, host, port, resource, ssl = parse_uri(self.uri)
        reader, writer = await asyncio.open_connection(host=host, port=port, ssl=ssl)
        self.reader = reader
        self.writer = writer
        self.hands = HandShake(remote, reader, writer,
                               headers=self.headers,
                               union_header=self.union_header)
        await self.hands.shake_()
        status_code = await self.hands.shake_result()
        if status_code != 101:
            raise ConnectionError('Connection failed,status code:{code}'.format(code=status_code))
        self.converse = NewConverse(reader, writer)
        self.state = SocketState.opened.value

    async def close_connection(self):
        """Close connection.
        Check connection status before closing.
        Send Closed Frame to Server.
        """
        if self.state is SocketState.closed.value:
            raise ConnectionError('SocketState is closed, can not close.')
        if self.state is SocketState.closing:
            self.logger.warning('SocketState is closing')
        await self.converse.send(message=b'', closed=True)


class NewConverse(Converse):
    async def send(self, message,
                   fin: bool = True, mask: bool = True, closed: bool = False):
        """Send close message to server """

        if isinstance(message, str):
            message = message.encode()
        code = 0x08 if closed else DataFrames.text.value
        await self.frame.write(fin=fin, code=code, message=message, mask=mask)
