"""图谱推理引擎测试"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kg.graph_reasoner import (
    GraphReasoner,
    REASONING_CONSTRAINT,
    REASONING_CHAIN,
    REASONING_STABILITY,
)
from src.kg.graph_store import MockGraphStore
from src.kg.graph_retriever import GraphRetriever
from src.kg.schema import NodeType, GraphNode, GraphRelation, RelationType


@pytest.fixture
def mock_store():
    return MockGraphStore()


@pytest.fixture
def populated_store(mock_store):
    """预填充零件和替代关系的图谱"""
    for pid, name in [
        ("3001", "Brick 2x4"), ("3002", "Brick 2x3"), ("3003", "Brick 2x2"),
        ("3005", "Brick 1x1"), ("3010", "Brick 1x4"), ("3020", "Plate 2x4"),
        ("3023", "Plate 1x2"),
    ]:
        mock_store.create_node(GraphNode(
            node_type=NodeType.PART, node_id=f"part_{pid}", name=name,
        ))
    # 替代关系
    for src, tgt in [("3001", "3002"), ("3002", "3003"), ("3001", "3020")]:
        mock_store.create_relation(GraphRelation(
            relation_type=RelationType.CAN_REPLACE,
            source_id=f"part_{src}", target_id=f"part_{tgt}",
            confidence=0.8,
        ))
    return mock_store


@pytest.fixture
def mock_llm():
    """模拟 LLM 返回合法 JSON"""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content='{"conclusion": "测试结论", "confidence": 0.85, "reasoning_chain": ["步骤1"], "suggestions": ["建议1"], "risks": [], "missing_info": []}')
    return llm


@pytest.fixture
def reasoner(populated_store, mock_llm):
    retriever = GraphRetriever(store=populated_store)
    return GraphReasoner(llm=mock_llm, retriever=retriever)


class TestGraphReasonerInit:
    """推理引擎初始化测试"""

    def test_init_with_llm_and_retriever(self, mock_llm, mock_store):
        retriever = GraphRetriever(store=mock_store)
        reasoner = GraphReasoner(llm=mock_llm, retriever=retriever)
        assert reasoner.llm is mock_llm
        assert reasoner.retriever is retriever

    def test_init_without_retriever_uses_default(self, mock_llm):
        reasoner = GraphReasoner(llm=mock_llm)
        assert reasoner.retriever is not None


class TestGraphReasonerConstraint:
    """约束推理测试"""

    def test_constraint_reasoning_returns_result(self, reasoner, mock_llm):
        result = reasoner.reason(
            query="我有3001但缺3003，有什么替代方案？",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result
        assert result["conclusion"] == "测试结论"
        assert result["confidence"] == 0.85
        mock_llm.invoke.assert_called_once()

    def test_constraint_reasoning_with_no_parts(self, reasoner):
        """无零件号的查询应返回空子图"""
        result = reasoner.reason(
            query="乐高怎么拼？",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result
        # 子图应无节点
        assert "subgraph_summary" in result


class TestGraphReasonerChain:
    """链式推理测试"""

    def test_chain_reasoning(self, reasoner):
        result = reasoner.reason(
            query="第35步和第36步可以跳过吗？",
            reasoning_type=REASONING_CHAIN,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result


class TestGraphReasonerStability:
    """稳定性推理测试"""

    def test_stability_reasoning(self, reasoner):
        result = reasoner.reason(
            query="这个位置放3023板够稳固吗？",
            reasoning_type=REASONING_STABILITY,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result


class TestGraphReasonerEdgeCases:
    """边缘情况测试"""

    def test_empty_graph(self, mock_llm, mock_store):
        """空图谱不应崩溃"""
        retriever = GraphRetriever(store=mock_store)
        reasoner = GraphReasoner(llm=mock_llm, retriever=retriever)

        result = reasoner.reason(
            query="3001的替代方案",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result

    def test_llm_returns_invalid_json(self, populated_store):
        """LLM 返回非法 JSON 时应降级解析"""
        bad_llm = MagicMock()
        bad_llm.invoke.return_value = MagicMock(content="这不是JSON，是普通文本结论")

        retriever = GraphRetriever(store=populated_store)
        reasoner = GraphReasoner(llm=bad_llm, retriever=retriever)

        result = reasoner.reason(
            query="3001的替代方案",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result
        assert result["conclusion"] == "这不是JSON，是普通文本结论"
        assert result["confidence"] == 0.5  # 降级解析的默认 confidence

    def test_llm_returns_json_in_markdown(self, populated_store):
        """LLM 返回 markdown 代码块中的 JSON"""
        md_llm = MagicMock()
        md_llm.invoke.return_value = MagicMock(
            content='```json\n{"conclusion": "markdown结论", "confidence": 0.75}\n```'
        )

        retriever = GraphRetriever(store=populated_store)
        reasoner = GraphReasoner(llm=md_llm, retriever=retriever)

        result = reasoner.reason(
            query="3001的替代方案",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert result["conclusion"] == "markdown结论"
        assert result["confidence"] == 0.75

    def test_llm_exception(self, populated_store):
        """LLM 异常时应返回错误信息"""
        error_llm = MagicMock()
        error_llm.invoke.side_effect = RuntimeError("LLM 服务不可用")

        retriever = GraphRetriever(store=populated_store)
        reasoner = GraphReasoner(llm=error_llm, retriever=retriever)

        result = reasoner.reason(
            query="3001的替代方案",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result
        assert "RuntimeError" in result["conclusion"] or "不可用" in result["conclusion"]
        assert result["confidence"] == 0

    def test_empty_query(self, reasoner):
        """空查询不应崩溃"""
        result = reasoner.reason(
            query="",
            reasoning_type=REASONING_CONSTRAINT,
            context={"set_id": "10295"},
        )
        assert "conclusion" in result

    def test_convenience_methods(self, reasoner):
        """便捷方法测试"""
        result = reasoner.reason_constraint(
            query="缺3003",
            has_parts=["3001"],
            missing_parts=["3003"],
        )
        assert "conclusion" in result

        result = reasoner.reason_chain(
            query="步骤跳过",
            steps=[35, 36],
        )
        assert "conclusion" in result

        result = reasoner.reason_stability(
            query="稳固吗",
            part_id="3023",
        )
        assert "conclusion" in result


class TestSubgraphRetrieval:
    """子图检索测试"""

    def test_constraint_retrieves_alternatives(self, reasoner):
        """约束推理应检索替代链"""
        result = reasoner._retrieve_subgraph(
            "3001的替代方案", REASONING_CONSTRAINT, {"set_id": "10295"}
        )
        # 应包含 3001 及其替代
        node_ids = [n["id"] for n in result["nodes"]]
        assert "part_3001" in node_ids

    def test_chain_retrieves_steps(self, populated_store, mock_llm):
        """链式推理应检索步骤"""
        populated_store.create_node(GraphNode(
            node_type=NodeType.STEP,
            node_id="set_10295_step_35",
            name="步骤 35",
            text_description="步骤35描述",
        ))
        populated_store.create_node(GraphNode(
            node_type=NodeType.STEP,
            node_id="set_10295_step_36",
            name="步骤 36",
            text_description="步骤36描述",
        ))

        retriever = GraphRetriever(store=populated_store)
        reasoner = GraphReasoner(llm=mock_llm, retriever=retriever)

        result = reasoner._retrieve_subgraph(
            "第35步和第36步", REASONING_CHAIN, {"set_id": "10295"}
        )
        node_ids = [n["id"] for n in result["nodes"]]
        assert "set_10295_step_35" in node_ids
        assert "set_10295_step_36" in node_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
