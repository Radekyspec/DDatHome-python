import asyncio
import os
import sys

from Connector import WSConnector
from Logger import Logger


async def main(w_logger):
    connector = WSConnector()
    try:
        await connector.connect()
    except (OSError, ConnectionError, ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError):
        w_logger.error("WS Server disconnected. Reconnecting...")
        await main(w_logger)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    logger = Logger(logger_name="start").get_logger()
    try:
        loop.run_until_complete(main(logger))
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        logger.exception(e)
        os.execlp(sys.executable, sys.executable, os.path.realpath(sys.argv[0]))
