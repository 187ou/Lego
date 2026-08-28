"""知识图谱 Schema 定义（增强版）

定义多模态知识图谱的节点类型、关系类型和属性。

新增：
- 物理/几何属性（studs、connection_type、height、material）
- 层次结构（SubAssembly 子装配）
- 冲突关系（INCOMPATIBLE_WITH 不兼容）
- 依赖关系（DEPENDS_ON 依赖）
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class NodeType(str, Enum):
    """节点类型"""
    SET = "Set"                 # 套装
    SUB_ASSEMBLY = "SubAssembly"  # 子装配（新增）
    PART = "Part"               # 零件
    STEP = "Step"               # 步骤
    COLOR = "Color"             # 颜色
    CATEGORY = "Category"       # 类别
    IMAGE = "Image"             # 图片


class RelationType(str, Enum):
    """关系类型"""
    # 结构关系
    CONTAINS = "CONTAINS"           # 套装 → 零件/子装配（包含）
    HAS_PART = "HAS_PART"           # 子装配 → 零件（组成）
    USES = "USES"                   # 步骤 → 零件（使用）
    FOLLOWS = "FOLLOWS"             # 步骤 → 步骤（顺序）

    # 零件关系
    CAN_REPLACE = "CAN_REPLACE"     # 零件 → 零件（替代）
    COMPATIBLE_WITH = "COMPATIBLE_WITH"  # 零件 → 零件（兼容）
    INCOMPATIBLE_WITH = "INCOMPATIBLE_WITH"  # 零件 → 零件（不兼容，新增）
    DEPENDS_ON = "DEPENDS_ON"       # 零件 → 零件（依赖，新增）

    # 属性关系
    HAS_COLOR = "HAS_COLOR"         # 零件 → 颜色
    BELONGS_TO = "BELONGS_TO"       # 零件 → 类别

    # 多模态关系
    HAS_IMAGE = "HAS_IMAGE"         # 步骤/零件 → 图片
    DEPICTS = "DEPICTS"             # 图片 → 零件（描绘）
    CROSS_MODAL = "CROSS_MODAL"     # 文本 ↔ 图片（跨模态关联）


@dataclass
class PartGeometry:
    """零件几何属性"""
    width: int = 0          # 宽度（studs）
    length: int = 0         # 长度（studs）
    height: float = 9.6     # 高度（mm，标准 Brick 高度）
    studs: int = 0          # 凸点数量
    pinholes: int = 0       # 孔洞数量
    connection_type: str = "stud"  # 连接类型：stud/pin/clip/axle


@dataclass
class PartPhysics:
    """零件物理属性"""
    material: str = "ABS"   # 材质
    weight: float = 0.0     # 重量（g）
    strength: float = 0.8   # 结构强度 0-1


@dataclass
class PartCommercial:
    """零件商业属性"""
    rarity: str = "common"  # 稀缺度：common/uncommon/rare/very_rare
    price: float = 0.0      # 单价（美元）
    discontinued: bool = False  # 是否停产
    year_introduced: int = 0    # 上市年份


@dataclass
class GraphNode:
    """图谱节点（增强版）"""
    node_type: NodeType
    node_id: str                    # 唯一标识
    name: str                       # 显示名称
    properties: dict = field(default_factory=dict)  # 额外属性

    # 多模态属性
    text_description: str = ""      # 文本描述
    image_url: str = ""             # 图片 URL/路径
    embedding: Optional[list[float]] = None  # 向量表示

    # 零件专用属性（仅 PART 类型使用）
    geometry: Optional[PartGeometry] = None     # 几何属性
    physics: Optional[PartPhysics] = None       # 物理属性
    commercial: Optional[PartCommercial] = None # 商业属性


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
    NodeType.SUB_ASSEMBLY: ["assembly_id", "name", "set_id"],
    NodeType.PART: ["part_id", "name"],
    NodeType.STEP: ["step_number", "set_id"],
    NodeType.COLOR: ["name"],
    NodeType.CATEGORY: ["name"],
    NodeType.IMAGE: ["image_url"],
}

# 每种关系类型的源/目标节点约束
RELATION_CONSTRAINTS = {
    RelationType.CONTAINS: (NodeType.SET, NodeType.PART),  # 也支持 SUB_ASSEMBLY
    RelationType.HAS_PART: (NodeType.SUB_ASSEMBLY, NodeType.PART),
    RelationType.USES: (NodeType.STEP, NodeType.PART),
    RelationType.FOLLOWS: (NodeType.STEP, NodeType.STEP),
    RelationType.CAN_REPLACE: (NodeType.PART, NodeType.PART),
    RelationType.COMPATIBLE_WITH: (NodeType.PART, NodeType.PART),
    RelationType.INCOMPATIBLE_WITH: (NodeType.PART, NodeType.PART),
    RelationType.DEPENDS_ON: (NodeType.PART, NodeType.PART),
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

    # 查询子装配结构（新增）
    "get_sub_assemblies": """
        MATCH (s:Set {{node_id: $set_id}})-[:CONSAINS]->(sa:SubAssembly)
        RETURN sa
    """,

    # 查询子装配的零件（新增）
    "get_assembly_parts": """
        MATCH (sa:SubAssembly {{node_id: $assembly_id}})-[:HAS_PART]->(p:Part)
        RETURN p
    """,

    # 查询不兼容零件（新增）
    "get_incompatible_parts": """
        MATCH (p {{node_id: $part_id}})-[:INCOMPATIBLE_WITH]-(incompat)
        RETURN incompat.node_id as part_id, incompat.name as name
    """,

    # 查询依赖零件（新增）
    "get_dependent_parts": """
        MATCH (p {{node_id: $part_id}})-[:DEPENDS_ON]-(dep)
        RETURN dep.node_id as part_id, dep.name as name
    """,
}


# ===== 零件知识库（增强版） =====

# 完整零件信息（几何+物理+商业）
PART_KNOWLEDGE_BASE = {
    # Brick 系列
    "3001": {
        "name": "Brick 2x4",
        "category": "Brick",
        "geometry": PartGeometry(width=2, length=4, height=9.6, studs=8, connection_type="stud"),
        "physics": PartPhysics(weight=2.3, strength=0.9),
        "commercial": PartCommercial(rarity="common", price=0.05, year_introduced=1958),
    },
    "3002": {
        "name": "Brick 2x3",
        "category": "Brick",
        "geometry": PartGeometry(width=2, length=3, height=9.6, studs=6, connection_type="stud"),
        "physics": PartPhysics(weight=1.8, strength=0.85),
        "commercial": PartCommercial(rarity="common", price=0.04, year_introduced=1958),
    },
    "3003": {
        "name": "Brick 2x2",
        "category": "Brick",
        "geometry": PartGeometry(width=2, length=2, height=9.6, studs=4, connection_type="stud"),
        "physics": PartPhysics(weight=1.2, strength=0.8),
        "commercial": PartCommercial(rarity="common", price=0.03, year_introduced=1958),
    },
    "3004": {
        "name": "Brick 1x2",
        "category": "Brick",
        "geometry": PartGeometry(width=1, length=2, height=9.6, studs=2, connection_type="stud"),
        "physics": PartPhysics(weight=0.6, strength=0.7),
        "commercial": PartCommercial(rarity="common", price=0.02, year_introduced=1958),
    },
    "3005": {
        "name": "Brick 1x1",
        "category": "Brick",
        "geometry": PartGeometry(width=1, length=1, height=9.6, studs=1, connection_type="stud"),
        "physics": PartPhysics(weight=0.3, strength=0.6),
        "commercial": PartCommercial(rarity="common", price=0.01, year_introduced=1958),
    },
    "3010": {
        "name": "Brick 1x4",
        "category": "Brick",
        "geometry": PartGeometry(width=1, length=4, height=9.6, studs=4, connection_type="stud"),
        "physics": PartPhysics(weight=1.2, strength=0.75),
        "commercial": PartCommercial(rarity="common", price=0.04, year_introduced=1958),
    },
    "3622": {
        "name": "Brick 1x3",
        "category": "Brick",
        "geometry": PartGeometry(width=1, length=3, height=9.6, studs=3, connection_type="stud"),
        "physics": PartPhysics(weight=0.9, strength=0.72),
        "commercial": PartCommercial(rarity="common", price=0.03, year_introduced=1960),
    },
    # Plate 系列
    "3020": {
        "name": "Plate 2x4",
        "category": "Plate",
        "geometry": PartGeometry(width=2, length=4, height=3.2, studs=8, connection_type="stud"),
        "physics": PartPhysics(weight=1.1, strength=0.7),
        "commercial": PartCommercial(rarity="common", price=0.04, year_introduced=1958),
    },
    "3021": {
        "name": "Plate 2x3",
        "category": "Plate",
        "geometry": PartGeometry(width=2, length=3, height=3.2, studs=6, connection_type="stud"),
        "physics": PartPhysics(weight=0.9, strength=0.65),
        "commercial": PartCommercial(rarity="common", price=0.03, year_introduced=1958),
    },
    "3022": {
        "name": "Plate 2x2",
        "category": "Plate",
        "geometry": PartGeometry(width=2, length=2, height=3.2, studs=4, connection_type="stud"),
        "physics": PartPhysics(weight=0.6, strength=0.6),
        "commercial": PartCommercial(rarity="common", price=0.02, year_introduced=1958),
    },
    "3023": {
        "name": "Plate 1x2",
        "category": "Plate",
        "geometry": PartGeometry(width=1, length=2, height=3.2, studs=2, connection_type="stud"),
        "physics": PartPhysics(weight=0.3, strength=0.5),
        "commercial": PartCommercial(rarity="common", price=0.01, year_introduced=1958),
    },
    "3024": {
        "name": "Plate 1x1",
        "category": "Plate",
        "geometry": PartGeometry(width=1, length=1, height=3.2, studs=1, connection_type="stud"),
        "physics": PartPhysics(weight=0.15, strength=0.4),
        "commercial": PartCommercial(rarity="common", price=0.01, year_introduced=1958),
    },
    # Tile 系列
    "3069": {
        "name": "Tile 1x2",
        "category": "Tile",
        "geometry": PartGeometry(width=1, length=2, height=3.2, studs=0, connection_type="stud"),
        "physics": PartPhysics(weight=0.25, strength=0.45),
        "commercial": PartCommercial(rarity="common", price=0.02, year_introduced=1977),
    },
    "3070": {
        "name": "Tile 1x1",
        "category": "Tile",
        "geometry": PartGeometry(width=1, length=1, height=3.2, studs=0, connection_type="stud"),
        "physics": PartPhysics(weight=0.12, strength=0.35),
        "commercial": PartCommercial(rarity="common", price=0.01, year_introduced=1977),
    },
    # Slope 系列
    "3039": {
        "name": "Slope 45° 2x2",
        "category": "Slope",
        "geometry": PartGeometry(width=2, length=2, height=9.6, studs=2, connection_type="stud"),
        "physics": PartPhysics(weight=1.0, strength=0.7),
        "commercial": PartCommercial(rarity="common", price=0.05, year_introduced=1958),
    },
    "3040": {
        "name": "Slope 45° 2x1",
        "category": "Slope",
        "geometry": PartGeometry(width=1, length=2, height=9.6, studs=1, connection_type="stud"),
        "physics": PartPhysics(weight=0.5, strength=0.6),
        "commercial": PartCommercial(rarity="common", price=0.03, year_introduced=1958),
    },
}


def get_part_knowledge(part_id: str) -> Optional[dict]:
    """获取零件知识"""
    return PART_KNOWLEDGE_BASE.get(part_id)


def calc_part_compatibility(part_a_id: str, part_b_id: str) -> float:
    """计算两个零件的兼容性得分（多维度）

    维度：
    - 尺寸相似度 (30%)
    - 凸点兼容性 (25%)
    - 连接类型兼容性 (20%)
    - 类别匹配 (15%)
    - 高度兼容性 (10%)

    Returns:
        0.0 - 1.0 的兼容性得分
    """
    part_a = PART_KNOWLEDGE_BASE.get(part_a_id)
    part_b = PART_KNOWLEDGE_BASE.get(part_b_id)

    if not part_a or not part_b:
        return 0.0

    geo_a = part_a["geometry"]
    geo_b = part_b["geometry"]

    # 1. 尺寸相似度 (30%)
    size_score = _calc_size_similarity(geo_a, geo_b)

    # 2. 凸点兼容性 (25%)
    stud_score = _calc_stud_compatibility(geo_a, geo_b)

    # 3. 连接类型兼容性 (20%)
    conn_score = 1.0 if geo_a.connection_type == geo_b.connection_type else 0.3

    # 4. 类别匹配 (15%)
    cat_score = 1.0 if part_a["category"] == part_b["category"] else 0.2

    # 5. 高度兼容性 (10%)
    height_diff = abs(geo_a.height - geo_b.height)
    height_score = max(0, 1.0 - height_diff / 10.0)

    # 加权求和
    total = (size_score * 0.30 +
             stud_score * 0.25 +
             conn_score * 0.20 +
             cat_score * 0.15 +
             height_score * 0.10)

    return round(min(1.0, max(0.0, total)), 3)


def _calc_size_similarity(geo_a: PartGeometry, geo_b: PartGeometry) -> float:
    """计算尺寸相似度"""
    # 面积比
    area_a = geo_a.width * geo_a.length
    area_b = geo_b.width * geo_b.length
    if area_a == 0 or area_b == 0:
        return 0.0

    area_ratio = min(area_a, area_b) / max(area_a, area_b)

    # 形状相似度（长宽比）
    aspect_a = geo_a.width / max(geo_a.length, 1)
    aspect_b = geo_b.width / max(geo_b.length, 1)
    aspect_ratio = min(aspect_a, aspect_b) / max(aspect_a, aspect_b) if max(aspect_a, aspect_b) > 0 else 0

    return (area_ratio * 0.7 + aspect_ratio * 0.3)


def _calc_stud_compatibility(geo_a: PartGeometry, geo_b: PartGeometry) -> float:
    """计算凸点兼容性"""
    if geo_a.studs == 0 or geo_b.studs == 0:
        return 0.5  # Tile 类零件

    stud_diff = abs(geo_a.studs - geo_b.studs)
    max_studs = max(geo_a.studs, geo_b.studs)

    return max(0, 1.0 - stud_diff / max_studs)
