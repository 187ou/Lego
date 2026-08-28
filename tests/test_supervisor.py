"""Supervisor 路由测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.agent.supervisor import _route_by_intent, route_to_agent, aggregator_node
from src.agent.state import AgentState


class TestRouteByIntent:
    """测试 Supervisor 路由逻辑"""

    def test_parse_image_routes_to_vision(self):
        """图片识别意图应路由到 vision"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.PARSE_IMAGE,
            level=ResponseLevel.L2_TOOL,
            confidence=0.9,
            tool_name="parse_lego_image",
        )
        result = _route_by_intent(intent, "这是什么零件", has_image=True)
        assert result == "vision"

    def test_find_alternative_routes_to_alternative(self):
        """零件替代意图应路由到 alternative"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.FIND_ALTERNATIVE,
            level=ResponseLevel.L2_TOOL,
            confidence=0.8,
            tool_name="find_part_alternative",
        )
        result = _route_by_intent(intent, "红色2x4砖有替代吗", has_image=False)
        assert result == "alternative"

    def test_search_manual_routes_to_manual(self):
        """说明书检索意图应路由到 manual"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.SEARCH_MANUAL,
            level=ResponseLevel.L2_TOOL,
            confidence=0.85,
            tool_name="search_manual_step",
        )
        result = _route_by_intent(intent, "第35步怎么拼", has_image=False)
        assert result == "manual"

    def test_verify_build_routes_to_verify(self):
        """成品验收意图应路由到 verify"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.VERIFY_BUILD,
            level=ResponseLevel.L2_TOOL,
            confidence=0.85,
            tool_name="verify_build_result",
        )
        result = _route_by_intent(intent, "帮我看下对么", has_image=True)
        assert result == "verify"

    def test_frustration_routes_to_psychology(self):
        """挫折情绪意图应路由到 psychology"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.FRUSTRATION,
            level=ResponseLevel.L1_QUICK,
            confidence=0.95,
        )
        result = _route_by_intent(intent, "好难啊不想拼了", has_image=False)
        assert result == "psychology"

    def test_greeting_routes_to_chat(self):
        """问候意图应路由到 chat"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.GREETING,
            level=ResponseLevel.L1_QUICK,
            confidence=0.95,
        )
        result = _route_by_intent(intent, "你好", has_image=False)
        assert result == "chat"

    def test_complex_routes_to_chat(self):
        """复杂问题应路由到 chat"""
        from src.agent.intent_router import Intent, IntentType, ResponseLevel

        intent = Intent(
            intent_type=IntentType.COMPLEX,
            level=ResponseLevel.L3_AGENT,
            confidence=0.7,
        )
        result = _route_by_intent(intent, "帮我设计一个乐高城堡", has_image=False)
        assert result == "chat"


class TestRouteToAgent:
    """测试条件路由函数"""

    def test_route_to_agent_returns_next_agent(self):
        """route_to_agent 应返回 state 中的 next_agent"""
        state: AgentState = {
            "next_agent": "vision",
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
            "agent_results": {},
            "vision_result": {},
            "alternative_result": {},
            "manual_result": {},
            "verify_result": {},
            "psychology_result": {},
        }
        assert route_to_agent(state) == "vision"

    def test_route_to_agent_defaults_to_chat(self):
        """route_to_agent 默认返回 chat"""
        state: AgentState = {
            "next_agent": "",
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
            "agent_results": {},
            "vision_result": {},
            "alternative_result": {},
            "manual_result": {},
            "verify_result": {},
            "psychology_result": {},
        }
        assert route_to_agent(state) == "chat"


class TestAggregatorNode:
    """测试结果汇总节点"""

    def test_aggregator_returns_existing_response(self):
        """如果已有 response，直接返回"""
        mock_llm = MagicMock()
        state: AgentState = {
            "messages": [],
            "intent": "",
            "parsed_result": {},
            "set_id": "",
            "step_number": 0,
            "require_human_confirm": False,
            "response": "已有回复",
            "frustration_score": 0,
            "retry_count": 0,
            "last_active_time": 0,
            "encouragement_triggered": False,
            "encouragement_messages": [],
            "graph_reasoning_result": {},
            "needs_graph_reasoning": False,
            "next_agent": "chat",
            "agent_results": {},
            "vision_result": {},
            "alternative_result": {},
            "manual_result": {},
            "verify_result": {},
            "psychology_result": {},
        }

        result = aggregator_node(state, mock_llm)
        assert result["response"] == "已有回复"

    def test_aggregator_with_no_response(self):
        """如果没有 response，调用 LLM 汇总"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "汇总后的回复"
        mock_llm.invoke.return_value = mock_response

        state: AgentState = {
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
            "next_agent": "vision",
            "agent_results": {},
            "vision_result": {"parts": [{"name": "3001", "color": "Red"}]},
            "alternative_result": {},
            "manual_result": {},
            "verify_result": {},
            "psychology_result": {},
        }

        result = aggregator_node(state, mock_llm)
        assert "response" in result
        mock_llm.invoke.assert_called_once()
