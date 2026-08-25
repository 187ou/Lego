"""知识图谱存储测试"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kg.schema import NodeType, RelationType, GraphNode, GraphRelation
from src.kg.graph_store import MockGraphStore


class TestMockGraphStore:
    """Mock 图谱存储测试"""

    def setup_method(self):
        self.store = MockGraphStore()

    def test_create_node(self):
        """创建节点"""
        node = GraphNode(
            node_type=NodeType.PART,
            node_id="part_3001",
            name="Brick 2x4",
        )
        assert self.store.create_node(node) is True
        assert "part_3001" in self.store._nodes

    def test_create_relation(self):
        """创建关系"""
        node_a = GraphNode(node_type=NodeType.SET, node_id="set_10295", name="Set 10295")
        node_b = GraphNode(node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4")

        self.store.create_node(node_a)
        self.store.create_node(node_b)

        relation = GraphRelation(
            relation_type=RelationType.CONTAINS,
            source_id="set_10295",
            target_id="part_3001",
        )
        assert self.store.create_relation(relation) is True
        assert len(self.store._relations) == 1

    def test_get_node(self):
        """获取节点"""
        node = GraphNode(
            node_type=NodeType.PART,
            node_id="part_3001",
            name="Brick 2x4",
        )
        self.store.create_node(node)

        result = self.store.get_node("part_3001")
        assert result is not None
        assert result.name == "Brick 2x4"

    def test_get_node_not_found(self):
        """获取不存在的节点"""
        result = self.store.get_node("nonexistent")
        assert result is None

    def test_get_neighbors(self):
        """获取邻居"""
        set_node = GraphNode(node_type=NodeType.SET, node_id="set_10295", name="Set")
        part_node = GraphNode(node_type=NodeType.PART, node_id="part_3001", name="Part")

        self.store.create_node(set_node)
        self.store.create_node(part_node)

        relation = GraphRelation(
            relation_type=RelationType.CONTAINS,
            source_id="set_10295",
            target_id="part_3001",
        )
        self.store.create_relation(relation)

        neighbors = self.store.get_neighbors("set_10295")
        assert len(neighbors) == 1
        assert neighbors[0]["node_id"] == "part_3001"

    def test_find_alternatives(self):
        """查找替代零件"""
        # 创建零件和替代关系
        parts = [
            GraphNode(node_type=NodeType.PART, node_id=f"part_{pid}", name=name)
            for pid, name in [("3001", "Brick 2x4"), ("3002", "Brick 2x3"), ("3003", "Brick 2x2")]
        ]
        for part in parts:
            self.store.create_node(part)

        # 3001 → 3002 → 3003
        self.store.create_relation(GraphRelation(
            relation_type=RelationType.CAN_REPLACE,
            source_id="part_3001",
            target_id="part_3002",
        ))
        self.store.create_relation(GraphRelation(
            relation_type=RelationType.CAN_REPLACE,
            source_id="part_3002",
            target_id="part_3003",
        ))

        alternatives = self.store.find_alternatives("3001", limit=5)
        assert len(alternatives) >= 1

    def test_get_stats(self):
        """统计信息"""
        node = GraphNode(node_type=NodeType.PART, node_id="part_3001", name="Part")
        self.store.create_node(node)

        stats = self.store.get_stats()
        assert stats["total_nodes"] == 1
        assert stats["available"] is True

    def test_clear_all(self):
        """清除所有"""
        node = GraphNode(node_type=NodeType.PART, node_id="part_3001", name="Part")
        self.store.create_node(node)

        self.store.clear_all()
        assert len(self.store._nodes) == 0


class TestGraphBuilder:
    """图谱构建器测试"""

    def setup_method(self):
        from src.kg.graph_builder import GraphBuilder
        self.store = MockGraphStore()
        self.builder = GraphBuilder(store=self.store)

    def test_build_from_manual(self):
        """从说明书构建"""
        from src.rag.multimodal_parser import MultimodalPage

        pages = [
            MultimodalPage(
                page_number=1,
                set_id="10295",
                text_content="步骤1：取出一块3001红色砖",
            ),
            MultimodalPage(
                page_number=2,
                set_id="10295",
                text_content="步骤2：取出3005蓝色砖",
            ),
        ]

        stats = self.builder.build_from_manual(pages, "10295")

        assert stats["nodes"] > 0
        assert stats["relations"] > 0

    def test_add_part_alternative(self):
        """添加替代关系"""
        self.builder.add_part_alternative("3001", "3002", confidence=0.9)
        assert len(self.store._relations) == 1

    def test_add_part_image(self):
        """添加零件图片"""
        # 先创建零件节点
        part_node = GraphNode(
            node_type=NodeType.PART,
            node_id="part_3001",
            name="Brick 2x4",
        )
        self.store.create_node(part_node)

        self.builder.add_part_image("3001", "http://example.com/3001.png")

        # 应创建了图片节点和跨模态关系
        assert len(self.store._nodes) >= 2
        assert len(self.store._relations) >= 1


class TestGraphRetriever:
    """图谱检索器测试"""

    def setup_method(self):
        from src.kg.graph_retriever import GraphRetriever
        self.store = MockGraphStore()
        self.retriever = GraphRetriever(store=self.store)

    def test_get_part_info(self):
        """获取零件信息"""
        part_node = GraphNode(
            node_type=NodeType.PART,
            node_id="part_3001",
            name="Brick 2x4",
        )
        self.store.create_node(part_node)

        info = self.retriever.get_part_info("3001")
        assert info["found"] is True
        assert info["part"]["name"] == "Brick 2x4"

    def test_get_part_info_not_found(self):
        """获取不存在的零件"""
        info = self.retriever.get_part_info("nonexistent")
        assert info["found"] is False

    def test_find_part_alternatives(self):
        """查找替代"""
        # 创建零件和关系
        for pid in ["3001", "3002"]:
            self.store.create_node(GraphNode(
                node_type=NodeType.PART,
                node_id=f"part_{pid}",
                name=f"Part {pid}",
            ))

        self.store.create_relation(GraphRelation(
            relation_type=RelationType.CAN_REPLACE,
            source_id="part_3001",
            target_id="part_3002",
        ))

        alternatives = self.retriever.find_part_alternatives("3001")
        assert len(alternatives) >= 1

    def test_get_step_info(self):
        """获取步骤信息"""
        step_node = GraphNode(
            node_type=NodeType.STEP,
            node_id="set_10295_step_1",
            name="步骤 1",
            text_description="步骤1描述",
        )
        self.store.create_node(step_node)

        info = self.retriever.get_step_info("10295", 1)
        assert info["found"] is True

    def test_get_set_overview(self):
        """获取套装概览"""
        set_node = GraphNode(
            node_type=NodeType.SET,
            node_id="set_10295",
            name="Set 10295",
        )
        self.store.create_node(set_node)

        overview = self.retriever.get_set_overview("10295")
        assert overview["found"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
