from __future__ import annotations

import configparser
import os
from typing import NoReturn

from logger import Logger


class ConfigParser:
    logger = Logger(logger_name="config")

    def __init__(self) -> None:
        self.parser = configparser.ConfigParser(allow_no_value=True)
        if not os.path.exists("config.ini"):
            self.init_config()
        self.get_parser()

    def get_parser(self) -> configparser.ConfigParser:
        self.parser.clear()
        try:
            self.parser.read("config.ini", encoding="utf-8")
        except UnicodeDecodeError:
            self.parser.read("config.ini", encoding="gbk")
        return self.parser

    def init_config(self) -> NoReturn:
        self.parser.clear()
        try:
            os.remove("config.ini")
        except FileNotFoundError:
            pass
        self.parser.read_dict({
            "Settings": {
                "; UUID | 选填, 留空为随机生成, 用于记录状态": None,
                "uuid": "",
                "; 昵称 | 选填, 会显示在统计中": None,
                "name": "DD",
                "; 请求间隔时间 (毫秒), 包括拉取任务间隔和请求API间隔 | 选填, 默认1000": None,
                "interval": 1000,
                "; 最大队列长度, 超出将不再获取新任务 | 选填, 默认10": None,
                "max_size": 10,
                "; 直播服务器连接数, 同时转发多少直播间 | 选填, 默认1000": None,
                "ws_limit": 1000,
            },
            "Network": {
                "; IP协议, ipv4/ipv6/同时使用(both) | 通常无需设置, 默认both": None,
                "ip": "both",
            }
        })
        self.parser.write(open("config.ini", "w", encoding="utf-8"))
        self.logger.info("Generated default config.ini file. Please edit it then restart this program. ")
        import platform

        if platform.system() == "Windows":
            input()
        exit(0)

    def has_section(self, section) -> bool:
        return self.parser.has_section(section)

    def save(self, section, option, content) -> None:
        self.parser.clear()
        try:
            self.parser.read("config.ini", encoding="utf-8")
        except UnicodeDecodeError:
            self.parser.read("config.ini", encoding="gbk")
        if not self.has_section(section):
            self.parser[section] = {}
        self.parser[section][option] = content
        with open("config.ini", "w", encoding="utf-8") as f:
            self.parser.write(f)

