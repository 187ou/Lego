"""上下文窗口管理

将融合后的检索结果构建为 LLM 可理解的上下文。
管理 token 预算，确保不超出 LLM 的上下文窗口限制。
"""

from dataclasses import dataclass, field
from typing import Optional

from src.retrieval.fusion_strategy import RetrievalResult


@dataclass
class ContextConfig:
    """上下文配置"""

    # Token 预算
    max_tokens: int = 4000                 # 最大 token 数
    reserved_tokens: int = 1000            # 为回复预留的 token 数

    # 各部分的 token 分配
    system_prompt_tokens: int = 500        # 系统提示
    memory_context_tokens: int = 1000     # 记忆上下文
    retrieval_context_tokens: int = 1500  # 检索结果
    user_profile_tokens: int = 300        # 用户画像

    # 格式
    include_metadata: bool = True         # 是否包含元数据
    include_scores: bool = False          # 是否包含分数
    separator: str = "\n---\n"            # 分隔符


class ContextBuilder:
    """上下文构建器"""

    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()

    def build(
        self,
        fused_results: list[RetrievalResult],
        user_query: str = "",
        user_profile: Optional[dict] = None,
        conversation_summary: str = "",
    ) -> list[dict]:
        """
        构建 LLM 上下文。

        Args:
            fused_results: 融合后的检索结果
            user_query: 用户查询
            user_profile: 用户画像
            conversation_summary: 对话摘要

        Returns:
            LLM 消息列表
        """
        context = []
        used_tokens = 0

        # 1. 系统提示
        system_msg = self._build_system_prompt()
        context.append({"role": "system", "content": system_msg})
        used_tokens += self._estimate_tokens(system_msg)

        # 2. 用户画像
        if user_profile:
            profile_msg = self._build_user_profile(user_profile)
            tokens = self._estimate_tokens(profile_msg)
            if used_tokens + tokens <= self.config.max_tokens:
                context.append({"role": "system", "content": profile_msg})
                used_tokens += tokens

        # 3. 对话摘要
        if conversation_summary:
            summary_msg = f"[对话摘要] {conversation_summary}"
            tokens = self._estimate_tokens(summary_msg)
            if used_tokens + tokens <= self.config.max_tokens:
                context.append({"role": "system", "content": summary_msg})
                used_tokens += tokens

        # 4. 检索结果
        remaining_tokens = self.config.max_tokens - used_tokens - self.config.reserved_tokens
        retrieval_msgs = self._build_retrieval_context(fused_results, remaining_tokens)
        context.extend(retrieval_msgs)

        return context

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return (
            "你是 LEGO-Mate，一个乐高拼搭智能助手。\n"
            "你可以帮助用户：\n"
            "1. 识别乐高零件\n"
            "2. 查找零件替代方案\n"
            "3. 检索说明书步骤\n"
            "4. 验收成品是否正确\n"
            "请基于提供的上下文信息回答用户问题。"
        )

    def _build_user_profile(self, profile: dict) -> str:
        """构建用户画像提示"""
        parts = ["[用户偏好]"]

        if profile.get("skill_level"):
            parts.append(f"技能水平: {profile['skill_level']}")
        if profile.get("preferred_sets"):
            parts.append(f"常拼套装: {', '.join(profile['preferred_sets'][:3])}")
        if profile.get("common_parts"):
            parts.append(f"常问零件: {', '.join(profile['common_parts'][:5])}")

        return "\n".join(parts)

    def _build_retrieval_context(
        self,
        results: list[RetrievalResult],
        token_budget: int,
    ) -> list[dict]:
        """构建检索结果上下文"""
        messages = []
        used_tokens = 0

        for i, result in enumerate(results):
            msg = self._format_result(result, i + 1)
            tokens = self._estimate_tokens(msg)

            if used_tokens + tokens > token_budget:
                break

            messages.append({"role": "system", "content": msg})
            used_tokens += tokens

        return messages

    def _format_result(self, result: RetrievalResult, index: int) -> str:
        """格式化单个结果"""
        parts = [f"[参考资料 {index}]"]

        if self.config.include_scores:
            parts.append(f"(来源: {result.source}, 相关度: {result.fused_score:.0%})")

        parts.append(result.content)

        if self.config.include_metadata and result.metadata:
            if result.metadata.get("page_number"):
                parts.append(f"📖 第 {result.metadata['page_number']} 页")
            if result.metadata.get("set_id"):
                parts.append(f"📦 套装: {result.metadata['set_id']}")

        return "\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数（改进版）。

        使用更准确的估算方法：
        - 中文：约 1.5-2 字符/token（GPT  tokenizer 特性）
        - 英文：约 4 字符/token
        - 标点和空格也计入
        """
        if not text:
            return 0

        # 统计中文字符
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')

        # 统计非中文部分（英文 + 数字 + 标点）
        non_chinese_len = len(text) - chinese_chars

        # 中文：约 1.5 字符/token
        chinese_tokens = int(chinese_chars / 1.5) + 1

        # 英文/其他：约 4 字符/token
        english_tokens = int(non_chinese_len / 4) + 1

        return chinese_tokens + english_tokens
