"""Agent 全局配置"""

from dataclasses import dataclass


@dataclass
class AgentTimeoutConfig:
    """Agent 超时配置"""
    supervisor_timeout: float = 5.0      # Supervisor 路由超时
    agent_timeout: float = 15.0          # 单个 Agent 执行超时
    aggregator_timeout: float = 10.0     # 汇总超时
    total_timeout: float = 30.0          # 全链路超时


@dataclass
class AgentBudgetConfig:
    """Agent 预算配置"""
    max_calls_per_session: int = 50      # 每会话最大调用次数
    max_calls_per_minute: int = 10       # 每分钟最大调用次数
    max_tokens_per_session: int = 100000  # 每会话最大 token 数


# 全局配置实例
timeout_config = AgentTimeoutConfig()
budget_config = AgentBudgetConfig()
