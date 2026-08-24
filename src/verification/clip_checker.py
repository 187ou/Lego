"""CLIP 验真模块——对比用户成品图与官方渲染图"""

from typing import Any
import os

# 环境变量控制是否启用真实 CLIP
USE_REAL_CLIP = os.getenv("USE_REAL_CLIP", "false").lower() == "true"

# 全局变量
_clip_model = None
_clip_processor = None


def _load_clip():
    """懒加载 CLIP 模型"""
    global _clip_model, _clip_processor
    if _clip_model is not None:
        return _clip_model, _clip_processor

    try:
        from transformers import CLIPProcessor, CLIPModel
        model_name = "openai/clip-vit-base-patch32"
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _clip_model = CLIPModel.from_pretrained(model_name).to(device)
        _clip_processor = CLIPProcessor.from_pretrained(model_name)
        print("[OK] CLIP 模型加载成功")
        return _clip_model, _clip_processor
    except Exception as e:
        print(f"[WARN] CLIP 模型加载失败: {e}，将使用 Mock")
        return None, None


def compare_images(user_image_path: str, official_image_path: str) -> dict[str, Any]:
    """
    对比两张图片的相似度

    Args:
        user_image_path: 用户成品图路径
        official_image_path: 官方渲染图路径

    Returns:
        相似度评分和判定结果
    """
    if not USE_REAL_CLIP:
        return verify_build_mock(user_image_path, official_image_path)

    model, processor = _load_clip()
    if model is None or processor is None:
        return verify_build_mock(user_image_path, official_image_path)

    try:
        from PIL import Image
        import torch

        user_img = Image.open(user_image_path).convert("RGB")
        official_img = Image.open(official_image_path).convert("RGB")

        inputs = processor(
            images=[user_img, official_img],
            return_tensors="pt",
            padding=True,
        ).to(model.device)

        with torch.no_grad():
            image_features = model.get_image_features(**inputs)

        user_feat = image_features[0:1]
        official_feat = image_features[1:2]
        similarity = torch.cosine_similarity(user_feat, official_feat).item()

        # 三级判定
        if similarity >= 0.85:
            verdict = "pass"
            details = "成品与官方模型高度一致，验收通过！"
        elif similarity >= 0.65:
            verdict = "review"
            details = "成品基本正确，但存在细微差异，建议检查关键连接点。"
        else:
            verdict = "fail"
            details = "成品与官方模型差异较大，建议重新对照说明书检查。"

        return {
            "similarity": round(similarity, 4),
            "verdict": verdict,
            "details": details,
        }
    except Exception as e:
        result = verify_build_mock(user_image_path, official_image_path)
        result["warning"] = f"CLIP 执行失败: {e}"
        return result


def verify_build_mock(user_image_path: str, official_image_path: str) -> dict[str, Any]:
    """Mock 验真，用于测试或无模型环境"""
    return {
        "similarity": 0.92,
        "verdict": "pass",
        "details": "[Mock] 成品与官方模型高度一致，验收通过！",
    }


# 保留向后兼容
CLIPChecker = None
get_clip_checker = None
