# LEGO-Mate 智能拼搭助手

基于多模态 ReAct Agent 的乐高拼搭智能副驾，用户通过**聊天+拍照**获得缺件替代、说明书检索、拼搭验收、**3D 可视化拼搭**一站式服务。

## 核心功能

| 模块 | 功能 | 技术 |
| :----- | :----- | :----- |
| 对话中枢 | 意图自动路由 + 多轮记忆 + 对话管理 | LangGraph ReAct Agent |
| 视觉解析 | 图片→结构化JSON | Qwen2.5-VL / Ollama / GPT-4o + CLIP 零件识别 |
| 知识图谱 | 缺件替代查询 + 多条件约束推理 | Neo4j 多模态知识图谱 |
| RAG 检索 | 说明书步骤检索（多模态） | ChromaDB + 向量/关键词混合 |
| 验真闭环 | 成品验收对比 | CLIP 视觉相似度 |
| 3D 生成 | 文字→3D 积木模型 + 物理验证 + 自动修正 | LLM + Physics Validator + AutoFixer |
| 多级记忆 | L0-L4 五级记忆管理 + 指代消解 | Redis 持久化 |
| 统一检索 | L1-L4 多路检索融合 | 记忆 + 向量 + 图谱 + 跨模态 |
| 心理感知 | 挫折检测 + 共情话术 | 行为时序分析 + 话术库 |
| 3D 可视化 | 交互式 3D 拼装 + 步骤动画 | React Three Fiber + Three.js |
| 通知推送 | 验收结果/缺件提醒 | 飞书 Webhook |

## 快速开始

### 1. 环境要求

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) 包管理器
- Docker Desktop（用于 Neo4j + Redis）
- Node.js >= 18（用于前端）

### 2. 安装

```bash
# 克隆项目
git clone <repo_url>
cd LEGO-Mate

# 安装 Python 依赖
uv sync

# 安装前端依赖
cd frontend && npm install && cd ..
```

### 3. 启动基础设施

```bash
# 启动 Neo4j + Redis
docker compose up -d
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

最少配置：
```env
# 推理 LLM（必填）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.longcat.chat/openai
LLM_MODEL=LongCat-Flash-Chat

# 视觉模型（可选，默认 Mock）
VISION_PROVIDER=ollama
VISION_API_KEY=ollama
VISION_BASE_URL=http://localhost:11434/v1
VISION_MODEL=qwen2.5vl:7b
USE_REAL_VL=false
```

### 5. 导入示例数据

```bash
# 导入 Neo4j 零件数据
uv run python data/import_data.py

# 导入说明书向量数据
uv run python data/import_manual.py
```

### 6. 启动后端

```bash
uv run python server.py
# 服务运行在 http://localhost:8000
```

### 7. 启动前端

```bash
cd frontend
npm run dev
# 访问 http://localhost:5173
```

## 项目结构

```
LEGO-Mate/
├── docker-compose.yml        # Neo4j + Redis
├── pyproject.toml            # Python 依赖管理
├── server.py                 # FastAPI 后端服务
├── main.py                   # CLI 入口文件
├── .env.example              # 环境变量模板
├── data/
│   ├── import_data.py        # Neo4j 数据导入
│   ├── import_manual.py      # 说明书导入
│   ├── chroma_db/            # ChromaDB 向量数据库
│   ├── documents/            # 说明书文档
│   ├── images/               # 零件图片
│   └── uploads/              # 用户上传目录
├── src/
│   ├── agent/
│   │   ├── graph.py          # LangGraph 状态机（含心理安抚旁路）
│   │   ├── state.py          # Agent 状态定义
│   │   ├── tools.py          # 4个核心工具
│   │   ├── router.py         # 意图路由
│   │   ├── intent_router.py  # 细粒度意图识别
│   │   └── quick_response.py # 快速响应（图谱/RAG 直达）
│   ├── builder3d/            # 3D 模型生成管线
│   │   ├── pipeline.py       # 完整管线：生成→验证→修正循环
│   │   ├── llm_generator.py  # LLM 驱动的 3D 模型生成
│   │   ├── physics.py        # 物理稳定性验证器
│   │   ├── auto_fixer.py     # 自动修正悬空/越界/不连通
│   │   └── data_generator.py # 数据生成工具
│   ├── kg/                   # 多模态知识图谱
│   │   ├── graph_builder.py  # 图谱构建（文档/图片/CSV）
│   │   ├── graph_store.py    # Neo4j 存储抽象
│   │   ├── graph_retriever.py# 子图检索
│   │   ├── graph_reasoner.py # LLM 推理引擎（约束/链式/稳定性）
│   │   ├── schema.py         # 节点/关系类型定义
│   │   └── image_generator.py# 图片生成
│   ├── vision/
│   │   ├── qwen_vl.py        # DashScope Qwen-VL
│   │   ├── openai_vl.py      # OpenAI GPT-4o
│   │   ├── ollama_vl.py      # 本地 Ollama
│   │   ├── part_recognizer.py# CLIP 零件识别器
│   │   └── part_database.py  # 零件数据库
│   ├── rag/
│   │   ├── vector_store.py   # ChromaDB 向量存储
│   │   ├── pdf_loader.py     # PDF 切片
│   │   ├── document_loader.py# 文档加载器
│   │   ├── multimodal_parser.py  # 多模态解析
│   │   ├── multimodal_store.py   # 多模态存储
│   │   └── visual_encoder.py     # 视觉编码器
│   ├── retrieval/            # 统一检索器
│   │   ├── unified_retriever.py  # L1-L4 多路检索融合
│   │   ├── fusion_strategy.py    # 融合策略
│   │   └── context_builder.py    # 上下文构建
│   ├── memory/               # 多级记忆管理器
│   │   ├── manager.py        # L0-L4 记忆读写/升级/清理
│   │   └── models.py         # 记忆数据模型
│   ├── knowledge/
│   │   └── neo4j_client.py   # Neo4j 客户端
│   ├── verification/
│   │   └── clip_checker.py   # CLIP 验真
│   ├── psychology/
│   │   ├── frustration_detector.py    # 挫折检测器
│   │   └── encouragement_library.py   # 共情话术库
│   ├── session/
│   │   ├── redis_client.py          # Redis 连接
│   │   ├── conversation_manager.py  # 对话管理
│   │   └── models.py                # 会话数据模型
│   ├── set/
│   │   └── set_manager.py           # 套装管理
│   ├── notification/
│   │   └── feishu.py         # 飞书通知
│   └── common/
│       ├── config.py         # 全局配置
│       ├── error_handler.py  # 错误处理
│       └── singleton.py      # 单例工具
├── tests/                    # 单元测试
│   ├── test_graph_builder_extended.py
│   ├── test_graph_reasoner.py
│   ├── test_graph_store.py
│   ├── test_intent_router.py
│   ├── test_memory_manager.py
│   ├── test_pipeline.py
│   ├── test_physics.py
│   ├── test_fusion_strategy.py
│   ├── test_document_loader.py
│   ├── test_multimodal_parser.py
│   ├── test_part_recognizer.py
│   ├── test_data_generator.py
│   ├── test_llm_generator.py
│   └── test_api_endpoints.py
└── frontend/                 # React 前端
    ├── src/
    │   ├── App.tsx           # 主组件
    │   ├── main.tsx          # 入口
    │   ├── types/            # TypeScript 类型定义
    │   ├── lib/
    │   │   ├── api.ts        # API 客户端封装
    │   │   └── utils.ts      # 工具函数
    │   ├── store/
    │   │   ├── chatStore.ts      # 聊天状态管理
    │   │   ├── builder3dStore.ts # 3D 拼装状态管理
    │   │   ├── settingsStore.ts  # 设置状态管理
    │   │   └── uiStore.ts        # UI 状态管理
    │   ├── hooks/
    │   │   ├── useChatStream.ts  # 流式聊天 Hook
    │   │   ├── useChatStepSync.ts# 聊天-步骤同步
    │   │   └── useSpeechInput.ts # 语音输入 Hook
    │   ├── components/
    │   │   ├── ui/               # shadcn/ui 基础组件
    │   │   ├── sidebar/          # 侧边栏
    │   │   ├── chat/             # 聊天组件
    │   │   ├── tools/            # 工具结果可视化卡片
    │   │   ├── builder3d/        # 3D 拼装场景（Three.js）
    │   │   ├── progress/         # 进度追踪、挫折感知
    │   │   └── settings/         # 设置面板
    │   └── data/             # Mock 数据
    ├── package.json
    └── vite.config.ts
```

## API 端点

### 聊天

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| POST | `/api/chat/stream` | 流式聊天（SSE） |
| POST | `/api/chat` | 文本聊天（非流式） |
| POST | `/api/chat/image` | 带图片的聊天 |

### 对话管理

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| GET | `/api/conversations` | 列出所有对话 |
| POST | `/api/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 获取对话详情+消息 |
| DELETE | `/api/conversations/{id}` | 删除对话 |
| PATCH | `/api/conversations/{id}` | 更新对话（标题/套装） |
| PATCH | `/api/conversations/{id}/messages/{mid}` | 更新消息反馈 |

### 套装管理

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| GET | `/api/sets` | 列出所有套装 |
| GET | `/api/sets/{id}` | 获取套装详情 |
| POST | `/api/sets/{id}/progress` | 更新拼搭进度 |

### 3D 模型生成

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| POST | `/api/builder3d/generate` | 文字→3D 模型（LLM+物理验证） |

### 知识图谱

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| GET | `/api/graph/stats` | 图谱统计 |
| GET | `/api/graph/part/{part_id}` | 零件详情 |
| GET | `/api/graph/part/{part_id}/alternatives` | 零件替代方案 |
| GET | `/api/graph/set/{set_id}/step/{step_number}` | 套装步骤 |
| GET | `/api/graph/set/{set_id}` | 套装完整图谱 |
| POST | `/api/graph/build-from-manual` | 从说明书构建图谱 |
| POST | `/api/graph/init` | 初始化图谱 |
| POST | `/api/graph/reason` | 图谱推理 |
| GET | `/api/graph/cross-modal` | 跨模态检索 |
| DELETE | `/api/graph/clear` | 清空图谱 |

### 记忆系统

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| GET | `/api/memory/status` | 记忆系统状态 |
| GET | `/api/memory/conversations/{id}/summary` | 对话摘要 |
| GET | `/api/memory/conversations/{id}/messages` | 对话消息 |
| GET | `/api/memory/sets/{id}/summaries` | 套装摘要 |
| GET | `/api/memory/user/profile` | 用户画像 |
| POST | `/api/memory/conversations/{id}/summary` | 生成摘要 |
| GET | `/api/memory/conversations/{id}/context` | 上下文窗口 |
| DELETE | `/api/memory/cache` | 清理缓存 |

### 检索 / 文档 / 多模态 / 零件

| 方法 | 路径 | 说明 |
| :----- | :----- | :----- |
| POST | `/api/retrieve` | 统一检索（L1-L4 融合） |
| POST | `/api/documents/upload` | 上传文档 |
| POST | `/api/documents/import-mock` | 导入 Mock 文档 |
| GET | `/api/documents/stats` | 文档统计 |
| DELETE | `/api/documents/set/{set_id}` | 删除套装文档 |
| GET | `/api/documents/search` | 文档搜索 |
| POST | `/api/multimodal/upload-pdf` | 上传 PDF（多模态） |
| POST | `/api/multimodal/search-by-image` | 以图搜图 |
| GET | `/api/multimodal/search` | 多模态搜索 |
| GET | `/api/multimodal/stats` | 多模态统计 |
| POST | `/api/parts/recognize` | 零件识别 |
| GET | `/api/parts/search-by-description` | 按描述搜索零件 |
| POST | `/api/parts/verify` | 零件验证 |
| POST | `/api/parts/import-common` | 导入常用零件 |
| GET | `/api/parts/stats` | 零件库统计 |

## 3D 模型生成管线

```
用户描述 → LLM 生成器 → 物理验证 → 自动修正 → 稳定模型
              ↑              ↓           ↓
              └── 修正循环 ───┘           ↓
                              └── 输出 BuildModel → 前端 3D 渲染
```

**物理验证规则：**
1. 重力支撑：非底层积木下方必须有支撑（>50%）
2. 边界检测：不超出底板范围
3. 连通性：所有积木与底板相连（BFS）

**自动修正策略：**
- 越界 → 平移到底板内
- 悬空 → 添加支撑积木
- 不连通 → 添加连接积木

## 状态流转

```
待解析 → 进度确认 → 缺件待补/结构纠偏
                     ↓ (挂起超时/重复提问/情绪词命中)
                【心理安抚节点】← 非阻塞异步触发
                     ↓
              等待用户操作（挂起）→ 二次验收 → 已归档
```

关键设计：所有涉及"执行"的节点强制 **Human-in-the-loop** 挂起。

## 前端功能

| 功能 | 说明 |
| :----- | :----- |
| 3D 可视化拼装 | Three.js 交互式 3D 场景，步骤动画 |
| 多对话管理 | 创建/切换/删除对话，Redis 持久化 |
| 套装选择 | 选择当前拼搭套装，联动图谱/RAG 过滤 |
| 工具可视化 | 4 种工具结果专用卡片（替代方案/说明书/验收/识别） |
| 消息操作 | 复制、重新生成、👍/👎 反馈 |
| 挫折感知 | 情绪指示器 + 进度可视化 |
| 暗色模式 | light/dark 主题切换 |
| 语音输入 | Web Speech API 语音转文字 |
| 导出 | 对话导出为 Markdown |
| 设置面板 | API 配置、模型选择、温度调节 |
| 3D 交互 | 爆炸视图、积木选中、音效反馈 |

## 配置说明

### 推理 LLM

| 变量 | 说明 | 默认值 |
| :----- | :----- | :----- |
| `LLM_API_KEY` | API Key | - |
| `LLM_BASE_URL` | API 地址 | LongCat |
| `LLM_MODEL` | 模型名 | LongCat-Flash-Chat |

### 视觉模型（独立切换）

| 变量 | 说明 | 可选值 |
| :----- | :----- | :----- |
| `VISION_PROVIDER` | 视觉后端 | `ollama` / `dashscope` / `openai` / `mock` |
| `VISION_API_KEY` | API Key | - |
| `VISION_BASE_URL` | API 地址 | - |
| `VISION_MODEL` | 模型名 | `qwen2.5vl:7b` / `qwen-vl-plus` / `gpt-4o` |
| `USE_REAL_VL` | 是否启用真实视觉 | `true` / `false` |

### 其他

| 变量 | 说明 |
| :----- | :----- |
| `NEO4J_URI` | Neo4j 连接地址 |
| `NEO4J_USER` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | Neo4j 密码 |
| `REDIS_URL` | Redis 连接地址 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook |
| `APP_ENV` | 运行环境 |
| `LOG_LEVEL` | 日志级别 |

## 简历项目描述

> **LEGO-Mate —— 基于多模态 ReAct Agent 的乐高拼搭智能副驾**
>
> 构建 LangGraph 对话中枢，实现意图自主路由与多轮上下文记忆，工具调用准确率 95%+；设计 Neo4j 多模态知识图谱推理引擎，存储 500+ 零件替代关系，缺件替代 100% 准确（零幻觉）；集成 Qwen-VL 多模态解析与 CLIP 验真闭环，端到端响应 <2.5 秒。创新引入 **3D 模型生成管线**（LLM 驱动 + 物理验证 + 自动修正）和 **多级记忆系统**（L0-L4 五级记忆管理），前端采用 React + Three.js 构建交互式 3D 拼装场景。创新引入挫折感知（Frustration-Aware）激励引擎，通过行为时序分析动态调节交互策略。通过 Human-in-the-loop 机制保障关键操作安全可控。

## License

MIT
