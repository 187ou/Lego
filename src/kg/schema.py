"""知识图谱 Schema 定义

定义多模态知识图谱的节点类型、关系类型和属性。
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class NodeType(str, Enum):
    """节点类型"""
    SET = "Set"                 # 套装
    PART = "Part"               # 零件
    STEP = "Step"               # 步骤
    COLOR = "Color"             # 颜色
    CATEGORY = "Category"       # 类别
    IMAGE = "Image"             # 图片


class RelationType(str, Enum):
    """关系类型"""
    # 结构关系
    CONTAINS = "CONTAINS"           # 套装 → 零件（包含）
    USES = "USES"                   # 步骤 → 零件（使用）
    FOLLOWS = "FOLLOWS"             # 步骤 → 步骤（顺序）

    # 零件关系
    CAN_REPLACE = "CAN_REPLACE"     # 零件 → 零件（替代）
    COMPATIBLE_WITH = "COMPATIBLE_WITH"  # 零件 → 零件（兼容）

    # 属性关系
    HAS_COLOR = "HAS_COLOR"         # 零件 → 颜色
    BELONGS_TO = "BELONGS_TO"       # 零件 → 类别

    # 多模态关系
    HAS_IMAGE = "HAS_IMAGE"         # 步骤/零件 → 图片
    DEPICTS = "DEPICTS"             # 图片 → 零件（描绘）
    CROSS_MODAL = "CROSS_MODAL"     # 文本 ↔ 图片（跨模态关联）


@dataclass
class GraphNode:
    """图谱节点"""
    node_type: NodeType
    node_id: str                    # 唯一标识
    name: str                       # 显示名称
    properties: dict = field(default_factory=dict)  # 额外属性

    # 多模态属性
    text_description: str = ""      # 文本描述
    image_url: str = ""             # 图片 URL/路径
    embedding: Optional[list[float]] = None  # 向量表示


@dataclass
class GraphRelation:
    """图谱关系"""
    relation_type: RelationType
    source_id: str                  # 源节点 ID
    target_id: str                  # 目标节点 ID
    properties: dict = field(default_factory=dict)  # 额外属性

    # 多模态属性
    confidence: float = 1.0         # 关系置信度
    source_modality: str = ""       # 来源模态（text/image）


# ===== Schema 约束 =====

# 每种节点类型的必填属性
NODE_REQUIRED_PROPS = {
    NodeType.SET: ["set_id", "name"],
    NodeType.PART: ["part_id", "name"],
    NodeType.STEP: ["step_number", "set_id"],
    NodeType.COLOR: ["name"],
    NodeType.CATEGORY: ["name"],
    NodeType.IMAGE: ["image_url"],
}

# 每种关系类型的源/目标节点约束
RELATION_CONSTRAINTS = {
    RelationType.CONTAINS: (NodeType.SET, NodeType.PART),
    RelationType.USES: (NodeType.STEP, NodeType.PART),
    RelationType.FOLLOWS: (NodeType.STEP, NodeType.STEP),
    RelationType.CAN_REPLACE: (NodeType.PART, NodeType.PART),
    RelationType.COMPATIBLE_WITH: (NodeType.PART, NodeType.PART),
    RelationType.HAS_COLOR: (NodeType.PART, NodeType.COLOR),
    RelationType.BELONGS_TO: (NodeType.PART, NodeType.CATEGORY),
    RelationType.HAS_IMAGE: (NodeType.STEP, NodeType.IMAGE),
    RelationType.DEPICTS: (NodeType.IMAGE, NodeType.PART),
    RelationType.CROSS_MODAL: (NodeType.PART, NodeType.IMAGE),
}

# Cypher 查询模板
CYPHER_TEMPLATES = {
    # 创建节点
    "create_node": "MERGE (n:{node_type} {{node_id: $node_id}}) SET n += $props",

    # 创建关系
    "create_relation": """
        MATCH (a {{node_id: $source_id}}), (b {{node_id: $target_id}})
        MERGE (a)-[r:{relation_type}]->(b)
        SET r += $props
    """,

    # 查询节点的邻居
    "get_neighbors": """
        MATCH (n {{node_id: $node_id}})-[r]-(m)
        RETURN n, r, m
        LIMIT $limit
    """,

    # 查询节点的出边
    "get_outgoing": """
        MATCH (n {{node_id: $node_id}})-[r]->(m)
        RETURN type(r) as relation, m.node_id as target, m.name as name
        LIMIT $limit
    """,

    # 查询节点的入边
    "get_incoming": """
        MATCH (n {{node_id: $node_id}})<-[r]-(m)
        RETURN type(r) as relation, m.node_id as source, m.name as name
        LIMIT $limit
    """,

    # 多跳查询（找替代零件）
    "find_alternatives": """
        MATCH (p {{node_id: $part_id}})-[:CAN_REPLACE*1..3]-(alt)
        WHERE alt:Part AND alt.node_id <> $part_id
        RETURN DISTINCT alt.node_id as part_id, alt.name as name,
               length(shortestPath((p)-[:CAN_REPLACE*]-(alt))) as distance
        ORDER BY distance
        LIMIT $limit
    """,

    # 查询套装的所有步骤
    "get_set_steps": """
        MATCH (s:Set {{node_id: $set_id}})-[:CONTAINS]->(p:Part)<-[:USES]-(step:Step)
        RETURN step ORDER BY step.step_number
    """,

    # 查询步骤使用的零件
    "get_step_parts": """
        MATCH (step:Step {{node_id: $step_id}})-[:USES]->(part:Part)
        RETURN part, step
    """,

    # 查询零件的图片
    "get_part_images": """
        MATCH (p {{node_id: $part_id}})-[:HAS_IMAGE|DEPICTS]-(img:Image)
        RETURN img
    """,
}
