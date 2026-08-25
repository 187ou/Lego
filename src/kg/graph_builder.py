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
            pages: MultimodalPage 列表
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
        """处理单个页面"""
        stats = {"nodes": 0, "relations": 0}

        # 提取步骤号
        step_number = page.page_number

        # 创建步骤节点
        step_node = GraphNode(
            node_type=NodeType.STEP,
            node_id=f"set_{set_id}_step_{step_number}",
            name=f"步骤 {step_number}",
            properties={
                "step_number": step_number,
                "set_id": set_id,
            },
            text_description=page.text_content,
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
        parts = self._extract_parts(page.text_content)

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
        if page.full_image:
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
