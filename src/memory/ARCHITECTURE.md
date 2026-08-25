# 多级记忆模块架构设计

## 一、记忆层级总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        多级记忆架构                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  L4 程序记忆 (Procedural)   ──── 知识库（图谱/说明书），只读         │
│     ↕ 查询接口                                                  │
│  L3 长期记忆 (Long-term)    ──── 用户画像 + 偏好，永久保留          │
│     ↕ 画像更新                                                  │
│  L2 中期记忆 (Mid-term)     ──── 对话摘要 + 关键事件，跨对话         │
│     ↕ 摘要生成                                                  │
│  L1 短期记忆 (Short-term)   ──── 对话完整历史，跨轮次               │
│     ↕ 消息追加                                                  │
│  L0 工作记忆 (Working)      ──── 当前轮次上下文，内存，不持久化     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 二、各层级详细说明

### L0 工作记忆 (Working Memory)

**存储**：内存字典 `{conversation_id: WorkingMemory}`，不持久化

**生命周期**：单次请求处理期间有效，对话结束后可清除

**内容**：
| 字段 | 用途 |
|:---|:---|
| `current_intent` | 当前意图，避免重复分类 |
| `current_set_id` | 当前套装，用于工具参数补全 |
| `current_step` | 当前步骤，用于指代消解 |
| `frustration_score` | 实时挫折分数 |
| `last_discussed_parts` | 最近讨论的零件列表 |
| `last_discussed_step` | 最近讨论的步骤号 |
| `tool_results` | 本轮工具调用结果缓存 |

**使用场景**：
- 指代消解："这一步" → 查询 `last_discussed_step`
- 工具参数补全：缺少 set_id 时从 `current_set_id` 获取
- 挫折检测：累积 `frustration_score`

---

### L1 短期记忆 (Short-term Memory)

**存储**：Redis List `conv:{id}:msgs`，每条消息是 JSON

**生命周期**：单对话，TTL 30 天

**消息结构**：
```json
{
  "id": "abc123",
  "role": "user",
  "content": "第35步怎么拼",
  "timestamp": "2024-01-01T12:00:00",
  "intent": "search_manual",
  "importance": 0.6,
  "entities": ["step_35"],
  "tool_calls": null,
  "feedback": null
}
```

**关键设计**：
1. **重要度评分**：每条消息自动计算 important (0-1)
   - 工具调用消息：0.7
   - 用户提问：0.6
   - 验收结果：0.8
   - 安抚消息：0.3

2. **自动清理**：超过 100 条时，保留重要消息（importance > 0.6）

3. **实体提取**：自动提取零件号/颜色/步骤号，用于后续检索

4. **反馈索引**：使用 Hash 索引加速反馈更新，O(1) 定位

---

### L2 中期记忆 (Mid-term Memory)

**存储**：Redis String `conv:{id}:summary` + List `set:{set_id}:summaries`

**生命周期**：对话结束后生成，永久保留（可配置上限）

**内容**：
```json
{
  "conversation_id": "abc",
  "set_id": "10295",
  "summary": "用户提出了 5 个问题，执行了 3 次工具调用",
  "key_events": ["调用 search_manual_step", "调用 find_part_alternative"],
  "total_messages": 12,
  "total_steps_covered": [35, 36, 37],
  "parts_discussed": ["3001", "3005"],
  "created_at": "2024-01-01T12:30:00"
}
```

**生成时机**：
- 消息数超过 10 条时自动生成
- 对话结束时（用户长时间无操作）
- 手动触发

**使用场景**：
- 上下文压缩：LLM 输入时用摘要代替全部历史
- 跨对话关联：同套装的历史摘要注入上下文
- 进度追踪：`total_steps_covered` 显示已完成的步骤

---

### L3 长期记忆 (Long-term Memory)

**存储**：Redis String `user:{user_id}:profile`

**生命周期**：永久保留，定期更新

**内容**：
```json
{
  "user_id": "default",
  "skill_level": "intermediate",
  "preferred_sets": ["10295", "42141"],
  "common_parts": ["3001", "3005", "3020"],
  "total_conversations": 15,
  "total_messages": 230,
  "avg_frustration_score": 25.5,
  "frustration_triggers": ["步骤复杂", "缺件"],
  "language": "zh",
  "response_style": "detailed",
  "first_seen": "2024-01-01T00:00:00",
  "last_seen": "2024-01-15T12:00:00"
}
```

**更新策略**：
- 每 10 条消息更新一次统计
- 挫折分数按 24 小时周期衰减
- 技能水平根据工具调用成功率调整

**使用场景**：
- 个性化回复：根据 `skill_level` 调整解释详细程度
- 挫折预防：`frustration_triggers` 预警
- 套装推荐：`preferred_sets` 推荐相关套装

---

### L4 程序记忆 (Procedural Memory)

**存储**：外部系统（Neo4j 图谱 + ChromaDB 向量）

**性质**：只读，不通过记忆管理器修改

**接口**：
```python
class ProceduralMemory:
    def query_part_alternative(part_name, color) -> dict
    def query_manual_step(set_id, step) -> dict
    def search_similar_images(image_url) -> dict
```

---

## 三、记忆流转机制

### 3.1 消息写入流程

```
用户消息
    │
    ▼
┌──────────────────────┐
│ 1. 指代消解 (L0)      │  "这一步" → "第35步"
│ 2. 意图分类           │  L1/L2/L3 路由
│ 3. 实体提取           │  ["step_35", "color_红"]
│ 4. 重要度计算         │  0.6
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 写入 L1 短期记忆      │  RPUSH conv:{id}:msgs
│ 更新 L0 工作记忆      │  last_discussed_step = 35
│ 检查清理条件          │  len > 100? → 清理
└──────────────────────┘
```

### 3.2 LLM 上下文构建流程

```
新消息到达
    │
    ▼
┌──────────────────────────────────────────┐
│ build_enhanced_context(conversation_id)   │
├──────────────────────────────────────────┤
│ 1. 用户画像 (L3)                          │  "[用户偏好] 技能水平: intermediate"
│ 2. 对话摘要 (L2, 如有)                    │  "[对话摘要] 用户提出了 5 个问题..."
│ 3. 套装历史摘要 (L2, 如有)                 │  "[历史拼搭记录] 上次拼到第 40 步..."
│ 4. 最近 N 条消息 (L1)                     │  最近 20 条消息
└──────────────────────────────────────────┘
    │
    ▼
  LLM 输入
```

### 3.3 记忆升级流程

```
L1 消息积累（> 10 条）
    │
    ▼
┌──────────────────────┐
│ 生成 L2 摘要          │  create_conversation_summary()
│ - 统计关键事件         │
│ - 提取涉及步骤         │
│ - 提取讨论零件         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 更新 L3 用户画像      │  update_user_profile()
│ - 更新统计            │
│ - 更新常见零件         │
│ - 衰减挫折分数         │
└──────────────────────┘
```

### 3.4 记忆清理流程

```
L1 消息数 > 100
    │
    ▼
┌──────────────────────┐
│ 按重要度排序           │
│ 保留 importance > 0.6 │
│ 归档其余消息           │  标记 archived=true
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ TTL 过期（30 天）      │  Redis 自动清理
│ 对话无活动 → 生成摘要   │  升级到 L2
└──────────────────────┘
```

---

## 四、与现有系统的集成

### 4.1 替换 ConversationManager

```python
# 旧方式
from src.session.conversation_manager import get_conversation_manager
conv_manager = get_conversation_manager()
conv_manager.add_message(conv_id, msg)

# 新方式
from src.memory.manager import get_memory_manager
memory = get_memory_manager()
memory.add_message(conv_id, role, content, intent="search_manual")
```

### 4.2 增强 Agent 上下文

```python
# server.py 中
memory = get_memory_manager()

# 旧：注入全部历史
messages_to_inject = [all messages]

# 新：智能构建上下文
context = memory.build_enhanced_context(
    conversation_id=request.conversation_id,
    user_id="default",
)
```

### 4.3 指代消解集成

```python
# 在意图分类前
resolved_message = memory.resolve_reference(
    conversation_id=request.conversation_id,
    message=request.message,
)
intent = classify_intent(resolved_message)
```

---

## 五、Redis 存储结构

```
# L0: 工作记忆（内存，不存储）

# L1: 短期记忆
conv:{id}:msgs       → List<JSON>  消息列表
conv:{id}:msg_index  → Hash        消息 ID → 索引位置
conv:{id}            → Hash        对话元数据

# L2: 中期记忆
conv:{id}:summary    → JSON String 对话摘要
set:{set_id}:summaries → List<JSON> 套装相关摘要列表

# L3: 长期记忆
user:{user_id}:profile → JSON String 用户画像

# 原有（保留）
conversations        → Set         所有对话 ID
set:{set_id}         → Hash        套装信息
```

---

## 六、配置参数

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `MAX_MESSAGES_PER_CONVERSATION` | 100 | 单对话最大消息数 |
| `CONTEXT_WINDOW_SIZE` | 20 | LLM 上下文窗口 |
| `MESSAGE_TTL_DAYS` | 30 | 消息过期天数 |
| `SUMMARY_THRESHOLD` | 10 | 生成摘要的最小消息数 |
| `FRUSTATION_DECAY_HOURS` | 24 | 挫折分数衰减周期 |
| `PROFILE_UPDATE_INTERVAL` | 10 | 画像更新间隔（消息数） |
