"""统一异常处理

提供结构化日志记录和异常分类，避免静默吞掉错误。
"""

import logging
import traceback
from enum import Enum
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    DEBUG = "debug"           # 调试信息
    INFO = "info"             # 信息
    WARNING = "warning"       # 警告（可恢复）
    ERROR = "error"           # 错误（功能受限）
    CRITICAL = "critical"     # 严重（系统不可用）


class AppError(Exception):
    """应用基础异常"""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        source: str = "",
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.source = source
        self.cause = cause


class StorageError(AppError):
    """存储层错误（Redis/Neo4j/ChromaDB）"""
    pass


class ModelLoadError(AppError):
    """模型加载错误"""
    pass


class ParseError(AppError):
    """文档解析错误"""
    pass


def handle_errors(
    default_return=None,
    severity: ErrorSeverity = ErrorSeverity.WARNING,
    reraise: bool = False,
):
    """
    错误处理装饰器。

    Args:
        default_return: 异常时的默认返回值
        severity: 错误严重程度
        reraise: 是否重新抛出异常

    使用示例：
        @handle_errors(default_return=[])
        def search(self, query):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AppError as e:
                # 结构化日志
                log_error(e, func.__name__)
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # 未知错误
                app_error = AppError(
                    message=str(e),
                    severity=severity,
                    source=func.__name__,
                    cause=e,
                )
                log_error(app_error, func.__name__)
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def log_error(error: AppError, context: str = ""):
    """记录结构化错误日志"""
    log_data = {
        "context": context,
        "severity": error.severity.value,
        "message": str(error),
        "source": error.source,
    }

    if error.cause:
        log_data["cause"] = str(error.cause)
        log_data["traceback"] = traceback.format_exc()

    log_func = {
        ErrorSeverity.DEBUG: logger.debug,
        ErrorSeverity.INFO: logger.info,
        ErrorSeverity.WARNING: logger.warning,
        ErrorSeverity.ERROR: logger.error,
        ErrorSeverity.CRITICAL: logger.critical,
    }.get(error.severity, logger.error)

    log_func(f"[{log_data['severity']}] {context}: {log_data['message']}")
