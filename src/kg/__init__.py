"""多模态知识图谱模块

构建包含文本、图片和它们之间关系的多模态知识图谱。

节点类型：
- Set（套装）
- Part（零件）
- Step（步骤）
- Color（颜色）
- Category（类别）
- Image（图片）

关系类型：
- CONTAINS（套装包含零件）
- USES（步骤使用零件）
- FOLLOWS（步骤顺序）
- CAN_REPLACE（零件替代）
- HAS_COLOR（零件颜色）
- BELONGS_TO（零件类别）
- HAS_IMAGE（步骤/零件图片）
- CROSS_MODAL（跨模态关联）
"""

from src.kg.graph_store import GraphStore, get_graph_store
from src.kg.graph_builder import GraphBuilder, build_from_manual
from src.kg.graph_retriever import GraphRetriever, get_graph_retriever
from src.kg.schema import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelation,
)

__all__ = [
    "GraphStore",
    "get_graph_store",
    "GraphBuilder",
    "build_from_manual",
    "GraphRetriever",
    "get_graph_retriever",
    "NodeType",
    "RelationType",
    "GraphNode",
    "GraphRelation",
]
