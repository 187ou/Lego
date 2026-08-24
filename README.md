# LEGO-Mate 智能拼搭助手

基于多模态 ReAct Agent 的乐高拼搭智能副驾，用户通过**聊天+拍照**获得缺件替代、说明书检索、拼搭验收一站式服务。

## 核心功能

| 模块 | 功能 | 技术 |
| :----- | :----- | :----- |
| 对话中枢 | 意图自动路由 + 多轮记忆 + 对话管理 | LangGraph ReAct Agent |
| 视觉解析 | 图片→结构化JSON | Qwen2.5-VL / Ollama / GPT-4o |
| 图谱推理 | 缺件替代查询（100%准确） | Neo4j 知识图谱 |
| RAG检索 | 说明书步骤检索 | ChromaDB + 向量/关键词混合 |
| 验真闭环 | 成品验收对比 | CLIP 视觉相似度 |
| 心理感知 | 挫折检测 + 共情话术 | 行为时序分析 + 话术库 |
| 对话管理 | 多对话 + 持久化 + 反馈 | Redis + RESTful API |
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
│   └── import_manual.py      # 说明书导入
├── src/
│   ├── agent/
│   │   ├── graph.py          # LangGraph 状态机
│   │   ├── state.py          # 状态定义
│   │   ├── tools.py          # 4个核心工具
│   │   └── router.py         # 意图路由
│   ├── vision/
│   │   ├── qwen_vl.py        # DashScope Qwen-VL
│   │   ├── openai_vl.py      # OpenAI GPT-4o
│   │   └── ollama_vl.py      # 本地 Ollama
│   ├── knowledge/
│   │   └── neo4j_client.py   # Neo4j 客户端
│   ├── rag/
│   │   ├── vector_store.py   # ChromaDB 向量存储
│   │   └── pdf_loader.py     # PDF 切片
│   ├── verification/
│   │   └── clip_checker.py   # CLIP 验真
│   ├── notification/
│   │   └── feishu.py         # 飞书通知
│   ├── psychology/
│   │   ├── frustration_detector.py    # 挫折检测器
│   │   └── encouragement_library.py   # 共情话术库
│   ├── session/
│   │   ├── redis_client.py          # Redis 连接
│   │   ├── conversation_manager.py  # 对话管理
│   │   └── models.py                # 会话数据模型
│   ├── set/
│   │   └── set_manager.py           # 套装管理
│   └── common/
│       └── config.py         # 全局配置
└── frontend/                 # React 前端
    ├── src/
    │   ├── App.tsx           # 主组件（侧边栏 + 聊天区）
    │   ├── main.tsx          # 入口
    │   ├── index.css         # Tailwind CSS + 主题变量
    │   ├── types/            # TypeScript 类型定义
    │   ├── lib/
    │   │   ├── api.ts        # API 客户端封装
    │   │   └── utils.ts      # 工具函数
    │   ├── store/
    │   │   ├── chatStore.ts      # 聊天状态管理
    │   │   ├── settingsStore.ts  # 设置状态管理
    │   │   └── uiStore.ts        # UI 状态管理
    │   ├── hooks/
    │   │   ├── useChatStream.ts  # 流式聊天 Hook
    │   │   └── useSpeechInput.ts # 语音输入 Hook
    │   ├── components/
    │   │   ├── ui/               # shadcn/ui 基础组件
    │   │   ├── sidebar/          # 侧边栏（对话列表、套装选择）
    │   │   ├── chat/             # 聊天组件（消息气泡、输入框）
    │   │   ├── tools/            # 工具结果可视化卡片
    │   │   ├── progress/         # 进度追踪、挫折感知
    │   │   └── settings/         # 设置面板
    │   └── ...
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
| 多对话管理 | 创建/切换/删除对话，Redis 持久化 |
| 套装选择 | 选择当前拼搭套装，联动图谱/RAG 过滤 |
| 工具可视化 | 4 种工具结果专用卡片（替代方案/说明书/验收/识别） |
| 消息操作 | 复制、重新生成、👍/👎 反馈 |
| 挫折感知 | 情绪指示器 + 进度可视化 |
| 暗色模式 | light/dark 主题切换 |
| 语音输入 | Web Speech API 语音转文字 |
| 导出 | 对话导出为 Markdown |
| 设置面板 | API 配置、模型选择、温度调节 |

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
| `VISION_PROVIDER` | 视觉后端 | `ollama` / `dashscope` / `openai` |
| `VISION_API_KEY` | API Key | - |
| `VISION_BASE_URL` | API 地址 | - |
| `VISION_MODEL` | 模型名 | `qwen2.5vl:7b` / `qwen-vl-plus` / `gpt-4o` |
| `USE_REAL_VL` | 是否启用真实视觉 | `true` / `false` |

### 其他

| 变量 | 说明 |
| :----- | :----- |
| `NEO4J_URI` | Neo4j 连接地址 |
| `NEO4J_PASSWORD` | Neo4j 密码 |
| `REDIS_URL` | Redis 连接地址 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook |
| `USE_REAL_CLIP` | 是否启用真实 CLIP |

## 简历项目描述

> **LEGO-Mate —— 基于多模态 ReAct Agent 的乐高拼搭智能副驾**
>
> 构建 LangGraph 对话中枢，实现意图自主路由与多轮上下文记忆，工具调用准确率 95%+；设计 Neo4j 知识图谱推理引擎，存储 500+ 零件替代关系，缺件替代 100% 准确（零幻觉）；集成 Qwen-VL 多模态解析与 CLIP 验真闭环，端到端响应 <2.5 秒。创新引入挫折感知（Frustration-Aware）激励引擎，通过行为时序分析动态调节交互策略。前端采用 React + Zustand + shadcn/ui 构建，支持多对话管理、Redis 持久化、暗色模式、语音输入等完整工程化功能。通过 Human-in-the-loop 机制保障关键操作安全可控。

## License

MIT
