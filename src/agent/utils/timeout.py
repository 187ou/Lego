"""超时控制工具"""

import asyncio
import functools
from typing import Callable, Any


class AgentTimeoutError(Exception):
    """Agent 超时异常"""
    pass


def with_timeout(seconds: float, fallback: Callable = None):
    """超时装饰器

    用法:
        @with_timeout(5.0, fallback=lambda: "timeout")
        async def my_func():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                if fallback:
                    return fallback(*args, **kwargs)
                raise AgentTimeoutError(f"{func.__name__} 超时 ({seconds}s)")
        return wrapper
    return decorator
