"""Prometheus 指标收集

提供以下指标：
- HTTP 请求计数和延迟
- Agent 调用统计
- 缓存命中率
- 业务指标（识别次数、替代查询次数等）
"""

import time
import functools
from typing import Callable

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Info,
        generate_latest, CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True

    # ===== HTTP 指标 =====
    http_requests_total = Counter(
        "http_requests_total",
        "HTTP 请求总数",
        ["method", "endpoint", "status"],
    )

    http_request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP 请求延迟",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    # ===== Agent 指标 =====
    agent_calls_total = Counter(
        "agent_calls_total",
        "Agent 调用次数",
        ["agent_name", "status"],
    )

    agent_call_duration = Histogram(
        "agent_call_duration_seconds",
        "Agent 调用延迟",
        ["agent_name"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    )

    # ===== 缓存指标 =====
    cache_hits_total = Counter(
        "cache_hits_total",
        "缓存命中次数",
        ["cache_level"],
    )

    cache_misses_total = Counter(
        "cache_misses_total",
        "缓存未命中次数",
        ["cache_level"],
    )

    # ===== 业务指标 =====
    image_parses_total = Counter(
        "image_parses_total",
        "图片解析次数",
        ["source"],
    )

    alternative_queries_total = Counter(
        "alternative_queries_total",
        "替代查询次数",
    )

    manual_queries_total = Counter(
        "manual_queries_total",
        "说明书查询次数",
    )

    # ===== 系统指标 =====
    active_sessions = Gauge(
        "active_sessions",
        "活跃会话数",
    )

    app_info = Info(
        "lego_mate",
        "应用信息",
    )

except ImportError:
    PROMETHEUS_AVAILABLE = False
    # 创建空占位符
    http_requests_total = None
    http_request_duration = None
    agent_calls_total = None
    agent_call_duration = None
    cache_hits_total = None
    cache_misses_total = None
    image_parses_total = None
    alternative_queries_total = None
    manual_queries_total = None
    active_sessions = None
    app_info = None


def track_http_request(method: str, endpoint: str, status: int, duration: float):
    """记录 HTTP 请求"""
    if not PROMETHEUS_AVAILABLE:
        return
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def track_agent_call(agent_name: str, duration: float, success: bool = True):
    """记录 Agent 调用"""
    if not PROMETHEUS_AVAILABLE:
        return
    status = "success" if success else "error"
    agent_calls_total.labels(agent_name=agent_name, status=status).inc()
    agent_call_duration.labels(agent_name=agent_name).observe(duration)


def track_cache_hit(cache_level: str = "l1"):
    """记录缓存命中"""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_hits_total.labels(cache_level=cache_level).inc()


def track_cache_miss(cache_level: str = "l1"):
    """记录缓存未命中"""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_misses_total.labels(cache_level=cache_level).inc()


def track_image_parse(source: str):
    """记录图片解析"""
    if not PROMETHEUS_AVAILABLE:
        return
    image_parses_total.labels(source=source).inc()


def get_metrics():
    """获取 Prometheus 格式的指标"""
    if not PROMETHEUS_AVAILABLE:
        return b""
    return generate_latest()


def get_content_type():
    """获取指标 Content-Type"""
    if not PROMETHEUS_AVAILABLE:
        return "text/plain"
    return CONTENT_TYPE_LATEST


def timed(metric_name: str = None):
    """计时装饰器"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                name = metric_name or func.__name__
                # 可以在这里记录指标

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                name = metric_name or func.__name__

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
