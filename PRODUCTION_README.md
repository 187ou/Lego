# LEGO-Mate 多 Agent 生产环境解决方案

## 12 个核心生产问题与解决方案

| # | 问题 | 当前状态 | 解决方案 |
|---|------|---------|---------|
| 1 | 推理延迟与超时 | ⚠️ 部分 | 添加 Agent 级超时 + 全链路超时 |
| 2 | 级联故障与容灾 | ✅ 已有 | 各 Agent 独立降级策略 |
| 3 | 无限死循环 | ⚠️ 部分 | 添加循环检测 + 最大迭代次数 |
| 4 | 上下文爆炸与记忆丢失 | ✅ 已有 | L0-L4 记忆系统 |
| 5 | 工具调用资源冲突 | ❌ 未解决 | 添加并发控制 + 连接池 |
| 6 | 成本非线性失控 | ❌ 未解决 | 添加调用次数限制 + 预算控制 |
| 7 | 结构化输出脆弱性 | ⚠️ 部分 | 添加输出校验 + 重试 |
| 8 | 分布式可观测性黑洞 | ❌ 未解决 | 添加链路追踪 + 结构化日志 |
| 9 | 安全攻击面扩大 | ❌ 未解决 | 添加输入过滤 + 权限控制 |
| 10 | 幻觉漂移与事实篡改 | ❌ 未解决 | 添加事实校验 + 置信度 |
| 11 | 非确定性回归测试失效 | ✅ 已有 | 117 个测试覆盖 |
| 12 | 长任务状态恢复困难 | ❌ 未解决 | 添加状态快照 + 断点续传 |

---

## 1. 推理延迟与超时（Latency）

### 问题
Agent 间多次 LLM 调用形成"链式反应"，总响应时间线性叠加。

### 解决方案

```python
# src/agent/config.py
from dataclasses import dataclass

@dataclass
class AgentTimeoutConfig:
    """Agent 超时配置"""
    supervisor_timeout: float = 5.0      # Supervisor 路由超时
    agent_timeout: float = 15.0          # 单个 Agent 执行超时
    aggregator_timeout: float = 10.0     # 汇总超时
    total_timeout: float = 30.0          # 全链路超时
```

```python
# src/agent/utils/timeout.py
import asyncio
import functools
from typing import Callable, Any

class AgentTimeoutError(Exception):
    """Agent 超时异常"""
    pass

def with_timeout(seconds: float, fallback: Callable = None):
    """超时装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                if fallback:
                    return fallback(*args, **kwargs)
                raise AgentTimeoutError(f"{func.__name__} 超时 ({seconds}s)")
        return wrapper
    return decorator
```

---

## 2. 级联故障与容灾（Cascading Failure）

### 当前实现
每个 Agent 已有独立降级策略：
- VisionAgent: CLIP 失败 → 回退到 VL 模型
- AlternativeAgent: Neo4j 失败 → 返回 Mock 数据
- ManualAgent: RAG 失败 → 返回 Mock 数据
- PsychologyAgent: LLM 失败 → 使用内置话术库

### 增强：全局降级开关

```python
# src/agent/utils/circuit_breaker.py
import time
from enum import Enum
from typing import Callable

class CircuitState(Enum):
    CLOSED = "closed"        # 正常
    OPEN = "open"            # 熔断
    HALF_OPEN = "half_open"  # 半开

class CircuitBreaker:
    """熔断器 - 防止级联故障"""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs):
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
```

---

## 3. 无限死循环（Infinite Loops）

### 问题
Agent 间因缺乏终止条件而互相"踢皮球"。

### 解决方案

```python
# src/agent/utils/loop_detector.py
from typing import Optional

class LoopDetector:
    """循环检测器 - 防止 Agent 间无限循环"""
    
    def __init__(self, max_iterations: int = 5, max_tool_calls: int = 10):
        self.max_iterations = max_iterations
        self.max_tool_calls = max_tool_calls
        self.iteration_count = 0
        self.tool_call_count = 0
        self._call_history: list[str] = []
    
    def check_loop(self, agent_name: str, tool_name: Optional[str] = None) -> bool:
        """检测是否进入循环
        
        Returns:
            True = 检测到循环
            False = 正常
        """
        self.iteration_count += 1
        
        if tool_name:
            self.tool_call_count += 1
            call_key = f"{agent_name}:{tool_name}"
            self._call_history.append(call_key)
            
            # 检测重复调用（同一 Agent 同一工具连续调用 3 次）
            if len(self._call_history) >= 3:
                last_3 = self._call_history[-3:]
                if len(set(last_3)) == 1:
                    return True  # 检测到循环
        
        # 超过最大迭代次数
        if self.iteration_count >= self.max_iterations:
            return True
        
        # 超过最大工具调用次数
        if self.tool_call_count >= self.max_tool_calls:
            return True
        
        return False
    
    def reset(self):
        self.iteration_count = 0
        self.tool_call_count = 0
        self._call_history.clear()
```

---

## 4. 上下文爆炸与记忆丢失（Context Overflow）

### 当前实现
- L0-L4 五级记忆系统
- 指代消解
- 多路检索融合

### 增强：上下文窗口管理

```python
# src/agent/utils/context_manager.py
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

class ContextManager:
    """上下文管理器 - 防止上下文爆炸"""
    
    def __init__(self, max_tokens: int = 8000, summary_threshold: int = 6000):
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold
    
    def trim_context(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """裁剪上下文到最大长度
        
        策略：
        1. 保留 SystemMessage
        2. 保留最近 N 条消息
        3. 旧消息用摘要替代
        """
        if not messages:
            return messages
        
        # 估算 token 数（粗略：1 token ≈ 4 字符）
        total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))
        estimated_tokens = total_chars // 4
        
        if estimated_tokens <= self.max_tokens:
            return messages
        
        # 保留 SystemMessage + 最近消息
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
        
        # 保留最近 10 条
        recent_msgs = other_msgs[-10:]
        
        return system_msgs + recent_msgs
    
    def should_summarize(self, messages: List[BaseMessage]) -> bool:
        """判断是否需要摘要"""
        total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))
        return (total_chars // 4) > self.summary_threshold
```

---

## 5. 工具调用资源冲突（Resource Contention）

### 解决方案

```python
# src/agent/utils/resource_pool.py
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

class ResourcePool:
    """资源池 - 控制并发访问"""
    
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
```

---

## 6. 成本非线性失控（Cost）

### 解决方案

```python
# src/agent/utils/cost_controller.py
import time
from typing import Optional
from enum import Enum

class BudgetLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"

class CostController:
    """成本控制器 - 防止预算超支"""
    
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
    
    def check_budget(self, estimated_tokens: int = 500) -> tuple[bool, BudgetLevel]:
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
        return {
            "session_calls": self.session_calls,
            "session_tokens": self.session_tokens,
            "minute_calls": self.minute_calls,
            "budget_level": self.check_budget()[1].value,
        }
```

---

## 7. 结构化输出脆弱性（Parsing Fragility）

### 解决方案

```python
# src/agent/utils/output_parser.py
import json
import re
from typing import Any, Optional, Type
from pydantic import BaseModel, ValidationError

class OutputParser:
    """输出解析器 - 容错解析 LLM 输出"""
    
    @staticmethod
    def parse_json(text: str) -> Optional[dict]:
        """容错 JSON 解析"""
        if not text:
            return None
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 提取 JSON 块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 提取裸 JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    @staticmethod
    def parse_with_validation(text: str, model: Type[BaseModel]) -> Optional[BaseModel]:
        """带校验的解析"""
        data = OutputParser.parse_json(text)
        if data is None:
            return None
        try:
            return model(**data)
        except ValidationError:
            return None
    
    @staticmethod
    def safe_extract(text: str, field: str, default: Any = None) -> Any:
        """安全提取字段"""
        data = OutputParser.parse_json(text)
        if data and isinstance(data, dict):
            return data.get(field, default)
        return default
```

---

## 8. 分布式可观测性黑洞（Observability）

### 解决方案

```python
# src/agent/utils/tracing.py
import time
import uuid
import logging
from typing import Optional, Any
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
    """链路追踪器"""
    
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
            logger.info(f"[TRACE] {agent_name}.{operation}: {span.duration_ms:.1f}ms [{span.status}]")
    
    def get_trace(self) -> list[dict]:
        """获取完整链路"""
        return [span.to_dict() for span in self._spans]
    
    def print_trace(self):
        """打印链路"""
        for span in self._spans:
            status_icon = "✅" if span.status == "success" else "❌"
            print(f"  {status_icon} {span.agent_name}.{span.operation}: {span.duration_ms:.1f}ms")


# 全局追踪器
tracer = Tracer()
```

---

## 9. 安全攻击面扩大（Security）

### 解决方案

```python
# src/agent/utils/security.py
import re
from typing import Tuple

class SecurityFilter:
    """安全过滤器 - 防止提示注入攻击"""
    
    # 危险模式
    DANGEROUS_PATTERNS = [
        r"ignore.*previous.*instructions",
        r"ignore.*above",
        r"disregard.*instructions",
        r"system.*prompt",
        r"you.*are.*now",
        r"new.*persona",
        r"jailbreak",
        r"DAN",
        r"do.*anything.*now",
        r"忽略.*指令",
        r"忘记.*规则",
        r"你现在是",
        r"扮演.*角色",
    ]
    
    # 敏感信息模式
    SENSITIVE_PATTERNS = [
        r"\b\d{16,}\b",  # 长数字（可能是卡号）
        r"\b[A-Za-z0-9+/]{40}\b",  # Base64（可能是密钥）
    ]
    
    @classmethod
    def check_input(cls, text: str) -> Tuple[bool, str]:
        """检查输入安全
        
        Returns:
            (是否安全, 原因)
        """
        if not text:
            return True, ""
        
        text_lower = text.lower()
        
        # 检查危险模式
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower):
                return False, f"检测到潜在的安全风险模式"
        
        return True, ""
    
    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """清理输入"""
        if not text:
            return ""
        
        # 限制长度
        if len(text) > 10000:
            text = text[:10000]
        
        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        return text.strip()
    
    @classmethod
    def check_output(cls, text: str) -> Tuple[bool, str]:
        """检查输出是否包含敏感信息"""
        if not text:
            return True, ""
        
        for pattern in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return False, "输出可能包含敏感信息"
        
        return True, ""
```

---

## 10. 幻觉漂移与事实篡改（Hallucination Propagation）

### 解决方案

```python
# src/agent/utils/fact_checker.py
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class FactClaim:
    """事实声明"""
    claim: str
    source: str  # 来源 Agent
    confidence: float  # 置信度 0-1
    verified: bool = False

class FactChecker:
    """事实校验器 - 防止幻觉传播"""
    
    def __init__(self):
        self._facts: List[FactClaim] = []
    
    def add_fact(self, claim: str, source: str, confidence: float):
        """添加事实声明"""
        self._facts.append(FactClaim(
            claim=claim,
            source=source,
            confidence=confidence,
        ))
    
    def check_consistency(self) -> List[dict]:
        """检查事实一致性"""
        issues = []
        
        # 简单实现：检查是否有矛盾声明
        for i, fact1 in enumerate(self._facts):
            for fact2 in self._facts[i+1:]:
                # 如果两个事实来源不同且置信度都高，标记为需验证
                if (fact1.source != fact2.source and 
                    fact1.confidence > 0.8 and 
                    fact2.confidence > 0.8):
                    # 简单矛盾检测（实际可用嵌入向量相似度）
                    if self._is_contradictory(fact1.claim, fact2.claim):
                        issues.append({
                            "type": "contradiction",
                            "fact1": fact1.claim,
                            "fact2": fact2.claim,
                            "sources": [fact1.source, fact2.source],
                        })
        
        return issues
    
    def get_confidence_score(self) -> float:
        """获取整体置信度"""
        if not self._facts:
            return 0.0
        return sum(f.confidence for f in self._facts) / len(self._facts)
    
    @staticmethod
    def _is_contradictory(claim1: str, claim2: str) -> bool:
        """简单矛盾检测"""
        # 实际可用 LLM 或嵌入向量判断
        # 这里简化为关键词否定检测
        negation_words = ["不", "没", "无", "非", "未"]
        
        for word in negation_words:
            if word in claim1 and word not in claim2:
                # 检查去掉否定词后是否相似
                simplified = claim1.replace(word, "")
                if simplified in claim2 or claim2 in simplified:
                    return True
        
        return False
    
    def reset(self):
        self._facts.clear()
```

---

## 12. 长任务状态恢复困难（State Recovery）

### 解决方案

```python
# src/agent/utils/state_persistence.py
import json
import time
import redis
from typing import Optional, Any
from pathlib import Path

class StatePersistence:
    """状态持久化 - 支持断点续传"""
    
    def __init__(self, redis_client=None, persist_dir: str = "./data/state"):
        self.redis = redis_client
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
    
    def save_state(self, session_id: str, state: dict, step: str):
        """保存状态快照"""
        snapshot = {
            "session_id": session_id,
            "step": step,
            "timestamp": time.time(),
            "state": state,
        }
        
        # 尝试 Redis
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                self.redis.set(key, json.dumps(snapshot, default=str), ex=3600)
                return
            except Exception:
                pass
        
        # 回退到文件
        file_path = self.persist_dir / f"{session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, default=str)
    
    def load_state(self, session_id: str) -> Optional[dict]:
        """加载状态快照"""
        # 尝试 Redis
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                data = self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        
        # 回退到文件
        file_path = self.persist_dir / f"{session_id}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None
    
    def can_resume(self, session_id: str) -> bool:
        """检查是否可以恢复"""
        state = self.load_state(session_id)
        if state:
            # 检查快照是否过期（1小时内）
            return (time.time() - state.get("timestamp", 0)) < 3600
        return False
    
    def clear_state(self, session_id: str):
        """清除状态"""
        if self.redis:
            try:
                key = f"lego_mate:state:{session_id}"
                self.redis.delete(key)
            except Exception:
                pass
        
        file_path = self.persist_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
```

---

## 集成到主图

```python
# src/agent/graph.py（增强版）

def build_production_graph(llm: BaseChatModel):
    """构建生产级多 Agent 图"""
    
    from src.agent.utils.tracing import tracer
    from src.agent.utils.loop_detector import LoopDetector
    from src.agent.utils.cost_controller import CostController
    from src.agent.utils.security import SecurityFilter
    
    loop_detector = LoopDetector(max_iterations=5)
    cost_controller = CostController()
    
    def production_supervisor_node(state: AgentState, llm: BaseChatModel) -> dict:
        """生产级 Supervisor - 包含安全检查和成本控制"""
        trace_id = tracer.start_trace()
        
        with tracer.span("supervisor", "route"):
            # 1. 安全检查
            last_msg = ""
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
                    last_msg = msg.content
                    break
            
            is_safe, reason = SecurityFilter.check_input(last_msg)
            if not is_safe:
                return {
                    "next_agent": "chat",
                    "response": "您的输入包含不安全内容，请重新输入。",
                    "security_blocked": True,
                }
            
            # 2. 预算检查
            allowed, level = cost_controller.check_budget()
            if not allowed:
                return {
                    "next_agent": "chat",
                    "response": "当前会话请求过多，请稍后再试。",
                    "budget_exceeded": True,
                }
            
            # 3. 正常路由
            result = supervisor_node(state, llm)
            
            # 4. 循环检测
            if loop_detector.check_loop(result.get("next_agent", "chat")):
                result["next_agent"] = "chat"
                result["loop_detected"] = True
            
            # 5. 记录调用
            cost_controller.record_call()
            
            return result
    
    # ... 其余图构建逻辑
```

---

## 总结

| 问题 | 解决方案 | 文件 |
|-----|---------|------|
| 延迟与超时 | 分级超时控制 | `config.py`, `timeout.py` |
| 级联故障 | 熔断器模式 | `circuit_breaker.py` |
| 无限循环 | 循环检测器 | `loop_detector.py` |
| 上下文爆炸 | 上下文裁剪 | `context_manager.py` |
| 资源冲突 | 信号量资源池 | `resource_pool.py` |
| 成本失控 | 预算控制器 | `cost_controller.py` |
| 输出脆弱 | 容错解析器 | `output_parser.py` |
| 可观测性 | 链路追踪 | `tracing.py` |
| 安全攻击 | 输入过滤 | `security.py` |
| 幻觉漂移 | 事实校验 | `fact_checker.py` |
| 状态恢复 | 状态持久化 | `state_persistence.py` |
