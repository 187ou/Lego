# -*- coding: utf-8 -*-
"""3D data generator tests: graph fetch, mock model, edge cases, validation"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.builder3d.data_generator import (
    generate_build_model,
    get_build_model,
    clear_cache,
    _generate_step_description,
    _color_name_to_hex,
    _parse_size_from_name,
)
from src.kg.graph_store import MockGraphStore
from src.kg.graph_retriever import GraphRetriever
from src.kg.schema import NodeType, GraphNode, GraphRelation, RelationType


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


class TestMockModelGeneration:
    """Mock model generation tests"""

    def test_generates_correct_number_of_steps(self):
        model = generate_build_model("test", "Test Set", 10)
        assert model["totalSteps"] == 10
        assert len(model["steps"]) == 10

    def test_each_step_has_bricks(self):
        model = generate_build_model("test", "Test Set", 5)
        for step in model["steps"]:
            assert len(step["bricksToAdd"]) > 0

    def test_bricks_have_required_fields(self):
        model = generate_build_model("test", "Test Set", 3)
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                assert "id" in brick
                assert "partId" in brick
                assert "name" in brick
                assert "color" in brick
                assert "colorName" in brick
                assert "size" in brick
                assert "position" in brick

    def test_brick_size_valid(self):
        model = generate_build_model("test", "Test Set", 5)
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                assert brick["size"]["x"] > 0
                assert brick["size"]["y"] > 0
                assert brick["size"]["z"] > 0

    def test_brick_position_within_base(self):
        model = generate_build_model("test", "Test Set", 5)
        bp = model["basePlate"]
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                pos = brick["position"]
                assert pos["x"] >= 0
                assert pos["y"] >= 0
                assert pos["z"] >= 0

    def test_base_plate_scales_with_steps(self):
        small = generate_build_model("s", "Small", 3)
        large = generate_build_model("l", "Large", 50)
        assert large["basePlate"]["width"] >= small["basePlate"]["width"]

    def test_model_has_source_field(self):
        model = generate_build_model("test", "Test", 5)
        assert "source" in model
        assert model["source"] == "mock"

    def test_total_bricks_count(self):
        model = generate_build_model("test", "Test", 5)
        actual = sum(len(s["bricksToAdd"]) for s in model["steps"])
        assert model["totalBricks"] == actual

    def test_set_metadata(self):
        model = generate_build_model("10295", "Porsche 911", 37)
        assert model["setId"] == "10295"
        assert model["setName"] == "Porsche 911"


class TestStepDescription:
    """Step description generation tests"""

    def test_first_step(self):
        desc = _generate_step_description(1, 10, 2)
        assert len(desc) > 0

    def test_last_step(self):
        desc = _generate_step_description(10, 10, 3)
        assert len(desc) > 0

    def test_middle_step(self):
        desc = _generate_step_description(5, 10, 2)
        assert len(desc) > 0

    def test_single_step(self):
        desc = _generate_step_description(1, 1, 1)
        assert len(desc) > 0


class TestColorConversion:
    """Color name to hex conversion tests"""

    def test_known_colors(self):
        assert _color_name_to_hex("Red") == "#E3000B"
        assert _color_name_to_hex("Blue") == "#0055BF"
        assert _color_name_to_hex("Yellow") == "#F5CD2F"

    def test_case_insensitive(self):
        assert _color_name_to_hex("red") == "#E3000B"
        assert _color_name_to_hex("RED") == "#E3000B"

    def test_unknown_color(self):
        assert _color_name_to_hex("NeonGreen") == "#808080"

    def test_empty_color(self):
        assert _color_name_to_hex("") == "#808080"


class TestSizeParsing:
    """Size parsing from name tests"""

    def test_standard_sizes(self):
        assert _parse_size_from_name("Brick 2x4") == {"x": 2, "y": 1, "z": 4}
        assert _parse_size_from_name("Plate 1x2") == {"x": 1, "y": 1, "z": 2}
        assert _parse_size_from_name("Brick 1x1") == {"x": 1, "y": 1, "z": 1}

    def test_no_size_in_name(self):
        assert _parse_size_from_name("Technic Pin") == {"x": 2, "y": 1, "z": 2}


class TestGraphFetch:
    """Graph data fetch tests"""

    def test_returns_mock_when_graph_empty(self):
        model = generate_build_model("unknown", "Unknown", 10)
        assert model["source"] == "mock"

    def test_returns_graph_data_when_available(self):
        """When graph has step data, should return graph source"""
        store = MockGraphStore()
        retriever = GraphRetriever(store=store)

        # Populate graph with step data
        store.create_node(GraphNode(
            node_type=NodeType.SET, node_id="set_test", name="Test",
        ))
        for step_num in [1, 2, 3]:
            store.create_node(GraphNode(
                node_type=NodeType.STEP,
                node_id=f"set_test_step_{step_num}",
                name=f"Step {step_num}",
                text_description=f"Step {step_num} desc",
            ))
            store.create_relation(GraphRelation(
                relation_type=RelationType.USES,
                source_id=f"set_test_step_{step_num}",
                target_id="part_3001",
            ))
        store.create_node(GraphNode(
            node_type=NodeType.PART, node_id="part_3001", name="Brick 2x4",
            properties={"part_id": "3001"},
        ))
        store.create_relation(GraphRelation(
            relation_type=RelationType.CONTAINS,
            source_id="set_test",
            target_id="part_3001",
        ))

        with patch("src.kg.graph_retriever.get_graph_retriever", return_value=retriever):
            model = generate_build_model("test", "Test", 10)

        assert model is not None
        assert model["source"] == "graph"
        assert model["totalSteps"] == 3

    def test_graph_fetch_handles_errors(self):
        """Graph fetch failure should fallback to mock"""
        with patch("src.kg.graph_retriever.get_graph_retriever", side_effect=RuntimeError("DB error")):
            model = generate_build_model("test", "Test", 5)

        assert model is not None
        assert model["source"] == "mock"


class TestCaching:
    """Model caching tests"""

    def test_cache_returns_same_object(self):
        model1 = get_build_model("cached", "Cached", 10)
        model2 = get_build_model("cached", "Cached", 10)
        assert model1 is model2

    def test_different_set_ids_return_different_models(self):
        model1 = get_build_model("set1", "Set 1", 10)
        model2 = get_build_model("set2", "Set 2", 10)
        assert model1 is not model2

    def test_clear_cache_works(self):
        model1 = get_build_model("clear_test", "Test", 10)
        clear_cache()
        model2 = get_build_model("clear_test", "Test", 10)
        assert model1 is not model2


class TestEdgeCases:
    """Edge case tests"""

    def test_zero_steps(self):
        model = generate_build_model("test", "Test", 0)
        assert model["totalSteps"] == 0
        assert len(model["steps"]) == 0

    def test_one_step(self):
        model = generate_build_model("test", "Test", 1)
        assert model["totalSteps"] == 1
        assert len(model["steps"]) == 1

    def test_large_step_count(self):
        model = generate_build_model("test", "Test", 500)
        assert model["totalSteps"] == 500
        assert model["totalBricks"] > 0

    def test_negative_step_count(self):
        model = generate_build_model("test", "Test", -1)
        assert model["totalSteps"] == -1

    def test_brick_color_format(self):
        model = generate_build_model("test", "Test", 5)
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                assert brick["color"].startswith("#")
                assert len(brick["color"]) == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
