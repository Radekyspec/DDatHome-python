from Connector import WSConnector
from Logger import Logger
import asyncio
import os
import sys


async def main():
    processor = WSConnector()
    await processor.connect()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    logger = Logger(logger_name="start").get_logger()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        logger.error(e)
        os.execlp(sys.executable, sys.executable, os.path.realpath(sys.argv[0]))
