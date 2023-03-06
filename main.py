from __future__ import annotations

import asyncio
import shutil

from connector import Connector
from logger import Logger


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    logger = Logger(logger_name="start", level="DEBUG").get_logger()
    logger.info("D" * (shutil.get_terminal_size().columns - 34))
    logger.info("Thank you for participating DD@Home,")
    logger.info("Please read README.md for more information;")
    logger.info("Edit config.ini to modify your settings.")
    logger.info("D" * (shutil.get_terminal_size().columns - 34))
    ws_connector = Connector()
    try:
        loop.run_until_complete(ws_connector.connect())
    except KeyboardInterrupt:
        try:
            loop.run_until_complete(ws_connector.close())
        except KeyboardInterrupt:
            pass
        exit(0)
    except Exception as e:
        import platform

        logger.exception(e)
        logger.critical("发生未知错误, 请重启程序")
        if platform.system() == "Windows":
            try:
                input()
            except KeyboardInterrupt:
                pass
