"""视觉识别 Agent - 零件图片识别、颜色/步骤号解析"""

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import ToolNode

from src.agent.state import AgentState
from src.agent.tools import parse_lego_image

VISION_SYSTEM_PROMPT = """你是 LEGO-Mate 的视觉识别专家。

你的职责：
1. 分析用户上传的乐高零件图片
2. 识别零件类型、颜色、数量
3. 判断步骤号（如果图片包含说明书步骤）

工作流程：
- 当用户上传图片时，调用 parse_lego_image 工具识别
- 识别结果包含：parts（零件列表）、colors（颜色）、step_number（步骤号）、confidence（置信度）
- 如果 confidence < 0.7，建议用户重新拍摄
- 用友好的语言总结识别结果

输出格式：
- 列出识别到的零件（名称 + 颜色 + 数量）
- 如果有步骤号，告知用户
- 如果识别到多个零件，按置信度排序"""

VISION_TOOLS = [parse_lego_image]


def vision_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """视觉识别 Agent 节点"""
    messages = [SystemMessage(content=VISION_SYSTEM_PROMPT)] + state["messages"]

    llm_with_tools = llm.bind_tools(VISION_TOOLS)
    response = llm_with_tools.invoke(messages)

    # 如果有工具调用，执行工具
    if response.tool_calls:
        tool_node = ToolNode(VISION_TOOLS)
        tool_result = tool_node.invoke({"messages": [response]})
        return {
            "messages": [response] + tool_result["messages"],
            "vision_result": _extract_vision_result(tool_result),
        }

    return {
        "messages": [response],
        "vision_result": {"response": response.content},
    }


def _extract_vision_result(tool_result: dict) -> dict:
    """从工具结果中提取视觉识别结果"""
    for msg in tool_result.get("messages", []):
        if hasattr(msg, "content"):
            try:
                import json
                data = json.loads(msg.content)
                if "parts" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return {}
