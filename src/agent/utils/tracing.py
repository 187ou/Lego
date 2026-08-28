"""链路追踪器 - 跨 Agent 调用链追踪"""

import time
import uuid
import logging
from typing import Optional
from dataclasses import dataclass, field
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """追踪 Span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    agent_name: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "agent_name": self.agent_name,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "metadata": self.metadata,
        }


class Tracer:
    """链路追踪器

    用法:
        tracer = Tracer()
        trace_id = tracer.start_trace()
        with tracer.span("vision_agent", "parse_image") as span:
            # 执行操作
            pass
        trace = tracer.get_trace()
    """

    def __init__(self):
        self._spans: list[TraceSpan] = []
        self._current_trace_id: Optional[str] = None

    def start_trace(self) -> str:
        """开始追踪"""
        self._current_trace_id = str(uuid.uuid4())[:12]
        self._spans.clear()
        return self._current_trace_id

    @contextmanager
    def span(self, agent_name: str, operation: str, parent_span_id: Optional[str] = None):
        """创建 Span"""
        span = TraceSpan(
            trace_id=self._current_trace_id or "no-trace",
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent_span_id,
            agent_name=agent_name,
            operation=operation,
            start_time=time.time(),
        )
        self._spans.append(span)

        try:
            yield span
            span.status = "success"
        except Exception as e:
            span.status = "error"
            span.metadata["error"] = str(e)
            raise
        finally:
            span.end_time = time.time()
            logger.info(
                f"[TRACE] {agent_name}.{operation}: {span.duration_ms:.1f}ms [{span.status}]"
            )

    def get_trace(self) -> list[dict]:
        """获取完整链路"""
        return [span.to_dict() for span in self._spans]


# 全局追踪器
tracer = Tracer()
