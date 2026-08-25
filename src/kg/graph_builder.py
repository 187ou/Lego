"""图谱构建器

从多种数据源构建多模态知识图谱：
1. 说明书文档（文本）
2. 零件图片（视觉）
3. Rebrickable CSV 数据
4. 手动输入

处理流程：
1. 解析文档 → 提取实体（零件/步骤/颜色）
2. 编码图片 → 生成视觉向量
3. 建立关系（包含/使用/替代）
4. 跨模态对齐（文本↔图片）
"""

import os
import re
from typing import Optional

from src.kg.schema import (
    NodeType,
    RelationType,
    GraphNode,
    GraphRelation,
)
from src.kg.graph_store import GraphStore, get_graph_store


class GraphBuilder:
    """图谱构建器"""

    def __init__(self, store: Optional[GraphStore] = None):
        self.store = store or get_graph_store()

    def build_from_manual(
        self,
        pages: list,
        set_id: str,
    ) -> dict:
        """
        从说明书页面构建图谱。

        Args:
            pages: MultimodalPage 列表 或 Document 列表（自动适配）
            set_id: 套装编号

        Returns:
            构建统计
        """
        stats = {"nodes": 0, "relations": 0}

        # 1. 创建套装节点
        set_node = GraphNode(
            node_type=NodeType.SET,
            node_id=f"set_{set_id}",
            name=f"Set {set_id}",
            properties={"set_id": set_id},
        )
        self.store.create_node(set_node)
        stats["nodes"] += 1

        # 2. 解析每个页面
        for page in pages:
            page_stats = self._process_page(page, set_id)
            stats["nodes"] += page_stats["nodes"]
            stats["relations"] += page_stats["relations"]

        return stats

    def _process_page(self, page, set_id: str) -> dict:
        """
        处理单个页面。
        支持 MultimodalPage 和 LangChain Document 两种格式。
        """
        stats = {"nodes": 0, "relations": 0}

        # 兼容 MultimodalPage 和 Document
        if hasattr(page, "page_number"):
            step_number = page.page_number
            text_content = page.text_content or ""
        else:
            # LangChain Document
            step_number = page.metadata.get("step_number", 0)
            text_content = page.page_content or ""

        if not step_number:
            return stats

        # 创建步骤节点
        step_node = GraphNode(
            node_type=NodeType.STEP,
            node_id=f"set_{set_id}_step_{step_number}",
            name=f"步骤 {step_number}",
            properties={
                "step_number": step_number,
                "set_id": set_id,
            },
            text_description=text_content,
        )
        self.store.create_node(step_node)
        stats["nodes"] += 1

        # 创建步骤顺序关系
        if step_number > 1:
            prev_step_id = f"set_{set_id}_step_{step_number - 1}"
            relation = GraphRelation(
                relation_type=RelationType.FOLLOWS,
                source_id=prev_step_id,
                target_id=step_node.node_id,
            )
            self.store.create_relation(relation)
            stats["relations"] += 1

        # 提取零件实体
        parts = self._extract_parts(text_content)

        for part in parts:
            # 创建零件节点
            part_node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{part['part_id']}",
                name=part["name"],
                properties={
                    "part_id": part["part_id"],
                    "category": part.get("category", ""),
                },
            )
            self.store.create_node(part_node)
            stats["nodes"] += 1

            # 创建 USES 关系
            uses_relation = GraphRelation(
                relation_type=RelationType.USES,
                source_id=step_node.node_id,
                target_id=part_node.node_id,
                properties={"quantity": part.get("quantity", 1)},
            )
            self.store.create_relation(uses_relation)
            stats["relations"] += 1

            # 创建 CONTAINS 关系（套装包含零件）
            contains_relation = GraphRelation(
                relation_type=RelationType.CONTAINS,
                source_id=f"set_{set_id}",
                target_id=part_node.node_id,
            )
            self.store.create_relation(contains_relation)
            stats["relations"] += 1

            # 创建颜色节点和关系
            if part.get("color"):
                color_node = GraphNode(
                    node_type=NodeType.COLOR,
                    node_id=f"color_{part['color']}",
                    name=part["color"],
                )
                self.store.create_node(color_node)
                stats["nodes"] += 1

                color_relation = GraphRelation(
                    relation_type=RelationType.HAS_COLOR,
                    source_id=part_node.node_id,
                    target_id=color_node.node_id,
                )
                self.store.create_relation(color_relation)
                stats["relations"] += 1

        # 如果有图片，创建图片节点和跨模态关系
        full_image = getattr(page, "full_image", None)
        if full_image:
            image_node = GraphNode(
                node_type=NodeType.IMAGE,
                node_id=f"set_{set_id}_page_{step_number}_img",
                name=f"步骤 {step_number} 图片",
                image_url=f"page_{step_number}",
            )
            self.store.create_node(image_node)
            stats["nodes"] += 1

            # 步骤 → 图片
            img_relation = GraphRelation(
                relation_type=RelationType.HAS_IMAGE,
                source_id=step_node.node_id,
                target_id=image_node.node_id,
            )
            self.store.create_relation(img_relation)
            stats["relations"] += 1

        return stats

    def _extract_parts(self, text: str) -> list[dict]:
        """
        从文本中提取零件信息（改进版）。

        支持更多格式：
        - 零件编号：3001, 3005 等 4-5 位数字
        - 颜色：红色、蓝色、深红等
        - 数量：2块、3个、x2 等
        - 尺寸：2x4、1x2 等
        """
        parts = []

        # 1. 匹配零件编号（4-5 位数字）
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", text)

        for part_id in set(part_ids):
            # 提取零件名称
            name = self._lookup_part_name(part_id)

            # 提取颜色（在零件号附近查找）
            color = self._extract_color_near_part(text, part_id)

            # 提取数量
            quantity = self._extract_quantity_near_part(text, part_id)

            parts.append({
                "part_id": part_id,
                "name": name,
                "color": color,
                "quantity": quantity,
            })

        return parts

    def _extract_color_near_part(self, text: str, part_id: str) -> str:
        """在零件号附近提取颜色"""
        # 在零件号前后 20 个字符内查找颜色
        idx = text.find(part_id)
        if idx == -1:
            return ""

        # 取零件号前后的文本片段
        start = max(0, idx - 20)
        end = min(len(text), idx + len(part_id) + 20)
        nearby_text = text[start:end]

        # 优先匹配复合颜色
        compound_colors = ["深红", "浅红", "深蓝", "浅蓝", "透明", "深绿", "浅绿"]
        for color in compound_colors:
            if color in nearby_text:
                return color

        # 匹配基本颜色
        basic_colors = ["红", "蓝", "黄", "绿", "白", "黑", "灰", "橙", "棕", "紫", "粉"]
        for color in basic_colors:
            if color in nearby_text:
                return color

        return ""

    def _extract_quantity_near_part(self, text: str, part_id: str) -> int:
        """在零件号附近提取数量"""
        idx = text.find(part_id)
        if idx == -1:
            return 1

        # 取零件号前后的文本片段
        start = max(0, idx - 15)
        end = min(len(text), idx + len(part_id) + 15)
        nearby_text = text[start:end]

        # 匹配数量：2块、3个、x2、*3 等
        qty_match = re.search(r'(\d+)\s*(块|个|件|颗)', nearby_text)
        if qty_match:
            return int(qty_match.group(1))

        qty_match = re.search(r'[xX*]\s*(\d+)', nearby_text)
        if qty_match:
            return int(qty_match.group(1))

        return 1

    def _lookup_part_name(self, part_id: str) -> str:
        """
        查找零件名称（扩展版）。

        支持更多零件类型，包括 Brick/Plate/Slope/Tile 等。
        """
        # 常见零件名称映射（扩展版）
        common_names = {
            # Brick 系列
            "3001": "Brick 2x4",
            "3002": "Brick 2x3",
            "3003": "Brick 2x2",
            "3004": "Brick 1x2",
            "3005": "Brick 1x1",
            "3008": "Brick 1x8",
            "3009": "Brick 1x6",
            "3010": "Brick 1x4",
            "3622": "Brick 1x3",
            # Plate 系列
            "3020": "Plate 2x4",
            "3021": "Plate 2x3",
            "3022": "Plate 2x2",
            "3023": "Plate 1x2",
            "3024": "Plate 1x1",
            "3031": "Plate 4x4",
            "3034": "Plate 2x8",
            # Tile 系列
            "3069": "Tile 1x2",
            "3070": "Tile 1x1",
            "3068": "Tile 2x2",
            # Slope 系列
            "3039": "Slope 45° 2x2",
            "3040": "Slope 45° 2x1",
            "3048": "Slope 45° 2x1 Double",
            # Technic 系列
            "3700": "Technic Brick 1x2",
            "3701": "Technic Brick 1x4",
            "3713": "Technic Bush",
            "4019": "Technic Pin",
            # 其他
            "3006": "Brick 2x10",
            "3007": "Brick 2x8",
            "3460": "Plate 1x8",
            "3795": "Plate 2x6",
            "3036": "Plate 6x8",
            "3035": "Plate 4x6",
            "3032": "Plate 4x4",
            "3030": "Plate 4x10",
            "3832": "Plate 2x10",
            "3659": "Brick 1x1 with Stud",
            "30414": "Brick 1x4 with 4 Studs",
        }
        return common_names.get(part_id, f"Part {part_id}")

    def _extract_color(self, text: str, part_id: str) -> str:
        """提取零件颜色"""
        colors = ["红", "蓝", "黄", "绿", "白", "黑", "灰", "橙", "棕", "紫", "粉"]
        for color in colors:
            if color in text:
                return color
        return ""

    def add_part_alternative(
        self,
        part_id_a: str,
        part_id_b: str,
        confidence: float = 1.0,
    ):
        """添加零件替代关系"""
        relation = GraphRelation(
            relation_type=RelationType.CAN_REPLACE,
            source_id=f"part_{part_id_a}",
            target_id=f"part_{part_id_b}",
            confidence=confidence,
        )
        self.store.create_relation(relation)

    def add_part_image(
        self,
        part_id: str,
        image_url: str,
        description: str = "",
    ):
        """添加零件图片（跨模态）"""
        # 创建图片节点
        image_node = GraphNode(
            node_type=NodeType.IMAGE,
            node_id=f"part_{part_id}_img",
            name=f"Part {part_id} Image",
            image_url=image_url,
            text_description=description,
        )
        self.store.create_node(image_node)

        # 创建跨模态关系
        relation = GraphRelation(
            relation_type=RelationType.CROSS_MODAL,
            source_id=f"part_{part_id}",
            target_id=image_node.node_id,
        )
        self.store.create_relation(relation)

    def import_from_rebrickable_csv(self, csv_path: str, set_id: str) -> int:
        """
        从 Rebrickable CSV 导入零件数据。

        CSV 格式：Part, Color, Category, Name, Quantity
        """
        import csv

        imported = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                part_id = row.get("Part", "")
                color = row.get("Color", "")
                category = row.get("Category", "")
                name = row.get("Name", "")
                quantity = int(row.get("Quantity", 1))

                if not part_id:
                    continue

                # 创建零件节点
                part_node = GraphNode(
                    node_type=NodeType.PART,
                    node_id=f"part_{part_id}",
                    name=name or self._lookup_part_name(part_id),
                    properties={
                        "part_id": part_id,
                        "category": category,
                    },
                )
                self.store.create_node(part_node)

                # 创建颜色节点
                if color:
                    color_node = GraphNode(
                        node_type=NodeType.COLOR,
                        node_id=f"color_{color}",
                        name=color,
                    )
                    self.store.create_node(color_node)

                    # HAS_COLOR 关系
                    relation = GraphRelation(
                        relation_type=RelationType.HAS_COLOR,
                        source_id=f"part_{part_id}",
                        target_id=f"color_{color}",
                    )
                    self.store.create_relation(relation)

                # 创建类别节点
                if category:
                    cat_node = GraphNode(
                        node_type=NodeType.CATEGORY,
                        node_id=f"category_{category}",
                        name=category,
                    )
                    self.store.create_node(cat_node)

                    # BELONGS_TO 关系
                    relation = GraphRelation(
                        relation_type=RelationType.BELONGS_TO,
                        source_id=f"part_{part_id}",
                        target_id=f"category_{category}",
                    )
                    self.store.create_relation(relation)

                # CONTAINS 关系
                contains = GraphRelation(
                    relation_type=RelationType.CONTAINS,
                    source_id=f"set_{set_id}",
                    target_id=f"part_{part_id}",
                    properties={"quantity": quantity},
                )
                self.store.create_relation(contains)

                imported += 1

        return imported


def build_from_manual(pages: list, set_id: str) -> dict:
    """
    便捷函数：从说明书构建图谱。

    Args:
        pages: MultimodalPage 列表
        set_id: 套装编号

    Returns:
        构建统计
    """
    builder = GraphBuilder()
    return builder.build_from_manual(pages, set_id)


# =========================================================================
# 从 Mock 说明书数据构建图谱
# =========================================================================

def build_from_mock_manual(set_id: str = "10295") -> dict:
    """
    从 Mock 说明书数据构建图谱。

    处理流程：
    1. 调用 create_mock_manual() 获取步骤文档
    2. 创建 Set 节点
    3. 遍历每个步骤 → 创建 Step 节点 + FOLLOWS 关系
    4. 正则提取零件 → 创建 Part 节点 + USES 关系 + CONTAINS 关系
    5. 提取颜色 → 创建 Color 节点 + HAS_COLOR 关系
    6. 建立零件替代关系（基于尺寸相似度自动计算）
    """
    from src.rag.pdf_loader import create_mock_manual

    builder = GraphBuilder()
    documents = create_mock_manual(set_id=set_id)

    stats = {"nodes": 0, "relations": 0}

    # 1. 创建套装节点
    set_node = GraphNode(
        node_type=NodeType.SET,
        node_id=f"set_{set_id}",
        name=f"Set {set_id}",
        properties={"set_id": set_id},
    )
    builder.store.create_node(set_node)
    stats["nodes"] += 1

    # 2. 遍历每个步骤文档
    prev_step_id = None
    all_parts = set()

    for doc in documents:
        step_number = doc.metadata.get("step_number", 0)
        if not step_number:
            continue

        # 创建步骤节点
        step_node = GraphNode(
            node_type=NodeType.STEP,
            node_id=f"set_{set_id}_step_{step_number}",
            name=f"步骤 {step_number}",
            properties={
                "step_number": step_number,
                "set_id": set_id,
            },
            text_description=doc.page_content,
        )
        builder.store.create_node(step_node)
        stats["nodes"] += 1

        # 创建步骤顺序关系
        if prev_step_id:
            rel = GraphRelation(
                relation_type=RelationType.FOLLOWS,
                source_id=prev_step_id,
                target_id=step_node.node_id,
            )
            builder.store.create_relation(rel)
            stats["relations"] += 1
        prev_step_id = step_node.node_id

        # 提取零件
        parts = builder._extract_parts(doc.page_content)
        for part in parts:
            part_key = f"{part['part_id']}_{part.get('color', '')}"
            if part_key not in all_parts:
                all_parts.add(part_key)

                # 解析尺寸
                import re
                size_match = re.search(r"(\d+)\s*[x×]\s*(\d+)", part["name"])
                size_props = {}
                if size_match:
                    size_props["width"] = int(size_match.group(1))
                    size_props["length"] = int(size_match.group(2))

                # 创建零件节点
                part_node = GraphNode(
                    node_type=NodeType.PART,
                    node_id=f"part_{part['part_id']}",
                    name=part["name"],
                    properties={
                        "part_id": part["part_id"],
                        "category": part.get("category", ""),
                        **size_props,
                    },
                )
                builder.store.create_node(part_node)
                stats["nodes"] += 1

                # 创建颜色节点和关系
                if part.get("color"):
                    color_node = GraphNode(
                        node_type=NodeType.COLOR,
                        node_id=f"color_{part['color']}",
                        name=part["color"],
                    )
                    builder.store.create_node(color_node)
                    stats["nodes"] += 1

                    color_rel = GraphRelation(
                        relation_type=RelationType.HAS_COLOR,
                        source_id=part_node.node_id,
                        target_id=color_node.node_id,
                    )
                    builder.store.create_relation(color_rel)
                    stats["relations"] += 1

            # 创建 USES 关系
            uses_rel = GraphRelation(
                relation_type=RelationType.USES,
                source_id=step_node.node_id,
                target_id=f"part_{part['part_id']}",
                properties={"quantity": part.get("quantity", 1)},
            )
            builder.store.create_relation(uses_rel)
            stats["relations"] += 1

            # 创建 CONTAINS 关系
            contains_rel = GraphRelation(
                relation_type=RelationType.CONTAINS,
                source_id=f"set_{set_id}",
                target_id=f"part_{part['part_id']}",
            )
            builder.store.create_relation(contains_rel)
            stats["relations"] += 1

    # 3. 建立零件替代关系（基于尺寸相似度自动计算）
    _auto_build_alternatives(builder, stats)

    # 4. 为零件生成合成图片（跨模态数据）
    _generate_part_images(builder, set_id)

    print(f"[OK] 从 Mock 说明书构建图谱完成: {stats['nodes']} 节点, {stats['relations']} 关系")
    return stats


def _auto_build_alternatives(builder: GraphBuilder, stats: dict):
    """
    自动计算零件替代关系。

    基于图谱中已有的 Part 节点和 _lookup_part_name 推断类型与尺寸。
    不使用硬编码零件表，只处理图谱中实际存在的零件。

    规则（基于 LEGO 几何兼容性）：
    - 同类型 + 同尺寸 → confidence=0.95（完全可替代）
    - 同类型 + 尺寸差一级 → confidence=0.6（可能替代，但长度不同）
    - 不同类型 → 不建立替代关系（高度不同，无法直接替代）
    """
    # 从图谱中获取所有 Part 节点的 part_id
    store = builder.store
    graph_stats = store.get_stats()
    if not graph_stats.get("available"):
        return

    # 收集图谱中的零件 ID（通过 part_ 前缀的 node_id）
    part_ids = _get_part_ids_from_store(store)
    if len(part_ids) < 2:
        return

    # 零件类型查找表（用于分类）
    type_prefixes = {
        "Brick": ["3001", "3002", "3003", "3004", "3005", "3008", "3009", "3010", "3622",
                    "3006", "3007"],
        "Plate": ["3020", "3021", "3022", "3023", "3024", "3031", "3034", "3795", "3032"],
        "Tile": ["3069", "3070", "3068"],
        "Slope": ["3039", "3040", "3048", "30414"],
    }

    def _get_type(part_id: str) -> str:
        for type_name, prefixes in type_prefixes.items():
            if part_id in prefixes:
                return type_name
        return "Other"

    def _get_size(part_id: str) -> tuple[int, int] | None:
        """从零件名称推断尺寸（如 'Brick 2x4' → (2, 4)）"""
        import re
        name = builder._lookup_part_name(part_id)
        match = re.search(r"(\d+)\s*[x×]\s*(\d+)", name)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    for i, part_id_a in enumerate(part_ids):
        type_a = _get_type(part_id_a)
        size_a = _get_size(part_id_a)
        if size_a is None:
            continue

        for part_id_b in part_ids[i + 1:]:
            type_b = _get_type(part_id_b)
            size_b = _get_size(part_id_b)
            if size_b is None:
                continue

            # 不同类型不建立替代关系（高度不同，无法直接替代）
            if type_a != type_b:
                continue

            if size_a == size_b:
                confidence = 0.95
            elif (abs(size_a[0] - size_b[0]) <= 1 and abs(size_a[1] - size_b[1]) <= 1
                  and (size_a[0] == size_b[0] or size_a[1] == size_b[1])):
                # 只有一维相同（如 2x4 和 2x3），另一维差1
                confidence = 0.6
            else:
                continue

            rel = GraphRelation(
                relation_type=RelationType.CAN_REPLACE,
                source_id=f"part_{part_id_a}",
                target_id=f"part_{part_id_b}",
                confidence=confidence,
            )
            store.create_relation(rel)
            stats["relations"] += 1


def _get_part_ids_from_store(store) -> list[str]:
    """从图谱存储中提取所有 Part 节点的 part_id"""
    part_ids = []

    # MockGraphStore: 从内存读取
    if hasattr(store, "_nodes"):
        for node_id, node in store._nodes.items():
            if node.node_type == NodeType.PART:
                pid = node.properties.get("part_id", node_id.replace("part_", ""))
                part_ids.append(pid)
        return part_ids

    # Neo4jGraphStore: 通过 Cypher 查询
    stats = store.get_stats()
    if stats.get("available") and hasattr(store, "_run_query"):
        try:
            rows = store._run_query(
                "MATCH (n:Part) RETURN n.part_id as part_id, n.node_id as node_id"
            )
            for r in rows:
                pid = r.get("part_id") or r.get("node_id", "").replace("part_", "")
                if pid:
                    part_ids.append(pid)
        except Exception:
            pass

    return part_ids


def init_default_graph() -> dict:
    """
    初始化默认图谱数据。

    从 Mock 说明书 + 常见零件数据库构建完整图谱。
    在服务启动时调用一次。
    幂等：如果图谱已有数据则跳过。

    Returns:
        构建统计
    """
    print("[INFO] 初始化默认知识图谱...")

    # 检查是否已有数据（幂等）
    try:
        from src.kg.graph_store import get_graph_store
        store = get_graph_store()
        existing_stats = store.get_stats()
        if existing_stats.get("total_nodes", 0) > 0:
            print(f"[INFO] 图谱已有 {existing_stats['total_nodes']} 个节点，跳过初始化")
            return existing_stats
    except Exception:
        pass

    # 1. 从 Mock 说明书构建
    stats = build_from_mock_manual(set_id="10295")

    # 2. 导入常见零件
    try:
        from src.vision.part_recognizer import get_part_recognizer
        recognizer = get_part_recognizer()
        builder = GraphBuilder()

        common_parts = [
            {"part_id": "3001", "name": "Brick 2x4", "category": "Brick"},
            {"part_id": "3002", "name": "Brick 2x3", "category": "Brick"},
            {"part_id": "3003", "name": "Brick 2x2", "category": "Brick"},
            {"part_id": "3005", "name": "Brick 1x1", "category": "Brick"},
            {"part_id": "3010", "name": "Brick 1x4", "category": "Brick"},
            {"part_id": "3020", "name": "Plate 2x4", "category": "Plate"},
            {"part_id": "3023", "name": "Plate 1x2", "category": "Plate"},
            {"part_id": "3622", "name": "Brick 1x3", "category": "Brick"},
            {"part_id": "3069", "name": "Tile 1x2", "category": "Tile"},
            {"part_id": "3070", "name": "Tile 1x1", "category": "Tile"},
            {"part_id": "3040", "name": "Slope 45° 2x1", "category": "Slope"},
            {"part_id": "3039", "name": "Slope 45° 2x2", "category": "Slope"},
        ]

        for part in common_parts:
            part_node = GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{part['part_id']}",
                name=part["name"],
                properties={
                    "part_id": part["part_id"],
                    "category": part["category"],
                },
            )
            builder.store.create_node(part_node)
            stats["nodes"] += 1

        # 重新计算替代关系
        _auto_build_alternatives(builder, stats)

    except Exception as e:
        print(f"[WARN] 导入常见零件失败: {e}")

    # 5. 为常见零件生成合成图片
    try:
        _generate_part_images(builder, set_id="common")
    except Exception as e:
        print(f"[WARN] 生成零件图片失败: {e}")

    print(f"[OK] 默认知识图谱初始化完成: {stats['nodes']} 节点, {stats['relations']} 关系")
    return stats


def _generate_part_images(builder: GraphBuilder, set_id: str):
    """
    为图谱中的零件生成合成图片，建立跨模态关联。

    对每个 Part 节点：
    1. 生成合成图片（Pillow 绘制）
    2. 创建 Image 节点
    3. 建立 CROSS_MODAL 关系
    """
    try:
        from src.kg.image_generator import generate_part_image, parse_size_from_name
    except ImportError:
        return

    part_ids = _get_part_ids_from_store(builder.store)
    if not part_ids:
        return

    image_dir = os.path.join(os.getcwd(), "data", "images", set_id)
    os.makedirs(image_dir, exist_ok=True)

    for part_id in part_ids:
        node_id = f"part_{part_id}"
        node = builder.store.get_node(node_id)
        if not node:
            continue

        # 解析尺寸
        size = parse_size_from_name(node.name)
        if not size:
            size = (2, 4)  # 默认尺寸

        # 获取颜色
        neighbors = builder.store.get_neighbors(node_id, limit=5)
        color = "Red"
        for n in neighbors:
            if n.get("relation") == RelationType.HAS_COLOR.value:
                color = n.get("name", "Red")
                break

        # 生成图片
        try:
            img_bytes = generate_part_image(
                part_name=node.name,
                width=size[0],
                length=size[1],
                color=color,
            )

            # 保存图片
            img_filename = f"{part_id}_{color.lower()}.png"
            img_path = os.path.join(image_dir, img_filename)
            with open(img_path, "wb") as f:
                f.write(img_bytes)

            # 创建 Image 节点
            image_node = GraphNode(
                node_type=NodeType.IMAGE,
                node_id=f"{node_id}_img",
                name=f"{node.name} ({color})",
                image_url=img_path,
            )
            builder.store.create_node(image_node)

            # 建立 CROSS_MODAL 关系
            cm_rel = GraphRelation(
                relation_type=RelationType.CROSS_MODAL,
                source_id=node_id,
                target_id=image_node.node_id,
                confidence=0.9,
            )
            builder.store.create_relation(cm_rel)

        except Exception as e:
            print(f"[WARN] 生成零件 {part_id} 图片失败: {e}")
