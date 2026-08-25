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

        使用多种策略检测区域：
        1. 文本密度分析：检测文字密集区域
        2. 图像内容分析：检测图片区域
        3. 结构分析：检测步骤号、零件列表等结构特征
        """
        regions = []
        rect = page.rect
        page_w = rect.width
        page_h = rect.height

        # 1. 获取页面文本块（pymupdf 原生支持）
        text_blocks = page.get_text("blocks")

        # 2. 分析文本块分布
        text_regions = []
        image_regions = []

        for block in text_blocks:
            x0, y0, x1, y1, text, block_type, _ = block
            if block_type == 0:  # 文本块
                text_regions.append({
                    "bbox": (x0, y0, x1, y1),
                    "text": text.strip(),
                    "area": (x1 - x0) * (y1 - y0),
                })

        # 3. 检测步骤区域（包含"步骤"、"step"、数字编号的区域）
        step_regions = []
        parts_regions = []
        text_only_regions = []

        for region in text_regions:
            text = region["text"]
            # 步骤特征：包含"步骤"、"step"、或数字+序号
            if any(kw in text.lower() for kw in ["步骤", "step", "第", "步"]):
                # 进一步检查是否有数字编号
                import re
                if re.search(r'\d+', text):
                    step_regions.append(region)
            # 零件列表特征：包含零件编号（4-5位数字）
            elif re.search(r'(?<!\d)(\d{4,5})(?!\d)', text):
                parts_regions.append(region)
            else:
                text_only_regions.append(region)

        # 4. 合并相邻的同类区域
        if step_regions:
            merged = self._merge_regions(step_regions)
            for m in merged:
                regions.append(PageRegion(
                    region_type="step_diagram",
                    bbox=m["bbox"],
                    text=m.get("text", ""),
                ))

        if parts_regions:
            merged = self._merge_regions(parts_regions)
            for m in merged:
                regions.append(PageRegion(
                    region_type="parts_list",
                    bbox=m["bbox"],
                    text=m.get("text", ""),
                ))

        if text_only_regions:
            merged = self._merge_regions(text_only_regions)
            for m in merged:
                regions.append(PageRegion(
                    region_type="text_description",
                    bbox=m["bbox"],
                    text=m.get("text", ""),
                ))

        # 5. 如果没有检测到任何区域，使用默认分割
        if not regions:
            regions.append(PageRegion(
                region_type="step_diagram",
                bbox=(0, 0, page_w, page_h * 0.6),
            ))
            regions.append(PageRegion(
                region_type="parts_list",
                bbox=(0, page_h * 0.6, page_w, page_h),
            ))

        return regions

    def _merge_regions(self, region_list: list[dict]) -> list[dict]:
        """合并相邻的区域"""
        if not region_list:
            return []

        # 按 y 坐标排序
        sorted_regions = sorted(region_list, key=lambda r: r["bbox"][1])

        merged = [sorted_regions[0]]

        for region in sorted_regions[1:]:
            last = merged[-1]
            last_x0, last_y0, last_x1, last_y1 = last["bbox"]
            cur_x0, cur_y0, cur_x1, cur_y1 = region["bbox"]

            # 检查是否相邻（垂直距离小于页面高度的 10%）
            if cur_y0 - last_y1 < (last_y1 - last_y0) * 0.5:
                # 合并
                merged[-1] = {
                    "bbox": (
                        min(last_x0, cur_x0),
                        min(last_y0, cur_y0),
                        max(last_x1, cur_x1),
                        max(last_y1, cur_y1),
                    ),
                    "text": last.get("text", "") + "\n" + region.get("text", ""),
                }
            else:
                merged.append(region)

        return merged

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
        2. 图片 Document（用于视觉检索，图片存文件系统）

        注意：不再将图片 base64 存入元数据，图片由 MultimodalVectorStore 管理
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

            # 图片 Document（只存元数据，不存 base64）
            if page.full_image:
                img_doc = Document(
                    page_content=f"[PAGE_IMAGE_{page.page_number}]",
                    metadata={
                        **page.metadata,
                        "modality": "image",
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
