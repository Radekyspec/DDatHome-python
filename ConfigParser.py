import configparser
import os
import time

from Logger import Logger


class ConfigParser:
    logger = Logger(logger_name="config").get_logger()

    def __init__(self):
        self.parser = configparser.ConfigParser(allow_no_value=True)
        if not os.path.exists(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini")):
            self.init_config()
        self.get_parser()

    def get_parser(self):
        self.parser.clear()
        try:
            self.parser.read(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), encoding="utf-8")
        except UnicodeDecodeError:
            self.parser.read(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), encoding="gbk")
        return self.parser

    def init_config(self):
        self.parser.clear()
        try:
            os.remove(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"))
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
            }})
        self.parser.write(open(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), "w"))
        self.logger.info("Generated default config.ini file. Please quit and edit it then restart this program. ")
        time.sleep(999999)
        return

    def has_section(self, section):
        if self.parser.has_section(section):
            return True
        else:
            return False

    def save(self, section="Settings", option="", content=""):
        self.parser.clear()
        try:
            self.parser.read(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), encoding="utf-8")
        except UnicodeDecodeError:
            self.parser.read(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), encoding="gbk")
        if not self.parser.has_section(section):
            self.parser[section] = {}
        self.parser[section][option] = content
        self.parser.write(
            open(os.path.join(os.path.realpath(os.path.dirname(__file__)), "config.ini"), "w"))
        return
