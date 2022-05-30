import asyncio
import shutil

from aiohttp.client_exceptions import ServerDisconnectedError

from Connector import WSConnector
from Logger import Logger


async def main(connector, w_logger):
    try:
        await connector.connect()
    except (OSError, ConnectionError, ConnectionResetError, ConnectionRefusedError, ServerDisconnectedError):
        w_logger.info("WS server disconnected. Reconnecting...")
        await main(connector, w_logger)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    logger = Logger(logger_name="start", level="DEBUG").get_logger()
    logger.info("D" * (shutil.get_terminal_size().columns - 34))
    logger.info("Thank you for participating DD@Home,")
    logger.info("Please read README.md for more information;")
    logger.info("Edit config.ini to modify your settings.")
    logger.info("D" * (shutil.get_terminal_size().columns - 34))
    ws_connector = WSConnector()
    try:
        loop.run_until_complete(main(ws_connector, logger))
    except KeyboardInterrupt:
        try:
            loop.run_until_complete(ws_connector.close())
        except KeyboardInterrupt:
            pass
        exit(0)
    except Exception as e:
        logger.exception(e)
