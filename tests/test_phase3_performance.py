"""Phase 3 性能压测和自动化运维测试

测试内容：
1. 性能压测工具
2. 灰度发布配置
3. 性能优化工具
4. 自动化运维
"""

import time
import pytest
from unittest.mock import MagicMock, patch


# ===== 1. 性能压测工具测试 =====

class TestPerformanceTester:
    """测试性能压测器"""

    def test_performance_result_stats(self):
        """性能结果统计应正确"""
        from tests.performance.performance_test import PerformanceResult

        result = PerformanceResult()
        result.total_requests = 100
        result.successful_requests = 95
        result.failed_requests = 5
        result.response_times = [100, 200, 300, 400, 500] * 20

        summary = result.summary()
        assert summary["total_requests"] == 100
        assert summary["successful_requests"] == 95
        assert summary["failed_requests"] == 5
        assert summary["error_rate"] == 0.05

    def test_performance_result_percentiles(self):
        """百分位数计算应正确"""
        from tests.performance.performance_test import PerformanceResult

        result = PerformanceResult()
        result.response_times = list(range(1, 101))  # 1-100

        assert result.p50_response_time == 50.5
        assert result.p95_response_time >= 95
        assert result.p99_response_time >= 99


# ===== 2. 灰度发布配置验证 =====

class TestCanaryConfig:
    """测试灰度发布配置"""

    def test_canary_compose_exists(self):
        """金丝雀发布配置应存在"""
        from pathlib import Path
        assert Path("docker-compose.canary.yml").exists()

    def test_canary_compose_has_backend(self):
        """金丝雀配置应包含后端服务"""
        from pathlib import Path
        content = Path("docker-compose.canary.yml").read_text(encoding="utf-8")
        assert "backend-canary" in content

    def test_canary_compose_has_nginx(self):
        """金丝雀配置应包含 Nginx"""
        from pathlib import Path
        content = Path("docker-compose.canary.yml").read_text(encoding="utf-8")
        assert "nginx" in content

    def test_nginx_config_exists(self):
        """Nginx 配置应存在"""
        from pathlib import Path
        assert Path("nginx/nginx.conf").exists()

    def test_nginx_config_has_upstream(self):
        """Nginx 配置应包含上游服务器"""
        from pathlib import Path
        content = Path("nginx/nginx.conf").read_text(encoding="utf-8")
        assert "upstream" in content

    def test_canary_config_exists(self):
        """金丝雀切流配置应存在"""
        from pathlib import Path
        assert Path("nginx/canary.conf").exists()


# ===== 3. 性能优化工具测试 =====

class TestPerformanceOptimization:
    """测试性能优化工具"""

    def test_connection_pool(self):
        """连接池应正确工作"""
        from src.agent.utils.performance import ConnectionPool

        def factory():
            return {"id": time.time()}

        pool = ConnectionPool(factory, max_size=5)

        # 获取连接
        conn = pool.acquire()
        assert conn is not None

        # 释放连接
        pool.release(conn)

        # 再次获取应复用
        conn2 = pool.acquire()
        assert conn2 is not None

    def test_batch_processor(self):
        """批处理器应正确工作"""
        from src.agent.utils.performance import BatchProcessor

        async def processor(items):
            return [item * 2 for item in items]

        batch = BatchProcessor(processor, max_batch_size=5, max_wait_time=0.1)

        # 不应抛出异常
        assert batch is not None

    def test_lazy_loader(self):
        """延迟加载器应正确工作"""
        from src.agent.utils.performance import LazyLoader

        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"data": "loaded"}

        loader = LazyLoader(factory)

        # 首次访问才加载
        assert call_count == 0
        instance = loader.instance
        assert call_count == 1
        assert instance == {"data": "loaded"}

        # 再次访问不重新加载
        instance2 = loader.instance
        assert call_count == 1
        assert instance2 is instance

    def test_measure_time_decorator(self):
        """计时装饰器应正确工作"""
        from src.agent.utils.performance import measure_time

        @measure_time(threshold_ms=1)
        def slow_func():
            time.sleep(0.01)
            return "done"

        result = slow_func()
        assert result == "done"

    def test_performance_profiler(self):
        """性能分析器应正确工作"""
        from src.agent.utils.performance import PerformanceProfiler

        profiler = PerformanceProfiler()

        # 模拟性能分析
        with profiler.profile("test_op"):
            time.sleep(0.01)

        stats = profiler.get_stats()
        assert "test_op" in stats
        assert stats["test_op"]["count"] == 1
        assert stats["test_op"]["avg_ms"] > 0


# ===== 4. 自动化运维测试 =====

class TestAutoScaling:
    """测试自动化运维"""

    def test_auto_scaler_scale_up(self):
        """扩容应正确工作"""
        from src.agent.utils.auto_scaling import AutoScaler, ScalingConfig, HealthStatus

        config = ScalingConfig(min_instances=1, max_instances=5)
        scaler = AutoScaler(config)

        # 模拟高负载
        status = HealthStatus(
            is_healthy=True,
            cpu_percent=90.0,  # 超过阈值
            memory_percent=50.0,
            request_count=100,
            error_rate=0.01,
            avg_response_time=100.0,
            last_check=time.time(),
        )

        # 强制跳过冷却期
        scaler._last_scale_time = 0

        result = scaler.evaluate(status)
        assert result == "up"
        assert scaler.current_instances == 2

    def test_auto_scaler_scale_down(self):
        """缩容应正确工作"""
        from src.agent.utils.auto_scaling import AutoScaler, ScalingConfig, HealthStatus

        config = ScalingConfig(min_instances=1, max_instances=5)
        scaler = AutoScaler(config)
        scaler.current_instances = 3

        # 模拟低负载
        status = HealthStatus(
            is_healthy=True,
            cpu_percent=10.0,  # 低于阈值
            memory_percent=20.0,
            request_count=10,
            error_rate=0.0,
            avg_response_time=50.0,
            last_check=time.time(),
        )

        # 强制跳过冷却期
        scaler._last_scale_time = 0

        result = scaler.evaluate(status)
        assert result == "down"
        assert scaler.current_instances == 2

    def test_auto_scaler_respects_limits(self):
        """扩缩容应遵守上下限"""
        from src.agent.utils.auto_scaling import AutoScaler, ScalingConfig, HealthStatus

        config = ScalingConfig(min_instances=1, max_instances=3)
        scaler = AutoScaler(config)

        # 达到上限后不再扩容
        scaler.current_instances = 3
        scaler._last_scale_time = 0

        status = HealthStatus(
            is_healthy=True,
            cpu_percent=95.0,
            memory_percent=90.0,
            request_count=200,
            error_rate=0.01,
            avg_response_time=100.0,
            last_check=time.time(),
        )

        result = scaler.evaluate(status)
        assert result is None  # 已达上限
        assert scaler.current_instances == 3

    def test_health_checker(self):
        """健康检查器应正确工作"""
        from src.agent.utils.auto_scaling import HealthChecker

        checker = HealthChecker()

        # 添加检查
        checker.add_check("database", lambda: True)
        checker.add_check("redis", lambda: True)
        checker.add_check("failing", lambda: False)

        results = checker.check()
        assert results["database"] is True
        assert results["redis"] is True
        assert results["failing"] is False

        assert checker.is_healthy() is False

    def test_self_healer(self):
        """自愈系统应正确工作"""
        from src.agent.utils.auto_scaling import SelfHealer

        healer = SelfHealer()

        # 注册自愈动作
        heal_called = [False]
        def heal_action():
            heal_called[0] = True

        healer.register_action("db_connection_lost", heal_action)

        # 执行自愈
        result = healer.try_heal("db_connection_lost")
        assert result is True
        assert heal_called[0] is True

    def test_self_healer_unknown_issue(self):
        """未知问题应返回 False"""
        from src.agent.utils.auto_scaling import SelfHealer

        healer = SelfHealer()
        result = healer.try_heal("unknown_issue")
        assert result is False
