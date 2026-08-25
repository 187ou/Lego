"""RAG 检索增强生成模块

支持多格式文档的上传、解析、向量化和检索：
- PDF 说明书
- 图片（PNG/JPG）→ OCR 文本
- 纯文本/Markdown
- Word 文档（DOCX）
"""

# 延迟导入，避免强制依赖 chromadb/transformers
from src.rag.document_loader import load_document, DocumentLoader, DocumentType
from src.rag.multimodal_parser import (
    MultimodalManualParser,
    MultimodalPage,
    PageRegion,
    get_multimodal_parser,
)

__all__ = [
    "load_document",
    "DocumentLoader",
    "DocumentType",
    "MultimodalManualParser",
    "MultimodalPage",
    "PageRegion",
    "get_multimodal_parser",
]


def __getattr__(name):
    """延迟导入，只在需要时加载"""
    if name == "ManualVectorStore":
        from src.rag.vector_store import ManualVectorStore
        return ManualVectorStore
    if name == "get_vector_store":
        from src.rag.vector_store import get_vector_store
        return get_vector_store
    if name == "load_manual_pdf":
        from src.rag.pdf_loader import load_manual_pdf
        return load_manual_pdf
    if name == "create_mock_manual":
        from src.rag.pdf_loader import create_mock_manual
        return create_mock_manual
    if name == "VisualEncoder":
        from src.rag.visual_encoder import VisualEncoder
        return VisualEncoder
    if name == "get_visual_encoder":
        from src.rag.visual_encoder import get_visual_encoder
        return get_visual_encoder
    if name == "MultimodalVectorStore":
        from src.rag.multimodal_store import MultimodalVectorStore
        return MultimodalVectorStore
    if name == "get_multimodal_store":
        from src.rag.multimodal_store import get_multimodal_store
        return get_multimodal_store
    raise AttributeError(f"module 'src.rag' has no attribute '{name}'")
