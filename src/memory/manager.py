"""多级记忆管理器

核心职责：
1. 管理 L0-L4 五级记忆的读写
2. 记忆升级/降级（重要消息从 L1 升级到 L2）
3. 记忆清理与压缩（L1 消息上限、TTL 过期）
4. 上下文窗口管理（为 LLM 构建最优输入）
5. 指代消解（利用工作记忆解析"这一步"等指代）
"""

import json
import re
import time
from typing import Optional
from datetime import datetime, timedelta

from src.memory.models import (
    MemoryLevel,
    WorkingMemory,
    MemoryMessage,
    ShortTermMemory,
    ConversationSummary,
    MidTermMemory,
    UserProfile,
    LongTermMemory,
)
from src.session.redis_client import get_redis


# ===== 配置常量 =====

class MemoryConfig:
    """记忆系统配置"""

    # L1 短期记忆
    MAX_MESSAGES_PER_CONVERSATION = 100     # 单对话最大消息数
    CONTEXT_WINDOW_SIZE = 20                # LLM 上下文窗口（消息数）
    MESSAGE_TTL_DAYS = 30                   # 消息过期天数

    # L2 中期记忆
    MAX_CONVERSATIONS_FOR_SUMMARY = 50     # 最多保留摘要的对话数
    SUMMARY_THRESHOLD = 10                 # 超过此消息数才生成摘要

    # L3 长期记忆
    FRUSTATION_DECAY_HOURS = 24            # 挫折分数衰减周期（小时）
    PROFILE_UPDATE_INTERVAL = 10           # 每 N 条消息更新用户画像

    # 重要度计算
    IMPORTANCE_TOOL_CALL = 0.7             # 工具调用消息重要度
    IMPORTANCE_USER_QUESTION = 0.6         # 用户提问重要度
    IMPORTANCE_VERIFICATION = 0.8          # 验收结果重要度
    IMPORTANCE_ENCOURAGEMENT = 0.3         # 安抚消息重要度


class MemoryManager:
    """多级记忆管理器"""

    def __init__(self):
        self._redis = None
        self._config = MemoryConfig()
        # L0 工作内存（不持久化，按 conversation_id 缓存）
        self._working_memory: dict[str, WorkingMemory] = {}

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    # =========================================================================
    # L0: 工作记忆（内存，不持久化）
    # =========================================================================

    def get_working_memory(self, conversation_id: str) -> WorkingMemory:
        """获取/创建工作记忆"""
        if conversation_id not in self._working_memory:
            self._working_memory[conversation_id] = WorkingMemory(
                conversation_id=conversation_id,
                last_active_time=time.time(),
            )
        return self._working_memory[conversation_id]

    def update_working_memory(self, conversation_id: str, **kwargs) -> WorkingMemory:
        """更新工作记忆"""
        wm = self.get_working_memory(conversation_id)
        for key, value in kwargs.items():
            if hasattr(wm, key):
                setattr(wm, key, value)
        wm.last_active_time = time.time()
        return wm

    def clear_working_memory(self, conversation_id: str):
        """清除工作记忆"""
        self._working_memory.pop(conversation_id, None)

    # =========================================================================
    # L1: 短期记忆（Redis 持久化）
    # =========================================================================

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        **kwargs,
    ) -> MemoryMessage:
        """
        添加消息到短期记忆。
        自动计算重要度、提取实体，并触发清理。
        """
        # 构建消息
        msg = MemoryMessage(
            id=kwargs.get("id", self._generate_id()),
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            image_url=kwargs.get("image_url"),
            tool_calls=kwargs.get("tool_calls"),
            thinking=kwargs.get("thinking"),
            feedback=kwargs.get("feedback"),
            intent=kwargs.get("intent", ""),
        )

        # 计算重要度
        msg.importance = self._calculate_importance(msg)

        # 提取实体
        msg.entities = self._extract_entities(content)

        # 保存到 Redis
        key = f"conv:{conversation_id}:msgs"
        self.r.rpush(key, json.dumps(msg.model_dump(), ensure_ascii=False))
        self.r.expire(key, timedelta(days=self._config.MESSAGE_TTL_DAYS))

        # 更新对话时间戳
        self.r.hset(f"conv:{conversation_id}", "updated_at", datetime.now().isoformat())

        # 自动更新标题（首条用户消息）
        if role == "user" and self.r.llen(key) == 1:
            title = self._generate_title(content)
            self.r.hset(f"conv:{conversation_id}", "title", title)

        # 触发清理（超出上限时）
        self._cleanup_old_messages(conversation_id)

        return msg

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[MemoryMessage]:
        """
        获取消息（支持分页）。
        limit=None 时返回最近 CONTEXT_WINDOW_SIZE 条。
        """
        key = f"conv:{conversation_id}:msgs"
        total = self.r.llen(key)

        if limit is None:
            limit = self._config.CONTEXT_WINDOW_SIZE

        start = max(0, total - limit - offset)
        end = total - offset - 1

        if end < 0:
            return []

        msg_list = self.r.lrange(key, start, end)
        return [MemoryMessage(**json.loads(m)) for m in msg_list]

    def get_all_messages(self, conversation_id: str) -> list[MemoryMessage]:
        """获取全部消息"""
        key = f"conv:{conversation_id}:msgs"
        msg_list = self.r.lrange(key, 0, -1)
        return [MemoryMessage(**json.loads(m)) for m in msg_list]

    def get_message_count(self, conversation_id: str) -> int:
        """获取消息总数"""
        return self.r.llen(f"conv:{conversation_id}:msgs")

    def update_message_feedback(
        self,
        conversation_id: str,
        message_id: str,
        feedback: Optional[int],
    ) -> bool:
        """更新消息反馈（使用索引优化）"""
        # 先检查索引
        index_key = f"conv:{conversation_id}:msg_index"
        idx_data = self.r.hget(index_key, message_id)

        if idx_data:
            # 有索引，直接定位
            idx = int(idx_data)
            key = f"conv:{conversation_id}:msgs"
            msg_str = self.r.lindex(key, idx)
            if msg_str:
                msg_data = json.loads(msg_str)
                msg_data["feedback"] = feedback
                self.r.lset(key, idx, json.dumps(msg_data, ensure_ascii=False))
                return True

        # 无索引，遍历查找并建立索引
        return self._update_feedback_with_index(conversation_id, message_id, feedback)

    def _update_feedback_with_index(
        self, conversation_id: str, message_id: str, feedback: Optional[int]
    ) -> bool:
        """遍历查找并建立索引"""
        key = f"conv:{conversation_id}:msgs"
        index_key = f"conv:{conversation_id}:msg_index"
        msg_list = self.r.lrange(key, 0, -1)

        for i, msg_str in enumerate(msg_list):
            msg_data = json.loads(msg_str)
            if msg_data.get("id") == message_id:
                msg_data["feedback"] = feedback
                self.r.lset(key, i, json.dumps(msg_data, ensure_ascii=False))
                # 建立索引
                self.r.hset(index_key, message_id, str(i))
                return True
        return False

    def _cleanup_old_messages(self, conversation_id: str):
        """清理超出上限的旧消息（保留重要消息）"""
        key = f"conv:{conversation_id}:msgs"
        total = self.r.llen(key)

        if total <= self._config.MAX_MESSAGES_PER_CONVERSATION:
            return

        # 需要清理的消息数
        excess = total - self._config.MAX_MESSAGES_PER_CONVERSATION

        # 获取所有消息及其重要度
        msg_list = self.r.lrange(key, 0, excess + 10)  # 多取一些以便筛选

        # 按重要度排序，保留重要消息
        msgs_with_importance = []
        for i, msg_str in enumerate(msg_list):
            msg_data = json.loads(msg_str)
            importance = msg_data.get("importance", 0.5)
            msgs_with_importance.append((i, importance, msg_data))

        # 保留重要消息（重要度 > 0.6），其余删除
        to_keep = {item[0] for item in msgs_with_importance if item[1] > 0.6}
        to_remove = [i for i in range(min(excess, len(msg_list))) if i not in to_keep]

        # 从后往前删除（避免索引偏移）
        for i in sorted(to_remove, reverse=True):
            msg_data = json.loads(msg_list[i])
            # 标记为已归档
            msg_data["archived"] = True
            self.r.lset(key, i, json.dumps(msg_data, ensure_ascii=False))

    # =========================================================================
    # L2: 中期记忆（对话摘要）
    # =========================================================================

    def create_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """
        为对话生成摘要。
        应在对话结束或消息数超过阈值时调用。
        """
        messages = self.get_all_messages(conversation_id)
        if len(messages) < self._config.SUMMARY_THRESHOLD:
            return None

        # 提取关键信息
        set_id = self.r.hget(f"conv:{conversation_id}", "set_id") or ""
        key_events = []
        resolved = []
        unresolved = []
        steps_covered = set()
        parts_discussed = set()

        for msg in messages:
            if msg.role == "user":
                # 提取步骤号
                for entity in msg.entities:
                    if entity.isdigit() and 1 <= int(entity) <= 999:
                        steps_covered.add(int(entity))
                # 提取零件
                parts_discussed.update(msg.entities)
            elif msg.role == "assistant":
                if msg.tool_calls:
                    for call in msg.tool_calls:
                        key_events.append(f"调用 {call.get('name', 'unknown')}")

        # 构建摘要
        summary = ConversationSummary(
            conversation_id=conversation_id,
            set_id=set_id,
            summary=self._generate_summary_text(messages),
            key_events=key_events[:10],  # 最多保留 10 个关键事件
            resolved_queries=resolved,
            unresolved_queries=unresolved,
            total_messages=len(messages),
            total_steps_covered=sorted(steps_covered),
            parts_discussed=sorted(parts_discussed),
            created_at=datetime.now().isoformat(),
        )

        # 保存摘要
        summary_key = f"conv:{conversation_id}:summary"
        self.r.set(summary_key, json.dumps(summary.model_dump(), ensure_ascii=False))

        # 添加到套装摘要列表
        if set_id:
            set_summary_key = f"set:{set_id}:summaries"
            self.r.lpush(set_summary_key, json.dumps(summary.model_dump(), ensure_ascii=False))
            self.r.ltrim(set_summary_key, 0, self._config.MAX_CONVERSATIONS_FOR_SUMMARY - 1)

        return summary

    def get_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """获取对话摘要"""
        summary_key = f"conv:{conversation_id}:summary"
        data = self.r.get(summary_key)
        if data:
            return ConversationSummary(**json.loads(data))
        return None

    def get_set_summaries(self, set_id: str, limit: int = 5) -> list[ConversationSummary]:
        """获取套装相关的最近摘要"""
        set_summary_key = f"set:{set_id}:summaries"
        data_list = self.r.lrange(set_summary_key, 0, limit - 1)
        return [ConversationSummary(**json.loads(d)) for d in data_list]

    # =========================================================================
    # L3: 长期记忆（用户画像）
    # =========================================================================

    def get_user_profile(self, user_id: str = "default") -> UserProfile:
        """获取用户画像"""
        key = f"user:{user_id}:profile"
        data = self.r.get(key)
        if data:
            return UserProfile(**json.loads(data))
        return UserProfile(user_id=user_id, first_seen=datetime.now().isoformat())

    def update_user_profile(
        self,
        user_id: str = "default",
        conversation_id: Optional[str] = None,
        **kwargs,
    ) -> UserProfile:
        """
        更新用户画像。
        应在对话结束或每隔 N 条消息后调用。
        """
        profile = self.get_user_profile(user_id)

        # 挫折分数衰减（在更新前检查）
        if profile.last_seen:
            try:
                last = datetime.fromisoformat(profile.last_seen)
                hours_since_last = (datetime.now() - last).total_seconds() / 3600
                if hours_since_last > self._config.FRUSTATION_DECAY_HOURS:
                    profile.avg_frustration_score *= 0.5
            except (ValueError, TypeError):
                pass

        # 更新基础字段
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        # 如果有对话 ID，从对话中提取信息更新画像
        if conversation_id:
            self._update_profile_from_conversation(profile, conversation_id)

        # 更新时间
        profile.last_seen = datetime.now().isoformat()

        # 保存
        key = f"user:{user_id}:profile"
        self.r.set(key, json.dumps(profile.model_dump(), ensure_ascii=False))

        return profile

    def _update_profile_from_conversation(self, profile: UserProfile, conversation_id: str):
        """从对话中提取信息更新用户画像"""
        messages = self.get_all_messages(conversation_id)

        # 统计
        profile.total_conversations += 1
        profile.total_messages += len(messages)

        # 提取常见零件
        all_entities = []
        for msg in messages:
            all_entities.extend(msg.entities)

        if all_entities:
            from collections import Counter
            common = Counter(all_entities).most_common(10)
            profile.common_parts = [item[0] for item in common]

    # =========================================================================
    # 上下文构建（为 LLM 准备输入）
    # =========================================================================

    def build_context(
        self,
        conversation_id: str,
        include_summary: bool = True,
        max_messages: Optional[int] = None,
    ) -> list[dict]:
        """
        构建 LLM 上下文。
        策略：摘要 + 最近 N 条消息
        """
        if max_messages is None:
            max_messages = self._config.CONTEXT_WINDOW_SIZE

        context = []

        # 1. 添加对话摘要（如果有）
        if include_summary:
            summary = self.get_conversation_summary(conversation_id)
            if summary:
                context.append({
                    "role": "system",
                    "content": f"[对话摘要] {summary.summary}",
                })

        # 2. 添加套装相关摘要
        set_id = self.r.hget(f"conv:{conversation_id}", "set_id")
        if set_id:
            set_summaries = self.get_set_summaries(set_id, limit=2)
            if set_summaries:
                prev_knowledge = "; ".join(
                    s.summary[:100] for s in set_summaries if s.summary
                )
                if prev_knowledge:
                    context.append({
                        "role": "system",
                        "content": f"[历史拼搭记录] {prev_knowledge}",
                    })

        # 3. 添加最近消息
        messages = self.get_messages(conversation_id, limit=max_messages)
        for msg in messages:
            context.append({
                "role": msg.role,
                "content": msg.content,
            })

        return context

    def build_enhanced_context(
        self,
        conversation_id: str,
        user_id: str = "default",
    ) -> list[dict]:
        """
        构建增强上下文（包含用户画像）。
        用于 L3 完整 Agent 链路。
        """
        context = self.build_context(conversation_id)

        # 添加用户画像
        profile = self.get_user_profile(user_id)
        if profile.skill_level != "beginner" or profile.preferred_sets:
            profile_hint = f"[用户偏好] 技能水平: {profile.skill_level}"
            if profile.preferred_sets:
                profile_hint += f", 常拼套装: {', '.join(profile.preferred_sets[:3])}"
            context.insert(0, {
                "role": "system",
                "content": profile_hint,
            })

        return context

    # =========================================================================
    # 指代消解
    # =========================================================================

    def resolve_reference(self, conversation_id: str, message: str) -> str:
        """
        解析消息中的指代词。
        例如："这一步" → "第35步"
        """
        wm = self.get_working_memory(conversation_id)

        resolved = message

        # 替换指代词
        if "这一步" in resolved or "这步" in resolved or "那一步" in resolved:
            if wm.last_discussed_step > 0:
                resolved = resolved.replace("这一步", f"第{wm.last_discussed_step}步")
                resolved = resolved.replace("这步", f"第{wm.last_discussed_step}步")
                resolved = resolved.replace("那一步", f"第{wm.last_discussed_step}步")

        if "上一步" in resolved or "前一步" in resolved:
            prev_step = max(1, wm.last_discussed_step - 1)
            resolved = resolved.replace("上一步", f"第{prev_step}步")
            resolved = resolved.replace("前一步", f"第{prev_step}步")

        if "下一步" in resolved or "后一步" in resolved:
            next_step = wm.last_discussed_step + 1
            resolved = resolved.replace("下一步", f"第{next_step}步")
            resolved = resolved.replace("后一步", f"第{next_step}步")

        return resolved

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _calculate_importance(self, msg: MemoryMessage) -> float:
        """计算消息重要度"""
        importance = 0.5  # 基础分

        # 工具调用消息更重要
        if msg.tool_calls:
            importance = max(importance, self._config.IMPORTANCE_TOOL_CALL)

        # 用户提问
        if msg.role == "user" and ("?" in msg.content or "？" in msg.content):
            importance = max(importance, self._config.IMPORTANCE_USER_QUESTION)

        # 验收结果
        if msg.tool_calls:
            for call in msg.tool_calls:
                if call.get("name") == "verify_build_result":
                    importance = max(importance, self._config.IMPORTANCE_VERIFICATION)

        # 安抚消息不太重要
        if msg.role == "assistant" and not msg.tool_calls:
            if any(w in msg.content for w in ["加油", "别急", "没关系"]):
                importance = min(importance, self._config.IMPORTANCE_ENCOURAGEMENT)

        return importance

    def _extract_entities(self, content: str) -> list[str]:
        """从内容中提取实体（零件号/颜色/步骤号）"""
        entities = []

        # 提取零件编号（如 3001, 3005）- 使用更宽松的匹配
        # 匹配独立的 4-5 位数字（前后不是数字）
        part_ids = re.findall(r"(?<!\d)(\d{4,5})(?!\d)", content)
        entities.extend(part_ids)

        # 提取步骤号
        steps = re.findall(r"第?\s*(\d+)\s*步", content)
        entities.extend([f"step_{s}" for s in steps])

        # 提取颜色（优先匹配复合颜色）
        color_matched = False
        for color in ["深红", "浅红", "深蓝", "浅蓝", "透明"]:
            if color in content:
                entities.append(f"color_{color}")
                color_matched = True
                break
        if not color_matched:
            for color in ["红", "蓝", "黄", "绿", "白", "黑", "灰", "橙", "棕", "紫", "粉"]:
                if color in content:
                    entities.append(f"color_{color}")
                    break

        return list(set(entities))

    def _generate_title(self, message: str) -> str:
        """生成对话标题"""
        title = message.strip()[:25]
        if len(message.strip()) > 25:
            title += "..."
        return title or "新对话"

    def _generate_id(self) -> str:
        """生成消息 ID"""
        import uuid
        return str(uuid.uuid4())[:12]

    def _generate_summary_text(self, messages: list[MemoryMessage]) -> str:
        """生成摘要文本（简化版，实际可用 LLM 生成）"""
        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        summary_parts = []
        if user_msgs:
            summary_parts.append(f"用户提出了 {len(user_msgs)} 个问题")
        if assistant_msgs:
            tool_calls = sum(1 for m in assistant_msgs if m.tool_calls)
            if tool_calls:
                summary_parts.append(f"执行了 {tool_calls} 次工具调用")

        return "，".join(summary_parts) if summary_parts else "简短对话"

    def _get_cache_info_safe(self) -> dict:
        """安全获取缓存信息（即使 Redis 不可用）"""
        try:
            return get_cache_info()
        except Exception:
            return {"error": "Cache info unavailable"}


# 全局单例
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例"""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
