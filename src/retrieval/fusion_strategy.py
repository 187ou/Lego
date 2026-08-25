"""融合策略

将来自不同检索源的结果融合排序。
支持多种融合策略：加权排序、RRF、最大置信度等。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetrievalResult:
    """统一的检索结果格式"""
    content: str                           # 内容
    source: str                            # 来源：memory/text/graph/image/cross_modal
    score: float = 0.0                     # 原始分数
    fused_score: float = 0.0               # 融合后分数
    metadata: dict = field(default_factory=dict)  # 元数据
    doc_id: str = ""                       # 文档 ID


@dataclass
class FusionConfig:
    """融合配置"""

    # 各源的权重
    memory_weight: float = 0.3             # L1-L3 记忆权重
    vector_weight: float = 0.25            # L4 向量检索权重
    graph_weight: float = 0.25             # L4 图谱检索权重
    cross_modal_weight: float = 0.2        # L4 跨模态检索权重

    # 融合策略
    strategy: str = "weighted"             # weighted / rrf / max_confidence

    # RRF 参数 (Reciprocal Rank Fusion)
    rrf_k: int = 60                        # RRF 平滑参数

    # 去重
    dedup: bool = True                     # 是否去重
    dedup_threshold: float = 0.85          # 相似度阈值（超过视为重复）

    # 结果限制
    max_results: int = 10                  # 最大返回数量
    min_score: float = 0.1                 # 最低分数阈值


class FusionStrategy:
    """融合策略"""

    def __init__(self, config: Optional[FusionConfig] = None):
        self.config = config or FusionConfig()

    def fuse(self, results_by_source: dict[str, list[RetrievalResult]]) -> list[RetrievalResult]:
        """
        融合多源检索结果。

        Args:
            results_by_source: {source_name: [results]}

        Returns:
            融合后的排序结果
        """
        if self.config.strategy == "weighted":
            return self._weighted_fusion(results_by_source)
        elif self.config.strategy == "rrf":
            return self._rrf_fusion(results_by_source)
        elif self.config.strategy == "max_confidence":
            return self._max_confidence_fusion(results_by_source)
        else:
            return self._weighted_fusion(results_by_source)

    def _weighted_fusion(
        self, results_by_source: dict[str, list[RetrievalResult]]
    ) -> list[RetrievalResult]:
        """加权融合"""
        # 源到权重的映射
        source_weights = {
            "memory": self.config.memory_weight,
            "vector": self.config.vector_weight,
            "graph": self.config.graph_weight,
            "cross_modal": self.config.cross_modal_weight,
        }

        all_results = []

        for source, results in results_by_source.items():
            weight = source_weights.get(source, 0.1)

            for result in results:
                result.fused_score = result.score * weight
                all_results.append(result)

        # 去重
        if self.config.dedup:
            all_results = self._deduplicate(all_results)

        # 排序
        all_results.sort(key=lambda x: x.fused_score, reverse=True)

        # 过滤低分
        all_results = [r for r in all_results if r.fused_score >= self.config.min_score]

        return all_results[:self.config.max_results]

    def _rrf_fusion(
        self, results_by_source: dict[str, list[RetrievalResult]]
    ) -> list[RetrievalResult]:
        """RRF (Reciprocal Rank Fusion) 融合"""
        k = self.config.rrf_k
        scores: dict[str, float] = {}
        result_map: dict[str, RetrievalResult] = {}

        for source, results in results_by_source.items():
            for rank, result in enumerate(results):
                doc_id = result.doc_id or result.content[:50]

                # RRF 分数
                rrf_score = 1.0 / (k + rank + 1)

                if doc_id in scores:
                    scores[doc_id] += rrf_score
                else:
                    scores[doc_id] = rrf_score
                    result_map[doc_id] = result

        # 更新融合分数
        for doc_id, score in scores.items():
            result_map[doc_id].fused_score = score

        # 排序
        fused = sorted(result_map.values(), key=lambda x: x.fused_score, reverse=True)

        return fused[:self.config.max_results]

    def _max_confidence_fusion(
        self, results_by_source: dict[str, list[RetrievalResult]]
    ) -> list[RetrievalResult]:
        """最大置信度融合（取每个文档的最高分数）"""
        best_scores: dict[str, RetrievalResult] = {}

        for source, results in results_by_source.items():
            for result in results:
                doc_id = result.doc_id or result.content[:50]

                if doc_id not in best_scores or result.score > best_scores[doc_id].score:
                    best_scores[doc_id] = result
                    result.fused_score = result.score

        fused = sorted(best_scores.values(), key=lambda x: x.fused_score, reverse=True)

        return fused[:self.config.max_results]

    def _deduplicate(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """去重（基于内容相似度）"""
        if not results:
            return results

        unique = [results[0]]

        for result in results[1:]:
            is_dup = False
            for existing in unique:
                similarity = self._text_similarity(result.content, existing.content)
                if similarity > self.config.dedup_threshold:
                    is_dup = True
                    # 保留分数更高的
                    if result.fused_score > existing.fused_score:
                        existing.content = result.content
                        existing.fused_score = result.fused_score
                        existing.metadata.update(result.metadata)
                    break

            if not is_dup:
                unique.append(result)

        return unique

    def _text_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度（Jaccard）"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1)
        set2 = set(text2)

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0
