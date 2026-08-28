"""说明书检索 Agent - 说明书步骤检索、图文内容返回"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import ToolNode

from src.agent.state import AgentState
from src.agent.tools import search_manual_step

MANUAL_SYSTEM_PROMPT = """你是 LEGO-Mate 的说明书检索专家。

你的职责：
1. 根据用户指定的步骤号，检索说明书内容
2. 返回步骤的图文描述、零件清单、注意事项
3. 支持上下文关联（如"上一步""下一步"）

工作流程：
- 当用户询问某一步怎么拼时，调用 search_manual_step 工具
- 工具从向量数据库（ChromaDB）检索最匹配的步骤内容
- 结合当前套装信息过滤结果
- 用清晰的步骤说明回复用户

输出格式：
- 步骤号 + 步骤描述
- 所需零件清单（如有）
- 注意事项/技巧（如有）
- 如果用户问"上一步/下一步"，自动关联

注意：
- 如果工具返回 warning（RAG 不可用），告知用户当前使用备用数据
- 如果找不到步骤内容，建议用户检查步骤号"""

MANUAL_TOOLS = [search_manual_step]


def manual_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """说明书检索 Agent 节点"""
    messages = [SystemMessage(content=MANUAL_SYSTEM_PROMPT)] + state["messages"]

    llm_with_tools = llm.bind_tools(MANUAL_TOOLS)
    response = llm_with_tools.invoke(messages)

    # 如果有工具调用，执行工具
    if response.tool_calls:
        tool_node = ToolNode(MANUAL_TOOLS)
        tool_result = tool_node.invoke({"messages": [response]})
        return {
            "messages": [response] + tool_result["messages"],
            "manual_result": _extract_manual_result(tool_result),
        }

    return {
        "messages": [response],
        "manual_result": {"response": response.content},
    }


def _extract_manual_result(tool_result: dict) -> dict:
    """从工具结果中提取说明书内容"""
    for msg in tool_result.get("messages", []):
        if hasattr(msg, "content"):
            try:
                import json
                data = json.loads(msg.content)
                if "content" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
    return {}
