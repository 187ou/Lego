"""文字 → 3D 模型完整管线

组合 LLM 生成器 + 物理验证 + 自动修正。
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from src.builder3d.llm_generator import LLMModelGenerator
from src.builder3d.physics import PhysicsValidator
from src.builder3d.auto_fixer import AutoFixer


class ModelGenerationPipeline:
    def __init__(self, llm: BaseChatModel):
        self.generator = LLMModelGenerator(llm)
        self.validator = PhysicsValidator()
        self.fixer = AutoFixer()

    def generate(
        self,
        description: str,
        max_attempts: int = 3,
        base_width: int = 16,
        base_length: int = 16,
    ) -> dict[str, Any]:
        """
        完整管线：生成 → 验证 → 修正循环。

        Returns:
            BuildModel + 生成日志
        """
        log = []
        model = None

        for attempt in range(max_attempts):
            log.append(f"[attempt {attempt + 1}] Generating...")

            # 生成
            if attempt == 0:
                model = self.generator.generate(description, base_width, base_length)
            else:
                # 后续尝试加入修正后的数据
                model = self.generator.generate(
                    description + " (revised)", base_width, base_length
                )

            log.append(f"[attempt {attempt + 1}] Generated {model['totalBricks']} bricks")

            # 提取零件
            bricks = []
            for step in model["steps"]:
                for b in step["bricksToAdd"]:
                    bricks.append({
                        "position": b["position"],
                        "size": b["size"],
                    })

            # 验证
            result = self.validator.validate(bricks, model["basePlate"])
            log.append(
                f"[attempt {attempt + 1}] Validation: stable={result['stable']}, "
                f"issues={len(result['issues'])}"
            )

            if result["stable"]:
                log.append("Model is stable!")
                break

            # 修正
            log.append(f"Fixing {len(result['issues'])} issues...")
            fixed_bricks = self.fixer.fix(bricks, result["issues"], model["basePlate"])

            # 用修正后的数据重建模型
            model = self._rebuild_model(fixed_bricks, model, base_width, base_length)
            log.append(f"Fixed model: {model['totalBricks']} bricks")

        model["generation_log"] = log
        return model

    def _rebuild_model(self, bricks: list[dict], original: dict, bw: int, bl: int) -> dict:
        """用修正后的零件重建模型"""
        layers: dict[int, list] = {}
        for b in bricks:
            y = b["position"]["y"]
            layers.setdefault(y, []).append(b)

        steps = []
        for y in sorted(layers.keys()):
            step_bricks = []
            for i, b in enumerate(layers[y]):
                sz = b.get("size", {"x": 2, "y": 1, "z": 2})
                step_bricks.append({
                    "id": f"step{y + 1}-brick{i}",
                    "partId": b.get("part_id", "3001"),
                    "name": _NAMES.get(b.get("part_id", ""), "Brick"),
                    "color": b.get("color", "#E3000B"),
                    "colorName": b.get("colorName", "Red"),
                    "size": sz,
                    "position": b["position"],
                })
            steps.append({
                "stepNumber": y + 1,
                "description": f"第 {y + 1} 层，{len(step_bricks)} 块",
                "bricksToAdd": step_bricks,
            })

        return {
            **original,
            "totalSteps": len(steps),
            "totalBricks": len(bricks),
            "steps": steps,
        }


_NAMES = {
    "3001": "Brick 2x4", "3002": "Brick 2x3", "3003": "Brick 2x2",
    "3004": "Brick 1x2", "3005": "Brick 1x1", "3010": "Brick 1x4",
    "3020": "Plate 2x4", "3023": "Plate 1x2", "3622": "Brick 1x3",
}


def get_pipeline(llm: BaseChatModel = None) -> ModelGenerationPipeline:
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
    return ModelGenerationPipeline(llm=llm)
