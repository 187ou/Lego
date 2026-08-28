"""LangGraph 状态定义"""

from typing import TypedDict, Annotated, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Agent 全局状态"""

    # ===== 对话相关 =====
    # 对话消息（自动累加）
    messages: Annotated[list[BaseMessage], add_messages]

    # 当前意图：parse_image | find_alternative | search_manual | verify_build | chat
    intent: str

    # 解析结果（视觉模块输出）
    parsed_result: dict[str, Any]

    # 当前套装编号
    set_id: str

    # 当前步骤号
    step_number: int

    # 是否需要人工确认
    require_human_confirm: bool

    # 最终响应文本
    response: str

    # ===== 心理感知相关 =====
    # 挫折分数（0-100，越高表示用户越沮丧）
    frustration_score: int

    # 同一节点重试次数
    retry_count: int

    # 最后活跃时间戳（用于检测挂起超时）
    last_active_time: float

    # 是否触发了心理安抚
    encouragement_triggered: bool

    # 心理安抚消息队列（旁路输出）
    encouragement_messages: list[str]

    # ===== 图谱推理相关 =====
    # 图谱推理结果（LLM 驱动的深度推理）
    graph_reasoning_result: dict[str, Any]

    # 是否需要图谱深度推理
    needs_graph_reasoning: bool

    # ===== 多 Agent 调度相关 =====
    # Supervisor 决定的下一个 Agent
    next_agent: str

    # 各 Agent 执行结果汇总
    agent_results: dict[str, Any]

    # 各 Agent 专用输出
    vision_result: dict[str, Any]
    alternative_result: dict[str, Any]
    manual_result: dict[str, Any]
    verify_result: dict[str, Any]
    psychology_result: dict[str, Any]
