"""合成零件图片生成器

为知识图谱中的零件生成合成图片，用于跨模态搜索。
使用 Pillow 绘制简化的零件俯视图（矩形+凸点）。
"""

import io
import os
from typing import Union

from PIL import Image, ImageDraw

# 标准乐高颜色映射
LEGO_COLORS = {
    "Red": "#E3000B", "Blue": "#0055BF", "Yellow": "#F5CD2F",
    "Green": "#00852B", "White": "#F4F4F4", "Black": "#1B2A34",
    "Gray": "#8A9299", "Dark Gray": "#6C6E68", "Light Gray": "#A0A5A9",
    "Orange": "#FE8A18", "Cyan": "#00BCD4", "Pink": "#F785B1",
    "Purple": "#8B4789", "Brown": "#583927", "Tan": "#E4CD9E",
    "Dark Red": "#720E0F", "Dark Blue": "#0A3463", "Lime": "#BBE90B",
    "Transparent": "#C9E4F0",
}


def generate_part_image(
    part_name: str,
    width: int = 2,
    length: int = 4,
    color: str = "Red",
    dpi: int = 100,
) -> bytes:
    """
    生成零件俯视图（PNG bytes）。

    Args:
        part_name: 零件名称
        width: 宽度（凸点数）
        length: 长度（凸点数）
        color: 颜色名称
        dpi: 分辨率

    Returns:
        PNG 图片 bytes
    """
    # 画布尺寸
    stud_size = dpi // 2  # 每个凸点的间距
    margin = stud_size // 2
    img_w = (width * stud_size) + 2 * margin
    img_h = (length * stud_size) + 2 * margin

    # 颜色
    hex_color = LEGO_COLORS.get(color, "#808080")
    # 稍深的边框色
    border_color = _darken_color(hex_color, 0.7)
    # 稍亮的高光色
    highlight_color = _lighten_color(hex_color, 1.2)

    img = Image.new("RGB", (max(img_w, 20), max(img_h, 20)), hex_color)
    draw = ImageDraw.Draw(img)

    # 绘制外边框
    draw.rectangle(
        [margin - 1, margin - 1, img_w - margin, img_h - margin],
        outline=border_color,
        width=2,
    )

    # 绘制凸点（studs）
    stud_radius = max(stud_size // 3, 3)
    for row in range(length):
        for col in range(width):
            cx = margin + col * stud_size + stud_size // 2
            cy = margin + row * stud_size + stud_size // 2

            # 凸点圆形
            draw.ellipse(
                [cx - stud_radius, cy - stud_radius, cx + stud_radius, cy + stud_radius],
                fill=highlight_color,
                outline=border_color,
                width=1,
            )

    # 转为 bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _darken_color(hex_color: str, factor: float) -> str:
    """将颜色变暗"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = max(0, int(r * factor))
    g = max(0, int(g * factor))
    b = max(0, int(b * factor))
    return f"#{r:02X}{g:02X}{b:02X}"


def _lighten_color(hex_color: str, factor: float) -> str:
    """将颜色变亮"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02X}{g:02X}{b:02X}"


def save_part_image(
    image_bytes: bytes,
    output_dir: str,
    part_id: str,
    color: str = "",
) -> str:
    """
    保存零件图片到文件系统。

    Returns:
        相对路径
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{part_id}_{color}.png" if color else f"{part_id}.png"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath


def parse_size_from_name(part_name: str) -> tuple[int, int] | None:
    """从零件名称解析尺寸"""
    import re
    match = re.search(r"(\d+)\s*[x×]\s*(\d+)", part_name)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return None
