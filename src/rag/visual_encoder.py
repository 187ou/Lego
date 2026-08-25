"""视觉编码器

使用视觉 Embedding 模型（SigLIP/CLIP）将图片编码为向量，
支持以图搜文、以文搜图。

支持模型：
- SigLIP (推荐): 更好的零样本性能
- CLIP: 经典视觉-语言对齐模型
- LEGO 专用微调 CLIP: 乐高零件识别
"""

import io
import base64
from typing import Optional, Union
from PIL import Image


class VisualEncoder:
    """视觉编码器"""

    def __init__(
        self,
        model_name: str = "siglip",
        device: str = "cpu",
    ):
        """
        Args:
            model_name: 模型名称 ("siglip", "clip", "lego_clip")
            device: 运行设备 ("cpu", "cuda")
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.processor = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        if self.model_name == "siglip":
            self._load_siglip()
        elif self.model_name == "clip":
            self._load_clip()
        elif self.model_name == "lego_clip":
            self._load_lego_clip()
        else:
            raise ValueError(f"不支持的模型: {self.model_name}")

    def _load_siglip(self):
        """加载 SigLIP 模型"""
        try:
            from transformers import SiglipModel, SiglipProcessor

            model_id = "google/siglip-base-patch16-224"
            self.processor = SiglipProcessor.from_pretrained(model_id)
            self.model = SiglipModel.from_pretrained(model_id).to(self.device)
            self.model.eval()
            print(f"[OK] SigLIP 模型加载成功: {model_id}")
        except ImportError:
            raise ValueError(
                "加载 SigLIP 需要安装 transformers: pip install transformers"
            )

    def _load_clip(self):
        """加载 CLIP 模型"""
        try:
            from transformers import CLIPModel, CLIPProcessor

            model_id = "openai/clip-vit-base-patch32"
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model = CLIPModel.from_pretrained(model_id).to(self.device)
            self.model.eval()
            print(f"[OK] CLIP 模型加载成功: {model_id}")
        except ImportError:
            raise ValueError(
                "加载 CLIP 需要安装 transformers: pip install transformers"
            )

    def _load_lego_clip(self):
        """加载乐高专用微调 CLIP"""
        try:
            from transformers import CLIPModel, CLIPProcessor

            # Hugging Face 上的乐高微调 CLIP
            model_id = "JunkGao/clip-vit-base-patch32_lego-brick"
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model = CLIPModel.from_pretrained(model_id).to(self.device)
            self.model.eval()
            print(f"[OK] LEGO CLIP 模型加载成功: {model_id}")
        except ImportError:
            raise ValueError(
                "加载 CLIP 需要安装 transformers: pip install transformers"
            )
        except Exception as e:
            print(f"[WARN] LEGO CLIP 加载失败: {e}，回退到标准 CLIP")
            self._load_clip()

    def encode_image(self, image: Union[str, bytes, Image.Image]) -> list[float]:
        """
        编码图片为向量。

        Args:
            image: 图片路径/PIL Image/bytes

        Returns:
            图片向量
        """
        if self.model is None:
            return self._mock_embedding()

        # 加载图片
        if isinstance(image, str):
            img = Image.open(image).convert("RGB")
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image)).convert("RGB")
        elif isinstance(image, Image.Image):
            img = image.convert("RGB")
        else:
            raise ValueError(f"不支持的图片类型: {type(image)}")

        # 编码
        import torch

        inputs = self.processor(images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            if self.model_name == "siglip":
                outputs = self.model.get_image_features(**inputs)
            else:
                outputs = self.model.get_image_features(**inputs)

        # 归一化
        embedding = outputs.cpu().numpy()[0]
        embedding = embedding / (embedding.norm() + 1e-8)

        return embedding.tolist()

    def encode_text(self, text: str) -> list[float]:
        """
        编码文本为向量（用于以文搜图）。

        Args:
            text: 文本描述

        Returns:
            文本向量
        """
        if self.model is None:
            return self._mock_embedding()

        import torch

        inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            if self.model_name == "siglip":
                outputs = self.model.get_text_features(**inputs)
            else:
                outputs = self.model.get_text_features(**inputs)

        embedding = outputs.cpu().numpy()[0]
        embedding = embedding / (embedding.norm() + 1e-8)

        return embedding.tolist()

    def compute_similarity(
        self,
        image: Union[str, bytes, Image.Image],
        text: str,
    ) -> float:
        """
        计算图片和文本的相似度。

        Args:
            image: 图片
            text: 文本

        Returns:
            相似度分数 (0-1)
        """
        img_emb = self.encode_image(image)
        txt_emb = self.encode_text(text)

        # 余弦相似度
        import numpy as np
        similarity = np.dot(img_emb, txt_emb)
        return float(similarity)

    def _mock_embedding(self) -> list[float]:
        """
        Mock 向量（模型未加载时使用）。

        使用固定种子确保同一输入产生相同输出。
        """
        import random
        rng = random.Random(42)
        return [rng.random() for _ in range(768)]


# 全局单例
_encoder: Optional[VisualEncoder] = None


def get_visual_encoder(
    model_name: str = "siglip",
    device: str = "cpu",
) -> VisualEncoder:
    """获取视觉编码器单例"""
    global _encoder
    if _encoder is None:
        _encoder = VisualEncoder(model_name=model_name, device=device)
    return _encoder
