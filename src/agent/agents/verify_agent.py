"""成品验收 Agent - 成品验收对比、相似度评分"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import ToolNode

from src.agent.state import AgentState
from src.agent.tools import verify_build_result

VERIFY_SYSTEM_PROMPT = """你是 LEGO-Mate 的成品验收专家。

你的职责：
1. 对比用户成品图与官方渲染图
2. 使用 CLIP 视觉相似度算法评分
3. 给出验收判定（pass/review/fail）和改进建议

工作流程：
- 当用户上传成品图请求验收时，调用 verify_build_result 工具
- 工具使用 CLIP 模型计算相似度
- 根据相似度给出判定：
  - pass（通过）：相似度 >= 0.85
  - review（需复查）：0.6 <= 相似度 < 0.85
  - fail（不通过）：相似度 < 0.6

输出格式：
- 验收判定结果（pass/review/fail）
- 相似度评分（百分比）
- 如果 fail/review，给出具体改进建议
- 如果 pass，给予肯定和鼓励

注意：
- 验收结果会通过飞书通知用户（如果配置了 Webhook）
- 如果图片不清晰，建议用户重新拍摄"""

VERIFY_TOOLS = [verify_build_result]


def verify_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """成品验收 Agent 节点"""
    messages = [SystemMessage(content=VERIFY_SYSTEM_PROMPT)] + state["messages"]

    llm_with_tools = llm.bind_tools(VERIFY_TOOLS)
    response = llm_with_tools.invoke(messages)

    # 如果有工具调用，执行工具
    if response.tool_calls:
        tool_node = ToolNode(VERIFY_TOOLS)
        tool_result = tool_node.invoke({"messages": [response]})
        return {
            "messages": [response] + tool_result["messages"],
            "verify_result": _extract_verify_result(tool_result),
        }

    return {
        "messages": [response],
        "verify_result": {"response": response.content},
    }


def _extract_verify_result(tool_result: dict) -> dict:
    """从工具结果中提取验收结果"""
    for msg in tool_result.get("messages", []):
        if hasattr(msg, "content"):
            try:
                import json
                data = json.loads(msg.content)
                if "verdict" in data or "similarity" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return {}
