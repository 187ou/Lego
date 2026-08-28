"""闲聊 Agent - 处理问候、感谢、告别、复杂问题、多步推理

增强功能：
- 当意图是工具类但参数不足时，主动追问用户
- 识别用户可能的工具需求并引导
"""

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState

CHAT_SYSTEM_PROMPT = """你是 LEGO-Mate，一个友好、专业的乐高拼搭助手。

你的职责：
1. 处理日常问候、感谢、告别等社交对话
2. 回答关于乐高的一般性问题
3. 处理复杂问题和多步推理
4. 当用户意图不明确时，主动澄清和引导

能力介绍：
- 🔍 识别零件：上传图片，我告诉你是什么零件
- 🔧 查找替代：缺件时推荐替代方案（告诉我缺了什么零件）
- 📖 说明书检索：输入步骤号，返回图文
- ✅ 成品验收：上传成品图，对比官方模型检查
- 🧱 3D 拼装：文字描述生成 3D 模型

对话风格：
- 简洁友好，不要过度啰嗦
- 用 emoji 增加亲和力（适度）
- 信息不足时主动追问，不要猜测
- 用户表现出沮丧时，给予鼓励

引导规则：
- 用户问"有替代吗"但没说具体零件 → 追问："请告诉我缺了什么零件？（如：红色2x4砖）"
- 用户问"这步怎么拼"但没说步骤号 → 追问："请告诉我步骤号（如：第35步）"
- 用户问"对吗"但没上传图片 → 引导："请上传成品图，我帮你验收"
- 用户表达想买/找零件 → 建议："我可以帮你查找零件替代方案，告诉我具体零件名称"
"""

# 追问模板（当意图匹配但参数不足时使用）
CLARIFICATION_PROMPTS = {
    "alternative": "请告诉我缺了什么零件？\n\n💡 示例：\n- \"红色2x4砖有替代吗\"\n- \"缺了3001怎么办\"",
    "manual": "请告诉我步骤号？\n\n💡 示例：\n- \"第35步怎么拼\"\n- \"第100步是什么\"",
    "verify": "请上传成品图，我帮你验收是否正确。\n\n💡 上传图片后我会对比官方模型给出判定",
    "vision": "请上传一张零件图片，我帮你识别。\n\n💡 图片越清晰，识别越准确",
}


def chat_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """闲聊 Agent 节点（增强版 - 支持参数不足时追问）"""
    # 获取最后一条用户消息
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content
            break

    # 尝试快速回复（问候/感谢/告别等）
    if last_user_msg:
        from src.agent.quick_response import get_quick_response
        quick_reply = get_quick_response(last_user_msg)
        if quick_reply:
            return {
                "messages": [AIMessage(content=quick_reply)],
                "response": quick_reply,
            }

    # 检查是否是参数不足的工具类意图
    clarification = _check_clarification_needed(state, last_user_msg)
    if clarification:
        return {
            "messages": [AIMessage(content=clarification)],
            "response": clarification,
        }

    # 完整 LLM 推理
    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)

    response_text = response.content if hasattr(response, "content") else str(response)

    return {
        "messages": [response],
        "response": response_text,
    }


def _check_clarification_needed(state: AgentState, message: str) -> str:
    """检查是否需要追问补充参数

    当意图路由器判断为 L3(COMPLEX) 但实际上用户的表达接近工具调用时，
    主动追问具体参数，而不是让 LLM 自由发挥。
    """
    if not message:
        return ""

    # 从状态中获取意图信息
    intent_value = state.get("intent", "")

    # 如果意图是 COMPLEX，检查是否是参数不足的工具类问题
    if intent_value != "complex":
        return ""

    msg = message.strip().lower()

    # 检查是否是替代类问题但缺少零件信息
    alt_keywords = ["替代", "代替", "替换", "兼容", "缺了", "没有"]
    if any(kw in msg for kw in alt_keywords):
        # 检查是否有具体零件信息
        from src.agent.intent_router import _extract_part_info
        info = _extract_part_info(message)
        if not info.get("part_name") and not info.get("color"):
            return CLARIFICATION_PROMPTS["alternative"]

    # 检查是否是说明书类问题但缺少步骤号
    manual_keywords = ["步", "step", "怎么拼", "如何拼"]
    if any(kw in msg for kw in manual_keywords):
        # 检查是否有步骤号
        from src.agent.intent_router import _extract_step_number
        step = _extract_step_number(message)
        if step is None:
            return CLARIFICATION_PROMPTS["manual"]

    # 检查是否是验收类问题但没有图片
    verify_keywords = ["对吗", "正确", "检查", "验收", "核对"]
    if any(kw in msg for kw in verify_keywords):
        return CLARIFICATION_PROMPTS["verify"]

    return ""
