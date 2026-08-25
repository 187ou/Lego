"""线程安全的单例装饰器

使用示例：
    @singleton
    class MyClass:
        def __init__(self):
            pass

    obj = MyClass()  # 始终返回同一实例
"""

import threading
from functools import wraps
from typing import Type, Dict, Any


_locks: Dict[Type, threading.Lock] = {}
_instances: Dict[Type, Any] = {}


def singleton(cls: Type) -> Type:
    """
    线程安全的单例装饰器。

    使用双重检查锁定（Double-Checked Locking）确保线程安全。
    """

    @wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in _instances:
            if cls not in _locks:
                _locks[cls] = threading.Lock()
            with _locks[cls]:
                if cls not in _instances:
                    _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]

    return wrapper


def reset_singleton(cls: Type = None):
    """
    重置单例（用于测试）。

    Args:
        cls: 要重置的类，为 None 时重置所有
    """
    if cls:
        _instances.pop(cls, None)
        _locks.pop(cls, None)
    else:
        _instances.clear()
        _locks.clear()
