# Vibe-Trading Feishu 部署指南

## 架构概览

```
用户浏览器 / 飞书客户端
        │
   ┌────┴────┐
   │ Nginx   │ (可选，域名+SSL)
   │ :80/:443│
   └────┬────┘
        │
┌───────┴──────────────────────┐
│   Docker 容器 (端口 8000)      │
│  ┌─────────────────────────┐ │
│  │  FastAPI (uvicorn)      │ │
│  │  ├── React 静态文件      │ │
│  │  ├── REST API           │ │
│  │  ├── 回测引擎            │ │
│  │  └── 用户管理 (SQLite)   │ │
│  ├─────────────────────────┤ │
│  │  飞书 WebSocket 渠道     │ │
│  └─────────────────────────┘ │
│  数据卷: /root/.vibe-trading  │
└──────────────────────────────┘
```

## 前提条件

- 阿里云轻量应用服务器（推荐 2核2G 200M带宽，38元/年起）
- 或任意 Linux 服务器（Ubuntu 22.04 / Debian 12）
- DeepSeek API Key（或其他 LLM）
- 飞书开放平台自建应用（App ID + App Secret）

## 一、服务器准备

### 1.1 购买阿里云轻量应用服务器

1. 访问 [阿里云轻量应用服务器](https://www.aliyun.com/product/swas)
2. 选择 2核2G、200M峰值带宽配置
3. 系统镜像选择 **Ubuntu 22.04 LTS**
4. 购买完成后记录公网 IP

### 1.2 安装 Docker

SSH 连接服务器后执行：

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | bash

# 验证安装
docker --version
docker compose version

# 设置 Docker 开机自启
systemctl enable docker
```

### 1.3 安装 Git

```bash
apt install -y git
```

## 二、部署应用

### 2.1 克隆代码

```bash
cd /opt
git clone https://github.com/gust2020ccc/vibe-trading-feishu.git
cd vibe-trading-feishu
```

### 2.2 创建配置文件

首次部署需要创建配置目录和文件：

```bash
# 创建配置目录（Docker 数据卷会挂载到这里）
mkdir -p /root/.vibe-trading
```

**创建 LLM 配置文件** `/root/.vibe-trading/.env`：

```bash
cat > /root/.vibe-trading/.env << 'EOF'
# LLM 配置
LANGCHAIN_PROVIDER=deepseek
LANGCHAIN_MODEL_NAME=deepseek-chat
DEEPSEEK_API_KEY=sk-你的API密钥

# A股数据源（AkShare 免费无需 Token，Tushare 需积分）
TUSHARE_TOKEN=你的TushareToken

# 搜索引擎（国内环境优化）
VIBE_TRADING_SEARCH_CN_FIRST=1
VIBE_TRADING_SEARCH_BING_FALLBACK=1

# 请求超时
TIMEOUT_SECONDS=300
MAX_RETRIES=2

# API 鉴权（生产环境必须设置）
API_AUTH_KEY=你的随机密钥
EOF
```

**创建飞书应用配置** `/root/.vibe-trading/agent.json`：

```bash
cat > /root/.vibe-trading/agent.json << 'EOF'
{
  "channels": {
    "operators": ["ou_你的飞书open_id"],
    "feishu": {
      "app_id": "cli_你的AppID",
      "app_secret": "你的AppSecret"
    }
  }
}
EOF
```

> 飞书 open_id 获取方式：机器人收到消息时日志会打印 `sender=open_id`。

### 2.3 构建并启动

```bash
cd /opt/vibe-trading-feishu

# 构建镜像（首次约 5-10 分钟）
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 2.4 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 浏览器访问
# http://你的服务器公网IP:8000
```

看到 API 返回正常即部署成功。飞书渠道连接成功后，在飞书中向机器人发消息测试。

## 三、域名与 SSL（可选）

### 3.1 域名解析

在域名服务商处添加 A 记录，指向服务器公网 IP。

### 3.2 安装 Nginx + Certbot

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 3.3 配置 Nginx 反向代理

```bash
cat > /etc/nginx/sites-available/vibe-trading << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（飞书渠道 + SSE 流式响应）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }
}
EOF

ln -s /etc/nginx/sites-available/vibe-trading /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 3.4 申请 SSL 证书

```bash
certbot --nginx -d your-domain.com
```

证书自动续期已配置，无需手动操作。

## 四、常用运维命令

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新代码并重新部署
git pull
docker compose build
docker compose up -d

# 进入容器调试
docker compose exec vibe-trading bash

# 备份配置和数据
docker compose run --rm -v /root/backup:/backup vibe-trading \
    cp -r /root/.vibe-trading /backup/
```

## 五、数据持久化说明

| 数据 | 容器路径 | 说明 |
|------|---------|------|
| LLM/数据源配置 | /root/.vibe-trading/.env | API 密钥、超时设置 |
| 飞书应用配置 | /root/.vibe-trading/agent.json | App ID、App Secret |
| 用户数据库 | /root/.vibe-trading/*.db | SQLite 用量追踪 |
| 自定义策略 | /root/.vibe-trading/custom_strategies/ | 用户创建的策略文件 |
| 回测结果 | /app/runs/ | 回测产物（图表、报告） |

Docker 数据卷 `vibe-trading-config` 和 `vibe-trading-runs` 确保容器重启后数据不丢失。

## 六、故障排查

### 容器启动失败

```bash
# 查看详细日志
docker compose logs --tail 100

# 检查配置文件是否存在
docker compose exec vibe-trading ls -la /root/.vibe-trading/
```

### API 服务器无法启动

常见原因：
1. `/root/.vibe-trading/.env` 未创建或格式错误
2. DeepSeek API Key 无效
3. 端口 8000 被占用：`docker compose down && docker compose up -d`

### 飞书渠道未连接

```bash
# 检查 agent.json 配置
docker compose exec vibe-trading cat /root/.vibe-trading/agent.json

# 查看渠道状态
docker compose exec vibe-trading vibe-trading channels status
```

### 回测失败：数据源连接问题

容器内已自动清除代理设置（`NO_PROXY=*`）。如仍有问题：

```bash
docker compose exec vibe-trading curl -I https://akshare.akfamily.xyz
```

### 数据卷权限问题

```bash
# 修复数据卷权限
docker compose run --rm --user root vibe-trading chown -R root:root /root/.vibe-trading
```

## 七、安全建议

1. **设置 API_AUTH_KEY**：在 `.env` 中设置，防止未授权 API 访问
2. **防火墙**：阿里云安全组仅放行 80/443 端口，8000 端口不对外暴露
3. **定期备份**：定期备份 `/root/.vibe-trading/` 目录
4. **镜像更新**：定期 `docker compose pull && docker compose up -d` 更新基础镜像
5. **密钥轮换**：定期更换 DeepSeek API Key 和 API_AUTH_KEY
