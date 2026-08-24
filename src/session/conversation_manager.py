"""对话管理器 - CRUD 操作"""

import json
import uuid
from datetime import datetime
from typing import Optional
from src.session.redis_client import get_redis, check_redis_connection
from src.session.models import (
    ConversationMeta,
    StoredMessage,
    ConversationCreate,
    ConversationUpdate,
)


def _now() -> str:
    return datetime.now().isoformat()


def _generate_title(message: str) -> str:
    """从首条消息自动生成标题"""
    title = message.strip()[:30]
    if len(message.strip()) > 30:
        title += "..."
    return title or "新对话"


class ConversationManager:
    """对话管理器"""

    def __init__(self):
        self._redis = None

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        return check_redis_connection()

    # ===== 对话 CRUD =====

    def list_conversations(self) -> list[ConversationMeta]:
        """列出所有对话（按更新时间倒序）"""
        try:
            r = self.r
            # 获取所有对话 ID
            conv_ids = r.smembers("conversations")
            if not conv_ids:
                return []

            conversations = []
            for cid in conv_ids:
                data = r.hgetall(f"conv:{cid}")
                if data:
                    conversations.append(ConversationMeta(
                        id=cid,
                        title=data.get("title", "未命名"),
                        set_id=data.get("set_id", ""),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                    ))

            # 按 updated_at 倒序
            conversations.sort(key=lambda x: x.updated_at, reverse=True)
            return conversations
        except Exception as e:
            print(f"[ERROR] 列出对话失败: {e}")
            return []

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        """获取对话详情 + 消息列表"""
        try:
            r = self.r
            data = r.hgetall(f"conv:{conv_id}")
            if not data:
                return None

            # 获取消息列表
            msg_list = r.lrange(f"conv:{conv_id}:msgs", 0, -1)
            messages = [StoredMessage(**json.loads(m)) for m in msg_list]

            return {
                "meta": ConversationMeta(
                    id=conv_id,
                    title=data.get("title", "未命名"),
                    set_id=data.get("set_id", ""),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                ),
                "messages": messages,
            }
        except Exception as e:
            print(f"[ERROR] 获取对话失败: {e}")
            return None

    def create_conversation(self, data: ConversationCreate) -> ConversationMeta:
        """创建新对话"""
        r = self.r
        conv_id = str(uuid.uuid4())[:8]
        now = _now()

        meta = ConversationMeta(
            id=conv_id,
            title=data.title or "新对话",
            set_id=data.set_id,
            created_at=now,
            updated_at=now,
        )

        # 保存元数据
        r.hset(f"conv:{conv_id}", mapping={
            "title": meta.title,
            "set_id": meta.set_id,
            "created_at": meta.created_at,
            "updated_at": meta.updated_at,
        })
        # 加入对话集合
        r.sadd("conversations", conv_id)

        return meta

    def update_conversation(self, conv_id: str, data: ConversationUpdate) -> Optional[ConversationMeta]:
        """更新对话"""
        try:
            r = self.r
            if not r.exists(f"conv:{conv_id}"):
                return None

            updates = {"updated_at": _now()}
            if data.title is not None:
                updates["title"] = data.title
            if data.set_id is not None:
                updates["set_id"] = data.set_id

            r.hset(f"conv:{conv_id}", mapping=updates)

            data = r.hgetall(f"conv:{conv_id}")
            return ConversationMeta(
                id=conv_id,
                title=data.get("title", ""),
                set_id=data.get("set_id", ""),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )
        except Exception as e:
            print(f"[ERROR] 更新对话失败: {e}")
            return None

    def delete_conversation(self, conv_id: str) -> bool:
        """删除对话"""
        try:
            r = self.r
            r.delete(f"conv:{conv_id}")
            r.delete(f"conv:{conv_id}:msgs")
            r.srem("conversations", conv_id)
            return True
        except Exception as e:
            print(f"[ERROR] 删除对话失败: {e}")
            return False

    # ===== 消息操作 =====

    def add_message(self, conv_id: str, message: StoredMessage) -> bool:
        """添加消息到对话"""
        try:
            r = self.r
            r.rpush(f"conv:{conv_id}:msgs", json.dumps(message.model_dump(), ensure_ascii=False))
            # 更新对话时间戳
            r.hset(f"conv:{conv_id}", "updated_at", _now())

            # 如果是第一条用户消息，自动更新标题
            msg_count = r.llen(f"conv:{conv_id}:msgs")
            if msg_count == 1 and message.role == "user":
                title = _generate_title(message.content)
                r.hset(f"conv:{conv_id}", "title", title)

            return True
        except Exception as e:
            print(f"[ERROR] 添加消息失败: {e}")
            return False

    def get_messages(self, conv_id: str) -> list[StoredMessage]:
        """获取对话的所有消息"""
        try:
            r = self.r
            msg_list = r.lrange(f"conv:{conv_id}:msgs", 0, -1)
            return [StoredMessage(**json.loads(m)) for m in msg_list]
        except Exception as e:
            print(f"[ERROR] 获取消息失败: {e}")
            return []

    def update_message_feedback(self, conv_id: str, message_id: str, feedback: Optional[int]) -> bool:
        """更新消息反馈"""
        try:
            r = self.r
            msg_list = r.lrange(f"conv:{conv_id}:msgs", 0, -1)
            for i, msg_str in enumerate(msg_list):
                msg_data = json.loads(msg_str)
                if msg_data.get("id") == message_id:
                    msg_data["feedback"] = feedback
                    r.lset(f"conv:{conv_id}:msgs", i, json.dumps(msg_data, ensure_ascii=False))
                    return True
            return False
        except Exception as e:
            print(f"[ERROR] 更新反馈失败: {e}")
            return False

    def clear_all(self) -> bool:
        """清除所有对话数据（危险操作）"""
        try:
            r = self.r
            conv_ids = r.smembers("conversations")
            for cid in conv_ids:
                r.delete(f"conv:{cid}")
                r.delete(f"conv:{cid}:msgs")
            r.delete("conversations")
            return True
        except Exception as e:
            print(f"[ERROR] 清除数据失败: {e}")
            return False


# 全局单例
_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器单例"""
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
