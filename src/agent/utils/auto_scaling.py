"""自动化运维

提供：
- 自动扩缩容
- 健康检查和自愈
- 资源监控
- 告警通知
"""

import time
import logging
import threading
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ScalingPolicy(str, Enum):
    """扩缩容策略"""
    CPU_BASED = "cpu_based"          # 基于 CPU
    MEMORY_BASED = "memory_based"    # 基于内存
    REQUEST_BASED = "request_based"  # 基于请求量
    CUSTOM = "custom"                # 自定义


@dataclass
class ScalingConfig:
    """扩缩容配置"""
    min_instances: int = 1
    max_instances: int = 10
    scale_up_threshold: float = 80.0   # 扩容阈值（百分比）
    scale_down_threshold: float = 20.0 # 缩容阈值（百分比)
    cooldown_period: int = 300         # 冷却期（秒）
    policy: ScalingPolicy = ScalingPolicy.CPU_BASED


@dataclass
class HealthStatus:
    """健康状态"""
    is_healthy: bool
    cpu_percent: float
    memory_percent: float
    request_count: int
    error_rate: float
    avg_response_time: float
    last_check: float


class AutoScaler:
    """自动扩缩容器"""

    def __init__(self, config: ScalingConfig):
        self.config = config
        self.current_instances = config.min_instances
        self._last_scale_time = 0
        self._metrics_history = []

    def should_scale_up(self, status: HealthStatus) -> bool:
        """判断是否需要扩容"""
        if self.current_instances >= self.config.max_instances:
            return False

        # 冷却期检查
        if time.time() - self._last_scale_time < self.config.cooldown_period:
            return False

        if self.config.policy == ScalingPolicy.CPU_BASED:
            return status.cpu_percent > self.config.scale_up_threshold
        elif self.config.policy == ScalingPolicy.MEMORY_BASED:
            return status.memory_percent > self.config.scale_up_threshold
        elif self.config.policy == ScalingPolicy.REQUEST_BASED:
            return status.request_count > 100  # 示例阈值

        return False

    def should_scale_down(self, status: HealthStatus) -> bool:
        """判断是否需要缩容"""
        if self.current_instances <= self.config.min_instances:
            return False

        # 冷却期检查
        if time.time() - self._last_scale_time < self.config.cooldown_period:
            return False

        if self.config.policy == ScalingPolicy.CPU_BASED:
            return status.cpu_percent < self.config.scale_down_threshold
        elif self.config.policy == ScalingPolicy.MEMORY_BASED:
            return status.memory_percent < self.config.scale_down_threshold

        return False

    def scale_up(self):
        """扩容"""
        if self.current_instances < self.config.max_instances:
            self.current_instances += 1
            self._last_scale_time = time.time()
            logger.info(f"[AUTO-SCALE] 扩容到 {self.current_instances} 实例")

    def scale_down(self):
        """缩容"""
        if self.current_instances > self.config.min_instances:
            self.current_instances -= 1
            self._last_scale_time = time.time()
            logger.info(f"[AUTO-SCALE] 缩容到 {self.current_instances} 实例")

    def evaluate(self, status: HealthStatus) -> Optional[str]:
        """评估并执行扩缩容

        Returns:
            "up" / "down" / None
        """
        if self.should_scale_up(status):
            self.scale_up()
            return "up"
        elif self.should_scale_down(status):
            self.scale_down()
            return "down"
        return None


class HealthChecker:
    """健康检查器"""

    def __init__(self, check_interval: float = 30.0):
        self._check_interval = check_interval
        self._checks: list[Callable] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_check(self, name: str, check_func: Callable[[], bool]):
        """添加健康检查"""
        self._checks.append((name, check_func))

    def check(self) -> dict:
        """执行所有健康检查"""
        results = {}
        for name, check_func in self._checks:
            try:
                results[name] = check_func()
            except Exception as e:
                results[name] = False
                logger.error(f"[HEALTH] {name} 检查失败: {e}")
        return results

    def is_healthy(self) -> bool:
        """是否健康"""
        results = self.check()
        return all(results.values())

    def start_monitoring(self):
        """启动持续监控"""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            results = self.check()
            unhealthy = [name for name, ok in results.items() if not ok]
            if unhealthy:
                logger.warning(f"[HEALTH] 不健康: {', '.join(unhealthy)}")
            time.sleep(self._check_interval)


class SelfHealer:
    """自愈系统"""

    def __init__(self):
        self._healing_actions: dict[str, Callable] = {}
        self._max_retries = 3
        self._retry_count: dict[str, int] = {}

    def register_action(self, issue: str, action: Callable):
        """注册自愈动作"""
        self._healing_actions[issue] = action

    def try_heal(self, issue: str) -> bool:
        """尝试自愈

        Returns:
            是否自愈成功
        """
        if issue not in self._healing_actions:
            logger.warning(f"[HEAL] 未知问题: {issue}")
            return False

        # 重试次数检查
        retries = self._retry_count.get(issue, 0)
        if retries >= self._max_retries:
            logger.error(f"[HEAL] {issue} 超过最大重试次数")
            return False

        try:
            logger.info(f"[HEAL] 尝试自愈: {issue} (第 {retries + 1} 次)")
            self._healing_actions[issue]()
            self._retry_count[issue] = 0
            return True
        except Exception as e:
            self._retry_count[issue] = retries + 1
            logger.error(f"[HEAL] 自愈失败: {e}")
            return False


# ===== 全局实例 =====

_auto_scaler: Optional[AutoScaler] = None
_health_checker = HealthChecker()
_self_healer = SelfHealer()


def get_auto_scaler() -> AutoScaler:
    """获取全局自动扩缩容器"""
    global _auto_scaler
    if _auto_scaler is None:
        _auto_scaler = AutoScaler(ScalingConfig())
    return _auto_scaler


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    return _health_checker


def get_self_healer() -> SelfHealer:
    """获取全局自愈系统"""
    return _self_healer
