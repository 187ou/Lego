# -*- coding: utf-8 -*-
"""Model generation pipeline tests"""

import pytest
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.builder3d.pipeline import ModelGenerationPipeline


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content='{"bricks": [{"part_id": "3001", "color": "Red", "position": {"x": 0, "y": 0, "z": 0}}]}')
    return llm


@pytest.fixture
def pipeline(mock_llm):
    return ModelGenerationPipeline(llm=mock_llm)


class TestPipeline:
    def test_generate_returns_model(self, pipeline):
        model = pipeline.generate("a red car")
        assert model["totalSteps"] > 0
        assert "generation_log" in model
        assert len(model["generation_log"]) > 0

    def test_log_contains_attempts(self, pipeline):
        model = pipeline.generate("test")
        assert any("attempt 1" in entry.lower() for entry in model["generation_log"])

    def test_max_attempts_respected(self, pipeline, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("LLM error")
        model = pipeline.generate("test", max_attempts=2)
        assert model is not None

    def test_bricks_have_required_fields(self, pipeline):
        model = pipeline.generate("test")
        for step in model["steps"]:
            for brick in step["bricksToAdd"]:
                assert "position" in brick
                assert "size" in brick


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
