# -*- coding: utf-8 -*-
"""Physics validator tests"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.builder3d.physics import PhysicsValidator


@pytest.fixture
def validator():
    return PhysicsValidator()


class TestStableModels:
    def test_single_layer_on_plate(self, validator):
        bricks = [
            {"position": {"x": 0, "y": 0, "z": 0}, "size": {"x": 2, "y": 1, "z": 4}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is True

    def test_stacked_bricks(self, validator):
        bricks = [
            {"position": {"x": 0, "y": 0, "z": 0}, "size": {"x": 2, "y": 1, "z": 4}},
            {"position": {"x": 0, "y": 1, "z": 0}, "size": {"x": 2, "y": 1, "z": 4}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is True

    def test_pyramid(self, validator):
        bricks = [
            {"position": {"x": 0, "y": 0, "z": 0}, "size": {"x": 4, "y": 1, "z": 4}},
            {"position": {"x": 1, "y": 1, "z": 1}, "size": {"x": 2, "y": 1, "z": 2}},
        ]
        result = validator.validate(bricks, {"width": 8, "length": 8})
        assert result["stable"] is True


class TestUnstableModels:
    def test_floating_brick(self, validator):
        bricks = [
            {"position": {"x": 0, "y": 0, "z": 0}, "size": {"x": 2, "y": 1, "z": 4}},
            {"position": {"x": 0, "y": 2, "z": 0}, "size": {"x": 2, "y": 1, "z": 4}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is False

    def test_out_of_bounds(self, validator):
        bricks = [
            {"position": {"x": 15, "y": 0, "z": 15}, "size": {"x": 4, "y": 1, "z": 4}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is False

    def test_disconnected(self, validator):
        bricks = [
            {"position": {"x": 0, "y": 0, "z": 0}, "size": {"x": 2, "y": 1, "z": 2}},
            {"position": {"x": 10, "y": 1, "z": 10}, "size": {"x": 2, "y": 1, "z": 2}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is False


class TestEdgeCases:
    def test_empty_bricks(self, validator):
        result = validator.validate([], {"width": 16, "length": 16})
        assert result["stable"] is False

    def test_negative_position(self, validator):
        bricks = [
            {"position": {"x": -1, "y": 0, "z": 0}, "size": {"x": 2, "y": 1, "z": 2}},
        ]
        result = validator.validate(bricks, {"width": 16, "length": 16})
        assert result["stable"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
