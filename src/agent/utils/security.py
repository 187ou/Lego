"""安全过滤器 - 防止提示注入攻击"""

import re
from typing import Tuple


class SecurityFilter:
    """安全过滤器 - 防止提示注入攻击"""

    # 危险模式（提示注入）
    DANGEROUS_PATTERNS = [
        r"ignore.*previous.*instructions",
        r"ignore.*above",
        r"disregard.*instructions",
        r"system.*prompt",
        r"you.*are.*now",
        r"new.*persona",
        r"jailbreak",
        r"DAN",
        r"do.*anything.*now",
        r"忽略.*指令",
        r"忘记.*规则",
        r"你现在是",
        r"扮演.*角色",
    ]

    # 敏感信息模式
    SENSITIVE_PATTERNS = [
        r"\b\d{16,}\b",  # 长数字（可能是卡号）
        r"\b[A-Za-z0-9+/]{40}\b",  # Base64（可能是密钥）
    ]

    @classmethod
    def check_input(cls, text: str) -> Tuple[bool, str]:
        """检查输入安全

        Returns:
            (是否安全, 原因)
        """
        if not text:
            return True, ""

        text_lower = text.lower()

        # 检查危险模式
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower):
                return False, "检测到潜在的安全风险模式"

        return True, ""

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """清理输入"""
        if not text:
            return ""

        # 限制长度
        if len(text) > 10000:
            text = text[:10000]

        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        return text.strip()

    @classmethod
    def check_output(cls, text: str) -> Tuple[bool, str]:
        """检查输出是否包含敏感信息"""
        if not text:
            return True, ""

        for pattern in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return False, "输出可能包含敏感信息"

        return True, ""
