"""Ollama 本地视觉解析模块"""

import base64
import json
from typing import Any
from openai import OpenAI
from src.common.config import get_settings

SYSTEM_PROMPT = """你是一个乐高零件识别专家。
请仔细分析用户提供的乐高图片，识别其中的零件、颜色、步骤号。
输出必须严格遵循 JSON 格式，不要包含任何额外文字。
如果无法识别某字段，confidence 应该低于 0.7。

JSON 格式：
{
  "parts": [{"name": "零件名", "color": "颜色", "quantity": 数量}],
  "colors": ["颜色1", "颜色2"],
  "step_number": 步骤号或null,
  "confidence": 0.0-1.0
}
"""


def _encode_image(image_path: str) -> str:
    """将本地图片转为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_lego_image(image_path: str) -> dict[str, Any]:
    """
    调用 Ollama 本地视觉模型解析乐高图片

    Args:
        image_path: 本地图片路径

    Returns:
        结构化解析结果
    """
    settings = get_settings()
    image_base64 = _encode_image(image_path)

    # Ollama OpenAI 兼容格式（Ollama >= 0.1.24）
    client = OpenAI(
        api_key="ollama",  # Ollama 不校验 key，随便填
        base_url=settings.vision_base_url,
    )

    response = client.chat.completions.create(
        model=settings.vision_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                    {"type": "text", "text": "请识别这张乐高图片，输出 JSON。"},
                ],
            },
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content
    # 提取 JSON
    json_str = content.strip()
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1])

    result = json.loads(json_str)

    # 置信度检查
    if result.get("confidence", 0) < 0.7:
        result["needs_retry"] = True

    return result
