"""零件数据库构建器

从多种来源导入零件数据：
1. Rebrickable CSV 导出（零件清单）
2. 本地图片目录
3. 手动注册

支持批量导入和增量更新。
"""

import os
import csv
import json
from typing import Optional
from pathlib import Path

from src.vision.part_recognizer import PartRecognizer, PartInfo, get_part_recognizer


class PartDatabaseBuilder:
    """零件数据库构建器"""

    def __init__(self, recognizer: Optional[PartRecognizer] = None):
        self.recognizer = recognizer or get_part_recognizer()

    def import_from_csv(
        self,
        csv_path: str,
        image_dir: str = "",
    ) -> int:
        """
        从 CSV 文件导入零件。

        CSV 格式（Rebrickable 导出）：
        Part, Color, Category, Name, ImageURL, Quantity

        Args:
            csv_path: CSV 文件路径
            image_dir: 零件图片目录（可选）

        Returns:
            导入的零件数
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        imported = 0

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                part_id = row.get("Part", row.get("part_id", ""))
                name = row.get("Name", row.get("name", ""))
                color = row.get("Color", row.get("color", ""))
                category = row.get("Category", row.get("category", ""))

                if not part_id:
                    continue

                # 查找对应的图片
                image = None
                if image_dir:
                    image = self._find_part_image(image_dir, part_id, color)

                # 注册零件
                self.recognizer.register_part(
                    part_id=part_id,
                    name=name,
                    image=image,
                    color=color,
                    category=category,
                )
                imported += 1

        print(f"[OK] 从 CSV 导入 {imported} 个零件")
        return imported

    def import_from_directory(
        self,
        image_dir: str,
        set_id: str = "",
    ) -> int:
        """
        从图片目录导入零件。

        目录结构：
        image_dir/
          ├── 3001/
          │   ├── red.png
          │   ├── blue.png
          │   └── white.png
          ├── 3005/
          │   └── ...
          └── parts.json  (可选，零件名称映射)

        Args:
            image_dir: 图片目录
            set_id: 套装编号

        Returns:
            导入的零件数
        """
        if not os.path.isdir(image_dir):
            raise FileNotFoundError(f"目录不存在: {image_dir}")

        imported = 0

        # 加载零件名称映射（如有）
        names_map = {}
        names_file = os.path.join(image_dir, "parts.json")
        if os.path.exists(names_file):
            with open(names_file, "r", encoding="utf-8") as f:
                names_map = json.load(f)

        # 遍历子目录
        for part_dir in sorted(Path(image_dir).iterdir()):
            if not part_dir.is_dir():
                continue

            part_id = part_dir.name
            part_name = names_map.get(part_id, part_id)

            # 遍历该零件的所有颜色图片
            for img_file in sorted(part_dir.iterdir()):
                if img_file.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    color = img_file.stem  # 文件名作为颜色名

                    self.recognizer.register_part(
                        part_id=f"{part_id}_{color}",
                        name=part_name,
                        image=str(img_file),
                        color=color,
                    )
                    imported += 1

        print(f"[OK] 从目录导入 {imported} 个零件")
        return imported

    def import_common_parts(self) -> int:
        """
        导入常见零件（内置数据）。

        包含最常用的乐高零件，无需外部数据。
        """
        common_parts = [
            {"part_id": "3001", "name": "Brick 2x4", "category": "Brick"},
            {"part_id": "3002", "name": "Brick 2x3", "category": "Brick"},
            {"part_id": "3003", "name": "Brick 2x2", "category": "Brick"},
            {"part_id": "3005", "name": "Brick 1x1", "category": "Brick"},
            {"part_id": "3010", "name": "Brick 1x4", "category": "Brick"},
            {"part_id": "3020", "name": "Plate 2x4", "category": "Plate"},
            {"part_id": "3023", "name": "Plate 1x2", "category": "Plate"},
            {"part_id": "3622", "name": "Brick 1x3", "category": "Brick"},
            {"part_id": "3069", "name": "Tile 1x2", "category": "Tile"},
            {"part_id": "3070", "name": "Tile 1x1", "category": "Tile"},
            {"part_id": "3040", "name": "Slope 45° 2x1", "category": "Slope"},
            {"part_id": "3039", "name": "Slope 45° 2x2", "category": "Slope"},
            {"part_id": "3004", "name": "Brick 1x2", "category": "Brick"},
            {"part_id": "3009", "name": "Brick 1x6", "category": "Brick"},
            {"part_id": "3008", "name": "Brick 1x8", "category": "Brick"},
        ]

        for part in common_parts:
            self.recognizer.register_part(
                part_id=part["part_id"],
                name=part["name"],
                category=part["category"],
            )

        print(f"[OK] 导入 {len(common_parts)} 个常见零件")
        return len(common_parts)

    def _find_part_image(
        self,
        image_dir: str,
        part_id: str,
        color: str = "",
    ) -> Optional[str]:
        """查找零件图片"""
        # 尝试多种可能的文件名
        candidates = [
            os.path.join(image_dir, f"{part_id}.png"),
            os.path.join(image_dir, f"{part_id}.jpg"),
            os.path.join(image_dir, part_id, f"{color}.png"),
            os.path.join(image_dir, part_id, f"{color}.jpg"),
        ]

        for path in candidates:
            if os.path.exists(path):
                return path

        return None

    def export_database(self, output_path: str):
        """导出数据库到 JSON"""
        data = {
            "parts": {
                pid: {
                    "part_id": p.part_id,
                    "name": p.name,
                    "color": p.color,
                    "category": p.category,
                }
                for pid, p in self.recognizer._part_database.items()
            },
            "stats": self.recognizer.get_stats(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[OK] 数据库已导出到 {output_path}")


def build_default_database() -> PartRecognizer:
    """
    构建默认零件数据库。

    导入常见零件，无需外部数据。
    """
    recognizer = get_part_recognizer()
    builder = PartDatabaseBuilder(recognizer)
    builder.import_common_parts()
    return recognizer
