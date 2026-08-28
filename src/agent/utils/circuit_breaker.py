"""熔断器 - 防止级联故障"""

import time
from enum import Enum
from typing import Callable


class CircuitState(Enum):
    CLOSED = "closed"        # 正常
    OPEN = "open"            # 熔断
    HALF_OPEN = "half_open"  # 半开


class CircuitBreaker:
    """熔断器 - 防止级联故障

    用法:
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        result = breaker.call(some_function, arg1, arg2)
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """执行函数，带熔断保护"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("服务熔断中，请稍后重试")

        try:
            result = func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise e
