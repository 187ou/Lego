"""公共模块"""

from src.common.singleton import singleton, reset_singleton
from src.common.error_handler import (
    AppError,
    ErrorSeverity,
    StorageError,
    ModelLoadError,
    ParseError,
    handle_errors,
)

__all__ = [
    "singleton",
    "reset_singleton",
    "AppError",
    "ErrorSeverity",
    "StorageError",
    "ModelLoadError",
    "ParseError",
    "handle_errors",
]
