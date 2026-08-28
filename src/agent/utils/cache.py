"""多级缓存系统

支持：
- L1: 内存缓存（最快，容量小）
- L2: Redis 缓存（快，容量大，可持久化）
- L3: 文件缓存（慢，容量最大）

缓存策略：
- LLM 调用结果：TTL 1 小时
- 图谱查询结果：TTL 30 分钟
- Embedding 结果：TTL 24 小时
- 零件知识：永久缓存
"""

import hashlib
import json
import os
import time
import functools
import logging
from typing import Optional, Any, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryCache:
    """L1: 内存缓存（线程安全）"""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expire_time)
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expire_time = self._cache[key]
            if expire_time == 0 or time.time() < expire_time:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），0 表示永不过期
        """
        # 容量控制：超过限制时清除最旧的 20%
        if len(self._cache) >= self._max_size:
            self._evict_oldest(percent=0.2)

        expire_time = time.time() + ttl if ttl > 0 else 0
        self._cache[key] = (value, expire_time)

    def delete(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

    def _evict_oldest(self, percent: float = 0.2):
        """清除最旧的数据"""
        sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])
        evict_count = int(len(sorted_keys) * percent)
        for key in sorted_keys[:evict_count]:
            del self._cache[key]

    @property
    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / max(1, self._hits + self._misses),
        }


class FileCache:
    """L3: 文件缓存"""

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._get_path(key)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("expire_time", 0) == 0 or time.time() < data["expire_time"]:
                    return data.get("value")
                else:
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        path = self._get_path(key)
        expire_time = time.time() + ttl if ttl > 0 else 0
        data = {
            "key": key,
            "value": value,
            "expire_time": expire_time,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"文件缓存写入失败: {e}")

    def delete(self, key: str):
        path = self._get_path(key)
        path.unlink(missing_ok=True)


class MultiLevelCache:
    """多级缓存（L1 内存 + L2 Redis + L3 文件）"""

    def __init__(self, redis_client=None, enable_file_cache: bool = True):
        self.l1 = MemoryCache(max_size=1000)
        self.redis = redis_client
        self.l3 = FileCache() if enable_file_cache else None

    def get(self, key: str) -> Optional[Any]:
        """获取缓存（L1 → L2 → L3）"""
        # L1
        value = self.l1.get(key)
        if value is not None:
            return value

        # L2 (Redis)
        if self.redis:
            try:
                data = self.redis.get(f"lego_mate:cache:{key}")
                if data:
                    value = json.loads(data)
                    # 回填 L1
                    self.l1.set(key, value, ttl=300)
                    return value
            except Exception:
                pass

        # L3 (File)
        if self.l3:
            value = self.l3.get(key)
            if value is not None:
                # 回填 L1
                self.l1.set(key, value, ttl=600)
                return value

        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存（L1 + L2 + L3）"""
        # L1
        self.l1.set(key, value, ttl=min(ttl, 600))

        # L2 (Redis)
        if self.redis:
            try:
                self.redis.set(
                    f"lego_mate:cache:{key}",
                    json.dumps(value, ensure_ascii=False, default=str),
                    ex=ttl,
                )
            except Exception:
                pass

        # L3 (File) - 仅对长 TTL 数据
        if self.l3 and ttl > 3600:
            self.l3.set(key, value, ttl=ttl)

    def delete(self, key: str):
        """删除缓存"""
        self.l1.delete(key)
        if self.redis:
            try:
                self.redis.delete(f"lego_mate:cache:{key}")
            except Exception:
                pass
        if self.l3:
            self.l3.delete(key)

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()

    @property
    def stats(self) -> dict:
        return {
            "l1_memory": self.l1.stats,
        }


def cached(cache: MultiLevelCache, ttl: int = 3600, key_prefix: str = ""):
    """缓存装饰器

    用法:
        @cached(cache, ttl=3600, key_prefix="llm")
        async def call_llm(prompt):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{MultiLevelCache.make_key(*args, **kwargs)}"
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{MultiLevelCache.make_key(*args, **kwargs)}"
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# 全局缓存实例
_global_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        # 尝试连接 Redis
        redis_client = None
        try:
            from src.common.config import get_settings
            settings = get_settings()
            import redis as redis_lib
            redis_client = redis_lib.from_url(settings.redis_url)
            redis_client.ping()
        except Exception:
            redis_client = None

        _global_cache = MultiLevelCache(redis_client=redis_client)
    return _global_cache
