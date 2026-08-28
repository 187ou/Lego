"""资源池 - 控制并发访问"""

import asyncio
from contextlib import asynccontextmanager


class ResourcePool:
    """资源池 - 控制并发访问

    用法:
        pool = ResourcePool(max_connections=3)
        async with pool.acquire(timeout=10.0) as res:
            # 使用资源
            pass
    """

    def __init__(self, max_connections: int = 5):
        self.semaphore = asyncio.Semaphore(max_connections)
        self._connection_count = 0

    @asynccontextmanager
    async def acquire(self, timeout: float = 10.0):
        """获取资源"""
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            self._connection_count += 1
            yield self
        except asyncio.TimeoutError:
            raise Exception("资源获取超时，请稍后重试")
        finally:
            self._connection_count -= 1
            self.semaphore.release()


# 全局资源池
neo4j_pool = ResourcePool(max_connections=3)
rag_pool = ResourcePool(max_connections=5)
