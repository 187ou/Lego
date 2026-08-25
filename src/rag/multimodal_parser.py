"""多模态说明书解析器

核心思想：不做文本提取和OCR，而是直接将PDF页面当作图片处理，
通过视觉Embedding模型编码，完整保留视觉信息。

处理流程：
1. PDF → 页面渲染为图片 (pymupdf)
2. 页面布局分析（步骤区域/零件图区域/文字区域）
3. 视觉编码器编码 (SigLIP/CLIP)
4. 同时提取文本（用于关键词检索）
5. 生成多模态 Document
"""

import os
import io
import base64
from typing import Optional
from dataclasses import dataclass, field
from langchain_core.documents import Document


@dataclass
class PageRegion:
    """页面区域"""
    region_type: str          # step_diagram / parts_list / text_description / finished_model
    bbox: tuple               # (x0, y0, x1, y1)
    image: Optional[bytes] = None  # 区域图片数据
    text: str = ""            # 区域文本（如有）


@dataclass
class MultimodalPage:
    """多模态页面"""
    page_number: int
    set_id: str
    full_image: bytes = b""           # 完整页面图片
    text_content: str = ""            # 提取的文本内容
    regions: list[PageRegion] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class MultimodalManualParser:
    """多模态说明书解析器"""

    def __init__(self, dpi: int = 200):
        """
        Args:
            dpi: PDF 渲染分辨率（越高越清晰，但越慢）
        """
        self.dpi = dpi

    def parse_pdf(self, pdf_path: str, set_id: str) -> list[MultimodalPage]:
        """
        解析 PDF 为多模态页面。

        Args:
            pdf_path: PDF 文件路径
            set_id: 套装编号

        Returns:
            多模态页面列表
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"文件不存在: {pdf_path}")

        pages = []
        try:
            import fitz  # pymupdf

            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]

                # 1. 渲染页面为图片
                pix = page.get_pixmap(dpi=self.dpi)
                img_data = pix.tobytes("png")

                # 2. 提取文本（用于关键词检索）
                text = page.get_text().strip()

                # 3. 创建多模态页面
                mm_page = MultimodalPage(
                    page_number=page_num + 1,
                    set_id=set_id,
                    full_image=img_data,
                    text_content=text,
                    metadata={
                        "source": pdf_path,
                        "set_id": set_id,
                        "page_number": page_num + 1,
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "doc_type": "pdf",
                    },
                )

                # 4. 分析页面布局（区域检测）
                mm_page.regions = self._analyze_layout(page, img_data)

                pages.append(mm_page)

            doc.close()
        except ImportError:
            raise ValueError(
                "解析 PDF 需要安装 pymupdf: pip install pymupdf"
            )

        return pages

    def parse_image(self, image_path: str, set_id: str) -> MultimodalPage:
        """
        解析单张图片（用户上传的说明书照片）。

        Args:
            image_path: 图片路径
            set_id: 套装编号

        Returns:
            多模态页面
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"文件不存在: {image_path}")

        from PIL import Image

        img = Image.open(image_path)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format="PNG")
        img_data = img_byte_arr.getvalue()

        # 尝试 OCR 提取文本
        text = self._ocr_image(image_path)

        return MultimodalPage(
            page_number=1,
            set_id=set_id,
            full_image=img_data,
            text_content=text,
            metadata={
                "source": image_path,
                "set_id": set_id,
                "page_number": 1,
                "width": img.width,
                "height": img.height,
                "doc_type": "image",
            },
        )

    def _analyze_layout(self, page, img_data: bytes) -> list[PageRegion]:
        """
        分析页面布局，检测不同区域。

        这是一个简化版本，实际可以使用：
        - LayoutParser: 文档布局分析
        - YOLO: 目标检测（检测零件图、步骤图）
        - PaddleOCR: 文字区域检测
        """
        regions = []

        # 简化实现：将页面分为几个预定义区域
        rect = page.rect
        page_w = rect.width
        page_h = rect.height

        # 上半部分通常是步骤图
        regions.append(PageRegion(
            region_type="step_diagram",
            bbox=(0, 0, page_w, page_h * 0.6),
        ))

        # 下半部分通常是零件列表和文字
        regions.append(PageRegion(
            region_type="parts_list",
            bbox=(0, page_h * 0.6, page_w, page_h),
        ))

        return regions

    def _ocr_image(self, image_path: str) -> str:
        """OCR 提取文本"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            return text.strip()
        except ImportError:
            return ""
        except Exception as e:
            print(f"[WARN] OCR 失败: {e}")
            return ""

    def to_documents(self, pages: list[MultimodalPage]) -> list[Document]:
        """
        将多模态页面转换为 LangChain Document。

        每个页面生成两种 Document：
        1. 文本 Document（用于关键词检索）
        2. 图片 Document（用于视觉检索）
        """
        documents = []

        for page in pages:
            # 文本 Document
            if page.text_content:
                text_doc = Document(
                    page_content=page.text_content,
                    metadata={
                        **page.metadata,
                        "modality": "text",
                        "has_image": True,
                    },
                )
                documents.append(text_doc)

            # 图片 Document（存储图片的 base64 编码）
            if page.full_image:
                img_b64 = base64.b64encode(page.full_image).decode("utf-8")
                img_doc = Document(
                    page_content=f"[PAGE_IMAGE_{page.page_number}]",
                    metadata={
                        **page.metadata,
                        "modality": "image",
                        "image_base64": img_b64,
                        "image_size": len(page.full_image),
                    },
                )
                documents.append(img_doc)

        return documents


# 全局单例
_parser: Optional[MultimodalManualParser] = None


def get_multimodal_parser(dpi: int = 200) -> MultimodalManualParser:
    """获取多模态解析器单例"""
    global _parser
    if _parser is None:
        _parser = MultimodalManualParser(dpi=dpi)
    return _parser
