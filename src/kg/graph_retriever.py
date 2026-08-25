"""图谱检索器

基于多模态知识图谱的检索和推理。
支持：
- 单跳查询（邻居节点）
- 多跳推理（替代零件链）
- 路径查询（步骤→零件→替代）
- 跨模态检索（文本→图片）
"""

from typing import Optional

from src.kg.schema import NodeType, RelationType
from src.kg.graph_store import GraphStore, get_graph_store


class GraphRetriever:
    """图谱检索器"""

    def __init__(self, store: Optional[GraphStore] = None):
        self.store = store or get_graph_store()

    def find_part_alternatives(
        self,
        part_id: str,
        max_depth: int = 3,
        limit: int = 5,
    ) -> list[dict]:
        """
        查找零件的替代方案（多跳推理）。

        Args:
            part_id: 零件编号
            max_depth: 最大跳数
            limit: 返回数量

        Returns:
            替代零件列表
        """
        return self.store.find_alternatives(part_id, limit=limit)

    def get_step_info(self, set_id: str, step_number: int) -> dict:
        """
        获取步骤信息（包括使用的零件）。

        Args:
            set_id: 套装编号
            step_number: 步骤号

        Returns:
            步骤信息
        """
        step_id = f"set_{set_id}_step_{step_number}"
        step_node = self.store.get_node(step_id)

        if not step_node:
            return {"found": False}

        # 获取该步骤使用的零件
        neighbors = self.store.get_neighbors(step_id, limit=20)
        parts = [
            n for n in neighbors
            if n.get("relation") == RelationType.USES.value
        ]

        return {
            "found": True,
            "step": {
                "step_number": step_number,
                "description": step_node.text_description,
            },
            "parts": parts,
        }

    def get_part_info(self, part_id: str) -> dict:
        """
        获取零件信息（包括颜色、类别、图片）。

        Args:
            part_id: 零件编号

        Returns:
            零件信息
        """
        node_id = f"part_{part_id}"
        node = self.store.get_node(node_id)

        if not node:
            return {"found": False}

        # 获取邻居（颜色、类别、图片）
        neighbors = self.store.get_neighbors(node_id, limit=20)

        colors = [
            n for n in neighbors
            if n.get("relation") == RelationType.HAS_COLOR.value
        ]
        categories = [
            n for n in neighbors
            if n.get("relation") == RelationType.BELONGS_TO.value
        ]
        images = [
            n for n in neighbors
            if n.get("relation") in (RelationType.HAS_IMAGE.value, RelationType.CROSS_MODAL.value)
        ]

        return {
            "found": True,
            "part": {
                "part_id": part_id,
                "name": node.name,
                "properties": node.properties,
            },
            "colors": colors,
            "categories": categories,
            "images": images,
        }

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 4,
    ) -> list[dict]:
        """
        查找两个节点之间的路径。

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            max_depth: 最大深度

        Returns:
            路径列表
        """
        # BFS 路径查找
        visited = {source_id}
        queue = [(source_id, [])]
        paths = []

        while queue and len(paths) < 5:
            current_id, path = queue.pop(0)

            if len(path) >= max_depth:
                continue

            neighbors = self.store.get_neighbors(current_id, limit=10)

            for neighbor in neighbors:
                next_id = neighbor.get("node_id")
                if next_id == target_id:
                    paths.append(path + [neighbor])
                elif next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [neighbor]))

        return paths

    def get_set_overview(self, set_id: str) -> dict:
        """
        获取套装概览。

        Args:
            set_id: 套装编号

        Returns:
            套装概览
        """
        set_node = self.store.get_node(f"set_{set_id}")

        if not set_node:
            return {"found": False}

        # 获取所有零件
        neighbors = self.store.get_neighbors(f"set_{set_id}", limit=100)
        parts = [
            n for n in neighbors
            if n.get("relation") == RelationType.CONTAINS.value
        ]

        return {
            "found": True,
            "set": {
                "set_id": set_id,
                "name": set_node.name,
            },
            "total_parts": len(parts),
            "parts": parts[:20],  # 最多返回 20 个
        }

    def cross_modal_search(
        self,
        query: str,
        modality: str = "text",
    ) -> list[dict]:
        """
        跨模态搜索。

        Args:
            query: 查询（文本或图片 ID）
            modality: 查询模态（"text" 或 "image"）

        Returns:
            匹配结果
        """
        results = []

        if modality == "text":
            # 文本 → 查找相关的图片节点
            # 简化实现：遍历所有图片节点，匹配描述
            pass
        elif modality == "image":
            # 图片 → 查找相关的文本描述
            pass

        return results

    def get_stats(self) -> dict:
        """获取图谱统计"""
        return self.store.get_stats()


# 全局单例
_retriever: Optional[GraphRetriever] = None


def get_graph_retriever() -> GraphRetriever:
    """获取图谱检索器单例"""
    global _retriever
    if _retriever is None:
        _retriever = GraphRetriever()
    return _retriever
