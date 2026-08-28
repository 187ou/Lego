"""零件替代 Agent - 缺件替代查询、图谱约束推理"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import ToolNode

from src.agent.state import AgentState
from src.agent.tools import find_part_alternative

ALTERNATIVE_SYSTEM_PROMPT = """你是 LEGO-Mate 的零件替代专家。

你的职责：
1. 当用户缺少某个零件时，查找替代方案
2. 基于 Neo4j 知识图谱进行约束推理
3. 考虑颜色兼容性、结构兼容性、功能等价性

工作流程：
- 当用户询问替代方案时，调用 find_part_alternative 工具
- 工具会查询 Neo4j 图谱，返回按匹配度排序的替代方案
- 如果有图谱推理结果，结合推理结论给出建议
- 用清晰的列表展示替代方案

输出格式：
- 列出替代方案（零件名 + 颜色 + 匹配置信度）
- 如果有约束条件（如"不要黑色"），说明哪些方案满足
- 给出最终推荐（最优替代方案）

注意：
- 如果工具返回 warning（Neo4j 不可用），告知用户当前使用备用数据
- 如果没有找到替代方案，建议用户购买原厂零件"""

ALTERNATIVE_TOOLS = [find_part_alternative]


def alternative_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """零件替代 Agent 节点"""
    messages = [SystemMessage(content=ALTERNATIVE_SYSTEM_PROMPT)] + state["messages"]

    llm_with_tools = llm.bind_tools(ALTERNATIVE_TOOLS)
    response = llm_with_tools.invoke(messages)

    # 如果有工具调用，执行工具
    if response.tool_calls:
        tool_node = ToolNode(ALTERNATIVE_TOOLS)
        tool_result = tool_node.invoke({"messages": [response]})

        # 尝试图谱深度推理
        reasoning_result = _try_graph_reasoning(state, response.tool_calls)

        return {
            "messages": [response] + tool_result["messages"],
            "alternative_result": _extract_alternative_result(tool_result, reasoning_result),
        }

    return {
        "messages": [response],
        "alternative_result": {"response": response.content},
    }


def _try_graph_reasoning(state: AgentState, tool_calls: list) -> dict:
    """尝试图谱深度推理"""
    try:
        from src.kg.graph_reasoner import get_graph_reasoner

        last_user_msg = ""
        for msg in reversed(state.get("messages", [])):
            if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
                last_user_msg = msg.content
                break

        if not last_user_msg:
            return {}

        reasoner = get_graph_reasoner()
        result = reasoner.reason(
            query=last_user_msg,
            reasoning_type="constraint",
            context={"set_id": state.get("set_id", "")},
        )
        return result
    except Exception:
        return {}


def _extract_alternative_result(tool_result: dict, reasoning_result: dict) -> dict:
    """从工具结果中提取替代方案"""
    for msg in tool_result.get("messages", []):
        if hasattr(msg, "content"):
            try:
                import json
                data = json.loads(msg.content)
                if "alternatives" in data:
                    data["graph_reasoning"] = reasoning_result
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return {"graph_reasoning": reasoning_result}
