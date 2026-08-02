#!/bin/bash
# ============================================================
# Vibe-Trading Feishu - 远程一键部署脚本
# 在全新的 Ubuntu 22.04 服务器上执行
# 用法: bash deploy-remote.sh
# ============================================================
set -e

echo "============================================"
echo "  Vibe-Trading Feishu 远程部署"
echo "============================================"

# ---- 1. 安装 Docker ----
echo "[1/6] 安装 Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    echo "  Docker 安装完成"
else
    echo "  Docker 已安装"
fi

# ---- 2. 安装 Git ----
echo "[2/6] 安装 Git..."
if ! command -v git &>/dev/null; then
    apt update && apt install -y git
fi
echo "  Git 就绪"

# ---- 3. 克隆代码 ----
echo "[3/6] 克隆代码..."
DEPLOY_DIR="/opt/vibe-trading-feishu"
if [ -d "$DEPLOY_DIR" ]; then
    cd "$DEPLOY_DIR"
    git pull || true
else
    git clone https://github.com/gust2020ccc/vibe-trading-feishu.git "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi
echo "  代码就绪: $DEPLOY_DIR"

# ---- 4. 创建 Docker 部署文件 ----
echo "[4/6] 创建 Docker 部署文件..."

# 4.1 requirements-prod.txt
cat > requirements-prod.txt << 'REQEOF'
vibe-trading-ai==0.1.12
lark-oapi>=1.4.0
PyJWT>=2.8.0
joserfc>=1.0.0
peewee>=4.0.0
email-validator>=2.0.0
python-dotenv>=1.0.0
numba>=0.60.0
REQEOF

# 4.2 Dockerfile
cat > Dockerfile << 'DOCKERFILE'
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 \
    libffi-dev shared-mime-info curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY customizations/ /app/customizations/
COPY --from=frontend-builder /build/dist /tmp/frontend-dist
RUN SITE_PKGS=$(python -c "import site; print(site.getsitepackages()[0])") && \
    cp -r /app/customizations/src/* "${SITE_PKGS}/src/" && \
    cp /app/customizations/api_server.py "${SITE_PKGS}/" && \
    mkdir -p "${SITE_PKGS}/frontend" && \
    cp -r /tmp/frontend-dist "${SITE_PKGS}/frontend/dist" && \
    rm -rf /tmp/frontend-dist && \
    find "${SITE_PKGS}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
RUN mkdir -p /root/.vibe-trading /app/runs
ENV VIBE_TRADING_SEARCH_CN_FIRST=1 \
    VIBE_TRADING_SEARCH_BING_FALLBACK=1 \
    NO_PROXY=* HTTP_PROXY="" HTTPS_PROXY="" HOME=/root PORT=8000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -sf http://localhost:8000/health || exit 1
EXPOSE 8000
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
DOCKERFILE

# 4.3 docker-entrypoint.sh
cat > docker-entrypoint.sh << 'ENTRYEOF'
#!/bin/bash
set -e
echo "============================================"
echo "  Vibe-Trading Feishu Service"
echo "============================================"
export HTTP_PROXY="" HTTPS_PROXY="" NO_PROXY="*"
export VIBE_TRADING_SEARCH_CN_FIRST="${VIBE_TRADING_SEARCH_CN_FIRST:-1}"
export VIBE_TRADING_SEARCH_BING_FALLBACK="${VIBE_TRADING_SEARCH_BING_FALLBACK:-1}"
PORT="${PORT:-8000}"
VT_HOME="/root/.vibe-trading"

if [ ! -f "${VT_HOME}/.env" ]; then
    echo "[WARN] ${VT_HOME}/.env not found. Starting API server anyway..."
fi

echo "[1/2] Starting API server on 0.0.0.0:${PORT}..."
vibe-trading serve --host 0.0.0.0 --port "${PORT}" &

echo "[2/2] Waiting for API to be ready..."
API_READY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
        echo "  API server is ready"
        API_READY=true
        break
    fi
    echo "  Waiting... (${i}/30)"
    sleep 2
done

if [ "${API_READY}" = false ]; then
    echo "[ERROR] API server failed to start within 60s"
    tail -f /dev/null
fi

if [ -f "${VT_HOME}/agent.json" ]; then
    echo "Starting Feishu channel..."
    exec vibe-trading channels start
else
    echo "[WARN] agent.json not found, skipping Feishu channel."
    echo "       Web UI: http://localhost:${PORT}"
    wait
fi
ENTRYEOF
chmod +x docker-entrypoint.sh

# 4.4 docker-compose.yml
cat > docker-compose.yml << 'COMPOSEEOF'
services:
  vibe-trading:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: vibe-trading
    ports:
      - "${PORT:-8000}:8000"
    volumes:
      - vibe-trading-config:/root/.vibe-trading
      - vibe-trading-runs:/app/runs
    environment:
      - VIBE_TRADING_SEARCH_CN_FIRST=1
      - VIBE_TRADING_SEARCH_BING_FALLBACK=1
      - NO_PROXY=*
      - HTTP_PROXY=
      - HTTPS_PROXY=
      - PORT=8000
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
volumes:
  vibe-trading-config:
  vibe-trading-runs:
COMPOSEEOF

# 4.5 .dockerignore
cat > .dockerignore << 'IGNOREEOF'
.venv/
venv/
env/
__pycache__/
*.py[cod]
node_modules/
frontend/node_modules/
frontend/dist/
.env
agent.json
*.pairing.json
users.json
pairing.json
.git/
.gitignore
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db
desktop.ini
*.log
logs/
runs/
*.md
*.html
*.zip
docs/
*.ps1
test_bridge.py
RESEARCH_PROMPT.md
Dockerfile
docker-compose.yml
.dockerignore
IGNOREEOF

echo "  Docker 部署文件已创建"

# ---- 5. 配置文件 ----
echo "[5/6] 检查配置文件..."
VT_HOME="/root/.vibe-trading"
mkdir -p "$VT_HOME"

if [ ! -f "$VT_HOME/.env" ]; then
    echo "  创建 .env 模板，请稍后编辑填入密钥..."
    cat > "$VT_HOME/.env" << 'ENVEOF'
LANGCHAIN_PROVIDER=deepseek
LANGCHAIN_MODEL_NAME=deepseek-chat
DEEPSEEK_API_KEY=sk-在此填入你的API密钥
TUSHARE_TOKEN=
VIBE_TRADING_SEARCH_CN_FIRST=1
VIBE_TRADING_SEARCH_BING_FALLBACK=1
TIMEOUT_SECONDS=300
MAX_RETRIES=2
API_AUTH_KEY=请设置一个随机密钥
ENVEOF
    echo "  [!] 请编辑 /root/.vibe-trading/.env 填入实际密钥"
fi

if [ ! -f "$VT_HOME/agent.json" ]; then
    echo "  创建 agent.json 模板..."
    cat > "$VT_HOME/agent.json" << 'AGENTEOF'
{
  "channels": {
    "operators": [],
    "feishu": {
      "app_id": "",
      "app_secret": ""
    }
  }
}
AGENTEOF
    echo "  [!] 请编辑 /root/.vibe-trading/agent.json 填入飞书凭据"
fi

# ---- 6. 构建并启动 ----
echo "[6/6] 构建 Docker 镜像（首次约 5-10 分钟）..."
docker compose build

echo "启动服务..."
docker compose up -d

echo ""
echo "============================================"
echo "  部署完成!"
echo "============================================"
echo "  Web UI:  http://$(hostname -I | awk '{print $1}'):8000"
echo "  API:     http://localhost:8000/health"
echo ""
echo "  下一步:"
echo "    1. 编辑 /root/.vibe-trading/.env 填入 DeepSeek API Key"
echo "    2. 编辑 /root/.vibe-trading/agent.json 填入飞书凭据"
echo "    3. 重启: cd /opt/vibe-trading-feishu && docker compose restart"
echo "    4. 日志: docker compose logs -f"
echo "============================================"
