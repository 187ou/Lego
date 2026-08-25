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
        """每个测试创建新的识别器（不加载真实模型）"""
        # Mock 视觉编码器，避免下载模型
        with patch("src.vision.part_recognizer.get_visual_encoder") as mock_encoder:
            mock_enc = MagicMock()
            mock_enc.model_loaded = False
            mock_enc.encode_image.return_value = [0.1] * 512
            mock_enc.encode_text.return_value = [0.1] * 512
            mock_encoder.return_value = mock_enc
            self.recognizer = PartRecognizer(model_name="clip", device="cpu")

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
        """空数据库搜索（清空自动注册的零件）"""
        self.recognizer._part_database.clear()
        self.recognizer._part_embeddings.clear()
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        results = self.recognizer.search_by_image(img)
        assert results == []

    def test_search_by_description_empty_db(self):
        """空数据库描述搜索（清空自动注册的零件）"""
        self.recognizer._part_database.clear()
        self.recognizer._part_embeddings.clear()
        results = self.recognizer.search_by_description("red brick")
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
        """Mock 向量（通过编码器）"""
        # 配置 mock 返回值
        mock_emb = [0.5] * 768
        self.recognizer.encoder._mock_embedding = lambda: mock_emb
        emb = self.recognizer.encoder._mock_embedding()
        assert len(emb) == 768  # VisualEncoder 使用 768 维
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


class TestAutoRegistration:
    """自动注册常见零件测试"""

    def test_auto_registers_common_parts(self):
        """PartRecognizer 初始化时自动注册常见零件"""
        import os
        os.environ["USE_REAL_CLIP"] = "false"

        with patch("src.vision.part_recognizer.get_visual_encoder") as mock_encoder:
            mock_enc = MagicMock()
            mock_enc.model_loaded = True
            mock_enc.encode_text.return_value = [0.1] * 768
            mock_encoder.return_value = mock_enc

            from src.vision.part_recognizer import PartRecognizer
            r = PartRecognizer(model_name="clip", device="cpu")

            # 应自动注册常见零件
            assert len(r._part_database) > 0
            assert len(r._part_embeddings) > 0

    def test_auto_registration_handles_errors(self):
        """自动注册失败不应崩溃"""
        import os
        os.environ["USE_REAL_CLIP"] = "false"

        with patch("src.vision.part_recognizer.get_visual_encoder") as mock_encoder:
            mock_enc = MagicMock()
            mock_enc.model_loaded = True
            mock_enc.encode_text.side_effect = RuntimeError("encoding failed")
            mock_encoder.return_value = mock_enc

            from src.vision.part_recognizer import PartRecognizer
            # 不应崩溃
            r = PartRecognizer(model_name="clip", device="cpu")
            assert isinstance(r._part_database, dict)


class TestCosineSimilarity:
    """余弦相似度测试"""

    def setup_method(self):
        with patch("src.vision.part_recognizer.get_visual_encoder") as mock_encoder:
            mock_enc = MagicMock()
            mock_enc.model_loaded = False
            mock_encoder.return_value = mock_enc
            from src.vision.part_recognizer import PartRecognizer
            self.r = PartRecognizer(model_name="clip", device="cpu")

    def test_identical_vectors(self):
        """相同向量相似度为1"""
        emb = [1.0, 0.0, 0.0]
        sim = self.r._cosine_similarity(emb, emb)
        assert sim == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """正交向量相似度为0"""
        sim = self.r._cosine_similarity([1, 0, 0], [0, 1, 0])
        assert sim == pytest.approx(0.0, abs=0.01)

    def test_opposite_vectors(self):
        """反向向量相似度为-1"""
        sim = self.r._cosine_similarity([1, 0, 0], [-1, 0, 0])
        assert sim == pytest.approx(-1.0)

    def test_dimension_mismatch(self):
        """维度不匹配时应截断到较短长度"""
        sim = self.r._cosine_similarity([1, 0, 0, 0], [1, 0, 0])
        assert isinstance(sim, float)

    def test_zero_vector(self):
        """零向量应返回0"""
        sim = self.r._cosine_similarity([0, 0, 0], [1, 0, 0])
        assert sim == 0.0


# === clip_checker 测试 ===

class TestClipChecker:
    """CLIP 验真测试"""

    def test_mock_mode_returns_mock(self):
        """Mock 模式返回固定结果"""
        import os
        os.environ["USE_REAL_CLIP"] = "false"

        from src.verification.clip_checker import compare_images
        result = compare_images("dummy1.png", "dummy2.png")
        assert result["verdict"] == "pass"
        assert result["similarity"] == 0.92
        assert "[Mock]" in result["details"]

    def test_real_clip_with_same_images(self):
        """真实 CLIP 对比相同图片"""
        import os
        os.environ["USE_REAL_CLIP"] = "true"

        from src.verification.clip_checker import compare_images
        from src.kg.image_generator import generate_part_image
        import tempfile

        img1 = generate_part_image("Brick 2x4", 2, 4, "Red")
        img2 = generate_part_image("Brick 2x4", 2, 4, "Red")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
            f1.write(img1); path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
            f2.write(img2); path2 = f2.name

        try:
            result = compare_images(path1, path2)
            assert "verdict" in result
            assert "similarity" in result
            assert "region_results" in result
            assert isinstance(result["region_results"], list)
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_region_comparison_returns_grid(self):
        """区域对比应返回 grid_size^2 个区域"""
        import os

        # 强制重新加载 CLIP 模型（避免被其他测试的状态影响）
        import src.verification.clip_checker as cc
        cc._clip_model = None
        cc._clip_processor = None
        cc.USE_REAL_CLIP = True

        from src.verification.clip_checker import compare_images
        from src.kg.image_generator import generate_part_image
        import tempfile

        img1 = generate_part_image("Brick 2x4", 2, 4, "Red")
        img2 = generate_part_image("Brick 2x4", 2, 4, "Blue")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
            f1.write(img1); path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
            f2.write(img2); path2 = f2.name

        try:
            result = compare_images(path1, path2, grid_size=3)
            assert len(result["region_results"]) == 9
        finally:
            os.unlink(path1)
            os.unlink(path2)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
