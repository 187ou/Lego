"""成本控制器 - 防止预算超支"""

import time
from enum import Enum


class BudgetLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class CostController:
    """成本控制器 - 防止预算超支

    用法:
        controller = CostController(max_calls_per_session=50)
        allowed, level = controller.check_budget()
        if allowed:
            controller.record_call(tokens_used=500)
    """

    def __init__(self,
                 max_calls_per_session: int = 50,
                 max_calls_per_minute: int = 10,
                 max_tokens_per_session: int = 100000):
        self.max_calls_per_session = max_calls_per_session
        self.max_calls_per_minute = max_calls_per_minute
        self.max_tokens_per_session = max_tokens_per_session

        self.session_calls = 0
        self.session_tokens = 0
        self.minute_calls = 0
        self.minute_start = time.time()

    def check_budget(self, estimated_tokens: int = 500) -> tuple:
        """检查预算

        Returns:
            (是否允许, 预算级别)
        """
        # 会话级别检查
        if self.session_calls >= self.max_calls_per_session:
            return False, BudgetLevel.CRITICAL

        # 分钟级别检查
        current_time = time.time()
        if current_time - self.minute_start > 60:
            self.minute_calls = 0
            self.minute_start = current_time

        if self.minute_calls >= self.max_calls_per_minute:
            return False, BudgetLevel.WARNING

        # Token 检查
        if self.session_tokens + estimated_tokens > self.max_tokens_per_session:
            return False, BudgetLevel.CRITICAL

        # 计算预算级别
        usage_ratio = self.session_calls / self.max_calls_per_session
        if usage_ratio > 0.8:
            level = BudgetLevel.CRITICAL
        elif usage_ratio > 0.5:
            level = BudgetLevel.WARNING
        else:
            level = BudgetLevel.NORMAL

        return True, level

    def record_call(self, tokens_used: int = 500):
        """记录调用"""
        self.session_calls += 1
        self.minute_calls += 1
        self.session_tokens += tokens_used

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "session_calls": self.session_calls,
            "session_tokens": self.session_tokens,
            "minute_calls": self.minute_calls,
            "budget_level": self.check_budget()[1].value,
        }
