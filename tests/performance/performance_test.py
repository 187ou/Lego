"""
性能压测自动化脚本

无需 Locust，使用 asyncio + httpx 进行压测
"""

import asyncio
import time
import json
import statistics
from typing import Optional
from dataclasses import dataclass, field

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class PerformanceResult:
    """压测结果"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    response_times: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def avg_response_time(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0

    @property
    def p50_response_time(self) -> float:
        return statistics.median(self.response_times) if self.response_times else 0

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def requests_per_second(self) -> float:
        return self.total_requests / max(0.001, self.total_time)

    @property
    def error_rate(self) -> float:
        return self.failed_requests / max(1, self.total_requests)

    def summary(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "avg_response_time_ms": round(self.avg_response_time, 1),
            "p50_response_time_ms": round(self.p50_response_time, 1),
            "p95_response_time_ms": round(self.p95_response_time, 1),
            "p99_response_time_ms": round(self.p99_response_time, 1),
            "requests_per_second": round(self.requests_per_second, 2),
            "error_rate": round(self.error_rate, 4),
            "total_time_s": round(self.total_time, 2),
        }


class PerformanceTester:
    """性能压测器"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        concurrency: int = 10,
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.concurrency = concurrency
        self.timeout = timeout
        self.result = PerformanceResult()

    async def _send_request(
        self,
        client: httpx.AsyncClient,
        message: str,
        endpoint: str = "/api/chat",
    ) -> tuple[bool, float, Optional[str]]:
        """发送单个请求

        Returns:
            (是否成功, 响应时间, 错误信息)
        """
        start = time.time()
        try:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json={"message": message, "set_id": "10295"},
                timeout=self.timeout,
            )
            elapsed = (time.time() - start) * 1000  # ms

            if response.status_code == 200:
                data = response.json()
                if data.get("response"):
                    return True, elapsed, None
                return False, elapsed, "Empty response"
            return False, elapsed, f"HTTP {response.status_code}"

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return False, elapsed, str(e)

    async def run_chat_test(
        self,
        messages: list[str],
        endpoint: str = "/api/chat",
    ) -> PerformanceResult:
        """运行聊天压测

        Args:
            messages: 消息列表
            endpoint: API 端点

        Returns:
            压测结果
        """
        self.result = PerformanceResult()
        semaphore = asyncio.Semaphore(self.concurrency)

        async def bounded_request(client, message):
            async with semaphore:
                return await self._send_request(client, message, endpoint)

        async with httpx.AsyncClient() as client:
            start = time.time()

            tasks = [bounded_request(client, msg) for msg in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            self.result.total_time = time.time() - start

        for result in results:
            if isinstance(result, Exception):
                self.result.failed_requests += 1
                self.result.errors.append(str(result))
            else:
                success, elapsed, error = result
                self.result.total_requests += 1
                self.result.response_times.append(elapsed)
                if success:
                    self.result.successful_requests += 1
                else:
                    self.result.failed_requests += 1
                    if error:
                        self.result.errors.append(error)

        return self.result

    async def run_health_check(self, count: int = 100) -> PerformanceResult:
        """运行健康检查压测"""
        self.result = PerformanceResult()

        async def check(client):
            start = time.time()
            try:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    timeout=5.0,
                )
                elapsed = (time.time() - start) * 1000
                return response.status_code == 200, elapsed, None
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                return False, elapsed, str(e)

        async with httpx.AsyncClient() as client:
            start = time.time()
            results = await asyncio.gather(
                *[check(client) for _ in range(count)],
                return_exceptions=True,
            )
            self.result.total_time = time.time() - start

        for result in results:
            if isinstance(result, Exception):
                self.result.failed_requests += 1
            else:
                success, elapsed, error = result
                self.result.total_requests += 1
                self.result.response_times.append(elapsed)
                if success:
                    self.result.successful_requests += 1
                else:
                    self.result.failed_requests += 1

        return self.result


# ===== 压测场景 =====

CHAT_MESSAGES = [
    "你好", "hello", "红色2x4砖有替代吗", "第35步怎么拼",
    "帮我设计一个乐高城堡", "谢谢", "3001有什么替代",
    "第100步是什么", "今天天气怎么样", "再见",
]


async def run_performance_test():
    """运行完整压测"""
    if not HTTPX_AVAILABLE:
        print("httpx not installed, skipping performance test")
        return

    tester = PerformanceTester(
        base_url="http://localhost:8000",
        concurrency=5,
        timeout=30.0,
    )

    print("=" * 60)
    print("LEGO-Mate 性能压测")
    print("=" * 60)

    # 测试 1: 健康检查
    print("\n[测试 1] 健康检查 (100 次)")
    result = await tester.run_health_check(100)
    summary = result.summary()
    print(f"  平均响应: {summary['avg_response_time_ms']:.1f}ms")
    print(f"  P95 响应: {summary['p95_response_time_ms']:.1f}ms")
    print(f"  错误率: {summary['error_rate']:.2%}")

    # 测试 2: 聊天消息
    print("\n[测试 2] 聊天消息 (50 次)")
    messages = [CHAT_MESSAGES[i % len(CHAT_MESSAGES)] for i in range(50)]
    result = await tester.run_chat_test(messages)
    summary = result.summary()
    print(f"  总请求: {summary['total_requests']}")
    print(f"  成功: {summary['successful_requests']}")
    print(f"  失败: {summary['failed_requests']}")
    print(f"  平均响应: {summary['avg_response_time_ms']:.1f}ms")
    print(f"  P95 响应: {summary['p95_response_time_ms']:.1f}ms")
    print(f"  P99 响应: {summary['p99_response_time_ms']:.1f}ms")
    print(f"  QPS: {summary['requests_per_second']:.1f}")
    print(f"  错误率: {summary['error_rate']:.2%}")

    # 性能判定
    print("\n" + "=" * 60)
    if summary['p95_response_time_ms'] < 2000 and summary['error_rate'] < 0.01:
        print("性能判定: PASS")
    elif summary['p95_response_time_ms'] < 5000 and summary['error_rate'] < 0.05:
        print("性能判定: WARNING")
    else:
        print("性能判定: FAIL")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_performance_test())
