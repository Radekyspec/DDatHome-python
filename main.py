import asyncio
import os
import sys
import shutil

from aiohttp.client_exceptions import ServerDisconnectedError
from Connector import WSConnector
from Logger import Logger


async def main(w_logger):
    connector = WSConnector()
    try:
        await connector.connect()
    except (OSError, ConnectionError, ConnectionResetError, ConnectionRefusedError, ServerDisconnectedError):
        w_logger.error("WS Server disconnected. Reconnecting...")
        await main(w_logger)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    logger = Logger(logger_name="start").get_logger()
    logger.info("D" * shutil.get_terminal_size().columns)
    logger.info("Thank you for participating DD@Home,")
    logger.info("Please read README.md for more information;")
    logger.info("Edit config.ini to modify your settings.")
    logger.info("D" * shutil.get_terminal_size().columns)
    try:
        loop.run_until_complete(main(logger))
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        logger.exception(e)
        os.execlp(sys.executable, sys.executable, os.path.realpath(sys.argv[0]))
