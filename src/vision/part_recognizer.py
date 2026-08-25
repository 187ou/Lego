"""乐高零件识别器

使用乐高专用微调的 CLIP 模型进行零件识别。
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
import base64
from typing import Optional, Union
from dataclasses import dataclass, field
from PIL import Image


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
    """乐高零件识别器"""

    # Hugging Face 上的乐高专用 CLIP 模型
    LEGO_CLIP_MODELS = {
        "base": "JunkGao/clip-vit-base-patch32_lego-brick",
        "finetuned_v1": "JunkGao/clip-vit-base-patch32_lego-finetuned",
        "finetuned_v2": "JunkGao/clip-vit-base-patch32_lego-v2",
    }

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        use_fallback: bool = True,
    ):
        """
        Args:
            model_name: 模型名称 ("base", "finetuned_v1", "finetuned_v2", 或 HF 路径)
            device: 运行设备 ("cpu", "cuda")
            use_fallback: 乐高模型加载失败时是否回退到标准 CLIP
        """
        self.device = device
        self.use_fallback = use_fallback
        self.model = None
        self.processor = None
        self.model_loaded = False

        # 零件数据库（内存缓存）
        self._part_database: dict[str, PartInfo] = {}
        self._part_embeddings: dict[str, list[float]] = {}

        self._load_model(model_name)

    def _load_model(self, model_name: str):
        """加载 CLIP 模型"""
        try:
            from transformers import CLIPModel, CLIPProcessor

            # 获取模型 ID
            model_id = self.LEGO_CLIP_MODELS.get(model_name, model_name)

            print(f"[INFO] 加载 CLIP 模型: {model_id}")
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model = CLIPModel.from_pretrained(model_id).to(self.device)
            self.model.eval()
            self.model_loaded = True
            print(f"[OK] CLIP 模型加载成功")
        except Exception as e:
            print(f"[WARN] 乐高 CLIP 加载失败: {e}")
            if self.use_fallback:
                print("[INFO] 回退到标准 CLIP 模型")
                self._load_standard_clip()
            else:
                print("[WARN] 零件识别功能将使用 Mock 模式")

    def _load_standard_clip(self):
        """加载标准 CLIP 模型"""
        try:
            from transformers import CLIPModel, CLIPProcessor

            model_id = "openai/clip-vit-base-patch32"
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model = CLIPModel.from_pretrained(model_id).to(self.device)
            self.model.eval()
            self.model_loaded = True
            print(f"[OK] 标准 CLIP 模型加载成功")
        except Exception as e:
            print(f"[WARN] 标准 CLIP 也加载失败: {e}")
            self.model_loaded = False

    def encode_image(self, image: Union[str, bytes, Image.Image]) -> list[float]:
        """
        编码零件图片为向量。

        Args:
            image: 图片路径/PIL Image/bytes

        Returns:
            图片向量
        """
        if not self.model_loaded:
            return self._mock_embedding()

        # 加载图片
        img = self._load_image(image)

        # 编码
        import torch

        inputs = self.processor(images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)

        # 归一化
        embedding = outputs.cpu().numpy()[0]
        embedding = embedding / (embedding.norm() + 1e-8)

        return embedding.tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        编码文本描述为向量。

        Args:
            text: 文本描述

        Returns:
            文本向量
        """
        if not self.model_loaded:
            return self._mock_embedding()

        import torch

        inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)

        embedding = outputs.cpu().numpy()[0]
        embedding = embedding / (embedding.norm() + 1e-8)

        return embedding.tolist()

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
        threshold = 0.75
        verified = similarity >= threshold

        part_info = self._part_database[expected_part_id]

        return {
            "verified": verified,
            "similarity": similarity,
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
        """计算余弦相似度"""
        import numpy as np
        return float(np.dot(emb1, emb2))

    def _mock_embedding(self) -> list[float]:
        """
        Mock 向量（模型未加载时使用）。

        使用固定种子确保同一输入产生相同输出。
        """
        import random
        # 使用固定种子，确保结果可复现
        rng = random.Random(42)
        return [rng.random() for _ in range(512)]

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
    model_name: str = "base",
    device: str = "cpu",
) -> PartRecognizer:
    """获取零件识别器单例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = PartRecognizer(model_name=model_name, device=device)
    return _recognizer
