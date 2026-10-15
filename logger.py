"""项目统一日志工具。

只需在 ``config.ini`` 的 ``[logging]`` 段写明日志文件路径即可使用::

    [logging]
    path = logs/app.log

随后直接调用::

    from logger import get_logger

    log = get_logger(__name__)
    log.info("服务启动")

日志级别、轮转大小、备份数量等参数均由本模块的常量决定，无需配置。
"""

from __future__ import annotations

import logging
import os
from configparser import ConfigParser
from logging.handlers import RotatingFileHandler

__all__ = ["get_logger", "setup_logging"]

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.ini")

# config.ini 未配置 [logging] path 时使用的默认路径
_DEFAULT_LOG_PATH = os.path.join("logs", "app.log")

# 以下为代码内默认参数，无需在 config.ini 中配置
_LOG_LEVEL = logging.INFO
_MAX_BYTES = 10 * 1024 * 1024  # 单个日志文件上限 10MB
_BACKUP_COUNT = 5  # 保留 5 个轮转备份
_CONSOLE = True  # 是否同时输出到控制台

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)
# 时间格式写在代码中：configparser 会把值里的 "%" 当作插值语法
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_loggers: dict[str, logging.Logger] = {}


def _get_log_path() -> str:
    """读取 ``config.ini`` 中 ``[logging] path``，缺失时回退到默认路径。"""
    parser = ConfigParser()
    parser.read(_CONFIG_PATH, encoding="utf-8")

    path = ""
    if parser.has_section("logging"):
        path = parser["logging"].get("path", "").strip()

    if not path:
        path = _DEFAULT_LOG_PATH
    if not os.path.isabs(path):
        path = os.path.join(_BASE_DIR, path)
    return os.path.normpath(path)


def _build_handlers(log_path: str) -> list[logging.Handler]:
    """构造控制台（可选）与轮转文件两个 handler。"""
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handlers: list[logging.Handler] = []

    if _CONSOLE:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)
    return handlers


def get_logger(name: str = "rag") -> logging.Logger:
    """获取（并缓存）指定名称的 logger，重复调用不会重复添加 handler。"""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(_LOG_LEVEL)
    logger.propagate = False

    if not logger.handlers:
        for handler in _build_handlers(_get_log_path()):
            logger.addHandler(handler)

    _loggers[name] = logger
    return logger


def setup_logging() -> None:
    """可在应用启动时调用以预热日志文件。"""
    get_logger("rag").info("日志系统初始化完成")
