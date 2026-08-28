"""闲聊 Agent - 处理问候、感谢、告别、复杂问题、多步推理"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState

CHAT_SYSTEM_PROMPT = """你是 LEGO-Mate，一个友好、专业的乐高拼搭助手。

你的职责：
1. 处理日常问候、感谢、告别等社交对话
2. 回答关于乐高的一般性问题
3. 处理复杂问题和多步推理
4. 当用户意图不明确时，主动澄清

能力介绍：
- 🔍 识别零件：上传图片，我告诉你是什么零件
- 🔧 查找替代：缺件时推荐替代方案
- 📖 说明书检索：输入步骤号，返回图文
- ✅ 成品验收：对比官方模型，检查是否正确
- 🧱 3D 拼装：文字描述生成 3D 模型

对话风格：
- 简洁友好，不要过度啰嗦
- 用 emoji 增加亲和力（适度）
- 信息不足时主动追问，不要猜测
- 用户表现出沮丧时，给予鼓励

注意：
- 对于简单问候/感谢，简短回复即可
- 对于复杂问题，可以分步骤解释
- 如果问题超出你的能力范围，诚实告知"""


def chat_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """闲聊 Agent 节点"""
    # 先检查是否有快速回复
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content
            break

    # 尝试快速回复
    if last_user_msg:
        from src.agent.quick_response import get_quick_response
        quick_reply = get_quick_response(last_user_msg)
        if quick_reply:
            from langchain_core.messages import AIMessage
            return {
                "messages": [AIMessage(content=quick_reply)],
                "response": quick_reply,
            }

    # 完整 LLM 推理
    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)

    response_text = response.content if hasattr(response, "content") else str(response)

    return {
        "messages": [response],
        "response": response_text,
    }
