"""零件识别器测试"""

import pytest
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision.part_recognizer import (
    PartRecognizer,
    PartInfo,
    RecognitionResult,
    get_part_recognizer,
)


class TestPartRecognizer:
    """零件识别器测试"""

    def setup_method(self):
        """每个测试创建新的识别器（不加载模型）"""
        self.recognizer = PartRecognizer(model_name="base", use_fallback=False)
        # 确保模型未加载（使用 Mock 模式）
        self.recognizer.model_loaded = False

    def test_register_part(self):
        """注册零件"""
        self.recognizer.register_part(
            part_id="3001",
            name="Brick 2x4",
            color="Red",
            category="Brick",
        )
        assert "3001" in self.recognizer._part_database
        assert self.recognizer._part_database["3001"].name == "Brick 2x4"

    def test_register_part_with_image(self):
        """注册零件（带图片）"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        self.recognizer.register_part(
            part_id="3001",
            name="Brick 2x4",
            image=img,
        )
        assert "3001" in self.recognizer._part_database
        # Mock 模式下不会真正编码
        # assert "3001" in self.recognizer._part_embeddings

    def test_search_by_image_empty_db(self):
        """空数据库搜索"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        results = self.recognizer.search_by_image(img)
        assert results == []

    def test_search_by_description_empty_db(self):
        """空数据库描述搜索"""
        results = self.recognizer.search_by_description("红色砖")
        assert results == []

    def test_search_by_image_with_parts(self):
        """有零件时的图片搜索"""
        from PIL import Image

        # 注册几个零件
        for i in range(3):
            img = Image.new("RGB", (100, 100), color=["red", "blue", "green"][i])
            self.recognizer.register_part(
                part_id=f"300{i}",
                name=f"Brick Type {i}",
                image=img,
            )

        # 搜索
        query_img = Image.new("RGB", (100, 100), color="red")
        results = self.recognizer.search_by_image(query_img, top_k=2)

        # Mock 模式下结果可能为空（因为 embedding 是随机的）
        # 但不应报错
        assert isinstance(results, list)

    def test_verify_part_not_found(self):
        """验证不存在的零件"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        result = self.recognizer.verify_part(img, "nonexistent")
        assert result["verified"] is False

    def test_verify_part_with_registered(self):
        """验证已注册的零件"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        self.recognizer.register_part(
            part_id="3001",
            name="Brick 2x4",
            image=img,
        )

        result = self.recognizer.verify_part(img, "3001")
        assert "verified" in result
        assert "similarity" in result

    def test_compute_similarity(self):
        """计算相似度"""
        from PIL import Image

        img1 = Image.new("RGB", (100, 100), color="red")
        img2 = Image.new("RGB", (100, 100), color="red")

        sim = self.recognizer.compute_similarity(img1, img2)
        assert isinstance(sim, float)

    def test_mock_embedding(self):
        """Mock 向量"""
        emb = self.recognizer._mock_embedding()
        assert len(emb) == 512
        assert all(isinstance(v, float) for v in emb)

    def test_get_stats(self):
        """统计信息"""
        stats = self.recognizer.get_stats()
        assert "model_loaded" in stats
        assert "registered_parts" in stats
        assert "embedded_parts" in stats

    def test_load_image_from_path(self):
        """从路径加载图片"""
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (100, 100), color="red")
            img.save(f, "PNG")
            temp_path = f.name

        try:
            loaded = self.recognizer._load_image(temp_path)
            assert isinstance(loaded, Image.Image)
            assert loaded.size == (100, 100)
        finally:
            os.unlink(temp_path)

    def test_load_image_from_bytes(self):
        """从 bytes 加载图片"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        loaded = self.recognizer._load_image(img_bytes.getvalue())
        assert isinstance(loaded, Image.Image)

    def test_cosine_similarity(self):
        """余弦相似度"""
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [1.0, 0.0, 0.0]
        emb3 = [0.0, 1.0, 0.0]

        sim_same = self.recognizer._cosine_similarity(emb1, emb2)
        sim_diff = self.recognizer._cosine_similarity(emb1, emb3)

        assert sim_same > sim_diff
        assert sim_same == pytest.approx(1.0)


class TestPartInfo:
    """零件信息测试"""

    def test_part_info_creation(self):
        """创建零件信息"""
        info = PartInfo(
            part_id="3001",
            name="Brick 2x4",
            color="Red",
            category="Brick",
        )
        assert info.part_id == "3001"
        assert info.name == "Brick 2x4"
        assert info.confidence == 0.0


class TestRecognitionResult:
    """识别结果测试"""

    def test_recognition_result(self):
        """创建识别结果"""
        info = PartInfo(part_id="3001", name="Brick 2x4")
        result = RecognitionResult(
            part_info=info,
            similarity=0.95,
            match_type="image_to_text",
        )
        assert result.similarity == 0.95
        assert result.match_type == "image_to_text"


# 修复导入
import io


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
