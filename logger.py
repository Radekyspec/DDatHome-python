from __future__ import annotations

import os
from logging import getLogger, StreamHandler, FileHandler, Formatter, DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL
from logging import Logger as DefaultLogger
from time import strftime, localtime
from typing import Optional


class Logger:
    INFO = INFO
    DEBUG = DEBUG
    WARNING = WARNING
    ERROR = ERROR
    WARN = WARN
    CRITICAL = CRITICAL

    def __init__(self, level: Optional[int] = INFO, logger_name: Optional[str] = "logger"):
        self.logger = None
        self.level = level
        self.name = logger_name
        self.set_logger()

    def set_logger(self) -> None:
        try:
            os.makedirs(os.path.join(os.path.realpath(os.path.dirname(__file__)), "logs"))
        except (FileExistsError, OSError):
            pass

        self.logger = getLogger(self.name)
        self.logger.setLevel(self.level)
        stream_handler = StreamHandler()
        stream_handler.setLevel(self.level)
        file_handler = FileHandler(
            filename=os.path.join(os.path.realpath(os.path.dirname(__file__)), "logs",
                                  "{log_time}.log".format(log_time=strftime("%Y-%m-%d", localtime()))),
            mode="a",
            encoding="utf-8",
        )
        file_handler.setLevel(DEBUG)
        formatter = Formatter(fmt="%(asctime)s - [%(levelname)s] %(message)s")
        stream_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        self.logger.handlers.clear()
        self.logger.addHandler(stream_handler)
        self.logger.addHandler(file_handler)
        return

    def get_logger(self) -> DefaultLogger:
        return self.logger
