"""会话数据模型"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ConversationMeta(BaseModel):
    """对话元数据"""
    id: str
    title: str
    set_id: str = ""
    created_at: str
    updated_at: str


class StoredMessage(BaseModel):
    """存储的消息"""
    id: str
    role: str  # user / assistant
    content: str
    image_url: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    thinking: Optional[list[str]] = None
    timestamp: str
    feedback: Optional[int] = None  # 1=like, -1=dislike


class ConversationCreate(BaseModel):
    """创建对话请求"""
    set_id: str = ""
    title: str = ""


class ConversationUpdate(BaseModel):
    """更新对话请求"""
    title: Optional[str] = None
    set_id: Optional[str] = None


class MessageFeedbackUpdate(BaseModel):
    """消息反馈更新"""
    feedback: Optional[int] = None  # 1=like, -1/None=清除


class SetInfo(BaseModel):
    """套装信息"""
    set_id: str
    name: str
    total_steps: int = 0
    total_parts: int = 0
    current_step: int = 0
    thumbnail_url: str = ""


class ProgressUpdate(BaseModel):
    """进度更新"""
    current_step: int
