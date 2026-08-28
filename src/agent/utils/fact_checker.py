"""事实校验器 - 防止幻觉传播"""

from typing import List
from dataclasses import dataclass


@dataclass
class FactClaim:
    """事实声明"""
    claim: str
    source: str  # 来源 Agent
    confidence: float  # 置信度 0-1
    verified: bool = False


class FactChecker:
    """事实校验器 - 防止幻觉传播

    用法:
        checker = FactChecker()
        checker.add_fact("零件3001是红色", "vision", 0.9)
        checker.add_fact("零件3001不是红色", "manual", 0.9)
        issues = checker.check_consistency()  # 返回矛盾列表
    """

    def __init__(self):
        self._facts: List[FactClaim] = []

    def add_fact(self, claim: str, source: str, confidence: float):
        """添加事实声明"""
        self._facts.append(FactClaim(
            claim=claim,
            source=source,
            confidence=confidence,
        ))

    def check_consistency(self) -> List[dict]:
        """检查事实一致性"""
        issues = []

        for i, fact1 in enumerate(self._facts):
            for fact2 in self._facts[i + 1:]:
                # 如果两个事实来源不同且置信度都高
                if (fact1.source != fact2.source and
                        fact1.confidence > 0.8 and
                        fact2.confidence > 0.8):
                    if self._is_contradictory(fact1.claim, fact2.claim):
                        issues.append({
                            "type": "contradiction",
                            "fact1": fact1.claim,
                            "fact2": fact2.claim,
                            "sources": [fact1.source, fact2.source],
                        })

        return issues

    def get_confidence_score(self) -> float:
        """获取整体置信度"""
        if not self._facts:
            return 0.0
        return sum(f.confidence for f in self._facts) / len(self._facts)

    @staticmethod
    def _is_contradictory(claim1: str, claim2: str) -> bool:
        """简单矛盾检测

        检测逻辑：
        1. 一个声明包含否定词，另一个不包含
        2. 去掉否定词后，两个声明相似
        """
        negation_words = ["不", "没", "无", "非", "未"]

        for word in negation_words:
            # claim1 有否定词，claim2 没有
            if word in claim1 and word not in claim2:
                simplified = claim1.replace(word, "")
                # 检查去掉否定词后是否相似（允许一定差异）
                if (simplified in claim2 or
                        claim2 in simplified or
                        FactChecker._similarity(simplified, claim2) > 0.7):
                    return True

            # claim2 有否定词，claim1 没有
            if word in claim2 and word not in claim1:
                simplified = claim2.replace(word, "")
                if (simplified in claim1 or
                        claim1 in simplified or
                        FactChecker._similarity(simplified, claim1) > 0.7):
                    return True

        return False

    @staticmethod
    def _similarity(s1: str, s2: str) -> float:
        """计算两个字符串的相似度（Jaccard）"""
        if not s1 or not s2:
            return 0.0

        set1 = set(s1)
        set2 = set(s2)

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0

    def reset(self):
        """重置"""
        self._facts.clear()
