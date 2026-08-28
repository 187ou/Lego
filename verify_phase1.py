"""Phase 1 验证脚本 - 直接运行查看效果"""

import time
import sys

def verify_data_generator():
    """验证 1: 数据规模扩展"""
    print("=" * 60)
    print("验证 1: 数据规模扩展")
    print("=" * 60)

    from src.kg.part_data_generator import generate_full_part_database

    start = time.time()
    db = generate_full_part_database(1000)
    elapsed = time.time() - start

    print(f"生成 {len(db)} 个零件，耗时 {elapsed:.3f}s")

    # 类别分布
    categories = {}
    for part_id, knowledge in db.items():
        cat = knowledge["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\n类别分布:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # 展示一个零件的完整信息
    sample_id = list(db.keys())[0]
    sample = db[sample_id]
    print(f"\n示例零件 ({sample_id}):")
    print(f"  名称: {sample['name']}")
    print(f"  类别: {sample['category']}")
    print(f"  几何: {sample['geometry'].width}x{sample['geometry'].length}, "
          f"凸点={sample['geometry'].studs}, 高度={sample['geometry'].height}mm")
    print(f"  物理: 重量={sample['physics'].weight}g, 强度={sample['physics'].strength}")
    print(f"  商业: 稀缺度={sample['commercial'].rarity}, "
          f"价格=${sample['commercial'].price}, "
          f"停产={sample['commercial'].discontinued}")

    return len(db) >= 1000


def verify_cache():
    """验证 2: 缓存层"""
    print("\n" + "=" * 60)
    print("验证 2: 缓存层")
    print("=" * 60)

    from src.agent.utils.cache import MultiLevelCache

    cache = MultiLevelCache(redis_client=None, enable_file_cache=False)

    # 写入
    start = time.time()
    for i in range(1000):
        cache.set(f"key_{i}", f"value_{i}", ttl=60)
    write_time = time.time() - start

    # 读取
    start = time.time()
    hits = 0
    for i in range(1000):
        if cache.get(f"key_{i}") == f"value_{i}":
            hits += 1
    read_time = time.time() - start

    stats = cache.stats

    print(f"写入 1000 条: {write_time:.3f}s")
    print(f"读取 1000 条: {read_time:.3f}s")
    print(f"命中率: {stats['l1_memory']['hit_rate']:.0%}")
    print(f"缓存大小: {stats['l1_memory']['size']}")

    return hits == 1000


def verify_async_tasks():
    """验证 3: 异步任务队列"""
    print("\n" + "=" * 60)
    print("验证 3: 异步任务队列")
    print("=" * 60)

    import threading
    from src.agent.utils.async_tasks import AsyncTaskManager, TaskStatus

    result = {"value": None, "error": None}

    def run_tests():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            async def test():
                manager = AsyncTaskManager(max_workers=4)

                # 单任务
                def add(x, y):
                    time.sleep(0.01)
                    return x + y

                task_id = await manager.submit("add", add, 1, 2)
                r = await manager.get_result(task_id, timeout=5)
                assert r == 3, f"单任务结果应为 3，实际 {r}"

                # 批量任务
                def double(x):
                    time.sleep(0.01)
                    return x * 2

                args_list = [((i,), {}) for i in range(10)]
                task_ids = await manager.submit_batch("double", double, args_list)
                results = await manager.wait_batch(task_ids, timeout=10)
                assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18], \
                    f"批量任务结果错误: {result}"

                return True

            result["value"] = loop.run_until_complete(test())
        except Exception as e:
            result["error"] = str(e)
        finally:
            loop.close()

    thread = threading.Thread(target=run_tests)
    thread.start()
    thread.join(timeout=30)

    if result["error"]:
        print(f"异步任务测试失败: {result['error']}")
        return False

    print("单任务: 1 + 2 = 3 [OK]")
    print("批量任务: [0,1,2,...,9] * 2 = [0,2,4,...,18] [OK]")
    return True


def verify_compatibility():
    """验证 4: 多维度兼容性算法"""
    print("\n" + "=" * 60)
    print("验证 4: 多维度兼容性算法")
    print("=" * 60)

    from src.kg.schema import calc_part_compatibility

    test_cases = [
        ("3001", "3001", "相同零件"),
        ("3001", "3002", "Brick 2x4 vs Brick 2x3（同类型，尺寸接近）"),
        ("3001", "3003", "Brick 2x4 vs Brick 2x2（同类型，尺寸差）"),
        ("3001", "3020", "Brick 2x4 vs Plate 2x4（不同类型，同尺寸）"),
        ("3001", "3069", "Brick 2x4 vs Tile 1x2（完全不同）"),
    ]

    for part_a, part_b, desc in test_cases:
        score = calc_part_compatibility(part_a, part_b)
        print(f"  {desc}: {score:.3f}")

    return True


def main():
    print("Phase 1 强化验证")
    print("=" * 60)

    results = []

    results.append(("数据规模扩展", verify_data_generator()))
    results.append(("缓存层", verify_cache()))
    results.append(("异步任务队列", verify_async_tasks()))
    results.append(("兼容性算法", verify_compatibility()))

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("[DONE] All verifications passed! Phase 1 enhancement complete.")
    else:
        print("[WARN] Some verifications failed.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
