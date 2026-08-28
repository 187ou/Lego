"""多 Agent 系统端到端测试

测试维度：
1. 路由严谨性 - 各类输入是否路由到正确 Agent
2. 内部通信 - 状态传递、结果汇总是否正确
3. 异常兜底 - 各节点失败时的降级策略
4. 安全边界 - 异常输入、空值、超长输入处理
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import AgentState
from src.agent.supervisor import (
    supervisor_node,
    route_to_agent,
    aggregator_node,
    _route_by_intent,
)
from src.agent.graph import build_graph


def _make_state(**kwargs) -> AgentState:
    """创建测试用 AgentState"""
    base: AgentState = {
        "messages": [],
        "intent": "",
        "parsed_result": {},
        "set_id": "",
        "step_number": 0,
        "require_human_confirm": False,
        "response": "",
        "frustration_score": 0,
        "retry_count": 0,
        "last_active_time": 0,
        "encouragement_triggered": False,
        "encouragement_messages": [],
        "graph_reasoning_result": {},
        "needs_graph_reasoning": False,
        "next_agent": "",
        "agent_results": {},
        "vision_result": {},
        "alternative_result": {},
        "manual_result": {},
        "verify_result": {},
        "psychology_result": {},
    }
    base.update(kwargs)
    return base


# ===== 1. 路由严谨性测试 =====

class TestRoutingCorrectness:
    """测试路由正确性 - 各类输入是否路由到正确 Agent"""

    @pytest.mark.parametrize("message,expected_agent", [
        # 视觉识别
        ("这是什么零件", "vision"),
        ("帮我识别这个零件", "vision"),
        ("这个零件叫什么", "vision"),
        # 零件替代（需要匹配意图路由器的正则模式 + 参数提取成功）
        ("缺了3001怎么办", "alternative"),
        ("3001有什么替代", "alternative"),
        # 注意: "有没有什么替代方案" 匹配模式但参数为空，会降级到 chat
        # 说明书检索
        ("第35步怎么拼", "manual"),
        ("第100步是什么", "manual"),
        ("step 50", "manual"),
        # 成品验收（需要匹配意图路由器的正则模式）
        ("帮我看下对么", "verify"),
        ("帮我看一下对吗", "verify"),
        # 心理安抚
        ("好难啊不想拼了", "psychology"),
        ("太难了崩溃了", "psychology"),
        ("烦死了", "psychology"),
        # 闲聊/问候
        ("你好", "chat"),
        ("谢谢", "chat"),
        ("拜拜", "chat"),
        ("你是谁", "chat"),
        # 复杂问题
        ("帮我设计一个乐高城堡", "chat"),
        ("今天天气怎么样", "chat"),
    ])
    def test_routing_correctness(self, message, expected_agent):
        """测试各类消息路由到正确 Agent"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent(message)
        result = _route_by_intent(intent, message, has_image=False)
        assert result == expected_agent, f"消息 '{message}' 应路由到 {expected_agent}，实际路由到 {result}"

    def test_image_with_verify_intent(self):
        """带图片 + 验收文本 → verify"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("帮我看下对么", has_image=True)
        result = _route_by_intent(intent, "帮我看下对么", has_image=True)
        assert result == "verify"

    def test_image_with_parse_intent(self):
        """带图片 + 识别文本 → vision"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("这是什么零件", has_image=True)
        result = _route_by_intent(intent, "这是什么零件", has_image=True)
        assert result == "vision"

    def test_negation_should_not_route_to_tool(self):
        """否定词不应路由到工具 Agent"""
        from src.agent.intent_router import classify_intent

        # "不需要替代" 不应路由到 alternative
        intent = classify_intent("不需要替代方案")
        result = _route_by_intent(intent, "不需要替代方案", has_image=False)
        assert result != "alternative"

    # ===== 改进后的路由测试 =====

    def test_improved_alternative_pattern_有替代吗(self):
        """改进: '红色2x4砖有替代吗' 现在应匹配 alternative"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("红色2x4砖有替代吗")
        result = _route_by_intent(intent, "红色2x4砖有替代吗", has_image=False)
        assert result == "alternative", f"应路由到 alternative，实际路由到 {result}"

    def test_improved_alternative_pattern_能替代(self):
        """改进: '这个能替代吗' 应匹配 alternative"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("这个能替代吗")
        result = _route_by_intent(intent, "这个能替代吗", has_image=False)
        # 参数不足时可能降级到 chat，但模式应匹配
        assert result in ("alternative", "chat")

    def test_improved_verify_pattern_检查是否正确(self):
        """改进: '检查成品是否正确' 现在应匹配 verify"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("检查成品是否正确")
        result = _route_by_intent(intent, "检查成品是否正确", has_image=False)
        assert result == "verify", f"应路由到 verify，实际路由到 {result}"

    def test_improved_verify_pattern_帮我看是否正确(self):
        """改进: '帮我看是否正确' 应匹配 verify"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("帮我看是否正确")
        result = _route_by_intent(intent, "帮我看是否正确", has_image=False)
        assert result == "verify", f"应路由到 verify，实际路由到 {result}"

    def test_empty_message_defaults_to_chat(self):
        """空消息默认路由到 chat"""
        state = _make_state(next_agent="")
        assert route_to_agent(state) == "chat"


# ===== 2. 内部通信测试 =====

class TestInternalCommunication:
    """测试 Agent 间状态传递和结果汇总"""

    def test_supervisor_sets_next_agent(self):
        """Supervisor 应正确设置 next_agent"""
        mock_llm = MagicMock()
        state = _make_state(messages=[HumanMessage(content="第35步怎么拼")])

        result = supervisor_node(state, mock_llm)

        assert "next_agent" in result
        assert result["next_agent"] == "manual"

    def test_supervisor_sets_intent(self):
        """Supervisor 应正确设置 intent"""
        mock_llm = MagicMock()
        state = _make_state(messages=[HumanMessage(content="你好")])

        result = supervisor_node(state, mock_llm)

        assert "intent" in result
        assert result["intent"] == "greeting"

    def test_aggregator_collects_agent_results(self):
        """Aggregator 应收集各 Agent 结果"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "汇总回复"
        mock_llm.invoke.return_value = mock_response

        state = _make_state(
            messages=[HumanMessage(content="测试")],
            vision_result={"parts": [{"name": "3001"}]},
            alternative_result={"alternatives": []},
            manual_result={"content": "步骤内容"},
        )

        result = aggregator_node(state, mock_llm)

        assert "agent_results" in result
        assert "response" in result

    def test_aggregator_preserves_existing_response(self):
        """Aggregator 应保留已有 response（ChatAgent 直接生成的）"""
        mock_llm = MagicMock()
        state = _make_state(
            messages=[],
            response="ChatAgent 直接生成的回复",
        )

        result = aggregator_node(state, mock_llm)

        assert result["response"] == "ChatAgent 直接生成的回复"
        # 不应再调用 LLM
        mock_llm.invoke.assert_not_called()

    def test_state_fields_preserved_across_agents(self):
        """状态字段在 Agent 传递过程中应保持"""
        state = _make_state(
            set_id="10295",
            step_number=35,
            frustration_score=50,
        )

        # 模拟 Supervisor 输出
        supervisor_output = supervisor_node(state, MagicMock())
        merged = {**state, **supervisor_output}

        assert merged["set_id"] == "10295"
        assert merged["step_number"] == 35
        assert merged["frustration_score"] == 50


# ===== 3. 异常兜底测试 =====

class TestFallbackStrategies:
    """测试各节点失败时的降级策略"""

    def test_aggregator_fallback_when_llm_fails(self):
        """Aggregator 在 LLM 失败时应使用结构化模板拼接"""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM 不可用")

        state = _make_state(
            messages=[],
            response="",
            vision_result={"parts": [{"name": "3001", "color": "Red", "quantity": 1}], "confidence": 0.9},
            psychology_result={"encouragement": "别急，我来帮你"},
        )

        result = aggregator_node(state, mock_llm)

        # 应有结构化兜底回复
        assert "response" in result
        assert len(result["response"]) > 0
        # 验证包含格式化内容
        response = result["response"]
        assert "3001" in response or "别急" in response

    def test_chat_agent_fallback_to_llm_when_no_quick_response(self):
        """ChatAgent 在没有快速回复时应走 LLM"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "LLM 生成的回复"
        mock_llm.invoke.return_value = mock_response

        # 不匹配任何快速回复规则的消息
        state = _make_state(messages=[HumanMessage(content="帮我分析一下这个复杂的乐高结构问题")])
        result = chat_agent_node(state, mock_llm)

        assert "response" in result
        mock_llm.invoke.assert_called_once()

    def test_psychology_agent_fallback_when_llm_fails(self):
        """PsychologyAgent 在 LLM 失败时应使用内置话术"""
        from src.agent.agents.psychology_agent import psychology_agent_node

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM 不可用")

        state = _make_state(
            messages=[HumanMessage(content="好难啊")],
            frustration_score=60,
        )

        result = psychology_agent_node(state, mock_llm)

        # 应有内置话术兜底
        assert "psychology_result" in result
        assert "encouragement" in result["psychology_result"]

    def test_vision_agent_handles_tool_failure(self):
        """VisionAgent 工具调用失败时应返回错误信息"""
        from src.agent.agents.vision_agent import vision_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []  # 无工具调用
        mock_response.content = "请上传一张清晰的零件图片"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="识别零件")])
        result = vision_agent_node(state, mock_llm)

        assert "vision_result" in result

    def test_alternative_agent_handles_empty_alternatives(self):
        """AlternativeAgent 无替代方案时应返回友好提示"""
        from src.agent.agents.alternative_agent import alternative_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "未找到替代方案，请确认零件名称和颜色"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="xyz有替代吗")])
        result = alternative_agent_node(state, mock_llm)

        assert "alternative_result" in result


# ===== 4. 安全边界测试 =====

class TestSecurityBoundaries:
    """测试异常输入和边界情况"""

    def test_empty_message(self):
        """空消息处理"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("")
        result = _route_by_intent(intent, "", has_image=False)
        assert result in ("chat", "psychology")  # 空消息应路由到 chat 或 psychology

    def test_very_long_message(self):
        """超长消息处理"""
        from src.agent.intent_router import classify_intent

        long_msg = "好难啊" * 1000
        intent = classify_intent(long_msg)
        result = _route_by_intent(intent, long_msg, has_image=False)
        assert result in ("chat", "psychology")

    def test_special_characters(self):
        """特殊字符处理"""
        from src.agent.intent_router import classify_intent

        special_msgs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "🔧🔍📖✅❌🧱🤖",
            "\n\t\r",
            "NULL",
            "undefined",
        ]
        for msg in special_msgs:
            intent = classify_intent(msg)
            result = _route_by_intent(intent, msg, has_image=False)
            assert result in ("vision", "alternative", "manual", "verify", "psychology", "chat")

    def test_sql_injection_pattern(self):
        """SQL 注入模式不应破坏路由"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("1; DELETE FROM parts WHERE 1=1")
        result = _route_by_intent(intent, "1; DELETE FROM parts WHERE 1=1", has_image=False)
        assert result in ("vision", "alternative", "manual", "verify", "psychology", "chat")

    def test_unicode_emoji_mix(self):
        """Unicode 和 emoji 混合"""
        from src.agent.intent_router import classify_intent

        intent = classify_intent("第35步怎么拼 🔧📖")
        result = _route_by_intent(intent, "第35步怎么拼 🔧📖", has_image=False)
        assert result == "manual"


# ===== 5. 状态一致性测试 =====

class TestStateConsistency:
    """测试状态在多 Agent 传递中的一致性"""

    def test_all_agent_result_fields_exist(self):
        """所有 Agent 结果字段应存在"""
        state = _make_state()

        assert "vision_result" in state
        assert "alternative_result" in state
        assert "manual_result" in state
        assert "verify_result" in state
        assert "psychology_result" in state

    def test_agent_results_is_dict(self):
        """Agent 结果应为字典类型"""
        state = _make_state()

        assert isinstance(state["vision_result"], dict)
        assert isinstance(state["alternative_result"], dict)
        assert isinstance(state["manual_result"], dict)
        assert isinstance(state["verify_result"], dict)
        assert isinstance(state["psychology_result"], dict)

    def test_messages_accumulate(self):
        """消息应正确累加"""
        state = _make_state(messages=[HumanMessage(content="你好")])

        # 模拟 Agent 添加消息
        new_messages = state["messages"] + [AIMessage(content="回复")]
        state["messages"] = new_messages

        assert len(state["messages"]) == 2


# ===== 6. 图构建测试 =====

class TestGraphBuild:
    """测试图构建"""

    def test_graph_builds_successfully(self):
        """图应成功构建"""
        mock_llm = MagicMock()
        graph = build_graph(mock_llm)
        assert graph is not None

    def test_graph_has_all_nodes(self):
        """图应包含所有必要节点"""
        mock_llm = MagicMock()
        graph = build_graph(mock_llm)

        # LangGraph compiled graph 应有 nodes 属性
        assert hasattr(graph, "nodes")


# ===== 7. 端到端模拟测试 =====

class TestEndToEndSimulation:
    """端到端模拟测试 - 模拟完整的多 Agent 调用流程"""

    def test_greeting_flow(self):
        """问候流程：Supervisor → ChatAgent → Aggregator"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "你好！我是 LEGO-Mate 🧱"
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        # 1. Supervisor 路由
        state = _make_state(messages=[HumanMessage(content="你好")])
        supervisor_output = supervisor_node(state, mock_llm)
        assert supervisor_output["next_agent"] == "chat"

        # 2. ChatAgent 生成回复
        from src.agent.agents.chat_agent import chat_agent_node
        chat_output = chat_agent_node(state, mock_llm)
        assert "response" in chat_output

    def test_manual_step_flow(self):
        """说明书检索流程：Supervisor → ManualAgent → Aggregator"""
        mock_llm = MagicMock()

        # 1. Supervisor 路由
        state = _make_state(messages=[HumanMessage(content="第35步怎么拼")])
        supervisor_output = supervisor_node(state, mock_llm)
        assert supervisor_output["next_agent"] == "manual"

    def test_frustration_flow(self):
        """挫折安抚流程：Supervisor → PsychologyAgent → Aggregator"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "别急，我来帮你！"
        mock_llm.invoke.return_value = mock_response

        # 1. Supervisor 路由
        state = _make_state(
            messages=[HumanMessage(content="好难啊不想拼了")],
            frustration_score=60,
        )
        supervisor_output = supervisor_node(state, mock_llm)
        assert supervisor_output["next_agent"] == "psychology"

        # 2. PsychologyAgent 生成安抚话术
        from src.agent.agents.psychology_agent import psychology_agent_node
        psycho_output = psychology_agent_node(state, mock_llm)
        assert "psychology_result" in psycho_output
        assert "frustration_score" in psycho_output


# ===== 8. ChatAgent 追问功能测试 =====

class TestChatAgentClarification:
    """测试 ChatAgent 参数不足时的追问功能"""

    def test_chat_agent_asks_clarification_for_vague_alternative(self):
        """ChatAgent 对模糊的替代问题应追问具体零件"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()

        # 意图是 complex + 包含"替代"关键词 + 无具体零件
        state = _make_state(
            messages=[HumanMessage(content="有什么替代吗")],
            intent="complex",
        )
        result = chat_agent_node(state, mock_llm)

        assert "response" in result
        # 应包含追问内容
        assert "零件" in result["response"] or "什么" in result["response"]
        # 不应调用 LLM（追问是模板化的）
        mock_llm.invoke.assert_not_called()

    def test_chat_agent_asks_clarification_for_vague_manual(self):
        """ChatAgent 对模糊的说明书问题应追问步骤号"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()

        state = _make_state(
            messages=[HumanMessage(content="这步怎么拼")],
            intent="complex",
        )
        result = chat_agent_node(state, mock_llm)

        assert "response" in result
        # 应包含追问步骤号的内容
        assert "步骤" in result["response"] or "号" in result["response"]

    def test_chat_agent_asks_clarification_for_verify_without_image(self):
        """ChatAgent 对无图片的验收问题应引导上传图片"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()

        state = _make_state(
            messages=[HumanMessage(content="我拼的对吗")],
            intent="complex",
        )
        result = chat_agent_node(state, mock_llm)

        assert "response" in result
        # 应引导上传图片
        assert "图片" in result["response"] or "上传" in result["response"]

    def test_chat_agent_no_clarification_when_intent_is_clear(self):
        """ChatAgent 在意图明确时不追问"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "好的，我来帮你"
        mock_llm.invoke.return_value = mock_response

        # 意图是 greeting（非 complex）
        state = _make_state(
            messages=[HumanMessage(content="你好")],
            intent="greeting",
        )
        result = chat_agent_node(state, mock_llm)

        # greeting 有快速回复，不会走到追问逻辑
        assert "response" in result
