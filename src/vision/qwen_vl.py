"""Qwen-VL 多模态视觉解析模块"""

import base64
from typing import Any
from dashscope import MultiModalConversation
from src.common.config import get_settings


# 结构化输出的 JSON Schema
PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "零件名称"},
                    "color": {"type": "string", "description": "颜色"},
                    "quantity": {"type": "integer", "description": "数量"},
                },
                "required": ["name", "color", "quantity"],
            },
        },
        "colors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "图中出现的所有颜色",
        },
        "step_number": {
            "type": "integer",
            "description": "如果能识别到步骤号，否则为 null",
        },
        "confidence": {
            "type": "number",
            "description": "整体置信度 0-1",
        },
    },
    "required": ["parts", "colors", "step_number", "confidence"],
}

SYSTEM_PROMPT = """你是一个乐高零件识别专家。
请仔细分析用户提供的乐高图片，识别其中的零件、颜色、步骤号。
输出必须严格遵循 JSON 格式，不要包含任何额外文字。
如果无法识别某字段，confidence 应该低于 0.7。
"""


def _encode_image(image_path: str) -> str:
    """将本地图片转为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_lego_image(image_path: str) -> dict[str, Any]:
    """
    调用 Qwen-VL 解析乐高图片

    Args:
        image_path: 本地图片路径

    Returns:
        结构化解析结果
    """
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")

    # 构建多模态消息
    image_base64 = _encode_image(image_path)
    messages = [
        {
            "role": "system",
            "content": [{"text": SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [
                {"image": f"data:image/jpeg;base64,{image_base64}"},
                {"text": "请识别这张乐高图片中的零件、颜色、步骤号，输出 JSON。"},
            ],
        },
    ]

    # 调用 Qwen-VL-Plus
    response = MultiModalConversation.call(
        model="qwen-vl-plus",
        api_key=settings.dashscope_api_key,
        messages=messages,
        result_format="message",
    )

    # 解析响应
    if response.status_code != 200:
        raise RuntimeError(f"Qwen-VL 调用失败: {response.message}")

    content = response.output.choices[0].message.content
    # 提取 JSON（模型可能返回 markdown 代码块）
    json_str = _extract_json(content[0]["text"])
    import json
    result = json.loads(json_str)

    # 置信度检查
    if result.get("confidence", 0) < 0.7:
        result["needs_retry"] = True

    return result


def _extract_json(text: str) -> str:
    """从模型输出中提取 JSON"""
    text = text.strip()
    # 去除 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉第一行和最后一行
        text = "\n".join(lines[1:-1])
    return text


# 保留 Mock 版本用于测试
def parse_lego_image_mock(image_path: str) -> dict[str, Any]:
    """Mock 版本，不调用真实 API"""
    return {
        "parts": [
            {"name": "2x4 Brick", "color": "Red", "quantity": 2},
            {"name": "1x2 Plate", "color": "Blue", "quantity": 1},
        ],
        "colors": ["Red", "Blue"],
        "step_number": 15,
        "confidence": 0.92,
        "needs_retry": False,
    }
