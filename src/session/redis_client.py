"""Redis 客户端封装"""

import redis
from functools import lru_cache
from src.common.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    """获取 Redis 连接（单例）"""
    settings = get_settings()
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )


def check_redis_connection() -> bool:
    """检查 Redis 连接是否正常"""
    try:
        r = get_redis()
        return r.ping()
    except Exception:
        return False
