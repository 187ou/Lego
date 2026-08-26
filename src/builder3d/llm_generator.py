"""LLM 驱动的 3D 积木模型生成器"""

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

SYSTEM_PROMPT = """你是乐高积木 3D 模型生成器。根据用户描述，生成积木坐标数据。

## 可用零件
| part_id | 名称 | 尺寸(x*z) |
|---------|------|-----------|
| 3001 | Brick 2x4 | 2x4 |
| 3002 | Brick 2x3 | 2x3 |
| 3003 | Brick 2x2 | 2x2 |
| 3004 | Brick 1x2 | 1x2 |
| 3005 | Brick 1x1 | 1x1 |
| 3010 | Brick 1x4 | 1x4 |
| 3020 | Plate 2x4 | 2x4(薄) |
| 3023 | Plate 1x2 | 1x2(薄) |
| 3622 | Brick 1x3 | 1x3 |

## 坐标系
- x: 左右（整数，0 开始）
- y: 上下（整数，0=底层）
- z: 前后（整数，0 开始）

## 物理规则
1. y=0 的积木放在底板上
2. 上层积木下方必须有支撑
3. 不能悬空超50%
4. 坐标必须整数

## 输出（严格JSON，无注释）
```json
{
  "bricks": [
    {"part_id": "3001", "color": "Red", "position": {"x": 0, "y": 0, "z": 0}}
  ],
  "base_plate": {"width": 16, "length": 16}
}
```
只输出JSON，不要解释。"""


class LLMModelGenerator:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def generate(self, description: str, base_width: int = 16, base_length: int = 16) -> dict:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"描述: {description}\n底板: {base_width}x{base_length}"),
        ]
        try:
            response = self.llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            return self._parse_response(raw, base_width, base_length)
        except Exception as e:
            return self._fallback(description, base_width, base_length, str(e))

    def _parse_response(self, raw: str, bw: int, bl: int) -> dict:
        json_str = self._extract_json(raw)
        if not json_str:
            return self._fallback("no JSON", bw, bl)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return self._fallback("bad JSON", bw, bl)

        bricks_raw = data.get("bricks", [])
        if not bricks_raw:
            return self._fallback("empty", bw, bl)

        bricks, errors = [], []
        for i, b in enumerate(bricks_raw):
            try:
                pid = str(b.get("part_id", "")).strip()
                if not re.match(r"^\d{4,5}$", pid):
                    errors.append(f"brick[{i}]: bad part_id '{pid}'"); continue
                pos = b.get("position", {})
                bricks.append({
                    "part_id": pid,
                    "color": str(b.get("color", "Red")).strip(),
                    "position": {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0)), "z": int(pos.get("z", 0))},
                })
            except (ValueError, TypeError) as e:
                errors.append(f"brick[{i}]: {e}")

        if not bricks:
            return self._fallback("no valid", bw, bl)
        return self._build_model(bricks, bw, bl, errors)

    def _build_model(self, bricks: list[dict], bw: int, bl: int, errors: list[str] | None = None) -> dict:
        layers: dict[int, list] = {}
        for b in bricks:
            y = b["position"]["y"]
            layers.setdefault(y, []).append(b)

        steps = []
        for y in sorted(layers.keys()):
            step_bricks = []
            for i, b in enumerate(layers[y]):
                sz = _PART_SIZES.get(b["part_id"], {"x": 2, "y": 1, "z": 2})
                step_bricks.append({
                    "id": f"step{y + 1}-brick{i}",
                    "partId": b["part_id"],
                    "name": _PART_NAMES.get(b["part_id"], f"Part {b['part_id']}"),
                    "color": _COLOR_HEX.get(b["color"].title(), _COLOR_HEX.get(b["color"], "#808080")),
                    "colorName": b["color"],
                    "size": sz,
                    "position": b["position"],
                })
            steps.append({
                "stepNumber": y + 1,
                "description": f"第 {y + 1} 层，{len(step_bricks)} 块",
                "bricksToAdd": step_bricks,
            })

        return {
            "setId": "llm-generated",
            "setName": "AI Generated",
            "totalSteps": len(steps),
            "totalBricks": len(bricks),
            "basePlate": {"width": bw, "length": bl},
            "steps": steps,
            "source": "llm",
            "errors": errors or [],
        }

    def _extract_json(self, raw: str) -> str | None:
        try:
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            pass
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return m.group(0) if m else None

    def _fallback(self, desc: str, bw: int, bl: int, err: str = "") -> dict:
        bricks = [{
            "id": "fallback-0", "partId": "3001", "name": "Brick 2x4",
            "color": "#E3000B", "colorName": "Red",
            "size": {"x": 2, "y": 1, "z": 4}, "position": {"x": 0, "y": 0, "z": 0},
        }]
        return {
            "setId": "llm-fallback", "setName": "Fallback", "totalSteps": 1,
            "totalBricks": 1, "basePlate": {"width": bw, "length": bl},
            "steps": [{"stepNumber": 1, "description": "基础层", "bricksToAdd": bricks}],
            "source": "llm", "errors": [f"LLM failed: {err}, using fallback"],
        }


_PART_SIZES = {
    "3001": {"x": 2, "y": 1, "z": 4}, "3002": {"x": 2, "y": 1, "z": 3},
    "3003": {"x": 2, "y": 1, "z": 2}, "3004": {"x": 1, "y": 1, "z": 2},
    "3005": {"x": 1, "y": 1, "z": 1}, "3010": {"x": 1, "y": 1, "z": 4},
    "3020": {"x": 2, "y": 1, "z": 4}, "3023": {"x": 1, "y": 1, "z": 2},
    "3622": {"x": 1, "y": 1, "z": 3},
}
_PART_NAMES = {
    "3001": "Brick 2x4", "3002": "Brick 2x3", "3003": "Brick 2x2",
    "3004": "Brick 1x2", "3005": "Brick 1x1", "3010": "Brick 1x4",
    "3020": "Plate 2x4", "3023": "Plate 1x2", "3622": "Brick 1x3",
}
_COLOR_HEX = {
    "Red": "#E3000B", "Blue": "#0055BF", "Yellow": "#F5CD2F",
    "Green": "#00852B", "White": "#F4F4F4", "Black": "#1B2A34",
    "Gray": "#8A9299", "Dark Red": "#720E0F", "Dark Blue": "#0A3463",
    "Orange": "#FE8A18", "Tan": "#E4CD9E", "Brown": "#583927",
}


def get_generator(llm: BaseChatModel = None) -> LLMModelGenerator:
    if llm is None:
        from langchain_openai import ChatOpenAI
        from src.common.config import get_settings
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.7,
        )
    return LLMModelGenerator(llm=llm)
