"""性能优化工具

提供：
- 连接池管理
- 请求批处理
- 延迟加载
- 性能分析
"""

import time
import functools
import logging
from typing import Callable, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ConnectionPool:
    """通用连接池"""

    def __init__(self, factory: Callable, max_size: int = 10):
        self._factory = factory
        self._max_size = max_size
        self._pool = []
        self._in_use = set()

    def acquire(self):
        """获取连接"""
        if self._pool:
            conn = self._pool.pop()
        else:
            conn = self._factory()
        self._in_use.add(id(conn))
        return conn

    def release(self, conn):
        """释放连接"""
        conn_id = id(conn)
        if conn_id in self._in_use:
            self._in_use.remove(conn_id)
            if len(self._pool) < self._max_size:
                self._pool.append(conn)

    @contextmanager
    def connection(self):
        """连接上下文管理器"""
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)


class BatchProcessor:
    """请求批处理器

    将多个请求合并为一次批量请求，减少网络开销
    """

    def __init__(self, processor: Callable, max_batch_size: int = 10, max_wait_time: float = 0.1):
        self._processor = processor
        self._max_batch_size = max_batch_size
        self._max_wait_time = max_wait_time
        self._pending = []
        self._results = {}
        self._lock = False

    async def add(self, item: Any) -> Any:
        """添加请求到批处理"""
        import asyncio

        item_id = id(item)
        future = asyncio.Future()

        self._pending.append((item_id, item, future))

        # 达到批处理大小，立即执行
        if len(self._pending) >= self._max_batch_size:
            await self._flush()

        # 设置超时
        asyncio.create_task(self._flush_after_timeout())

        return await future

    async def _flush(self):
        """执行批处理"""
        if self._lock or not self._pending:
            return

        self._lock = True
        batch = self._pending[:self._max_batch_size]
        self._pending = self._pending[self._max_batch_size:]

        try:
            items = [item for _, item, _ in batch]
            results = await self._processor(items)

            for (item_id, _, future), result in zip(batch, results):
                if not future.done():
                    future.set_result(result)

        except Exception as e:
            for _, _, future in batch:
                if not future.done():
                    future.set_exception(e)

        finally:
            self._lock = False

    async def _flush_after_timeout(self):
        """超时后自动执行"""
        import asyncio
        await asyncio.sleep(self._max_wait_time)
        await self._flush()


class LazyLoader:
    """延迟加载器

    首次访问时才加载资源
    """

    def __init__(self, factory: Callable):
        self._factory = factory
        self._instance = None
        self._loaded = False

    @property
    def instance(self):
        if not self._loaded:
            self._instance = self._factory()
            self._loaded = True
        return self._instance

    def reset(self):
        self._instance = None
        self._loaded = False


def measure_time(func: Callable = None, threshold_ms: float = 100):
    """性能测量装饰器

    Args:
        func: 被装饰的函数
        threshold_ms: 慢查询阈值（毫秒）
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await fn(*args, **kwargs)
            finally:
                elapsed = (time.time() - start) * 1000
                if elapsed > threshold_ms:
                    logger.warning(
                        f"[SLOW] {fn.__name__} took {elapsed:.1f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = (time.time() - start) * 1000
                if elapsed > threshold_ms:
                    logger.warning(
                        f"[SLOW] {fn.__name__} took {elapsed:.1f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    if func is not None:
        return decorator(func)
    return decorator


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self._timings = {}

    @contextmanager
    def profile(self, name: str):
        """性能分析上下文"""
        start = time.time()
        try:
            yield
        finally:
            elapsed = (time.time() - start) * 1000
            if name not in self._timings:
                self._timings[name] = []
            self._timings[name].append(elapsed)

    def get_stats(self) -> dict:
        """获取性能统计"""
        import statistics
        stats = {}
        for name, timings in self._timings.items():
            stats[name] = {
                "count": len(timings),
                "avg_ms": round(statistics.mean(timings), 2),
                "p50_ms": round(statistics.median(timings), 2),
                "p95_ms": round(sorted(timings)[int(len(timings) * 0.95)], 2) if timings else 0,
                "max_ms": round(max(timings), 2) if timings else 0,
            }
        return stats

    def reset(self):
        self._timings.clear()


# 全局性能分析器
profiler = PerformanceProfiler()
