"""多格式文档加载器测试"""

import pytest
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入（与 pdf_loader 使用相同的导入机制）
from src.rag.document_loader import DocumentLoader, DocumentType, detect_document_type, load_document


class TestDocumentTypeDetection:
    """文档类型检测测试"""

    def test_pdf_detection(self):
        assert detect_document_type("test.pdf") == DocumentType.PDF
        assert detect_document_type("test.PDF") == DocumentType.PDF

    def test_image_detection(self):
        assert detect_document_type("test.png") == DocumentType.IMAGE
        assert detect_document_type("test.jpg") == DocumentType.IMAGE
        assert detect_document_type("test.jpeg") == DocumentType.IMAGE
        assert detect_document_type("test.bmp") == DocumentType.IMAGE
        assert detect_document_type("test.webp") == DocumentType.IMAGE

    def test_text_detection(self):
        assert detect_document_type("test.txt") == DocumentType.TEXT
        assert detect_document_type("test.md") == DocumentType.TEXT
        assert detect_document_type("test.markdown") == DocumentType.TEXT

    def test_docx_detection(self):
        assert detect_document_type("test.docx") == DocumentType.DOCX

    def test_unknown_detection(self):
        assert detect_document_type("test.exe") == DocumentType.UNKNOWN
        assert detect_document_type("test.unknown") == DocumentType.UNKNOWN


class TestDocumentLoader:
    """文档加载器测试"""

    def setup_method(self):
        self.loader = DocumentLoader()

    def test_load_nonexistent_file(self):
        """加载不存在的文件"""
        with pytest.raises(FileNotFoundError):
            self.loader.load("/nonexistent/file.pdf")

    def test_load_unsupported_format(self):
        """加载不支持的格式"""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"test")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="不支持的文档格式"):
                self.loader.load(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_text_file(self):
        """加载文本文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("这是测试内容。\n第二行。\n第三行。")
            temp_path = f.name

        try:
            docs = self.loader.load(temp_path, set_id="test_set")
            assert len(docs) > 0
            assert docs[0].metadata["set_id"] == "test_set"
            assert docs[0].metadata["doc_type"] == "text"
        finally:
            os.unlink(temp_path)

    def test_load_markdown_file(self):
        """加载 Markdown 文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# 标题\n\n## 子标题\n\n内容在这里。")
            temp_path = f.name

        try:
            docs = self.loader.load(temp_path, set_id="test_set")
            assert len(docs) > 0
            assert "标题" in docs[0].page_content or "内容" in docs[0].page_content
        finally:
            os.unlink(temp_path)

    def test_load_empty_text_file(self):
        """加载空文本文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            temp_path = f.name

        try:
            docs = self.loader.load(temp_path, set_id="test_set")
            assert docs == []
        finally:
            os.unlink(temp_path)

    def test_load_with_metadata(self):
        """加载时添加额外元数据"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("测试内容")
            temp_path = f.name

        try:
            docs = self.loader.load(
                temp_path,
                set_id="test_set",
                metadata={"author": "test", "version": "1.0"},
            )
            assert docs[0].metadata["author"] == "test"
            assert docs[0].metadata["version"] == "1.0"
        finally:
            os.unlink(temp_path)

    def test_text_chunking(self):
        """文本切片"""
        # 创建一个大文本
        large_text = "。\n".join([f"这是第{i}段内容" for i in range(100)])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(large_text)
            temp_path = f.name

        try:
            docs = self.loader.load(temp_path, set_id="test_set")
            # 大文本应被切成多个片段
            assert len(docs) > 1
        finally:
            os.unlink(temp_path)


class TestLoadDocumentFunction:
    """便捷函数测试"""

    def test_load_document_convenience(self):
        """测试便捷函数"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("便捷函数测试")
            temp_path = f.name

        try:
            docs = load_document(temp_path, set_id="test")
            assert len(docs) > 0
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
