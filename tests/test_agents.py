"""专家 Agent 测试"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import AgentState


def _make_state(messages=None, **kwargs) -> AgentState:
    """创建测试用的 AgentState"""
    base: AgentState = {
        "messages": messages or [],
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


class TestVisionAgent:
    """测试视觉识别 Agent"""

    def test_vision_agent_with_no_tool_call(self):
        """测试无工具调用的情况"""
        from src.agent.agents.vision_agent import vision_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "请上传一张零件图片"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="这是什么零件")])
        result = vision_agent_node(state, mock_llm)

        assert "messages" in result
        assert "vision_result" in result

    def test_vision_agent_returns_result(self):
        """测试返回结果结构"""
        from src.agent.agents.vision_agent import vision_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "识别结果"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="识别这个零件")])
        result = vision_agent_node(state, mock_llm)

        assert isinstance(result["vision_result"], dict)


class TestAlternativeAgent:
    """测试零件替代 Agent"""

    def test_alternative_agent_with_no_tool_call(self):
        """测试无工具调用的情况"""
        from src.agent.agents.alternative_agent import alternative_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "请告诉我缺了什么零件"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="缺了红色2x4砖")])
        result = alternative_agent_node(state, mock_llm)

        assert "messages" in result
        assert "alternative_result" in result


class TestManualAgent:
    """测试说明书检索 Agent"""

    def test_manual_agent_with_no_tool_call(self):
        """测试无工具调用的情况"""
        from src.agent.agents.manual_agent import manual_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "请告诉我步骤号"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="这步怎么拼")])
        result = manual_agent_node(state, mock_llm)

        assert "messages" in result
        assert "manual_result" in result


class TestVerifyAgent:
    """测试成品验收 Agent"""

    def test_verify_agent_with_no_tool_call(self):
        """测试无工具调用的情况"""
        from src.agent.agents.verify_agent import verify_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "请上传成品图"
        mock_llm.bind_tools.return_value.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="帮我看下对么")])
        result = verify_agent_node(state, mock_llm)

        assert "messages" in result
        assert "verify_result" in result


class TestPsychologyAgent:
    """测试心理安抚 Agent"""

    def test_psychology_agent_detects_frustration(self):
        """测试挫折检测"""
        from src.agent.agents.psychology_agent import psychology_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "别急，我来帮你！"
        mock_llm.invoke.return_value = mock_response

        state = _make_state(
            messages=[HumanMessage(content="好难啊不想拼了")],
            frustration_score=60,
        )
        result = psychology_agent_node(state, mock_llm)

        assert "messages" in result
        assert "psychology_result" in result
        assert "frustration_score" in result

    def test_psychology_agent_generates_encouragement(self):
        """测试生成安抚话术"""
        from src.agent.agents.psychology_agent import psychology_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "你已经做得很好了！"
        mock_llm.invoke.return_value = mock_response

        state = _make_state(
            messages=[HumanMessage(content="太难了")],
            frustration_score=80,
        )
        result = psychology_agent_node(state, mock_llm)

        assert result["psychology_result"]["frustration_score"] > 0


class TestChatAgent:
    """测试闲聊 Agent"""

    def test_chat_agent_with_quick_response(self):
        """测试快速回复"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()

        state = _make_state(messages=[HumanMessage(content="你好")])
        result = chat_agent_node(state, mock_llm)

        assert "messages" in result
        # 快速回复应该直接返回 response
        assert "response" in result

    def test_chat_agent_with_complex_message(self):
        """测试复杂消息走 LLM"""
        from src.agent.agents.chat_agent import chat_agent_node

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "我是 LEGO-Mate，你的智能拼搭助手"
        mock_llm.invoke.return_value = mock_response

        state = _make_state(messages=[HumanMessage(content="你是谁")])
        result = chat_agent_node(state, mock_llm)

        assert "messages" in result


class TestAgentState:
    """测试 AgentState 结构"""

    def test_state_has_multi_agent_fields(self):
        """测试状态包含多 Agent 字段"""
        state = _make_state()

        # 多 Agent 调度字段
        assert "next_agent" in state
        assert "agent_results" in state

        # 各 Agent 专用输出
        assert "vision_result" in state
        assert "alternative_result" in state
        assert "manual_result" in state
        assert "verify_result" in state
        assert "psychology_result" in state

    def test_state_preserves_original_fields(self):
        """测试保留原有字段"""
        state = _make_state()

        # 原有字段
        assert "messages" in state
        assert "intent" in state
        assert "frustration_score" in state
        assert "graph_reasoning_result" in state
