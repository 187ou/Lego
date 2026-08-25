# -*- coding: utf-8 -*-
"""Graph builder extended tests: part extraction, alternatives, edge cases"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kg.graph_builder import GraphBuilder, _auto_build_alternatives
from src.kg.graph_store import MockGraphStore
from src.kg.schema import NodeType, RelationType, GraphNode, GraphRelation


@pytest.fixture
def builder():
    return GraphBuilder(store=MockGraphStore())


class TestExtractParts:
    """Part extraction tests"""

    def test_extract_part_id(self, builder):
        parts = builder._extract_parts("Take one 3001 red brick")
        assert len(parts) >= 1
        assert any(p["part_id"] == "3001" for p in parts)

    def test_extract_multiple_parts(self, builder):
        parts = builder._extract_parts("Take 3001 brick and 3005 plate, then 3023")
        part_ids = {p["part_id"] for p in parts}
        assert "3001" in part_ids
        assert "3005" in part_ids
        assert "3023" in part_ids

    def test_no_parts_in_text(self, builder):
        parts = builder._extract_parts("This step is hard, be patient")
        assert len(parts) == 0

    def test_step_number_not_extracted(self, builder):
        parts = builder._extract_parts("Step 35: take red brick")
        assert all(p["part_id"] != "35" for p in parts)

    def test_lookup_part_name(self, builder):
        assert builder._lookup_part_name("3001") == "Brick 2x4"
        assert builder._lookup_part_name("9999") == "Part 9999"


class TestAutoBuildAlternatives:
    """Alternative relationship tests"""

    def test_same_type_same_size(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4",
            properties={"part_id": "3001"},
        ))
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3002", name="Brick 2x3",
            properties={"part_id": "3002"},
        ))
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(b, stats)
        # Brick 2x4 and Brick 2x3: same type, one dim same (2), other dim diff=1
        assert stats["relations"] > 0

    def test_different_type_no_relation(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4",
            properties={"part_id": "3001"},
        ))
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3020", name="Plate 2x4",
            properties={"part_id": "3020"},
        ))
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(b, stats)
        assert stats["relations"] == 0

    def test_alternative_symmetry(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4",
            properties={"part_id": "3001"},
        ))
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3002", name="Brick 2x3",
            properties={"part_id": "3002"},
        ))
        stats = {"nodes": 0, "relations": 0}
        _auto_build_alternatives(b, stats)
        alts_3001 = store.find_alternatives("3001", limit=5)
        alts_3002 = store.find_alternatives("3002", limit=5)
        assert len(alts_3001) > 0
        assert len(alts_3002) > 0


class TestBuildFromDocuments:
    """Build graph from LangChain Document objects"""

    def _make_docs(self, set_id="10295"):
        from langchain_core.documents import Document
        return [
            Document(
                page_content=f"Step 1: Take 3001 Brick 2x4 red brick.",
                metadata={"set_id": set_id, "step_number": s, "page_number": s},
            )
            for s in [1, 2, 3]
        ]

    def test_build_creates_nodes(self, builder):
        docs = self._make_docs()
        stats = builder.build_from_manual(docs, "10295")
        assert stats["nodes"] > 0
        assert stats["relations"] > 0

    def test_build_creates_set_node(self, builder):
        docs = self._make_docs()
        builder.build_from_manual(docs, "10295")
        assert builder.store.get_node("set_10295") is not None

    def test_build_creates_step_chain(self, builder):
        docs = self._make_docs()
        builder.build_from_manual(docs, "10295")
        neighbors = builder.store.get_neighbors("set_10295_step_2", limit=5)
        follows = [n for n in neighbors if n.get("relation") == "FOLLOWS"]
        assert len(follows) > 0

    def test_build_creates_part_nodes(self, builder):
        docs = self._make_docs()
        builder.build_from_manual(docs, "10295")
        assert builder.store.get_node("part_3001") is not None

    def test_build_creates_uses_relations(self, builder):
        docs = self._make_docs()
        builder.build_from_manual(docs, "10295")
        neighbors = builder.store.get_neighbors("set_10295_step_1", limit=10)
        uses = [n for n in neighbors if n.get("relation") == "USES"]
        assert len(uses) > 0

    def test_empty_pages(self, builder):
        stats = builder.build_from_manual([], "10295")
        assert stats["nodes"] == 1

    def test_document_without_step_number(self, builder):
        from langchain_core.documents import Document
        doc = Document(page_content="no step number", metadata={"set_id": "10295"})
        stats = builder.build_from_manual([doc], "10295")
        assert stats["nodes"] == 1
        assert stats["relations"] == 0


class TestEdgeCases:
    """Edge case tests"""

    def test_missing_part(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4",
        ))
        assert store.get_node("part_9999") is None

    def test_duplicate_part_creation(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        node = GraphNode(node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4")
        assert store.create_node(node) is True
        assert store.create_node(node) is True

    def test_relation_with_missing_node(self, builder):
        store = MockGraphStore()
        b = GraphBuilder(store=store)
        rel = GraphRelation(
            relation_type=RelationType.USES,
            source_id="set_10295_step_1",
            target_id="part_nonexistent",
        )
        store.create_relation(rel)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
