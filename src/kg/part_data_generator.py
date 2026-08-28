"""零件数据生成器 - 扩展知识库到 1000+ 零件

生成合成但合理的零件数据，包括：
- 几何属性（尺寸、凸点、连接类型）
- 物理属性（重量、强度）
- 商业属性（稀缺度、价格）
"""

import random
from typing import Optional
from src.kg.schema import PartGeometry, PartPhysics, PartCommercial


# 零件类别和命名规则
PART_CATEGORIES = {
    "Brick": {
        "prefixes": ["3001", "3002", "3003", "3004", "3005", "3006", "3007", "3008", "3009", "3010",
                     "3622", "3011", "3012", "3013", "3014", "3015", "3016", "3017", "3018", "3019"],
        "sizes": [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10), (1, 12),
                  (2, 2), (2, 3), (2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (2, 16)],
        "height": 9.6,
        "weight_per_stud": 0.3,
        "strength": 0.85,
    },
    "Plate": {
        "prefixes": ["3020", "3021", "3022", "3023", "3024", "3031", "3032", "3034", "3035", "3036",
                     "3037", "3038", "3039", "3040", "3041", "3042", "3043", "3044", "3045", "3046"],
        "sizes": [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10), (1, 12),
                  (2, 2), (2, 3), (2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (2, 16),
                  (3, 3), (3, 4), (3, 6), (3, 8), (4, 4), (4, 6), (4, 8), (4, 10), (4, 12),
                  (6, 6), (6, 8), (6, 10), (6, 12), (6, 14), (6, 16), (8, 8), (8, 12), (8, 16)],
        "height": 3.2,
        "weight_per_stud": 0.15,
        "strength": 0.6,
    },
    "Tile": {
        "prefixes": ["3069", "3070", "3068", "3067", "3066", "3065", "3064", "3063", "3062", "3061"],
        "sizes": [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8),
                  (2, 2), (2, 3), (2, 4), (2, 6), (2, 8)],
        "height": 3.2,
        "weight_per_stud": 0.12,
        "strength": 0.4,
    },
    "Slope": {
        "prefixes": ["3039", "3040", "3048", "3049", "3050", "3051", "3052", "3053", "3054", "3055"],
        "sizes": [(1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2), (2, 3), (2, 4)],
        "height": 9.6,
        "weight_per_stud": 0.35,
        "strength": 0.7,
    },
    "Technic": {
        "prefixes": ["3700", "3701", "3702", "3703", "3704", "3705", "3706", "3707", "3708", "3709",
                     "3710", "3711", "3712", "3713", "3714", "3715", "3716", "3717", "3718", "3719"],
        "sizes": [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10), (1, 12)],
        "height": 9.6,
        "weight_per_stud": 0.4,
        "strength": 0.9,
    },
}

# 颜色库
COLORS = [
    "Red", "Blue", "Yellow", "Green", "White", "Black", "Gray", "Orange", "Brown", "Purple", "Pink",
    "Dark Red", "Dark Blue", "Dark Green", "Dark Gray", "Light Blue", "Light Green", "Light Gray",
    "Tan", "Lime", "Magenta", "Cyan", "Transparent", "Trans-Red", "Trans-Blue", "Trans-Green",
    "Trans-Yellow", "Trans-Clear", "Silver", "Gold", "Pearl Gold", "Pearl Silver",
    "Flat Dark Gold", "Metallic Green", "Satin White", "Glow In Dark White",
]

# 稀缺度分布
RARITY_WEIGHTS = {
    "common": 0.50,
    "uncommon": 0.25,
    "rare": 0.15,
    "very_rare": 0.10,
}

# 价格范围（按稀缺度）
PRICE_RANGES = {
    "common": (0.01, 0.10),
    "uncommon": (0.05, 0.25),
    "rare": (0.15, 1.00),
    "very_rare": (0.50, 5.00),
}


def generate_part_id(category: str, index: int) -> str:
    """生成零件 ID"""
    prefixes = PART_CATEGORIES[category]["prefixes"]
    if index < len(prefixes):
        return prefixes[index]
    # 生成新的 ID
    base = prefixes[0][:2]
    return f"{base}{100 + index:03d}"


def generate_part_name(category: str, size: tuple) -> str:
    """生成零件名称"""
    w, l = size
    if category == "Brick":
        return f"Brick {w}x{l}"
    elif category == "Plate":
        return f"Plate {w}x{l}"
    elif category == "Tile":
        return f"Tile {w}x{l}"
    elif category == "Slope":
        return f"Slope 45° {w}x{l}"
    elif category == "Technic":
        return f"Technic Brick {w}x{l}"
    return f"{category} {w}x{l}"


def generate_geometry(category: str, size: tuple) -> PartGeometry:
    """生成几何属性"""
    w, l = size
    cat_info = PART_CATEGORIES[category]
    studs = w * l

    # 连接类型
    if category == "Technic":
        connection = random.choice(["pin", "axle"])
    else:
        connection = "stud"

    return PartGeometry(
        width=w,
        length=l,
        height=cat_info["height"],
        studs=studs,
        pinholes=max(0, studs // 2) if category == "Technic" else 0,
        connection_type=connection,
    )


def generate_physics(category: str, size: str) -> PartPhysics:
    """生成物理属性"""
    cat_info = PART_CATEGORIES[category]
    w, l = size
    studs = w * l

    weight = round(studs * cat_info["weight_per_stud"] * random.uniform(0.8, 1.2), 2)
    strength = round(min(1.0, cat_info["strength"] * random.uniform(0.85, 1.0)), 2)

    return PartPhysics(
        material="ABS",
        weight=weight,
        strength=strength,
    )


def generate_commercial(category: str) -> PartCommercial:
    """生成商业属性"""
    rarity = random.choices(
        list(RARITY_WEIGHTS.keys()),
        weights=list(RARITY_WEIGHTS.values()),
    )[0]

    price_range = PRICE_RANGES[rarity]
    price = round(random.uniform(*price_range), 2)

    discontinued = random.random() < 0.15  # 15% 概率停产
    year = random.randint(1958, 2024)

    return PartCommercial(
        rarity=rarity,
        price=price,
        discontinued=discontinued,
        year_introduced=year,
    )


def generate_part_knowledge(part_id: str, category: str, size: tuple) -> dict:
    """生成完整零件知识"""
    return {
        "name": generate_part_name(category, size),
        "category": category,
        "geometry": generate_geometry(category, size),
        "physics": generate_physics(category, size),
        "commercial": generate_commercial(category),
    }


def generate_full_part_database(target_count: int = 1000) -> dict:
    """生成完整零件数据库

    Args:
        target_count: 目标零件数量

    Returns:
        {part_id: knowledge_dict}
    """
    database = {}
    categories = list(PART_CATEGORIES.keys())

    # 为每个类别生成零件
    per_category = target_count // len(categories)

    for category in categories:
        cat_info = PART_CATEGORIES[category]
        sizes = cat_info["sizes"]
        prefixes = cat_info["prefixes"]

        for i in range(per_category):
            # 循环使用尺寸和编号
            size = sizes[i % len(sizes)]
            prefix_idx = i % len(prefixes)

            # 生成唯一 ID
            if i < len(prefixes):
                part_id = prefixes[i]
            else:
                # 超出预定义编号范围，生成新 ID
                base = prefixes[0][:2]
                part_id = f"{base}{200 + i:03d}"

            # 避免重复
            original_id = part_id
            counter = 0
            while part_id in database:
                part_id = f"{original_id}_{counter}"
                counter += 1

            database[part_id] = generate_part_knowledge(part_id, category, size)

    return database


def generate_color_variants(part_database: dict, colors_per_part: int = 3) -> list[dict]:
    """为零件生成颜色变体

    Returns:
        [{"part_id": "3001", "color": "Red", "color_id": "color_Red"}, ...]
    """
    variants = []
    colors = random.sample(COLORS, min(colors_per_part * 3, len(COLORS)))

    for i, (part_id, knowledge) in enumerate(part_database.items()):
        selected_colors = random.sample(colors, min(colors_per_part, len(colors)))
        for color in selected_colors:
            variants.append({
                "part_id": part_id,
                "color": color,
                "color_id": f"color_{color.replace(' ', '_')}",
                "name": f"{knowledge['name']} ({color})",
            })

    return variants


# 预生成的 1000+ 零件数据库
_PART_DATABASE_CACHE: Optional[dict] = None


def get_extended_part_database(force_refresh: bool = False) -> dict:
    """获取扩展零件数据库（带缓存）"""
    global _PART_DATABASE_CACHE
    if _PART_DATABASE_CACHE is None or force_refresh:
        _PART_DATABASE_CACHE = generate_full_part_database(target_count=1000)
    return _PART_DATABASE_CACHE


if __name__ == "__main__":
    # 测试生成
    db = generate_full_part_database(1000)
    print(f"生成了 {len(db)} 个零件")

    # 统计
    categories = {}
    for part_id, knowledge in db.items():
        cat = knowledge["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("类别分布:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # 颜色变体
    variants = generate_color_variants(db, colors_per_part=2)
    print(f"生成了 {len(variants)} 个颜色变体")
