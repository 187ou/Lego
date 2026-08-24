"""
Neo4j 数据导入脚本
运行方式：uv run python data/import_data.py
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge.neo4j_client import Neo4jClient


def seed_data():
    """导入示例数据"""
    with Neo4jClient() as client:
        # 初始化 schema
        client.init_schema()
        print("[OK] Schema 初始化完成")

        # 导入零件
        parts = [
            ("3001", "Brick 2x4", "Red", {"category": "Brick", "width": 4, "length": 2}),
            ("3001-blu", "Brick 2x4", "Blue", {"category": "Brick", "width": 4, "length": 2}),
            ("3001-dred", "Brick 2x4", "Dark Red", {"category": "Brick", "width": 4, "length": 2}),
            ("3001-wht", "Brick 2x4", "White", {"category": "Brick", "width": 4, "length": 2}),
            ("3002", "Brick 2x3", "Red", {"category": "Brick", "width": 3, "length": 2}),
            ("3003", "Brick 2x2", "Red", {"category": "Brick", "width": 2, "length": 2}),
            ("3005", "Brick 1x1", "Red", {"category": "Brick", "width": 1, "length": 1}),
            ("3020", "Plate 2x4", "Red", {"category": "Plate", "width": 4, "length": 2}),
            ("3020-blu", "Plate 2x4", "Blue", {"category": "Plate", "width": 4, "length": 2}),
            ("3023", "Plate 1x2", "Blue", {"category": "Plate", "width": 2, "length": 1}),
            ("3622", "Brick 1x3", "Red", {"category": "Brick", "width": 3, "length": 1}),
            ("3010", "Brick 1x4", "Red", {"category": "Brick", "width": 4, "length": 1}),
        ]

        for part_id, name, color, props in parts:
            client.import_part(part_id, name, color, **props)
        print(f"[OK] 导入 {len(parts)} 个零件")

        # 导入替代关系 (part_a -> part_b, confidence)
        alternatives = [
            # 同色同形状 = 完全匹配
            ("3001", "3001-blu", 1.0, "same_shape"),
            # 同形状不同色 = 高匹配
            ("3001", "3001-dred", 0.8, "color_diff"),
            ("3001", "3001-wht", 0.8, "color_diff"),
            # 相似形状 = 中等匹配
            ("3001", "3002", 0.6, "similar_shape"),
            ("3001", "3003", 0.5, "similar_shape"),
            # 同色不同形状 = 低匹配
            ("3001", "3622", 0.3, "same_color"),
            ("3001", "3010", 0.3, "same_color"),
            # 跨类型替代
            ("3020", "3020-blu", 1.0, "same_shape"),
            ("3020", "3023", 0.6, "similar_plate"),
        ]

        for a, b, conf, source in alternatives:
            client.import_alternative(a, b, conf, source)
        print(f"[OK] 导入 {len(alternatives)} 条替代关系")


if __name__ == "__main__":
    seed_data()
    print("\n数据导入完成！")
