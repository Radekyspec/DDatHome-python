import json

import aiofiles


class Collector:
    def __init__(self, path: str):
        self.path: str = path

    async def __read(self):
        async with aiofiles.open(self.path, "r") as r:
            content = await r.read()
            await r.close()
        return content

    async def __write(self, content: str) -> None:
        try:
            origin = await self.__read()
            content: list = json.loads(origin).append(content) if origin is not None else [content]
        except FileNotFoundError:
            content: list = [content]
        async with aiofiles.open(self.path, "w") as w:
            await w.write(json.dumps(content))
            await w.close()
        return

    async def process_404(self, message: str, link: str) -> None:
        message = json.loads(message)
        if "code" in message and message["code"] == -404:
            print(link)
            await self.__write(link)
        return
