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

    # ===== 心理感知相关（新增） =====
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
