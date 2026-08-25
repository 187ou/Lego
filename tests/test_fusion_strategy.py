"""融合策略测试"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.fusion_strategy import (
    RetrievalResult,
    FusionStrategy,
    FusionConfig,
)


class TestRetrievalResult:
    """检索结果测试"""

    def test_create_result(self):
        """创建检索结果"""
        result = RetrievalResult(
            content="测试内容",
            source="vector",
            score=0.9,
        )
        assert result.content == "测试内容"
        assert result.source == "vector"
        assert result.score == 0.9
        assert result.fused_score == 0.0


class TestFusionStrategy:
    """融合策略测试"""

    def test_weighted_fusion(self):
        """加权融合"""
        config = FusionConfig(strategy="weighted")
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content="记忆1", source="memory", score=0.8),
                RetrievalResult(content="记忆2", source="memory", score=0.6),
            ],
            "vector": [
                RetrievalResult(content="向量1", source="vector", score=0.9),
            ],
            "graph": [
                RetrievalResult(content="图谱1", source="graph", score=0.85),
            ],
        }

        fused = strategy.fuse(results_by_source)

        assert len(fused) > 0
        # 加权后分数应正确
        for r in fused:
            assert r.fused_score > 0

    def test_rrf_fusion(self):
        """RRF 融合"""
        config = FusionConfig(strategy="rrf")
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content="结果A", source="memory", score=0.9, doc_id="a"),
                RetrievalResult(content="结果B", source="memory", score=0.7, doc_id="b"),
            ],
            "vector": [
                RetrievalResult(content="结果A", source="vector", score=0.85, doc_id="a"),
                RetrievalResult(content="结果C", source="vector", score=0.75, doc_id="c"),
            ],
        }

        fused = strategy.fuse(results_by_source)

        # 结果 A 在两个源中都出现，排名应最高
        assert len(fused) >= 2
        assert fused[0].doc_id == "a"  # 跨源出现，RRF 分数最高

    def test_max_confidence_fusion(self):
        """最大置信度融合"""
        config = FusionConfig(strategy="max_confidence")
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content="结果A", source="memory", score=0.6, doc_id="a"),
            ],
            "vector": [
                RetrievalResult(content="结果A", source="vector", score=0.9, doc_id="a"),
            ],
        }

        fused = strategy.fuse(results_by_source)

        # 应取最高分数 0.9
        assert len(fused) == 1
        assert fused[0].fused_score == 0.9

    def test_deduplication(self):
        """去重"""
        config = FusionConfig(dedup=True, dedup_threshold=0.5)
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content="完全相同的内容", source="memory", score=0.8, doc_id="a"),
            ],
            "vector": [
                RetrievalResult(content="完全相同的内容", source="vector", score=0.9, doc_id="a"),
            ],
        }

        fused = strategy.fuse(results_by_source)

        # 应去重为一个
        assert len(fused) == 1

    def test_empty_results(self):
        """空结果"""
        config = FusionConfig()
        strategy = FusionStrategy(config)

        fused = strategy.fuse({})
        assert fused == []

    def test_min_score_filter(self):
        """最低分数过滤"""
        config = FusionConfig(min_score=0.3, strategy="weighted")
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content="高分", source="memory", score=0.9),
                RetrievalResult(content="低分", source="memory", score=0.1),
            ],
        }

        fused = strategy.fuse(results_by_source)

        # 低分应被过滤（加权后 0.1 * 0.3 = 0.03 < 0.3）
        for r in fused:
            assert r.fused_score >= config.min_score

    def test_max_results_limit(self):
        """最大结果数限制"""
        config = FusionConfig(max_results=3)
        strategy = FusionStrategy(config)

        results_by_source = {
            "memory": [
                RetrievalResult(content=f"结果{i}", source="memory", score=0.9 - i * 0.1)
                for i in range(10)
            ],
        }

        fused = strategy.fuse(results_by_source)
        assert len(fused) <= 3


class TestContextBuilder:
    """上下文构建器测试"""

    def test_build_context(self):
        """构建上下文"""
        from src.retrieval.context_builder import ContextBuilder, ContextConfig

        builder = ContextBuilder()
        results = [
            RetrievalResult(content="测试内容1", source="vector", score=0.9),
            RetrievalResult(content="测试内容2", source="graph", score=0.8),
        ]

        context = builder.build(
            fused_results=results,
            user_query="测试查询",
        )

        assert len(context) > 0
        assert context[0]["role"] == "system"

    def test_build_with_profile(self):
        """带用户画像"""
        from src.retrieval.context_builder import ContextBuilder

        builder = ContextBuilder()
        results = [RetrievalResult(content="内容", source="vector", score=0.9)]

        context = builder.build(
            fused_results=results,
            user_profile={"skill_level": "advanced", "preferred_sets": ["10295"]},
        )

        # 应包含用户画像
        has_profile = any("用户偏好" in m.get("content", "") for m in context)
        assert has_profile

    def test_build_with_summary(self):
        """带对话摘要"""
        from src.retrieval.context_builder import ContextBuilder

        builder = ContextBuilder()
        results = [RetrievalResult(content="内容", source="vector", score=0.9)]

        context = builder.build(
            fused_results=results,
            conversation_summary="用户问了5个问题",
        )

        has_summary = any("对话摘要" in m.get("content", "") for m in context)
        assert has_summary

    def test_token_budget(self):
        """Token 预算"""
        from src.retrieval.context_builder import ContextBuilder, ContextConfig

        config = ContextConfig(max_tokens=100)
        builder = ContextBuilder(config)

        # 大量结果
        results = [
            RetrievalResult(content="A" * 100, source="vector", score=0.9 - i * 0.01)
            for i in range(20)
        ]

        context = builder.build(fused_results=results)

        # 应在预算内
        assert len(context) < 20  # 不可能全部放入


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
