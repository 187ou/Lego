"""多模态说明书解析器测试"""

import pytest
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.multimodal_parser import (
    MultimodalManualParser,
    MultimodalPage,
    PageRegion,
    get_multimodal_parser,
)


class TestMultimodalManualParser:
    """多模态解析器测试"""

    def setup_method(self):
        self.parser = MultimodalManualParser(dpi=100)

    def test_parse_nonexistent_pdf(self):
        """解析不存在的 PDF"""
        with pytest.raises(FileNotFoundError):
            self.parser.parse_pdf("/nonexistent/file.pdf", "test_set")

    def test_parse_non_pdf_file(self):
        """解析非 PDF 文件"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            temp_path = f.name

        try:
            with pytest.raises(Exception):
                self.parser.parse_pdf(temp_path, "test_set")
        finally:
            os.unlink(temp_path)

    def test_parse_image_file(self):
        """解析图片文件"""
        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (100, 100), color="red")
            img.save(f, "PNG")
            temp_path = f.name

        try:
            page = self.parser.parse_image(temp_path, "test_set")
            assert isinstance(page, MultimodalPage)
            assert page.page_number == 1
            assert page.set_id == "test_set"
            assert len(page.full_image) > 0
        finally:
            os.unlink(temp_path)

    def test_parse_nonexistent_image(self):
        """解析不存在的图片"""
        with pytest.raises(FileNotFoundError):
            self.parser.parse_image("/nonexistent/image.png", "test_set")

    def test_to_documents(self):
        """转换为 Document（图片不再存 base64）"""
        page = MultimodalPage(
            page_number=1,
            set_id="test_set",
            full_image=b"fake_image_data",
            text_content="测试文本内容",
            metadata={"source": "test.pdf"},
        )

        docs = self.parser.to_documents([page])

        # 应生成两个 Document：文本 + 图片
        assert len(docs) == 2

        text_doc = [d for d in docs if d.metadata.get("modality") == "text"]
        img_doc = [d for d in docs if d.metadata.get("modality") == "image"]

        assert len(text_doc) == 1
        assert len(img_doc) == 1
        assert text_doc[0].page_content == "测试文本内容"
        # 图片不再存 base64，只存元数据
        assert "image_base64" not in img_doc[0].metadata
        assert "image_size" in img_doc[0].metadata

    def test_page_region(self):
        """页面区域"""
        region = PageRegion(
            region_type="step_diagram",
            bbox=(0, 0, 100, 50),
        )
        assert region.region_type == "step_diagram"
        assert region.bbox == (0, 0, 100, 50)

    def test_analyze_layout(self):
        """布局分析"""
        # Mock page object
        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792

        regions = self.parser._analyze_layout(mock_page, b"fake_image")

        assert len(regions) == 2
        assert regions[0].region_type == "step_diagram"
        assert regions[1].region_type == "parts_list"


class TestGetMultimodalParser:
    """单例测试"""

    def test_singleton(self):
        """测试单例模式"""
        p1 = get_multimodal_parser()
        p2 = get_multimodal_parser()
        assert p1 is p2

    def test_custom_dpi(self):
        """测试自定义 DPI"""
        # 重置单例
        import src.rag.multimodal_parser as mod
        mod._parser = None

        p = get_multimodal_parser(dpi=300)
        assert p.dpi == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
