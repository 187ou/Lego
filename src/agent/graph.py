"""LangGraph 对话中枢——完整状态机实现（含心理安抚旁路）

状态流转：
待解析 → 进度确认 → 缺件待补/结构纠偏
                     ↓ (挂起超时/重复提问/情绪词命中)
                【心理安抚节点】← 非阻塞旁路触发
                     ↓
              等待用户操作（挂起）→ 二次验收 → 已归档
"""

import time
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.state import AgentState
from src.agent.tools import ALL_TOOLS

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


def build_graph(llm: BaseChatModel):
    """构建 LangGraph 状态机（含心理安抚旁路）"""

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    tool_node = ToolNode(ALL_TOOLS)

    # ===== 节点函数 =====

    def agent_node(state: AgentState) -> dict:
        """Agent 节点：调用 LLM 生成回复或工具调用"""
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)

        require_confirm = False
        if response.tool_calls:
            for call in response.tool_calls:
                if call["name"] in ("find_part_alternative", "verify_build_result"):
                    require_confirm = True

        return {
            "messages": [response],
            "require_human_confirm": require_confirm,
            "last_active_time": time.time(),
        }

    def route_after_agent(state: AgentState) -> str:
        """路由：有工具调用则执行，否则直接回复"""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "respond"

    def human_in_the_loop_node(state: AgentState) -> dict:
        """Human-in-the-loop 节点：挂起等待用户确认"""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for call in last_message.tool_calls:
                print(f"\n[HITL] 即将执行: {call['name']}")
                print(f"  参数: {call['args']}")
        return {}

    def respond_node(state: AgentState) -> dict:
        """回复节点：生成最终回复 + 发送通知"""
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and not last_message.tool_calls:
            return {"response": last_message.content}

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)

        _send_notification_if_needed(state, response.content)

        return {
            "messages": [response],
            "response": response.content,
        }

    def frustration_check_node(state: AgentState) -> dict:
        """
        挫折检测节点（旁路）
        检测用户是否需要心理安抚，更新挫折分数
        """
        from src.psychology.frustration_detector import FrustrationDetector

        detector = FrustrationDetector()
        current_score = state.get("frustration_score", 0)
        retry_count = state.get("retry_count", 0)
        last_active = state.get("last_active_time", time.time())

        # 获取最后一条用户消息
        last_user_msg = ""
        for msg in reversed(state.get("messages", [])):
            if hasattr(msg, "content") and getattr(msg, "type", "") == "human":
                last_user_msg = msg.content
                break

        msg_result = detector.check_message(last_user_msg)
        retry_result = detector.check_retry(retry_count)
        idle_result = detector.check_idle(last_active)

        new_score = detector.calculate_frustration_score(
            current_score, msg_result, retry_result, idle_result
        )

        return {"frustration_score": new_score}

    def should_encourage(state: AgentState) -> str:
        """判断是否需要心理安抚"""
        score = state.get("frustration_score", 0)
        retry_count = state.get("retry_count", 0)
        last_active = state.get("last_active_time", time.time())

        from src.psychology.frustration_detector import FrustrationDetector
        detector = FrustrationDetector()

        if detector.should_encourage(score, retry_count, last_active):
            return "yes"
        return "no"

    def encouragement_node(state: AgentState) -> dict:
        """
        心理安抚节点（旁路）
        生成共情话术，附加到响应中
        """
        from src.psychology.encouragement_library import get_encouragement_library

        score = state.get("frustration_score", 0)
        library = get_encouragement_library()
        encouragement = library.get_full_encouragement(score)

        # 将安抚话术附加到响应中
        current_response = state.get("response", "")
        if current_response:
            new_response = f"{current_response}\n\n---\n💝 {encouragement}"
        else:
            new_response = f"💝 {encouragement}"

        # 重置挫折分数
        return {
            "response": new_response,
            "frustration_score": max(0, score - 30),
        }

    def _send_notification_if_needed(state: AgentState, response_content: str):
        """根据工具调用结果发送通知"""
        try:
            from src.notification.feishu import (
                send_build_verification_result,
                send_missing_part_alert,
            )

            for msg in state["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for call in msg.tool_calls:
                        if call["name"] == "verify_build_result":
                            for result_msg in state["messages"]:
                                if hasattr(result_msg, "content") and "verdict" in str(result_msg.content):
                                    import json
                                    try:
                                        data = json.loads(result_msg.content)
                                        send_build_verification_result(
                                            set_id=state.get("set_id", "unknown"),
                                            verdict=data.get("verdict", "unknown"),
                                            similarity=data.get("similarity", 0),
                                            details=data.get("details", ""),
                                        )
                                    except:
                                        pass
                                    break

                        elif call["name"] == "find_part_alternative":
                            for result_msg in state["messages"]:
                                if hasattr(result_msg, "content") and "alternatives" in str(result_msg.content):
                                    import json
                                    try:
                                        data = json.loads(result_msg.content)
                                        alts = data.get("alternatives", [])
                                        if alts:
                                            send_missing_part_alert(
                                                set_id=state.get("set_id", "unknown"),
                                                part_name=call["args"].get("part_name", "unknown"),
                                                color=call["args"].get("color", "unknown"),
                                                alternatives=alts,
                                            )
                                    except:
                                        pass
                                    break
        except Exception as e:
            print(f"[WARN] 通知发送失败: {e}")

    # ===== 构建图 =====

    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("human_check", human_in_the_loop_node)
    workflow.add_node("respond", respond_node)
    workflow.add_node("frustration_check", frustration_check_node)
    workflow.add_node("encouragement", encouragement_node)

    # 设置入口
    workflow.set_entry_point("agent")

    # 主流程
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "respond": "respond"},
    )

    workflow.add_edge("tools", "human_check")
    workflow.add_edge("human_check", "respond")

    # 回复后 → 挫折检测（旁路）
    workflow.add_edge("respond", "frustration_check")

    # 挫折检测后 → 判断是否需要安抚
    workflow.add_conditional_edges(
        "frustration_check",
        should_encourage,
        {"yes": "encouragement", "no": END},
    )

    # 安抚后 → 结束
    workflow.add_edge("encouragement", END)

    return workflow.compile()
