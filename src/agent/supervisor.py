"""Supervisor 调度中心 - 分析意图，决定调用哪个/哪些专家 Agent"""

import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState

SUPERVISOR_SYSTEM_PROMPT = """你是 LEGO-Mate 的调度中心（Supervisor）。

你的职责是分析用户意图，决定调用哪个专家 Agent 来处理。

可选的专家 Agent：
- vision: 视觉识别（零件图片识别、颜色/步骤号解析）
- alternative: 零件替代（缺件替代查询、图谱约束推理）
- manual: 说明书检索（说明书步骤检索、图文内容返回）
- verify: 成品验收（成品验收对比、相似度评分）
- psychology: 心理安抚（挫折检测、共情话术生成）
- chat: 闲聊/通用（问候、感谢、复杂问题、多步推理）

路由规则：
1. 用户上传图片问"这是什么零件" → vision
2. 用户问"XX零件有替代吗" → alternative
3. 用户问"第X步怎么拼" → manual
4. 用户上传成品图问"对吗" → verify
5. 用户表达负面情绪（"好难""不想拼"） → psychology
6. 问候/感谢/告别 → chat
7. 复杂问题/模糊意图 → chat

只返回 Agent 名称（vision/alternative/manual/verify/psychology/chat），不要解释。"""


def supervisor_node(state: AgentState, llm: BaseChatModel) -> dict:
    """Supervisor 节点：分析意图，决定路由"""

    # 获取最后一条用户消息
    last_user_msg = ""
    has_image = False
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content
            # 检查是否包含图片（简化判断：消息中有图片路径或图片标记）
            if any(ext in last_user_msg.lower() for ext in [".png", ".jpg", ".jpeg", "图片", "image"]):
                has_image = True
            break

    # 使用意图路由器做初步分类
    from src.agent.intent_router import classify_intent, IntentType, ResponseLevel

    intent = classify_intent(last_user_msg, has_image)

    # 根据意图类型决定路由
    next_agent = _route_by_intent(intent, last_user_msg, has_image)

    return {
        "next_agent": next_agent,
        "intent": intent.intent_type.value,
        "last_active_time": time.time(),
    }


def _route_by_intent(intent, message: str, has_image: bool) -> str:
    """根据意图类型决定路由到哪个 Agent"""
    from src.agent.intent_router import ResponseLevel, IntentType

    # L1 快速回复类 → chat（但挫折情绪例外 → psychology）
    if intent.level == ResponseLevel.L1_QUICK:
        if intent.intent_type == IntentType.FRUSTRATION:
            return "psychology"
        return "chat"

    # L2 工具直调类
    if intent.level == ResponseLevel.L2_TOOL:
        routing_map = {
            IntentType.PARSE_IMAGE: "vision",
            IntentType.FIND_ALTERNATIVE: "alternative",
            IntentType.SEARCH_MANUAL: "manual",
            IntentType.VERIFY_BUILD: "verify",
        }
        return routing_map.get(intent.intent_type, "chat")

    # L3 或情绪类
    if intent.intent_type == IntentType.FRUSTRATION:
        return "psychology"

    # 复杂问题/闲聊 → chat
    return "chat"


def route_to_agent(state: AgentState) -> str:
    """条件路由函数 - 供 LangGraph add_conditional_edges 使用"""
    next_agent = state.get("next_agent", "")
    if not next_agent:
        return "chat"
    return next_agent


def aggregator_node(state: AgentState, llm: BaseChatModel) -> dict:
    """结果汇总节点 - 收集各 Agent 结果，生成最终回复"""

    # 收集各 Agent 的执行结果
    agent_results = {
        "vision": state.get("vision_result", {}),
        "alternative": state.get("alternative_result", {}),
        "manual": state.get("manual_result", {}),
        "verify": state.get("verify_result", {}),
        "psychology": state.get("psychology_result", {}),
    }

    # 获取各 Agent 的消息
    messages = state.get("messages", [])

    # 如果已经有 response（chat agent 直接生成的），直接返回
    existing_response = state.get("response", "")
    if existing_response:
        return {
            "response": existing_response,
            "agent_results": agent_results,
        }

    # 否则，用 LLM 汇总各 Agent 结果
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content
            break

    # 构建汇总 prompt
    summary_prompt = _build_summary_prompt(last_user_msg, agent_results, state)

    from langchain_core.messages import AIMessage
    try:
        response = llm.invoke([
            SystemMessage(content="你是 LEGO-Mate 的回复生成器。根据以下信息，生成友好、简洁的回复。"),
            HumanMessage(content=summary_prompt),
        ])
        final_response = response.content if hasattr(response, "content") else str(response)
    except Exception:
        # 如果 LLM 调用失败，使用简单拼接
        final_response = _simple_aggregate(agent_results)

    return {
        "response": final_response,
        "agent_results": agent_results,
    }


def _build_summary_prompt(user_msg: str, agent_results: dict, state: AgentState) -> str:
    """构建汇总 prompt（增强版 - 结构化输出）"""
    parts = [f"用户消息：{user_msg}\n"]

    # 视觉识别结果
    vision = agent_results.get("vision", {})
    if vision:
        parts.append(_format_vision_result(vision))

    # 零件替代结果
    alternative = agent_results.get("alternative", {})
    if alternative:
        parts.append(_format_alternative_result(alternative))

    # 说明书结果
    manual = agent_results.get("manual", {})
    if manual:
        parts.append(_format_manual_result(manual))

    # 验收结果
    verify = agent_results.get("verify", {})
    if verify:
        parts.append(_format_verify_result(verify))

    # 心理安抚结果
    psychology = agent_results.get("psychology", {})
    if psychology:
        parts.append(_format_psychology_result(psychology))

    parts.append("\n请根据以上信息，生成一段友好、简洁的回复。直接回复用户，不要提及内部处理过程。")
    return "\n".join(parts)


def _format_vision_result(result: dict) -> str:
    """格式化视觉识别结果"""
    lines = ["🔍 视觉识别结果："]
    parts_list = result.get("parts", [])
    if parts_list:
        for p in parts_list:
            lines.append(f"  - {p.get('name', '未知')} x{p.get('quantity', 1)} ({p.get('color', '未知')})")
    colors = result.get("colors", [])
    if colors:
        lines.append(f"  颜色：{', '.join(colors)}")
    conf = result.get("confidence", 0)
    lines.append(f"  置信度：{conf:.0%}")
    if result.get("needs_retry"):
        lines.append("  ⚠️ 建议重新拍摄")
    return "\n".join(lines)


def _format_alternative_result(result: dict) -> str:
    """格式化零件替代结果"""
    lines = ["🔧 零件替代方案："]
    alts = result.get("alternatives", [])
    if alts:
        for i, alt in enumerate(alts[:5], 1):
            conf = alt.get("confidence", 0)
            emoji = "🟢" if conf >= 0.8 else "🟡" if conf >= 0.5 else "🔴"
            lines.append(f"  {emoji} {alt.get('name', '未知')} ({alt.get('color', '未知')}) - 匹配度 {conf:.0%}")
    else:
        lines.append("  未找到替代方案")
    # 图谱推理结果
    reasoning = result.get("graph_reasoning", {})
    if reasoning and reasoning.get("conclusion"):
        lines.append(f"  🧠 推理：{reasoning['conclusion']}")
    return "\n".join(lines)


def _format_manual_result(result: dict) -> str:
    """格式化说明书检索结果"""
    lines = ["📖 说明书内容："]
    step = result.get("step_number")
    if step:
        lines.append(f"  步骤 {step}")
    content = result.get("content", "")
    if content:
        lines.append(f"  {content}")
    page = result.get("page_number")
    if page:
        lines.append(f"  参考第 {page} 页")
    return "\n".join(lines)


def _format_verify_result(result: dict) -> str:
    """格式化验收结果"""
    lines = ["✅ 验收结果："]
    verdict = result.get("verdict", "unknown")
    emoji_map = {"pass": "✅ 通过", "review": "⚠️ 需复查", "fail": "❌ 不通过"}
    lines.append(f"  判定：{emoji_map.get(verdict, verdict)}")
    similarity = result.get("similarity", 0)
    lines.append(f"  相似度：{similarity:.0%}")
    details = result.get("details", "")
    if details:
        lines.append(f"  详情：{details}")
    return "\n".join(lines)


def _format_psychology_result(result: dict) -> str:
    """格式化心理安抚结果"""
    encouragement = result.get("encouragement", "")
    if encouragement:
        return f"💝 心理安抚：\n  {encouragement}"
    return ""


def _simple_aggregate(agent_results: dict) -> str:
    """简单拼接各 Agent 结果（LLM 不可用时的降级方案，增强版）"""
    parts = []

    # 按优先级顺序处理各 Agent 结果
    # 1. 心理安抚（最高优先级）
    psychology = agent_results.get("psychology", {})
    if psychology and psychology.get("encouragement"):
        parts.append(psychology["encouragement"])

    # 2. 视觉识别
    vision = agent_results.get("vision", {})
    if vision:
        parts.append(_format_vision_result(vision))

    # 3. 零件替代
    alternative = agent_results.get("alternative", {})
    if alternative:
        parts.append(_format_alternative_result(alternative))

    # 4. 说明书
    manual = agent_results.get("manual", {})
    if manual:
        parts.append(_format_manual_result(manual))

    # 5. 验收
    verify = agent_results.get("verify", {})
    if verify:
        parts.append(_format_verify_result(verify))

    # 兜底回复
    if not parts:
        return "抱歉，我暂时无法处理你的请求。请稍后再试，或者换个方式描述你的问题。"

    return "\n\n".join(parts)
