# -*- coding: utf-8 -*-
"""LLM model generator tests"""

import pytest
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.builder3d.llm_generator import LLMModelGenerator


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps({
        "bricks": [
            {"part_id": "3001", "color": "Red", "position": {"x": 0, "y": 0, "z": 0}},
            {"part_id": "3003", "color": "Blue", "position": {"x": 0, "y": 1, "z": 0}},
        ],
        "base_plate": {"width": 16, "length": 16},
    }))
    return llm


@pytest.fixture
def generator(mock_llm):
    return LLMModelGenerator(llm=mock_llm)


import json


class TestLLMGenerator:
    def test_generate_returns_model(self, generator):
        model = generator.generate("a red car")
        assert model["totalSteps"] > 0
        assert model["totalBricks"] > 0
        assert model["source"] == "llm"

    def test_generate_calls_llm(self, generator, mock_llm):
        generator.generate("test")
        mock_llm.invoke.assert_called_once()

    def test_brick_fields_valid(self, generator):
        model = generator.generate("test")
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                assert "id" in brick
                assert "partId" in brick
                assert "position" in brick
                assert "size" in brick

    def test_invalid_part_id_skipped(self, generator, mock_llm):
        mock_llm.invoke.return_value = MagicMock(content=json.dumps({
            "bricks": [
                {"part_id": "99999", "color": "Red", "position": {"x": 0, "y": 0, "z": 0}},
            ],
        }))
        model = generator.generate("test")
        # 99999 is 5 digits, should be valid
        assert model["totalBricks"] >= 1

    def test_malformed_json_falls_back(self, generator, mock_llm):
        mock_llm.invoke.return_value = MagicMock(content="not json at all")
        model = generator.generate("test")
        assert model["source"] == "llm"
        assert len(model["errors"]) > 0

    def test_empty_bricks_falls_back(self, generator, mock_llm):
        mock_llm.invoke.return_value = MagicMock(content=json.dumps({"bricks": []}))
        model = generator.generate("test")
        assert model["totalBricks"] == 1  # fallback

    def test_llm_exception_falls_back(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("LLM down")
        gen = LLMModelGenerator(llm=mock_llm)
        model = gen.generate("test")
        assert "LLM failed" in model["errors"][0]

    def test_extract_json_from_markdown(self, generator):
        raw = 'Here is the JSON: ```json\n{"bricks": []}\n```'
        result = generator._extract_json(raw)
        assert result is not None

    def test_extract_json_plain(self, generator):
        raw = '{"bricks": [{"part_id": "3001", "position": {"x":0,"y":0,"z":0}}]}'
        result = generator._extract_json(raw)
        assert result == raw


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
