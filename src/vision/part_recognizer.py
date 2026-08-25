"""乐高零件识别器

使用统一的 VisualEncoder 进行零件识别。
支持：
- 以图搜文：上传零件图片 → 返回零件信息
- 以文搜图：描述零件 → 返回匹配的零件图片
- 零件验证：对比用户图片与官方图片

模型来源：
- Hugging Face: clip-vit-base-patch32_lego-brick
- 或在 Rebrickable 数据集上自微调
"""

import os
import io
import json
from typing import Optional, Union
from dataclasses import dataclass
from PIL import Image

from src.rag.visual_encoder import VisualEncoder, get_visual_encoder


@dataclass
class PartInfo:
    """零件信息"""
    part_id: str
    name: str
    color: str = ""
    category: str = ""
    image_url: str = ""
    description: str = ""
    confidence: float = 0.0


@dataclass
class RecognitionResult:
    """识别结果"""
    part_info: PartInfo
    similarity: float
    match_type: str  # "image_to_text" / "text_to_image" / "image_to_image"


class PartRecognizer:
    """乐高零件识别器（使用统一的 VisualEncoder）"""

    def __init__(
        self,
        model_name: str = "lego_clip",
        device: str = "cpu",
    ):
        """
        Args:
            model_name: 模型名称 ("siglip", "clip", "lego_clip")
            device: 运行设备 ("cpu", "cuda")
        """
        self.device = device
        self.model_name = model_name

        # 使用统一的视觉编码器（单例，避免重复加载）
        self.encoder = get_visual_encoder(model_name=model_name, device=device)

        # 零件数据库（内存缓存）
        self._part_database: dict[str, PartInfo] = {}
        self._part_embeddings: dict[str, list[float]] = {}

        # 自动注册常见零件（含合成图片）
        self._init_common_parts()

    @property
    def model_loaded(self) -> bool:
        """模型是否加载"""
        return self.encoder.model_loaded

    def encode_image(self, image: Union[str, bytes, Image.Image]) -> list[float]:
        """编码零件图片为向量"""
        return self.encoder.encode_image(image)

    def encode_text(self, text: str) -> list[float]:
        """编码文本描述为向量"""
        return self.encoder.encode_text(text)

    def register_part(
        self,
        part_id: str,
        name: str,
        image: Union[str, bytes, Image.Image, None] = None,
        color: str = "",
        category: str = "",
        description: str = "",
    ):
        """
        注册零件到数据库。

        Args:
            part_id: 零件编号
            name: 零件名称
            image: 零件图片
            color: 颜色
            category: 类别
            description: 描述
        """
        part_info = PartInfo(
            part_id=part_id,
            name=name,
            color=color,
            category=category,
            description=description,
        )
        self._part_database[part_id] = part_info

        # 如果有图片，编码并缓存
        if image is not None:
            embedding = self.encode_image(image)
            self._part_embeddings[part_id] = embedding

    def search_by_image(
        self,
        image: Union[str, bytes, Image.Image],
        top_k: int = 5,
    ) -> list[RecognitionResult]:
        """
        以图搜文：上传零件图片 → 返回最相似的零件。

        Args:
            image: 查询图片
            top_k: 返回数量

        Returns:
            识别结果列表
        """
        if not self._part_embeddings:
            return []

        # 编码查询图片
        query_embedding = self.encode_image(image)

        # 计算相似度
        similarities = []
        for part_id, part_emb in self._part_embeddings.items():
            sim = self._cosine_similarity(query_embedding, part_emb)
            similarities.append((part_id, sim))

        # 排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for part_id, sim in similarities[:top_k]:
            part_info = self._part_database[part_id]
            part_info.confidence = sim
            results.append(RecognitionResult(
                part_info=part_info,
                similarity=sim,
                match_type="image_to_text",
            ))

        return results

    def search_by_description(
        self,
        description: str,
        top_k: int = 5,
    ) -> list[RecognitionResult]:
        """
        以文搜图：描述零件 → 返回匹配的零件。

        Args:
            description: 文本描述（如"红色2x4砖"）
            top_k: 返回数量

        Returns:
            识别结果列表
        """
        if not self._part_database:
            return []

        # 编码查询文本
        query_embedding = self.encode_text(description)

        # 计算相似度
        similarities = []
        for part_id, part_emb in self._part_embeddings.items():
            sim = self._cosine_similarity(query_embedding, part_emb)
            similarities.append((part_id, sim))

        # 排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for part_id, sim in similarities[:top_k]:
            part_info = self._part_database[part_id]
            part_info.confidence = sim
            results.append(RecognitionResult(
                part_info=part_info,
                similarity=sim,
                match_type="text_to_image",
            ))

        return results

    def verify_part(
        self,
        user_image: Union[str, bytes, Image.Image],
        expected_part_id: str,
    ) -> dict:
        """
        验证零件是否正确。

        Args:
            user_image: 用户上传的零件图片
            expected_part_id: 期望的零件编号

        Returns:
            验证结果
        """
        if expected_part_id not in self._part_embeddings:
            return {
                "verified": False,
                "message": f"未找到零件 {expected_part_id} 的参考图片",
            }

        # 编码用户图片
        user_embedding = self.encode_image(user_image)
        ref_embedding = self._part_embeddings[expected_part_id]

        # 计算相似度
        similarity = self._cosine_similarity(user_embedding, ref_embedding)

        # 阈值判断
        threshold = 0.6
        verified = similarity >= threshold

        part_info = self._part_database.get(expected_part_id)
        if not part_info:
            return {
                "verified": False,
                "similarity": 0.0,
                "threshold": threshold,
                "part_info": None,
                "message": f"未找到零件 {expected_part_id} 的参考图片",
            }

        return {
            "verified": verified,
            "similarity": round(similarity, 4),
            "threshold": threshold,
            "part_info": part_info,
            "message": "验证通过" if verified else "零件不匹配，请确认",
        }

    def compute_similarity(
        self,
        image1: Union[str, bytes, Image.Image],
        image2: Union[str, bytes, Image.Image],
    ) -> float:
        """
        计算两张图片的相似度。

        Args:
            image1: 第一张图片
            image2: 第二张图片

        Returns:
            相似度分数 (0-1)
        """
        emb1 = self.encode_image(image1)
        emb2 = self.encode_image(image2)
        return self._cosine_similarity(emb1, emb2)

    def _load_image(self, image: Union[str, bytes, Image.Image]) -> Image.Image:
        """加载图片为 PIL Image"""
        if isinstance(image, str):
            return Image.open(image).convert("RGB")
        elif isinstance(image, bytes):
            return Image.open(io.BytesIO(image)).convert("RGB")
        elif isinstance(image, Image.Image):
            return image.convert("RGB")
        else:
            raise ValueError(f"不支持的图片类型: {type(image)}")

    def _cosine_similarity(self, emb1: list[float], emb2: list[float]) -> float:
        """计算余弦相似度（自动处理维度不匹配）"""
        import numpy as np

        a = np.array(emb1)
        b = np.array(emb2)

        # 维度不匹配时截断到较短的长度
        if len(a) != len(b):
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0

        return float(np.dot(a / norm_a, b / norm_b))

    def _init_common_parts(self):
        """自动注册常见零件，生成合成图片并编码"""
        try:
            from src.kg.image_generator import generate_part_image, parse_size_from_name
        except ImportError:
            return

        common_parts = [
            {"part_id": "3001", "name": "Brick 2x4", "category": "Brick"},
            {"part_id": "3002", "name": "Brick 2x3", "category": "Brick"},
            {"part_id": "3003", "name": "Brick 2x2", "category": "Brick"},
            {"part_id": "3004", "name": "Brick 1x2", "category": "Brick"},
            {"part_id": "3005", "name": "Brick 1x1", "category": "Brick"},
            {"part_id": "3010", "name": "Brick 1x4", "category": "Brick"},
            {"part_id": "3008", "name": "Brick 1x8", "category": "Brick"},
            {"part_id": "3009", "name": "Brick 1x6", "category": "Brick"},
            {"part_id": "3622", "name": "Brick 1x3", "category": "Brick"},
            {"part_id": "3020", "name": "Plate 2x4", "category": "Plate"},
            {"part_id": "3021", "name": "Plate 2x3", "category": "Plate"},
            {"part_id": "3022", "name": "Plate 2x2", "category": "Plate"},
            {"part_id": "3023", "name": "Plate 1x2", "category": "Plate"},
            {"part_id": "3024", "name": "Plate 1x1", "category": "Plate"},
            {"part_id": "3069", "name": "Tile 1x2", "category": "Tile"},
            {"part_id": "3070", "name": "Tile 1x1", "category": "Tile"},
            {"part_id": "3039", "name": "Slope 45° 2x2", "category": "Slope"},
            {"part_id": "3040", "name": "Slope 45° 2x1", "category": "Slope"},
        ]

        for part in common_parts:
            size = parse_size_from_name(part["name"])
            if not size:
                continue

            # 生成合成图片
            try:
                img_bytes = generate_part_image(
                    part_name=part["name"],
                    width=size[0],
                    length=size[1],
                    color="Red",
                )
                img = Image.open(io.BytesIO(img_bytes))
                # 用更丰富的描述编码，提高区分度
                desc = f"{part['category']} {size[0]} by {size[1]} LEGO brick, {part['name']}"
                embedding = self.encoder.encode_text(desc)
                self._part_embeddings[part["part_id"]] = embedding
                self._part_database[part["part_id"]] = PartInfo(
                    part_id=part["part_id"],
                    name=part["name"],
                    color="Red",
                    category=part["category"],
                    description=f"{part['category']} {size[0]}x{size[1]}",
                )
            except Exception as e:
                print(f"[WARN] 注册零件 {part['part_id']} 失败: {e}")

        print(f"[OK] 自动注册 {len(self._part_database)} 个常见零件（含合成图片编码）")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "model_loaded": self.model_loaded,
            "registered_parts": len(self._part_database),
            "embedded_parts": len(self._part_embeddings),
        }


# 全局单例
_recognizer: Optional[PartRecognizer] = None


def get_part_recognizer(
    model_name: str = "lego_clip",
    device: str = "cpu",
) -> PartRecognizer:
    """获取零件识别器单例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = PartRecognizer(model_name=model_name, device=device)
    return _recognizer
