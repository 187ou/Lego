"""结构化日志配置

支持：
- JSON 格式输出（便于日志聚合）
- 请求 ID 追踪
- 不同日志级别输出到不同目标
"""

import sys
import json
import logging
import uuid
from typing import Optional
from contextvars import ContextVar

# 请求 ID 上下文变量
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加请求 ID
        req_id = request_id_var.get()
        if req_id:
            log_data["request_id"] = req_id

        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志"""

    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[41m",  # 红色背景
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
):
    """配置日志

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式
        log_file: 日志文件路径
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            ColoredFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root_logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)


def set_request_id(request_id: Optional[str] = None) -> str:
    """设置请求 ID"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:12]
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """获取当前请求 ID"""
    return request_id_var.get()


def clear_request_id():
    """清除请求 ID"""
    request_id_var.set(None)
