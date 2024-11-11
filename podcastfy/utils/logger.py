"""
Logger Module

This module provides a utility function to set up and configure a logger for the Podcastfy application.
It ensures consistent logging format and configuration across the application.
"""

import logging
import pytz
from podcastfy.utils import load_config
from datetime import datetime

# TimezoneFormatter 类继承自 logging.Formatter，用于自定义日志格式化
class TimezoneFormatter(logging.Formatter):
    def __init__(
            self, fmt="%(asctime)s - %(levelname)s - %(message)s", 
            datefmt="%y.%-m.%-d %H:%M:%S", 
            timezone="Asia/Shanghai"
        ):
        # 调用父类初始化，设置基本格式
        super().__init__(fmt=fmt, datefmt=datefmt)
        # 保存时区信息
        self.timezone = pytz.timezone(timezone)

    def formatTime(self, record, datefmt=None):  # 修改这里，添加 datefmt 参数
        """
        格式化时间戳为指定时区的时间字符串
        
        Args:
            record: LogRecord 对象
            datefmt: 日期格式字符串，如果为 None 则使用默认格式
            
        Returns:
            str: 格式化后的时间字符串
        """
        # 创建 UTC 时间
        utc_dt = datetime.fromtimestamp(record.created, pytz.UTC)
        # 转换到目标时区
        local_dt = utc_dt.astimezone(self.timezone)
        # 使用指定的格式或默认格式
        if datefmt:
            return local_dt.strftime(datefmt)
        return local_dt.strftime(self.datefmt or '%Y-%m-%d %H:%M:%S %z')

def setup_logger(name: str) -> logging.Logger:
    """
    Set up and configure a logger.

    Args:
        name (str): The name of the logger.

    Returns:
        logging.Logger: A configured logger instance.
    """
    config = load_config()
    logging_config = config.get('logging', {})

    logger = logging.getLogger(name)
    logger.setLevel(logging_config.get('level', 'INFO'))
    
    if not logger.handlers:
        # 配置时区，默认使用上海时区
        timezone_str = logging_config.get('timezone', 'Asia/Shanghai')

        # 创建格式化器和处理器
        formatter = TimezoneFormatter(
            fmt=logging_config.get('format', '%(asctime)s - %(levelname)s - %(message)s'),
            datefmt=logging_config.get('datefmt', '%y.%m.%d %H:%M:%S'),  # 修改默认日期格式
            timezone=timezone_str
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger