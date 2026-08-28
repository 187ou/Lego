"""心理安抚 Agent - 挫折检测、共情话术生成"""

import time
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState

PSYCHOLOGY_SYSTEM_PROMPT = """你是 LEGO-Mate 的心理安抚专家。

你的职责：
1. 检测用户的情绪状态（特别是挫折、沮丧）
2. 生成共情话术，安抚用户情绪
3. 提供鼓励和实用建议

工作流程：
- 分析用户消息中的负面情绪关键词
- 结合挫折分数（frustration_score）判断安抚级别
- 生成包含以下内容的安抚话术：
  - 共情理解（"我理解你的感受"）
  - 鼓励支持（"你已经做得很好了"）
  - 实用建议（具体的解决思路）
  - 冷知识/小贴士（转移注意力）

安抚级别：
- 高度挫折（>=80）：深度安抚 + 贴士 + 冷知识
- 中度挫折（>=50）：鼓励 + 贴士
- 轻度挫折（<50）：简单鼓励

输出格式：
- 以 💝 开头
- 语气温暖、真诚
- 避免空洞的"加油"，给出具体建议"""


def psychology_agent_node(state: AgentState, llm: BaseChatModel) -> dict:
    """心理安抚 Agent 节点"""
    from src.psychology.frustration_detector import FrustrationDetector
    from src.psychology.encouragement_library import get_encouragement_library

    detector = FrustrationDetector()
    library = get_encouragement_library()

    # 获取当前挫折分数
    current_score = state.get("frustration_score", 0)
    retry_count = state.get("retry_count", 0)
    last_active = state.get("last_active_time", time.time())

    # 获取最后一条用户消息
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
            last_user_msg = msg.content
            break

    # 检测挫折信号
    msg_result = detector.check_message(last_user_msg)
    retry_result = detector.check_retry(retry_count)
    idle_result = detector.check_idle(last_active)

    # 计算新挫折分数
    new_score = detector.calculate_frustration_score(
        current_score, msg_result, retry_result, idle_result
    )

    # 生成安抚话术
    encouragement = library.get_full_encouragement(new_score)

    # 用 LLM 润色话术（结合上下文）
    messages = [
        SystemMessage(content=PSYCHOLOGY_SYSTEM_PROMPT),
        AIMessage(content=encouragement),
    ]

    try:
        response = llm.invoke(messages)
        final_encouragement = response.content if hasattr(response, "content") else encouragement
    except Exception:
        final_encouragement = encouragement

    return {
        "messages": [AIMessage(content=final_encouragement)],
        "psychology_result": {
            "encouragement": final_encouragement,
            "frustration_score": new_score,
            "msg_analysis": msg_result,
        },
        "frustration_score": new_score,
    }
