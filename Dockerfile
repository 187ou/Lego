# ============================================
# LEGO-Mate 多阶段构建 Dockerfile
# ============================================
# 阶段 1: 依赖安装
# 阶段 2: 应用构建
# 阶段 3: 生产镜像
# ============================================

# ===== 阶段 1: 基础镜像 + 依赖 =====
FROM python:3.11-slim as dependencies

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装 Python 依赖
RUN uv sync --frozen --no-dev

# ===== 阶段 2: 构建 =====
FROM dependencies as builder

WORKDIR /app

# 复制源码
COPY src/ src/
COPY data/ data/

# 预编译 Python 字节码
RUN python -m compileall src/ -q

# ===== 阶段 3: 生产镜像 =====
FROM python:3.11-slim as production

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r lego && useradd -r -g lego lego

# 从构建阶段复制依赖
COPY --from=dependencies /app/.venv /app/.venv

# 从构建阶段复制源码
COPY --from=builder /app/src/ /app/src/
COPY --from=builder /app/data/ /app/data/

# 复制其他必要文件
COPY server.py main.py ./
COPY pyproject.toml ./

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

# 创建必要的目录
RUN mkdir -p /app/data/uploads /app/data/cache /app/data/state /app/logs && \
    chown -R lego:lego /app

# 切换到非 root 用户
USER lego

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "python", "server.py"]
