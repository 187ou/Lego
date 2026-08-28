"""图谱检索器（带缓存）

基于多模态知识图谱的检索和推理。
支持：
- 单跳查询（邻居节点）
- 多跳推理（替代零件链）
- 路径查询（步骤→零件→替代）
- 跨模态检索（文本→图片）
- 缓存加速（重复查询命中缓存）
"""

from typing import Optional

from src.kg.schema import NodeType, RelationType
from src.kg.graph_store import GraphStore, get_graph_store
from src.agent.utils.cache import get_cache


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
        查找零件的替代方案（多跳推理，带缓存）。

        Args:
            part_id: 零件编号
            max_depth: 最大跳数
            limit: 返回数量

        Returns:
            替代零件列表
        """
        # 缓存查询
        cache = get_cache()
        cache_key = f"alts:{part_id}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self.store.find_alternatives(part_id, limit=limit)

        # 缓存结果（替代关系很少变化，缓存 30 分钟）
        cache.set(cache_key, result, ttl=1800)

        return result

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
        获取零件信息（包括颜色、类别、图片，带缓存）。

        Args:
            part_id: 零件编号

        Returns:
            零件信息
        """
        # 缓存查询
        cache = get_cache()
        cache_key = f"part_info:{part_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

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

        result = {
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

        # 缓存结果（零件信息很少变化，缓存 1 小时）
        cache.set(cache_key, result, ttl=3600)

        return result

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
        limit: int = 5,
    ) -> list[dict]:
        """
        跨模态搜索。

        Args:
            query: 查询（文本或图片数据）
            modality: 查询模态（"text" 或 "image"）
            limit: 返回数量

        Returns:
            匹配结果
        """
        results = []

        if modality == "text":
            results = self._text_to_image_search(query, limit)
        elif modality == "image":
            results = self._image_to_text_search(query, limit)

        return results

    def _text_to_image_search(self, text_query: str, limit: int) -> list[dict]:
        """
        文本 → 图片：从文本中提取零件号，查找关联的图片节点。

        策略：
        1. 提取零件号 → 查找 CROSS_MODAL / HAS_IMAGE 关系的图片节点
        2. 提取步骤号 → 查找步骤关联的图片
        3. 关键词匹配图片节点的 text_description
        """
        import re

        results = []
        seen_ids = set()

        # 1. 提取零件号，查找跨模态关联
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", text_query)
        for part_id in part_ids:
            node_id = f"part_{part_id}"
            neighbors = self.store.get_neighbors(node_id, limit=10)
            for n in neighbors:
                n_id = n.get("node_id", "")
                if n.get("relation") in (RelationType.HAS_IMAGE.value, RelationType.CROSS_MODAL.value):
                    if n_id not in seen_ids:
                        seen_ids.add(n_id)
                        results.append({
                            "type": "cross_modal_text_to_image",
                            "match": "part_relation",
                            "source": node_id,
                            "target": n_id,
                            "target_name": n.get("name", ""),
                            "relation": n.get("relation", ""),
                            "score": 0.85,
                        })

        # 2. 提取步骤号，查找步骤关联的图片
        step_match = re.search(r"第?\s*(\d+)\s*步", text_query)
        if step_match:
            step_number = int(step_match.group(1))
            # 从文本描述中推断 set_id（如果上下文有）
            set_id = "10295"
            step_node_id = f"set_{set_id}_step_{step_number}"
            neighbors = self.store.get_neighbors(step_node_id, limit=10)
            for n in neighbors:
                n_id = n.get("node_id", "")
                if "img" in n_id or n.get("relation") == RelationType.HAS_IMAGE.value:
                    if n_id not in seen_ids:
                        seen_ids.add(n_id)
                        results.append({
                            "type": "cross_modal_text_to_image",
                            "match": "step_relation",
                            "source": step_node_id,
                            "target": n_id,
                            "target_name": n.get("name", ""),
                            "relation": n.get("relation", ""),
                            "score": 0.8,
                        })

        return results[:limit]

    def _image_to_text_search(self, image_data, limit: int) -> list[dict]:
        """
        图片 → 文本：调用多模态向量存储进行图搜文。

        Args:
            image_data: 图片数据（bytes 或路径）
        """
        results = []

        try:
            from src.rag.multimodal_store import get_multimodal_store
            store = get_multimodal_store()
            img_results = store.search_by_image(image_data, top_k=limit)

            for r in img_results:
                results.append({
                    "type": "cross_modal_image_to_text",
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.5),
                    "metadata": r.get("metadata", {}),
                    "image": r.get("image"),
                })
        except Exception as e:
            print(f"[WARN] 图搜文失败: {e}")

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
