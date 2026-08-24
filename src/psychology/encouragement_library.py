"""共情话术库 - 按难度和情绪类型匹配鼓励语"""

import json
import os
import random
from typing import Any

# 话术库路径
LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "encouragement_library.json")


class EncouragementLibrary:
    """共情话术库"""

    def __init__(self):
        self.library = self._load_library()

    def _load_library(self) -> dict[str, Any]:
        """加载话术库"""
        if os.path.exists(LIBRARY_PATH):
            with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        # 返回默认话术库
        return self._default_library()

    def _default_library(self) -> dict[str, Any]:
        """默认话术库（内置 20 条）"""
        return {
            "encouragement": [
                {"text": "这一步确实有点绕，试试先把左下角的卡扣对齐，会顺畅很多！", "difficulty": "medium"},
                {"text": "你已经完成68%的颗粒，超过同期53%的玩家！加油！", "difficulty": "easy"},
                {"text": "大神也会在这一步卡住，你不是一个人在战斗！", "difficulty": "hard"},
                {"text": "换个角度看看，也许从底部往上搭会更直观哦。", "difficulty": "medium"},
                {"text": "说明书这一步确实画得不太清楚，我来帮你拆解一下。", "difficulty": "medium"},
                {"text": "拼乐高就像写代码，有时候需要停下来喝口水，回来就通了。", "difficulty": "easy"},
                {"text": "你已经攻克了最难的第三部分，剩下的都是重复劳动！", "difficulty": "hard"},
                {"text": "试试把零件按颜色分好类，拼起来会更快。", "difficulty": "easy"},
                {"text": "这一步的机关设计很巧妙，拼好之后会动哦，期待吗？", "difficulty": "medium"},
                {"text": "拼错是正常的，我帮你看看哪里需要调整。", "difficulty": "easy"},
            ],
            "tips": [
                {"step_hint": "先把所有 2x4 砖挑出来放一边，用的时候不用翻。", "difficulty": "easy"},
                {"step_hint": "这步的卡扣是斜着按下去的，别用蛮力。", "difficulty": "medium"},
                {"step_hint": "如果零件装不进去，检查一下是不是方向反了。", "difficulty": "medium"},
                {"step_hint": "这步可以先不装最后两颗砖，方便后面调整。", "difficulty": "hard"},
                {"step_hint": "说明书上的箭头方向很重要，别忽略。", "difficulty": "easy"},
            ],
            "facts": [
                {"fact": "乐高每年生产约 1000 种新零件，但经典的 2x4 砖从 1958 年就没变过。"},
                {"text": "全世界每个人平均分到的乐高积木超过 80 块。", "difficulty": "easy"},
                {"fact": "乐高积木的精度误差不超过 0.002 毫米，这也是它们咬合那么紧的原因。"},
                {"text": "世界上最高的乐高塔超过 35 米，用了 50 万块积木。", "difficulty": "easy"},
                {"fact": "乐高名字来自丹麦语 'leg godt'，意思是 '玩得好'。"},
            ],
            "positive_feedback": [
                {"text": "整体配色很还原！", "difficulty": "easy"},
                {"text": "拼得不错，就差一点点就完美了！", "difficulty": "medium"},
                {"text": "这个角度搭得很好，很有创意！", "difficulty": "easy"},
                {"text": "比说明书的示例还有个性！", "difficulty": "easy"},
                {"text": "你的空间想象力很强，这一步很多人都拼反了。", "difficulty": "hard"},
            ],
            "correction_prefix": [
                {"text": "整体效果很好！不过", "difficulty": "easy"},
                {"text": "配色很还原！不过", "difficulty": "medium"},
                {"text": "拼得不错，不过", "difficulty": "easy"},
                {"text": "这一步基本对了，不过", "difficulty": "medium"},
                {"text": "很有创意！不过", "difficulty": "easy"},
            ],
        }

    def get_encouragement(self, difficulty: str = "medium", count: int = 1) -> list[str]:
        """
        获取鼓励语

        Args:
            difficulty: 难度等级 (easy/medium/hard)
            count: 返回数量

        Returns:
            鼓励语列表
        """
        items = self.library.get("encouragement", [])
        filtered = [item for item in items if item.get("difficulty") == difficulty]
        if not filtered:
            filtered = items

        selected = random.sample(filtered, min(count, len(filtered)))
        return [item["text"] for item in selected]

    def get_tip(self, difficulty: str = "medium") -> str:
        """获取避坑贴士"""
        items = self.library.get("tips", [])
        filtered = [item for item in items if item.get("difficulty") == difficulty]
        if not filtered:
            filtered = items

        if filtered:
            return random.choice(filtered).get("step_hint", "")
        return ""

    def get_fact(self) -> str:
        """获取冷知识"""
        items = self.library.get("facts", [])
        if items:
            return random.choice(items).get("fact", "")
        return ""

    def get_positive_feedback(self, difficulty: str = "medium") -> str:
        """获取肯定语"""
        items = self.library.get("positive_feedback", [])
        filtered = [item for item in items if item.get("difficulty") == difficulty]
        if not filtered:
            filtered = items

        if filtered:
            return random.choice(filtered).get("text", "")
        return ""

    def get_correction_prefix(self, difficulty: str = "medium") -> str:
        """获取纠正前缀（先肯定后纠正）"""
        items = self.library.get("correction_prefix", [])
        filtered = [item for item in items if item.get("difficulty") == difficulty]
        if not filtered:
            filtered = items

        if filtered:
            return random.choice(filtered).get("text", "不过")
        return "不过"

    def get_full_encouragement(self, frustration_score: int, step_number: int = 0) -> str:
        """
        根据挫折分数生成完整安抚话术

        Args:
            frustration_score: 挫折分数
            step_number: 当前步骤号

        Returns:
            完整安抚话术
        """
        if frustration_score >= 80:
            # 高度挫折：鼓励 + 贴士 + 冷知识
            difficulty = "hard"
            parts = [
                self.get_encouragement(difficulty, 1)[0],
                f"💡 小贴士：{self.get_tip(difficulty)}",
                f"🎲 冷知识：{self.get_fact()}",
            ]
        elif frustration_score >= 50:
            # 中度挫折：鼓励 + 贴士
            difficulty = "medium"
            parts = [
                self.get_encouragement(difficulty, 1)[0],
                f"💡 小贴士：{self.get_tip(difficulty)}",
            ]
        else:
            # 轻度：简单鼓励
            difficulty = "easy"
            parts = self.get_encouragement(difficulty, 1)

        return "\n\n".join(parts)

    def get_correction_message(self, error_detail: str, difficulty: str = "medium") -> str:
        """
        生成纠正话术（先肯定后纠正）

        Args:
            error_detail: 错误详情
            difficulty: 难度等级

        Returns:
            完整纠正话术
        """
        prefix = self.get_correction_prefix(difficulty)
        tip = self.get_tip(difficulty)
        return f"{prefix}{error_detail}\n\n💡 修复建议：{tip}"


# 全局单例
_library: EncouragementLibrary | None = None


def get_encouragement_library() -> EncouragementLibrary:
    """获取话术库单例"""
    global _library
    if _library is None:
        _library = EncouragementLibrary()
    return _library
