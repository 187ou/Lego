"""多路检索融合模块

将来自不同层级和模态的检索结果融合为统一的 LLM 输入：
- L1 短期记忆检索（Redis - 对话历史）
- L2 中期记忆检索（Redis - 对话摘要）
- L3 长期记忆检索（Redis - 用户画像）
- L4 向量检索（ChromaDB - 语义搜索）
- L4 图谱检索（Neo4j - 关系推理）
- L4 跨模态检索（文本↔图片）
"""

from src.retrieval.unified_retriever import UnifiedRetriever, get_unified_retriever
from src.retrieval.fusion_strategy import FusionStrategy, FusionConfig
from src.retrieval.context_builder import ContextBuilder, ContextConfig

__all__ = [
    "UnifiedRetriever",
    "get_unified_retriever",
    "FusionStrategy",
    "FusionConfig",
    "ContextBuilder",
    "ContextConfig",
]
