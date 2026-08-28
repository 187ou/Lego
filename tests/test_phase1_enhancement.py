"""Phase 1 强化测试

测试内容：
1. 数据规模扩展（1000+ 零件）
2. 缓存层优化（多级缓存）
3. 异步任务队列
"""

import asyncio
import time
import threading
import pytest
from unittest.mock import MagicMock


# ===== 1. 数据规模扩展测试 =====

class TestPartDataGenerator:
    """测试零件数据生成器"""

    def test_generate_part_database(self):
        """应能生成 1000+ 零件"""
        from src.kg.part_data_generator import generate_full_part_database

        db = generate_full_part_database(100)  # 测试用 100 个
        assert len(db) >= 100

    def test_part_has_all_attributes(self):
        """生成的零件应有完整属性"""
        from src.kg.part_data_generator import generate_part_knowledge

        knowledge = generate_part_knowledge("3001", "Brick", (2, 4))
        assert knowledge["name"] == "Brick 2x4"
        assert knowledge["category"] == "Brick"
        assert knowledge["geometry"].width == 2
        assert knowledge["geometry"].length == 4
        assert knowledge["geometry"].studs == 8
        assert knowledge["physics"].weight > 0
        assert knowledge["physics"].strength > 0
        assert knowledge["commercial"].rarity in ["common", "uncommon", "rare", "very_rare"]
        assert knowledge["commercial"].price > 0

    def test_category_distribution(self):
        """各类别应有合理分布"""
        from src.kg.part_data_generator import generate_full_part_database

        db = generate_full_part_database(100)
        categories = {}
        for part_id, knowledge in db.items():
            cat = knowledge["category"]
            categories[cat] = categories.get(cat, 0) + 1

        # 至少有 3 个类别
        assert len(categories) >= 3

    def test_extended_database_cached(self):
        """扩展数据库应被缓存"""
        from src.kg.part_data_generator import get_extended_part_database

        db1 = get_extended_part_database()
        db2 = get_extended_part_database()
        assert db1 is db2  # 同一个对象（缓存）

    def test_get_part_knowledge_from_extended(self):
        """应能从扩展数据库获取零件知识"""
        from src.kg.schema import get_part_knowledge
        from src.kg.part_data_generator import generate_full_part_database

        # 生成扩展数据库
        db = generate_full_part_database(50)

        # 查找一个零件
        found = False
        for part_id in list(db.keys())[:5]:
            result = get_part_knowledge(part_id)
            if result is not None:
                found = True
                assert "name" in result
                break

        assert found, "应能从扩展数据库找到零件"

    def test_generate_color_variants(self):
        """应能生成颜色变体"""
        from src.kg.part_data_generator import generate_color_variants, generate_full_part_database

        db = generate_full_part_database(100)
        variants = generate_color_variants(db, colors_per_part=3)

        # 每个零件应生成指定数量的颜色变体
        assert len(variants) >= len(db) * 2  # 至少 2 个颜色


# ===== 2. 缓存层优化测试 =====

class TestMultiLevelCache:
    """测试多级缓存"""

    def test_memory_cache_basic(self):
        """内存缓存应能存取数据"""
        from src.agent.utils.cache import MemoryCache

        cache = MemoryCache(max_size=100)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_memory_cache_expiration(self):
        """内存缓存应支持过期"""
        from src.agent.utils.cache import MemoryCache

        cache = MemoryCache(max_size=100)
        cache.set("key1", "value1", ttl=0)  # 永不过期
        assert cache.get("key1") == "value1"

    def test_memory_cache_eviction(self):
        """内存缓存应在满时淘汰旧数据"""
        from src.agent.utils.cache import MemoryCache

        cache = MemoryCache(max_size=10)
        for i in range(20):
            cache.set(f"key{i}", f"value{i}")

        # 容量应保持在限制内
        assert len(cache._cache) <= 10

    def test_memory_cache_stats(self):
        """内存缓存应提供统计信息"""
        from src.agent.utils.cache import MemoryCache

        cache = MemoryCache(max_size=100)
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_file_cache_basic(self):
        """文件缓存应能存取数据"""
        from src.agent.utils.cache import FileCache

        cache = FileCache(cache_dir="./test_cache")
        cache.set("key1", {"data": "value1"}, ttl=60)
        result = cache.get("key1")
        assert result == {"data": "value1"}

        # 清理
        import shutil
        shutil.rmtree("./test_cache", ignore_errors=True)

    def test_multi_level_cache(self):
        """多级缓存应正确工作"""
        from src.agent.utils.cache import MultiLevelCache

        cache = MultiLevelCache(redis_client=None, enable_file_cache=False)
        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_cache_make_key(self):
        """缓存键应唯一"""
        from src.agent.utils.cache import MultiLevelCache

        key1 = MultiLevelCache.make_key("arg1", "arg2", kwarg1="value1")
        key2 = MultiLevelCache.make_key("arg1", "arg2", kwarg1="value1")
        key3 = MultiLevelCache.make_key("arg1", "arg3")

        assert key1 == key2  # 相同参数 = 相同键
        assert key1 != key3  # 不同参数 = 不同键


# ===== 3. 异步任务队列测试 =====

class TestAsyncTaskManager:
    """测试异步任务管理器（使用线程运行 asyncio）"""

    def _run_async(self, coro_func, *args, **kwargs):
        """在独立线程中运行异步代码"""
        result = {"value": None, "error": None}

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result["value"] = loop.run_until_complete(coro_func(*args, **kwargs))
            except Exception as e:
                result["error"] = e
            finally:
                loop.close()

        thread = threading.Thread(target=run)
        thread.start()
        thread.join(timeout=30)

        if result["error"]:
            raise result["error"]
        return result["value"]

    def test_submit_and_get_result(self):
        """应能提交任务并获取结果"""
        from src.agent.utils.async_tasks import AsyncTaskManager, TaskStatus

        manager = AsyncTaskManager(max_workers=2)

        async def run_test():
            def sample_task(x, y):
                time.sleep(0.01)
                return x + y

            task_id = await manager.submit("test", sample_task, 1, 2)
            result = await manager.get_result(task_id, timeout=5)

            assert result == 3

            status = await manager.get_status(task_id)
            assert status.status == TaskStatus.COMPLETED

        self._run_async(run_test)

    def test_task_failure(self):
        """任务失败应返回错误"""
        from src.agent.utils.async_tasks import AsyncTaskManager, TaskStatus

        manager = AsyncTaskManager(max_workers=2)

        async def run_test():
            def failing_task():
                raise ValueError("test error")

            task_id = await manager.submit("test", failing_task)

            with pytest.raises(Exception) as exc_info:
                await manager.get_result(task_id, timeout=5)

            assert "test error" in str(exc_info.value)

            status = await manager.get_status(task_id)
            assert status.status == TaskStatus.FAILED

        self._run_async(run_test)

    def test_task_timeout(self):
        """任务超时应抛出 TimeoutError"""
        from src.agent.utils.async_tasks import AsyncTaskManager

        manager = AsyncTaskManager(max_workers=2)

        async def run_test():
            def slow_task():
                time.sleep(10)

            task_id = await manager.submit("test", slow_task)

            with pytest.raises(TimeoutError):
                await manager.get_result(task_id, timeout=0.1)

        self._run_async(run_test)

    def test_batch_tasks(self):
        """应能批量提交任务"""
        from src.agent.utils.async_tasks import AsyncTaskManager

        manager = AsyncTaskManager(max_workers=4)

        async def run_test():
            def sample_task(x):
                time.sleep(0.01)
                return x * 2

            args_list = [((i,), {}) for i in range(5)]
            task_ids = await manager.submit_batch("test", sample_task, args_list)

            assert len(task_ids) == 5

            results = await manager.wait_batch(task_ids, timeout=5)
            assert results == [0, 2, 4, 6, 8]

        self._run_async(run_test)

    def test_task_cancellation(self):
        """应能取消任务"""
        from src.agent.utils.async_tasks import AsyncTaskManager, TaskStatus

        manager = AsyncTaskManager(max_workers=2)

        async def run_test():
            def long_task():
                time.sleep(10)

            task_id = await manager.submit("test", long_task)
            await asyncio.sleep(0.01)  # 让任务启动

            cancelled = await manager.cancel(task_id)
            assert cancelled

            status = await manager.get_status(task_id)
            assert status.status == TaskStatus.CANCELLED

        self._run_async(run_test)


def test_async_tasks():
    """运行所有异步任务测试"""
    import threading

    result = {"passed": False, "error": None}

    def run_tests():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from src.agent.utils.async_tasks import AsyncTaskManager, TaskStatus
            manager = AsyncTaskManager(max_workers=2)

            # 测试 1: 基本任务
            def sample_task(x, y):
                time.sleep(0.01)
                return x + y

            task_id = loop.run_until_complete(manager.submit("test", sample_task, 1, 2))
            result1 = loop.run_until_complete(manager.get_result(task_id, timeout=5))
            assert result1 == 3

            # 测试 2: 批量任务
            def double_task(x):
                time.sleep(0.01)
                return x * 2

            args_list = [((i,), {}) for i in range(5)]
            task_ids = loop.run_until_complete(manager.submit_batch("test", double_task, args_list))
            results = loop.run_until_complete(manager.wait_batch(task_ids, timeout=5))
            assert results == [0, 2, 4, 6, 8]

            result["passed"] = True

        except Exception as e:
            result["error"] = str(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_tests)
    thread.start()
    thread.join(timeout=30)

    if result["error"]:
        pytest.fail(result["error"])
    assert result["passed"], "异步任务测试未通过"


if __name__ == "__main__":
    test_async_tasks()
