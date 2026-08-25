"""3D 拼装数据生成器

从图谱数据生成 3D 拼装模型。
如果图谱中没有数据，则生成模拟数据。
"""

import random
from typing import Any

# 标准乐高颜色
LEGO_COLORS = [
    {"name": "Red", "hex": "#E3000B"},
    {"name": "Blue", "hex": "#0055BF"},
    {"name": "Yellow", "hex": "#F5CD2F"},
    {"name": "Green", "hex": "#00852B"},
    {"name": "White", "hex": "#F4F4F4"},
    {"name": "Black", "hex": "#1B2A34"},
    {"name": "Light Gray", "hex": "#8A9299"},
    {"name": "Dark Gray", "hex": "#6C6E68"},
    {"name": "Orange", "hex": "#FE8A18"},
    {"name": "Cyan", "hex": "#00BCD4"},
]


def generate_build_model(set_id: str, set_name: str, total_steps: int) -> dict[str, Any]:
    """
    生成套装的 3D 拼装模型数据。

    优先从图谱获取真实数据，否则生成合理的模拟数据。
    """
    # 尝试从图谱获取
    model = _try_get_from_graph(set_id, set_name)
    if model:
        return model

    # 生成模拟数据
    return _generate_mock_model(set_id, set_name, total_steps)


def _try_get_from_graph(set_id: str, set_name: str) -> dict[str, Any] | None:
    """尝试从知识图谱获取拼装数据"""
    try:
        from src.kg.graph_retriever import get_graph_retriever
        retriever = get_graph_retriever()

        overview = retriever.get_set_overview(set_id)
        if not overview.get("found"):
            return None

        steps = []
        for step_num in range(1, min(overview.get("total_parts", 0) + 1, 100)):
            step_info = retriever.get_step_info(set_id, step_num)
            if not step_info.get("found"):
                break

            bricks = []
            for i, part in enumerate(step_info.get("parts", [])):
                color = random.choice(LEGO_COLORS)
                bricks.append({
                    "id": f"step{step_num}-brick{i}",
                    "partId": part.get("part_id", f"300{i}"),
                    "name": part.get("name", f"Brick {i+1}"),
                    "color": color["hex"],
                    "colorName": color["name"],
                    "size": {"x": 2, "y": 1, "z": 2},
                    "position": {"x": i * 2, "y": step_num - 1, "z": 0},
                })

            if bricks:
                steps.append({
                    "stepNumber": step_num,
                    "description": step_info["step"].get("description", f"步骤 {step_num}"),
                    "bricksToAdd": bricks,
                })

        if not steps:
            return None

        return {
            "setId": set_id,
            "setName": set_name,
            "totalSteps": len(steps),
            "totalBricks": sum(len(s["bricksToAdd"]) for s in steps),
            "basePlate": {"width": 8, "length": 8},
            "steps": steps,
        }
    except Exception as e:
        print(f"[WARN] 从图谱获取数据失败: {e}")
        return None


def _generate_mock_model(set_id: str, set_name: str, total_steps: int) -> dict[str, Any]:
    """生成模拟拼装数据"""
    steps = []
    brick_id_counter = 0

    for step_num in range(1, total_steps + 1):
        bricks = []
        # 每步 1-3 个积木
        num_bricks = min(random.randint(1, 3), 3)

        for i in range(num_bricks):
            color = random.choice(LEGO_COLORS)
            size_x = random.choice([1, 2, 2, 4])
            size_z = random.choice([1, 2, 2, 4])

            bricks.append({
                "id": f"brick-{brick_id_counter}",
                "partId": f"300{brick_id_counter % 10}",
                "name": f"Brick {size_x}x{size_z}",
                "color": color["hex"],
                "colorName": color["name"],
                "size": {"x": size_x, "y": 1, "z": size_z},
                "position": {
                    "x": i * 2,
                    "y": step_num - 1,
                    "z": 0,
                },
            })
            brick_id_counter += 1

        steps.append({
            "stepNumber": step_num,
            "description": _generate_step_description(step_num, total_steps, len(bricks)),
            "bricksToAdd": bricks,
        })

    return {
        "setId": set_id,
        "setName": set_name,
        "totalSteps": total_steps,
        "totalBricks": brick_id_counter,
        "basePlate": {"width": 8, "length": 8},
        "steps": steps,
    }


def _generate_step_description(step_num: int, total_steps: int, num_bricks: int) -> str:
    """生成步骤描述"""
    if step_num == 1:
        return "放置底板作为基础"
    elif step_num == total_steps:
        return f"最后一步，添加 {num_bricks} 块积木完成拼装"
    elif step_num <= 3:
        return f"建造第一层，放置 {num_bricks} 块积木"
    elif step_num >= total_steps - 2:
        return f"收尾阶段，添加 {num_bricks} 块积木"
    else:
        actions = ["添加", "安装", "放置", "拼接"]
        return f"{random.choice(actions)} {num_bricks} 块积木，继续向上建造"


# 全局缓存
_model_cache: dict[str, dict[str, Any]] = {}


def get_build_model(set_id: str, set_name: str = "", total_steps: int = 30) -> dict[str, Any]:
    """获取拼装模型（带缓存）"""
    if set_id in _model_cache:
        return _model_cache[set_id]

    model = generate_build_model(set_id, set_name or f"套装 {set_id}", total_steps)
    _model_cache[set_id] = model
    return model


def clear_cache():
    """清除缓存"""
    _model_cache.clear()
