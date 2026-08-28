# LEGO-Mate 智能拼搭助手

基于多模态多 Agent 的乐高拼搭智能副驾，通过**聊天+拍照**提供缺件替代、说明书检索、拼搭验收、3D 可视化拼搭一站式服务。

## 核心功能

- **智能对话** - 意图自动路由，6 个专家 Agent 各司其职（视觉识别、零件替代、说明书检索、成品验收、心理安抚、闲聊）
- **视觉解析** - 图片→结构化 JSON，支持 Qwen2.5-VL / GPT-4o / CLIP 多种后端
- **知识图谱** - Neo4j 多模态知识图谱，支持缺件替代查询与约束推理
- **RAG 检索** - ChromaDB 向量/关键词混合检索说明书步骤
- **成品验收** - CLIP 视觉相似度对比，判定 pass/review/fail
- **3D 生成** - 文字→3D 积木模型，物理验证 + 自动修正
- **多级记忆** - L0-L4 五级记忆管理，指代消解，Redis 持久化
- **心理感知** - 挫折检测 + 共情话术，动态调节交互策略
- **3D 可视化** - React + Three.js 交互式拼装，步骤动画

## 快速开始

### 环境要求

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) 包管理器
- Docker Desktop（Neo4j + Redis）
- Node.js >= 18（前端）

### 启动步骤

```bash
# 1. 克隆项目
git clone <repo_url>
cd LEGO-Mate

# 2. 安装依赖
uv sync
cd frontend && npm install && cd ..

# 3. 启动基础设施（Neo4j + Redis）
docker compose up -d

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY 等配置

# 5. 启动后端
uv run python server.py
# 服务运行在 http://localhost:8000

# 6. 启动前端
cd frontend && npm run dev
# 访问 http://localhost:5173
```

## 使用示例

| 输入 | 功能 |
|-----|------|
| "上传零件图片" | 视觉识别 Agent 识别零件 |
| "红色2x4砖有替代吗" | 零件替代 Agent 查询图谱 |
| "第35步怎么拼" | 说明书 Agent 检索步骤 |
| "帮我看下对么" + 图片 | 验收 Agent 对比成品 |
| "好难啊不想拼了" | 心理安抚 Agent 共情鼓励 |

## 技术栈

| 层级 | 技术 |
|-----|------|
| 后端 | FastAPI + LangGraph + LangChain |
| 前端 | React + TypeScript + Three.js |
| 数据库 | Neo4j + Redis + ChromaDB |
| LLM | LongCat / GPT-4o / Qwen2.5-VL |

## License

MIT
