"""视觉模块

包含：
- 零件识别器（CLIP 模型）
- 多模态视觉解析（Qwen-VL / GPT-4o / Ollama）
- CLIP 验成品对比
"""

from src.vision.part_recognizer import PartRecognizer, PartInfo, RecognitionResult, get_part_recognizer
from src.vision.part_database import PartDatabaseBuilder, build_default_database

__all__ = [
    "PartRecognizer",
    "PartInfo",
    "RecognitionResult",
    "get_part_recognizer",
    "PartDatabaseBuilder",
    "build_default_database",
]


def __getattr__(name):
    """延迟导入，避免强制依赖"""
    if name == "parse_lego_image":
        from src.vision.qwen_vl import parse_lego_image
        return parse_lego_image
    if name == "parse_lego_image_mock":
        from src.vision.qwen_vl import parse_lego_image_mock
        return parse_lego_image_mock
    raise AttributeError(f"module 'src.vision' has no attribute '{name}'")
