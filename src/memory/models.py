"""多级记忆数据模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class MemoryLevel(str, Enum):
    """记忆层级"""
    L0_WORKING = "l0_working"       # 工作记忆
    L1_SHORTTERM = "l1_shortterm"   # 短期记忆（对话历史）
    L2_MIDTERM = "l2_midterm"       # 中期记忆（摘要/事件）
    L3_LONGTERM = "l3_longterm"     # 长期记忆（用户画像）
    L4_PROCEDURAL = "l4_procedural" # 程序记忆（知识库）


# ===== L0: 工作记忆 =====

class WorkingMemory(BaseModel):
    """工作记忆 - 当前轮次的即时上下文（不持久化，内存中）"""

    # 当前对话状态
    conversation_id: str = ""
    current_intent: str = ""                # 当前意图
    current_set_id: str = ""                # 当前套装
    current_step: int = 0                   # 当前步骤

    # 心理状态
    frustration_score: int = 0              # 挫折分数 0-100
    retry_count: int = 0                    # 当前节点重试次数
    last_active_time: float = 0.0           # 最后活跃时间

    # 上下文缓存（指代消解用）
    last_discussed_parts: list[str] = []    # 最近讨论的零件
    last_discussed_step: int = 0            # 最近讨论的步骤
    pending_confirmation: Optional[dict] = None  # 待确认操作

    # 本轮工具调用结果缓存
    tool_results: dict = {}                 # {tool_name: result}


# ===== L1: 短期记忆 =====

class MemoryMessage(BaseModel):
    """记忆中的消息（比 StoredMessage 更丰富）"""

    id: str
    role: str                               # user / assistant / system
    content: str

    # 元数据
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    image_url: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    thinking: Optional[list[str]] = None
    feedback: Optional[int] = None          # 1=like, -1=dislike

    # 记忆增强字段
    intent: str = ""                        # 该消息的意图分类
    importance: float = 0.5                 # 重要度 0-1（用于摘要和清理）
    entities: list[str] = []                # 提取的实体（零件号/颜色/步骤号）


class ShortTermMemory(BaseModel):
    """短期记忆 - 单个对话的完整历史"""

    conversation_id: str
    messages: list[MemoryMessage] = []

    # 对话元数据
    set_id: str = ""
    title: str = ""
    created_at: str = ""
    updated_at: str = ""

    # 统计
    total_messages: int = 0
    total_tool_calls: int = 0


# ===== L2: 中期记忆 =====

class ConversationSummary(BaseModel):
    """对话摘要 - 对话结束后生成"""

    conversation_id: str
    set_id: str = ""

    # 摘要内容
    summary: str = ""                       # 自然语言摘要
    key_events: list[str] = []              # 关键事件列表
    resolved_queries: list[str] = []        # 已解决的问题
    unresolved_queries: list[str] = []      # 未解决的问题

    # 统计
    total_messages: int = 0
    total_steps_covered: list[int] = []     # 涉及到的步骤号
    parts_discussed: list[str] = []         # 讨论过的零件

    # 时间
    created_at: str = ""
    duration_minutes: float = 0.0           # 对话时长


class MidTermMemory(BaseModel):
    """中期记忆 - 跨对话的摘要和关键事件"""

    # 按套装组织的摘要
    set_summaries: dict[str, list[ConversationSummary]] = {}  # {set_id: [summary]}

    # 关键事件时间线
    key_events: list[dict] = []             # [{date, event, set_id}]

    # 最近 N 次对话的 ID（用于快速加载）
    recent_conversation_ids: list[str] = []


# ===== L3: 长期记忆 =====

class UserProfile(BaseModel):
    """用户画像 - 跨会话持久化"""

    # 基础信息
    user_id: str = "default"

    # 拼搭习惯
    skill_level: str = "beginner"           # beginner/intermediate/advanced
    preferred_sets: list[str] = []          # 常拼的套装
    common_parts: list[str] = []            # 常问的零件

    # 行为统计
    total_conversations: int = 0
    total_messages: int = 0
    total_build_time_minutes: float = 0.0   # 总拼搭时长

    # 挫折模式
    avg_frustration_score: float = 0.0      # 平均挫折分
    frustration_triggers: list[str] = []    # 常见挫折触发词
    encouragement_effectiveness: dict = {}  # 安抚话术效果统计

    # 偏好
    language: str = "zh"                    # 语言偏好
    response_style: str = "detailed"        # concise/detailed

    # 时间
    first_seen: str = ""
    last_seen: str = ""


class LongTermMemory(BaseModel):
    """长期记忆"""

    user_profile: UserProfile = Field(default_factory=UserProfile)

    # 长期知识（从对话中提炼）
    known_techniques: list[str] = []        # 用户已掌握的技巧
    common_mistakes: list[str] = []         # 常犯的错误
    favorite_solutions: dict = {}           # 偏好的解决方案 {problem: solution}


# ===== L4: 程序记忆（知识库接口） =====

class ProceduralMemory(BaseModel):
    """程序记忆 - 只读知识库接口"""

    # 这些是其他模块的引用，不重复存储
    model_config = {"arbitrary_types_allowed": True}
    neo4j_client: Optional[object] = None   # 图谱客户端
    vector_store: Optional[object] = None   # 向量存储

    def query_part_alternative(self, part_name: str, color: str) -> dict:
        """查询零件替代"""
        pass

    def query_manual_step(self, set_id: str, step: int) -> dict:
        """查询说明书步骤"""
        pass
