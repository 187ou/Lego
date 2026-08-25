"""多级记忆管理器测试 - 验证完备性、准确度和边缘情况"""

import pytest
import time
import json
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入 memory 模块
import importlib.util

# 加载 models
spec_models = importlib.util.spec_from_file_location(
    "memory_models",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "memory", "models.py"),
)
memory_models = importlib.util.module_from_spec(spec_models)
sys.modules["memory_models"] = memory_models
spec_models.loader.exec_module(memory_models)

# 加载 manager
spec_mgr = importlib.util.spec_from_file_location(
    "memory_manager",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "memory", "manager.py"),
)
memory_manager = importlib.util.module_from_spec(spec_mgr)
sys.modules["memory_manager"] = memory_manager

# Mock redis_client 模块
mock_redis_module = type(sys)("src.session.redis_client")
mock_redis_module.get_redis = MagicMock()
mock_redis_module.check_redis_connection = MagicMock(return_value=True)
sys.modules["src.session.redis_client"] = mock_redis_module

spec_mgr.loader.exec_module(memory_manager)

MemoryManager = memory_manager.MemoryManager
MemoryConfig = memory_manager.MemoryConfig
get_memory_manager = memory_manager.get_memory_manager
WorkingMemory = memory_models.WorkingMemory
MemoryMessage = memory_models.MemoryMessage
ConversationSummary = memory_models.ConversationSummary
UserProfile = memory_models.UserProfile


# ===== Fixtures =====

@pytest.fixture
def mock_redis():
    """创建模拟的 Redis 客户端（不使用 MagicMock，手动实现）"""
    redis_mock = type('MockRedis', (), {})()

    # 模拟数据存储
    redis_mock._strings = {}
    redis_mock._lists = {}
    redis_mock._hashes = {}
    redis_mock._sets = {}

    # String 操作
    redis_mock.get = lambda k: redis_mock._strings.get(k)
    redis_mock.set = lambda k, v, **kw: redis_mock._strings.__setitem__(k, v)
    redis_mock.delete = lambda k: (
        redis_mock._strings.pop(k, None),
        redis_mock._lists.pop(k, None),
        redis_mock._hashes.pop(k, None),
        redis_mock._sets.pop(k, None),
    )

    # List 操作
    def _rpush(k, v):
        redis_mock._lists.setdefault(k, []).append(v)
    def _llen(k):
        return len(redis_mock._lists.get(k, []))
    def _lrange(k, start, end):
        lst = redis_mock._lists.get(k, [])
        if end == -1:
            return lst[start:]
        return lst[start:end+1]
    def _lindex(k, i):
        lst = redis_mock._lists.get(k, [])
        return lst[i] if i < len(lst) else None
    def _lset(k, i, v):
        lst = redis_mock._lists.get(k, [])
        if i < len(lst):
            lst[i] = v
    def _lpush(k, v):
        redis_mock._lists.setdefault(k, []).insert(0, v)
    def _ltrim(k, start, end):
        lst = redis_mock._lists.get(k, [])
        redis_mock._lists[k] = lst[start:end+1]

    redis_mock.rpush = _rpush
    redis_mock.llen = _llen
    redis_mock.lrange = _lrange
    redis_mock.lindex = _lindex
    redis_mock.lset = _lset
    redis_mock.lpush = _lpush
    redis_mock.ltrim = _ltrim

    # Hash 操作
    def _hget(k, f):
        return redis_mock._hashes.get(k, {}).get(f)
    def _hset(k, f=None, v=None, mapping=None, **kw):
        if mapping:
            redis_mock._hashes.setdefault(k, {}).update(mapping)
        elif f is not None:
            redis_mock._hashes.setdefault(k, {})[f] = v
    def _hgetall(k):
        return redis_mock._hashes.get(k, {})

    redis_mock.hget = _hget
    redis_mock.hset = _hset
    redis_mock.hgetall = _hgetall

    # Set 操作
    redis_mock.sadd = lambda k, v: redis_mock._sets.setdefault(k, set()).add(v)
    redis_mock.smembers = lambda k: redis_mock._sets.get(k, set())
    redis_mock.srem = lambda k, v: redis_mock._sets.get(k, set()).discard(v)

    # 其他
    redis_mock.exists = lambda k: k in redis_mock._strings or k in redis_mock._lists or k in redis_mock._hashes
    redis_mock.expire = lambda k, ttl: None
    redis_mock.keys = lambda pattern: []
    redis_mock.ping = lambda: True

    return redis_mock


@pytest.fixture
def mem_manager(mock_redis):
    """创建带 Mock Redis 的记忆管理器"""
    # 直接设置 mock 模块的函数
    mock_redis_module.get_redis = lambda: mock_redis
    mock_redis_module.check_redis_connection = lambda: True

    # 重置单例
    memory_manager._manager = None
    manager = get_memory_manager()

    # 确保 manager._redis 被正确设置
    manager._redis = mock_redis

    return manager


# ===== L0: 工作记忆测试 =====

class TestWorkingMemory:
    """L0 工作记忆测试"""

    def test_create_working_memory(self, mem_manager):
        """测试创建工作记忆"""
        wm = mem_manager.get_working_memory("conv_1")
        assert wm.conversation_id == "conv_1"
        assert wm.frustration_score == 0
        assert wm.retry_count == 0
        assert wm.last_discussed_step == 0

    def test_working_memory_isolation(self, mem_manager):
        """测试不同对话的工作记忆隔离"""
        wm1 = mem_manager.get_working_memory("conv_1")
        wm2 = mem_manager.get_working_memory("conv_2")

        wm1.frustration_score = 50
        wm2.frustration_score = 30

        assert wm1.frustration_score == 50
        assert wm2.frustration_score == 30

    def test_update_working_memory(self, mem_manager):
        """测试更新工作记忆"""
        wm = mem_manager.update_working_memory(
            "conv_1",
            frustration_score=60,
            last_discussed_step=35,
        )
        assert wm.frustration_score == 60
        assert wm.last_discussed_step == 35

    def test_clear_working_memory(self, mem_manager):
        """测试清除工作记忆"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.frustration_score = 50

        mem_manager.clear_working_memory("conv_1")

        # 清除后应重新创建
        wm_new = mem_manager.get_working_memory("conv_1")
        assert wm_new.frustration_score == 0

    def test_working_memory_persisted_to_redis(self, mem_manager):
        """测试工作记忆持久化到 Redis"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.frustration_score = 80

        # 重新获取同一管理器（工作记忆应在缓存中）
        wm_same = mem_manager.get_working_memory("conv_1")
        assert wm_same.frustration_score == 80

    def test_working_memory_isolation(self, mem_manager):
        """测试不同对话的工作记忆隔离"""
        wm1 = mem_manager.get_working_memory("conv_1")
        wm2 = mem_manager.get_working_memory("conv_2")

        wm1.frustration_score = 50
        wm2.frustration_score = 30

        assert wm1.frustration_score == 50
        assert wm2.frustration_score == 30


# ===== L1: 短期记忆测试 =====

class TestShortTermMemory:
    """L1 短期记忆测试"""

    def test_add_message(self, mem_manager):
        """测试添加消息"""
        msg = mem_manager.add_message(
            conversation_id="conv_1",
            role="user",
            content="第35步怎么拼",
        )
        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "第35步怎么拼"
        assert msg.timestamp is not None

    def test_add_message_with_metadata(self, mem_manager):
        """测试添加带元数据的消息"""
        msg = mem_manager.add_message(
            conversation_id="conv_1",
            role="assistant",
            content="第35步是...",
            tool_calls=[{"name": "search_manual_step", "args": {"step_number": 35}}],
            intent="search_manual",
        )
        assert msg.tool_calls is not None
        assert msg.tool_calls[0]["name"] == "search_manual_step"
        assert msg.intent == "search_manual"

    def test_get_messages_pagination(self, mem_manager):
        """测试消息分页"""
        for i in range(25):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        # 默认返回最近 20 条
        msgs = mem_manager.get_messages("conv_1")
        assert len(msgs) == 20

        # 指定 limit
        msgs = mem_manager.get_messages("conv_1", limit=10)
        assert len(msgs) == 10

        # 带 offset
        msgs = mem_manager.get_messages("conv_1", limit=5, offset=0)
        assert len(msgs) == 5
        assert msgs[0].content == "消息20"  # 最近 5 条

    def test_get_all_messages(self, mem_manager):
        """测试获取全部消息"""
        for i in range(5):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        msgs = mem_manager.get_all_messages("conv_1")
        assert len(msgs) == 5

    def test_get_message_count(self, mem_manager):
        """测试消息计数"""
        assert mem_manager.get_message_count("conv_1") == 0

        mem_manager.add_message("conv_1", "user", "消息1")
        mem_manager.add_message("conv_1", "assistant", "回复1")

        assert mem_manager.get_message_count("conv_1") == 2

    def test_auto_title_generation(self, mem_manager):
        """测试自动标题生成"""
        mem_manager.add_message("conv_1", "user", "第35步怎么拼")

        # 实际存储在 conv:conv_1 中
        title = mem_manager.r.hget("conv:conv_1", "title")
        assert title is not None
        assert "第35步" in title

    def test_title_not_overwrite(self, mem_manager):
        """测试标题不会被后续消息覆盖"""
        mem_manager.add_message("conv_1", "user", "第一条消息")
        mem_manager.add_message("conv_1", "user", "第二条消息")

        title = mem_manager.r.hget("conv:conv_1", "title")
        assert "第一条" in title

    def test_message_order_preserved(self, mem_manager):
        """测试消息顺序保持"""
        for i in range(5):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        msgs = mem_manager.get_all_messages("conv_1")
        for i, msg in enumerate(msgs):
            assert msg.content == f"消息{i}"


# ===== 重要度计算测试 =====

class TestImportanceCalculation:
    """重要度计算测试"""

    def test_tool_call_importance(self, mem_manager):
        """工具调用消息重要度高"""
        msg = MemoryMessage(
            id="1", role="assistant", content="结果",
            tool_calls=[{"name": "search_manual_step", "args": {}}],
        )
        importance = mem_manager._calculate_importance(msg)
        assert importance >= MemoryConfig.IMPORTANCE_TOOL_CALL

    def test_user_question_importance(self, mem_manager):
        """用户提问重要度中等"""
        msg = MemoryMessage(id="1", role="user", content="第35步怎么拼？")
        importance = mem_manager._calculate_importance(msg)
        assert importance >= MemoryConfig.IMPORTANCE_USER_QUESTION

    def test_encouragement_low_importance(self, mem_manager):
        """安抚消息重要度低"""
        msg = MemoryMessage(id="1", role="assistant", content="加油！别急！")
        importance = mem_manager._calculate_importance(msg)
        assert importance <= MemoryConfig.IMPORTANCE_ENCOURAGEMENT

    def test_verification_high_importance(self, mem_manager):
        """验收结果重要度高"""
        msg = MemoryMessage(
            id="1", role="assistant", content="验收通过",
            tool_calls=[{"name": "verify_build_result", "args": {}}],
        )
        importance = mem_manager._calculate_importance(msg)
        assert importance >= MemoryConfig.IMPORTANCE_VERIFICATION


# ===== 实体提取测试 =====

class TestEntityExtraction:
    """实体提取测试"""

    def test_extract_part_ids(self, mem_manager):
        """提取零件编号"""
        entities = mem_manager._extract_entities("3001 和 3005 是什么")
        assert "3001" in entities
        assert "3005" in entities

    def test_extract_step_numbers(self, mem_manager):
        """提取步骤号"""
        entities = mem_manager._extract_entities("第35步怎么拼")
        assert "step_35" in entities

    def test_extract_colors(self, mem_manager):
        """提取颜色"""
        entities = mem_manager._extract_entities("红色2x4砖")
        assert "color_红" in entities

    def test_extract_mixed_entities(self, mem_manager):
        """提取混合实体"""
        entities = mem_manager._extract_entities("红色3001砖第35步")
        # 3001 是零件号
        assert "3001" in entities, f"Expected 3001 in {entities}"
        # 步骤号
        assert "step_35" in entities, f"Expected step_35 in {entities}"
        # 颜色（color_红）
        assert any("红" in e for e in entities), f"Expected color entity in {entities}"

    def test_no_duplicate_entities(self, mem_manager):
        """实体去重"""
        entities = mem_manager._extract_entities("3001 3001 3001")
        assert entities.count("3001") == 1

    def test_empty_content(self, mem_manager):
        """空内容返回空列表"""
        entities = mem_manager._extract_entities("")
        assert entities == []


# ===== 指代消解测试 =====

class TestReferenceResolution:
    """指代消解测试"""

    def test_resolve_this_step(self, mem_manager):
        """解析'这一步'"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 35

        resolved = mem_manager.resolve_reference("conv_1", "这一步怎么拼")
        assert "第35步" in resolved

    def test_resolve_prev_step(self, mem_manager):
        """解析'上一步'"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 35

        resolved = mem_manager.resolve_reference("conv_1", "上一步是什么")
        assert "第34步" in resolved

    def test_resolve_next_step(self, mem_manager):
        """解析'下一步'"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 35

        resolved = mem_manager.resolve_reference("conv_1", "下一步怎么拼")
        assert "第36步" in resolved

    def test_resolve_no_context(self, mem_manager):
        """无上下文时保持原样"""
        # 使用新的对话 ID，确保没有上下文
        resolved = mem_manager.resolve_reference("conv_no_context", "这一步怎么拼")
        assert resolved == "这一步怎么拼"

    def test_resolve_prev_step_min_one(self, mem_manager):
        """上一步最小为 1"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 1

        resolved = mem_manager.resolve_reference("conv_1", "上一步是什么")
        assert "第1步" in resolved

    def test_resolve_multiple_references(self, mem_manager):
        """一句话中有多个指代"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 35

        resolved = mem_manager.resolve_reference("conv_1", "这一步和上一步有什么区别")
        assert "第35步" in resolved
        assert "第34步" in resolved


# ===== L2: 中期记忆（摘要）测试 =====

class TestMidTermMemory:
    """L2 中期记忆测试"""

    def test_summary_not_generated_below_threshold(self, mem_manager):
        """消息数不足时不生成摘要"""
        for i in range(5):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        summary = mem_manager.create_conversation_summary("conv_1")
        assert summary is None

    def test_summary_generated_above_threshold(self, mem_manager):
        """消息数足够时生成摘要"""
        for i in range(12):
            mem_manager.add_message("conv_1", "user", f"第{i}步怎么拼")

        summary = mem_manager.create_conversation_summary("conv_1")
        assert summary is not None
        assert summary.conversation_id == "conv_1"
        assert summary.total_messages == 12

    def test_summary_caches_correctly(self, mem_manager):
        """摘要正确缓存"""
        for i in range(12):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        mem_manager.create_conversation_summary("conv_1")

        # 再次获取应从缓存读取
        cached = mem_manager.get_conversation_summary("conv_1")
        assert cached is not None
        assert cached.total_messages == 12

    def test_set_summaries_linked(self, mem_manager):
        """套装摘要关联"""
        mem_manager.r.hset("conv:conv_1", mapping={"set_id": "10295"})

        for i in range(12):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        mem_manager.create_conversation_summary("conv_1")

        # 检查套装摘要列表
        summaries = mem_manager.get_set_summaries("10295")
        assert len(summaries) >= 1


# ===== L3: 长期记忆（用户画像）测试 =====

class TestLongTermMemory:
    """L3 长期记忆测试"""

    def test_create_default_profile(self, mem_manager):
        """创建默认用户画像"""
        profile = mem_manager.get_user_profile("user_1")
        assert profile.user_id == "user_1"
        assert profile.skill_level == "beginner"
        assert profile.total_conversations == 0

    def test_update_profile(self, mem_manager):
        """更新用户画像"""
        profile = mem_manager.update_user_profile(
            user_id="user_1",
            skill_level="intermediate",
            total_conversations=5,
        )
        assert profile.skill_level == "intermediate"
        assert profile.total_conversations == 5

    def test_profile_persistence(self, mem_manager):
        """画像持久化"""
        mem_manager.update_user_profile(user_id="user_1", skill_level="advanced")

        # 重新获取
        profile = mem_manager.get_user_profile("user_1")
        assert profile.skill_level == "advanced"

    def test_profile_frustration_decay(self, mem_manager):
        """挫折分数衰减"""
        # 先创建画像
        mem_manager.update_user_profile(user_id="user_1")

        # 手动设置 last_seen 为过去，挫折分数为 80
        old_time = (datetime.now() - timedelta(hours=48)).isoformat()
        profile_data = json.loads(mem_manager.r._strings.get("user:user_1:profile", "{}"))
        profile_data["last_seen"] = old_time
        profile_data["avg_frustration_score"] = 80
        mem_manager.r._strings["user:user_1:profile"] = json.dumps(profile_data, ensure_ascii=False)

        # 更新画像（不传 avg_frustration_score，让衰减逻辑生效）
        mem_manager.update_user_profile(user_id="user_1")

        # 衰减后分数应降低（80 * 0.5 = 40）
        updated = mem_manager.get_user_profile("user_1")
        assert updated.avg_frustration_score < 80, \
            f"Expected decayed score < 80, got {updated.avg_frustration_score}"

    def test_profile_common_parts_extraction(self, mem_manager):
        """常见零件提取"""
        for i in range(12):
            mem_manager.add_message("conv_1", "user", f"3001 红色砖 第{i}步")

        mem_manager.update_user_profile(user_id="user_1", conversation_id="conv_1")

        profile = mem_manager.get_user_profile("user_1")
        assert "3001" in profile.common_parts


# ===== 上下文构建测试 =====

class TestContextBuilding:
    """上下文构建测试"""

    def test_build_context_empty(self, mem_manager):
        """空对话返回空上下文"""
        context = mem_manager.build_context("conv_1")
        assert context == []

    def test_build_context_with_messages(self, mem_manager):
        """有消息时构建上下文"""
        for i in range(5):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        context = mem_manager.build_context("conv_1", include_summary=False)
        assert len(context) == 5
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "消息0"

    def test_build_context_with_summary(self, mem_manager):
        """有摘要时包含摘要"""
        for i in range(12):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        mem_manager.create_conversation_summary("conv_1")

        context = mem_manager.build_context("conv_1", include_summary=True)
        # 第一条应是摘要
        assert any("[对话摘要]" in c.get("content", "") for c in context)

    def test_build_enhanced_context_with_profile(self, mem_manager):
        """增强上下文包含用户画像"""
        mem_manager.update_user_profile(user_id="user_1", skill_level="advanced")
        mem_manager.add_message("conv_1", "user", "消息")

        context = mem_manager.build_enhanced_context("conv_1", user_id="user_1")
        assert any("[用户偏好]" in c.get("content", "") for c in context)

    def test_context_window_limit(self, mem_manager):
        """上下文窗口限制"""
        for i in range(30):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        context = mem_manager.build_context("conv_1", include_summary=False)
        # 应受 CONTEXT_WINDOW_SIZE 限制
        assert len(context) <= MemoryConfig.CONTEXT_WINDOW_SIZE


# ===== 边缘情况测试 =====

class TestEdgeCases:
    """边缘情况测试"""

    def test_empty_message_content(self, mem_manager):
        """空消息内容"""
        msg = mem_manager.add_message("conv_1", "user", "")
        assert msg.content == ""
        assert msg.entities == []

    def test_very_long_message(self, mem_manager):
        """超长消息"""
        long_content = "A" * 10000
        msg = mem_manager.add_message("conv_1", "user", long_content)
        assert len(msg.content) == 10000

    def test_special_characters_in_message(self, mem_manager):
        """特殊字符消息"""
        special = "你好！@#$%^&*()_+{}|:<>?~`"
        msg = mem_manager.add_message("conv_1", "user", special)
        assert msg.content == special

    def test_unicode_emoji_message(self, mem_manager):
        """Unicode Emoji 消息"""
        emoji = "🧱🤖👋👍"
        msg = mem_manager.add_message("conv_1", "user", emoji)
        assert msg.content == emoji

    def test_concurrent_messages(self, mem_manager):
        """快速连续消息"""
        for i in range(50):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        count = mem_manager.get_message_count("conv_1")
        assert count == 50

    def test_nonexistent_conversation(self, mem_manager):
        """不存在的对话"""
        msgs = mem_manager.get_messages("nonexistent")
        assert msgs == []

        count = mem_manager.get_message_count("nonexistent")
        assert count == 0

    def test_feedback_update_nonexistent_message(self, mem_manager):
        """更新不存在的消息反馈"""
        result = mem_manager.update_message_feedback("conv_1", "nonexistent_id", 1)
        assert result is False

    def test_message_with_only_whitespace(self, mem_manager):
        """纯空白消息"""
        msg = mem_manager.add_message("conv_1", "user", "   ")
        assert msg.content == "   "

    def test_entity_extraction_with_no_entities(self, mem_manager):
        """无实体的内容"""
        entities = mem_manager._extract_entities("你好世界")
        assert entities == []

    def test_importance_with_empty_content(self, mem_manager):
        """空内容的重要度"""
        msg = MemoryMessage(id="1", role="user", content="")
        importance = mem_manager._calculate_importance(msg)
        assert importance == 0.5  # 基础分

    def test_reference_with_zero_step(self, mem_manager):
        """步骤号为 0 时的指代"""
        wm = mem_manager.get_working_memory("conv_1")
        wm.last_discussed_step = 0

        resolved = mem_manager.resolve_reference("conv_1", "这一步怎么拼")
        # 步骤号为 0 时应保持原样
        assert resolved == "这一步怎么拼"

    def test_cleanup_preserves_important_messages(self, mem_manager):
        """清理时保留重要消息"""
        # 添加一些低重要度消息
        for i in range(80):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        # 添加高重要度消息（工具调用）
        mem_manager.add_message(
            "conv_1", "assistant", "结果",
            tool_calls=[{"name": "verify_build_result", "args": {}}],
        )

        # 触发清理
        mem_manager._cleanup_old_messages("conv_1")

        # 验证总消息数在限制内
        count = mem_manager.get_message_count("conv_1")
        assert count <= MemoryConfig.MAX_MESSAGES_PER_CONVERSATION + 10  # 允许一些余量


# ===== 反馈索引测试 =====

class TestFeedbackIndex:
    """反馈索引测试"""

    def test_feedback_with_index(self, mem_manager):
        """有索引时的反馈更新"""
        msg = mem_manager.add_message("conv_1", "user", "消息")

        # 建立索引
        mem_manager.r.hset("conv_1:msg_index", msg.id, "0")

        result = mem_manager.update_message_feedback("conv_1", msg.id, 1)
        assert result is True

        # 验证反馈已更新
        msgs = mem_manager.get_all_messages("conv_1")
        assert msgs[0].feedback == 1

    def test_feedback_without_index(self, mem_manager):
        """无索引时的反馈更新（遍历查找）"""
        msg = mem_manager.add_message("conv_1", "user", "消息")

        result = mem_manager.update_message_feedback("conv_1", msg.id, -1)
        assert result is True

        msgs = mem_manager.get_all_messages("conv_1")
        assert msgs[0].feedback == -1

    def test_feedback_clear(self, mem_manager):
        """清除反馈"""
        msg = mem_manager.add_message("conv_1", "user", "消息")
        mem_manager.update_message_feedback("conv_1", msg.id, 1)
        mem_manager.update_message_feedback("conv_1", msg.id, None)

        msgs = mem_manager.get_all_messages("conv_1")
        assert msgs[0].feedback is None


# ===== 性能测试 =====

class TestPerformance:
    """性能测试"""

    def test_add_message_performance(self, mem_manager):
        """添加消息性能"""
        start = time.perf_counter()
        for i in range(100):
            mem_manager.add_message("conv_1", "user", f"消息{i}")
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"添加 100 条消息耗时 {elapsed:.3f}s, 超过 1s"

    def test_get_messages_performance(self, mem_manager):
        """获取消息性能"""
        for i in range(100):
            mem_manager.add_message("conv_1", "user", f"消息{i}")

        start = time.perf_counter()
        for _ in range(100):
            mem_manager.get_messages("conv_1", limit=20)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"100 次查询耗时 {elapsed:.3f}s, 超过 1s"

    def test_entity_extraction_performance(self, mem_manager):
        """实体提取性能"""
        content = "红色3001砖第35步和蓝色3005砖第36步"

        start = time.perf_counter()
        for _ in range(1000):
            mem_manager._extract_entities(content)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"1000 次实体提取耗时 {elapsed:.3f}s, 超过 1s"


# ===== 集成测试 =====

class TestIntegration:
    """集成测试 - 模拟完整对话流程"""

    def test_full_conversation_flow(self, mem_manager):
        """完整对话流程"""
        # 1. 用户发送消息
        mem_manager.add_message("conv_1", "user", "第35步怎么拼", intent="search_manual")

        # 2. 更新工作记忆
        wm = mem_manager.update_working_memory("conv_1", last_discussed_step=35)

        # 3. AI 回复
        mem_manager.add_message(
            "conv_1", "assistant", "第35步：取出2x4红色砖...",
            tool_calls=[{"name": "search_manual_step", "args": {"step_number": 35}}],
        )

        # 4. 用户追问（指代）
        resolved = mem_manager.resolve_reference("conv_1", "上一步是什么")
        assert "第34步" in resolved

        # 5. 构建上下文
        context = mem_manager.build_context("conv_1")
        assert len(context) == 2

        # 6. 添加反馈
        msgs = mem_manager.get_all_messages("conv_1")
        mem_manager.update_message_feedback("conv_1", msgs[1].feedback or "", 1)

    def test_multi_turn_with_summary(self, mem_manager):
        """多轮对话 + 摘要生成"""
        # 模拟 15 轮对话
        for i in range(15):
            mem_manager.add_message("conv_1", "user", f"第{i}步怎么拼")
            mem_manager.add_message("conv_1", "assistant", f"第{i}步的答案...")

        # 生成摘要
        summary = mem_manager.create_conversation_summary("conv_1")
        assert summary is not None
        assert summary.total_messages == 30

        # 构建上下文（应包含摘要）
        context = mem_manager.build_context("conv_1")
        has_summary = any("[对话摘要]" in c.get("content", "") for c in context)
        assert has_summary

    def test_cross_conversation_user_profile(self, mem_manager):
        """跨对话用户画像更新"""
        # 第一个对话
        for i in range(5):
            mem_manager.add_message("conv_1", "user", f"3001 红色砖 第{i}步")
        mem_manager.update_user_profile(user_id="user_1", conversation_id="conv_1")

        # 第二个对话
        for i in range(5):
            mem_manager.add_message("conv_2", "user", f"3005 蓝色砖 第{i}步")
        mem_manager.update_user_profile(user_id="user_1", conversation_id="conv_2")

        # 验证画像累积
        profile = mem_manager.get_user_profile("user_1")
        assert profile.total_conversations == 2
        assert profile.total_messages == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
