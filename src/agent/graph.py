"""LangGraph 多 Agent 对话中枢

架构：Supervisor 模式
- Supervisor Agent：分析意图，调度专家 Agent
- 专家 Agent：vision / alternative / manual / verify / psychology / chat
- Aggregator：汇总各 Agent 结果，生成最终回复

状态流转：
用户输入 → Supervisor → 路由到专家Agent → Aggregator → 输出
                         ↓ (心理安抚可并行)
                      Psychology Agent
"""

import time
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState
from src.agent.supervisor import supervisor_node, route_to_agent, aggregator_node


def build_graph(llm: BaseChatModel):
    """构建多 Agent LangGraph 状态机"""

    # ===== 构建图 =====
    workflow = StateGraph(AgentState)

    # ===== 添加节点 =====
    workflow.add_node("supervisor", lambda state: supervisor_node(state, llm))
    workflow.add_node("vision", lambda state: _vision_node(state, llm))
    workflow.add_node("alternative", lambda state: _alternative_node(state, llm))
    workflow.add_node("manual", lambda state: _manual_node(state, llm))
    workflow.add_node("verify", lambda state: _verify_node(state, llm))
    workflow.add_node("psychology", lambda state: _psychology_node(state, llm))
    workflow.add_node("chat", lambda state: _chat_node(state, llm))
    workflow.add_node("aggregator", lambda state: aggregator_node(state, llm))

    # ===== 设置入口 =====
    workflow.set_entry_point("supervisor")

    # ===== Supervisor → 专家 Agent（条件路由）=====
    workflow.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "vision": "vision",
            "alternative": "alternative",
            "manual": "manual",
            "verify": "verify",
            "psychology": "psychology",
            "chat": "chat",
            "end": END,
        },
    )

    # ===== 所有专家 Agent → Aggregator =====
    for agent_name in ["vision", "alternative", "manual", "verify", "psychology", "chat"]:
        workflow.add_edge(agent_name, "aggregator")

    # ===== Aggregator → END =====
    workflow.add_edge("aggregator", END)

    return workflow.compile()


# ===== 专家 Agent 节点包装器 =====
# 这些包装器将 llm 传递给各 Agent 节点函数

def _vision_node(state: AgentState, llm: BaseChatModel) -> dict:
    """视觉识别 Agent 节点"""
    from src.agent.agents.vision_agent import vision_agent_node
    return vision_agent_node(state, llm)


def _alternative_node(state: AgentState, llm: BaseChatModel) -> dict:
    """零件替代 Agent 节点"""
    from src.agent.agents.alternative_agent import alternative_agent_node
    return alternative_agent_node(state, llm)


def _manual_node(state: AgentState, llm: BaseChatModel) -> dict:
    """说明书检索 Agent 节点"""
    from src.agent.agents.manual_agent import manual_agent_node
    return manual_agent_node(state, llm)


def _verify_node(state: AgentState, llm: BaseChatModel) -> dict:
    """成品验收 Agent 节点"""
    from src.agent.agents.verify_agent import verify_agent_node
    return verify_agent_node(state, llm)


def _psychology_node(state: AgentState, llm: BaseChatModel) -> dict:
    """心理安抚 Agent 节点"""
    from src.agent.agents.psychology_agent import psychology_agent_node
    return psychology_agent_node(state, llm)


def _chat_node(state: AgentState, llm: BaseChatModel) -> dict:
    """闲聊 Agent 节点"""
    from src.agent.agents.chat_agent import chat_agent_node
    return chat_agent_node(state, llm)


# ===== 兼容旧接口 =====
# 保留旧的 build_graph 签名，确保 main.py 和 server.py 兼容

# 保留 SYSTEM_PROMPT 供参考/兼容
SYSTEM_PROMPT = """你是 LEGO-Mate，一个乐高拼搭智能助手。

你可以帮助用户：
1. 识别乐高零件图片（parse_lego_image）
2. 查找零件替代方案（find_part_alternative）
3. 检索说明书步骤（search_manual_step）
4. 验收成品是否正确（verify_build_result）

工作流程：
- 用户上传图片时，先调用 parse_lego_image 识别
- 用户问缺件时，调用 find_part_alternative 查图谱
- 用户问步骤时，调用 search_manual_step 查说明书
- 用户验收时，调用 verify_build_result 对比

重要规则：
- 信息不足时主动追问，不要猜测
- 工具返回结果后，用友好的语言总结
- 如果工具返回 warning，告知用户当前使用的是备用数据
- 用户表现出沮丧时，给予鼓励和帮助
"""
