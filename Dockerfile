# ============================================================
# Vibe-Trading Feishu - Dockerfile
# 多阶段构建：前端构建 + Python 后端 + 自定义代码补丁
# ============================================================

# ---- Stage 1: 前端构建 ----
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# 先复制依赖文件，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent

# 复制源码并构建
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python 后端 ----
FROM python:3.12-slim

# 系统依赖
# weasyprint 需要 pango/cairo/gdk-pixbuf
# matplotlib 需要 freetype（通常已包含在 slim 镜像中）
# curl 用于健康检查
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

# 复制自定义代码
COPY customizations/ /app/customizations/

# 复制前端构建产物（暂存）
COPY --from=frontend-builder /build/dist /tmp/frontend-dist

# 将自定义代码和前端产物应用到 site-packages
# api_server.py 通过 _find_frontend_dist() 在 site-packages/frontend/dist 查找前端
RUN SITE_PKGS=$(python -c "import site; print(site.getsitepackages()[0])") && \
    echo "Site-packages: ${SITE_PKGS}" && \
    cp -r /app/customizations/src/* "${SITE_PKGS}/src/" && \
    cp /app/customizations/api_server.py "${SITE_PKGS}/" && \
    mkdir -p "${SITE_PKGS}/frontend" && \
    cp -r /tmp/frontend-dist "${SITE_PKGS}/frontend/dist" && \
    rm -rf /tmp/frontend-dist && \
    find "${SITE_PKGS}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 创建配置和数据目录
RUN mkdir -p /root/.vibe-trading /app/runs

# 环境变量默认值
ENV VIBE_TRADING_SEARCH_CN_FIRST=1 \
    VIBE_TRADING_SEARCH_BING_FALLBACK=1 \
    NO_PROXY=* \
    HTTP_PROXY="" \
    HTTPS_PROXY="" \
    HOME=/root \
    PORT=8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# 入口点
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
