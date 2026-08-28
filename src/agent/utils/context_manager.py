"""上下文管理器 - 防止上下文爆炸"""

from typing import List
from langchain_core.messages import BaseMessage, SystemMessage


class ContextManager:
    """上下文管理器 - 防止上下文爆炸

    用法:
        manager = ContextManager(max_tokens=8000)
        trimmed = manager.trim_context(messages)
    """

    def __init__(self, max_tokens: int = 8000, summary_threshold: int = 6000):
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold

    def estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """估算 token 数（粗略：1 token ≈ 4 字符）"""
        total_chars = sum(len(m.content) for m in messages if hasattr(m, 'content'))
        return total_chars // 4

    def trim_context(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """裁剪上下文到最大长度

        策略：
        1. 保留 SystemMessage
        2. 保留最近 N 条消息
        3. 旧消息被裁剪
        """
        if not messages:
            return messages

        estimated_tokens = self.estimate_tokens(messages)

        if estimated_tokens <= self.max_tokens:
            return messages

        # 保留 SystemMessage + 最近消息
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]

        # 保留最近 10 条
        recent_msgs = other_msgs[-10:]

        return system_msgs + recent_msgs

    def should_summarize(self, messages: List[BaseMessage]) -> bool:
        """判断是否需要摘要"""
        return self.estimate_tokens(messages) > self.summary_threshold
