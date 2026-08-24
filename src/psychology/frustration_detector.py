"""挫折检测器 - 监测用户挫折信号"""

import re
import time
from typing import Any

# 负面情绪关键词（中文 + 英文）
NEGATIVE_KEYWORDS = [
    # 中文
    "烦", "烦死了", "不想拼", "太难", "不会", "拼不好", "放弃", "不拼了",
    "崩溃", "头疼", "晕", "讨厌", "垃圾", "废物", "蠢", "笨",
    "什么鬼", "怎么回事", "搞不定", "弄不好", "气死", "无语",
    # 英文
    "frustrated", "hard", "difficult", "stuck", "quit", "give up",
    "annoying", "boring", "confused", "angry", "hate", "suck",
]

# 正则模式（匹配完整词）
NEGATIVE_PATTERNS = [
    re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE | re.UNICODE)
    for kw in NEGATIVE_KEYWORDS
]


class FrustrationDetector:
    """挫折检测器"""

    # 阈值配置
    RETRY_THRESHOLD = 2        # 同一节点重试超过2次触发
    IDLE_TIMEOUT = 180         # 挂起超过3分钟（180秒）触发
    FRUSTRATION_THRESHOLD = 50  # 挫折分数超过50触发安抚

    def __init__(self):
        self.last_check_time = time.time()

    def check_message(self, message: str) -> dict[str, Any]:
        """
        检测消息中的挫折信号

        Args:
            message: 用户输入消息

        Returns:
            检测结果字典
        """
        result = {
            "is_negative": False,
            "matched_keywords": [],
            "frustration_delta": 0,
        }

        # 检测负面关键词
        for pattern in NEGATIVE_PATTERNS:
            match = pattern.search(message)
            if match:
                result["is_negative"] = True
                result["matched_keywords"].append(match.group())
                result["frustration_delta"] += 25  # 每个关键词 +25 挫折分

        return result

    def check_retry(self, retry_count: int) -> dict[str, Any]:
        """
        检测重试次数

        Args:
            retry_count: 当前重试次数

        Returns:
            检测结果
        """
        result = {
            "is_frustrated": False,
            "frustration_delta": 0,
        }

        if retry_count > self.RETRY_THRESHOLD:
            result["is_frustrated"] = True
            result["frustration_delta"] = 15 * (retry_count - self.RETRY_THRESHOLD)

        return result

    def check_idle(self, last_active_time: float) -> dict[str, Any]:
        """
        检测挂起超时

        Args:
            last_active_time: 最后活跃时间戳

        Returns:
            检测结果
        """
        result = {
            "is_idle": False,
            "frustration_delta": 0,
            "idle_seconds": 0,
        }

        idle_time = time.time() - last_active_time
        result["idle_seconds"] = idle_time

        if idle_time > self.IDLE_TIMEOUT:
            result["is_idle"] = True
            result["frustration_delta"] = min(30, int((idle_time - self.IDLE_TIMEOUT) / 10))

        return result

    def should_encourage(self, frustration_score: int, retry_count: int, last_active_time: float) -> bool:
        """
        综合判断是否需要触发心理安抚

        Args:
            frustration_score: 当前挫折分数
            retry_count: 重试次数
            last_active_time: 最后活跃时间

        Returns:
            是否需要触发安抚
        """
        # 挫折分数超过阈值
        if frustration_score >= self.FRUSTRATION_THRESHOLD:
            return True

        # 重试次数过多
        if retry_count > self.RETRY_THRESHOLD:
            return True

        # 挂起超时
        idle_time = time.time() - last_active_time
        if idle_time > self.IDLE_TIMEOUT:
            return True

        return False

    def calculate_frustration_score(
        self,
        current_score: int,
        message_result: dict[str, Any],
        retry_result: dict[str, Any],
        idle_result: dict[str, Any],
    ) -> int:
        """
        计算新的挫折分数

        Args:
            current_score: 当前分数
            message_result: 消息检测结果
            retry_result: 重试检测结果
            idle_result: 空闲检测结果

        Returns:
            新的挫折分数（0-100）
        """
        delta = 0
        delta += message_result.get("frustration_delta", 0)
        delta += retry_result.get("frustration_delta", 0)
        delta += idle_result.get("frustration_delta", 0)

        new_score = min(100, max(0, current_score + delta))
        return new_score
