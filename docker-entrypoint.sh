#!/bin/bash
set -e

echo "============================================"
echo "  Vibe-Trading Feishu Service"
echo "============================================"

# ---- 环境配置 ----
export HTTP_PROXY=""
export HTTPS_PROXY=""
export NO_PROXY="*"
export VIBE_TRADING_SEARCH_CN_FIRST="${VIBE_TRADING_SEARCH_CN_FIRST:-1}"
export VIBE_TRADING_SEARCH_BING_FALLBACK="${VIBE_TRADING_SEARCH_BING_FALLBACK:-1}"

PORT="${PORT:-8000}"
VT_HOME="/root/.vibe-trading"

# ---- 配置文件检查 ----
if [ ! -f "${VT_HOME}/.env" ]; then
    echo "[WARN] ${VT_HOME}/.env not found."
    echo "       Mount your config volume and create .env with LLM keys."
    echo "       See DEPLOY.md for configuration guide."
    echo "       Starting API server anyway (will fail on LLM calls)..."
fi

# ---- 启动 API 服务器（后台）----
echo "[1/2] Starting API server on 0.0.0.0:${PORT}..."
vibe-trading serve --host 0.0.0.0 --port "${PORT}" &

# ---- 等待 API 就绪 ----
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
    echo "        Keeping container alive for debugging..."
    tail -f /dev/null
fi

# ---- 启动飞书渠道（前台，保持容器运行）----
if [ -f "${VT_HOME}/agent.json" ]; then
    echo "Starting Feishu channel..."
    exec vibe-trading channels start
else
    echo "[WARN] agent.json not found, skipping Feishu channel."
    echo "       API server running at http://0.0.0.0:${PORT}"
    echo "       Web UI: http://localhost:${PORT}"
    # 保持容器运行
    wait
fi
