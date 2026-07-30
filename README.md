# Vibe-Trading Feishu Bot

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) 的 AI 量化交易飞书机器人。

通过飞书 IM 随时随地获取股票分析、投研判断和策略回测，支持自然语言交互。

## 功能特性

- **自然语言投研**：直接在飞书中发送问题，AI 自动分析股票（如"分析一下贵州茅台"）
- **流式卡片回复**：基于飞书 CardKit 2.0 的打字机效果，实时显示生成进度，COT 思考过程折叠展示
- **WebSocket 长连接**：无需公网 IP 或域名，本地直接运行
- **多数据源支持**：AkShare（A股）、Tushare、yfinance
- **量化因子库**：内置 Alpha101、学术因子、基本面因子、国泰君安191 因子
- **用户配对认证**：原生配对码白名单机制，控制访问权限
- **用户管理后台**：SQLite 用量追踪 + 配额限制 + Web 管理界面 + 飞书 /admin 命令

## 快速开始

### 1. 环境要求

- Python 3.11+
- 飞书开放平台账号（创建自建应用）
- DeepSeek API Key（或其他 LLM）

### 2. 安装

```powershell
# 克隆仓库
git clone https://github.com/gust2020ccc/vibe-trading-feishu.git
cd vibe-trading-feishu

# 运行安装脚本（创建虚拟环境 + 安装 vibe-trading）
.\setup.ps1

# 应用自定义代码补丁（流式卡片 + 用户管理等功能）
.\apply_customizations.ps1
```

### 3. 配置

```powershell
# 复制配置模板
Copy-Item .env.example .env

# 编辑 .env，填入你的 API Key
# DEEPSEEK_API_KEY=sk-xxxx
# TUSHARE_TOKEN=xxxx
```

飞书配置请参考 [部署指南](docs/deploy-guide.html)。

### 4. 启动

```powershell
.\start.ps1
```

### 5. 测试

在飞书中搜索你的机器人，发送消息：
- `分析一下贵州茅台`
- `帮我看看比亚迪的技术面`
- `/admin` — 查看自己的用量统计
- `/admin help` — 显示管理命令帮助

## 新机器部署流程

```powershell
git clone https://github.com/gust2020ccc/vibe-trading-feishu.git
cd vibe-trading-feishu
.\setup.ps1              # 安装虚拟环境 + vibe-trading
.\apply_customizations.ps1  # 应用自定义代码（必须！）
# 配置 ~/.vibe-trading/.env 和 agent.json
.\start.ps1              # 启动服务
```

> **重要**：`apply_customizations.ps1` 必须在 `setup.ps1` 之后、`start.ps1` 之前运行，否则流式卡片、用户管理等功能不可用。

## 项目结构

```
vibe-trading-feishu/
├── .env.example             # 配置模板（不含密钥）
├── .gitignore
├── README.md
├── start.ps1                # 一键启动
├── setup.ps1                # 环境初始化
├── apply_customizations.ps1 # 应用自定义代码补丁
├── requirements.txt         # Python 依赖
├── login_feishu.ps1         # 飞书扫码登录
├── config_feishu_manual.ps1 # 手动配置飞书凭据
└── customizations/          # 自定义代码（git 跟踪）
    ├── api_server.py        # 注册 admin 路由
    └── src/
        ├── usage/           # 用户管理模块（新增）
        │   ├── __init__.py
        │   ├── db.py            # SQLite 数据层
        │   ├── models.py        # 数据模型
        │   ├── rate_limiter.py  # 限流 + 并发控制
        │   ├── service.py       # 核心服务
        │   ├── admin_commands.py # 飞书 /admin 命令
        │   ├── admin_routes.py  # Web API 路由
        │   └── dashboard.py     # HTML 管理界面
        ├── channels/
        │   └── runtime.py       # 集成配额检查
        ├── session/
        │   └── service.py       # 集成用量回调
        └── api/
            └── state.py         # 服务接线
```

## 用户管理功能

### 飞书命令

| 命令 | 权限 | 功能 |
|------|------|------|
| `/admin` | 所有人 | 查看自己的用量与配额 |
| `/admin help` | 所有人 | 显示帮助 |
| `/admin list` | 管理员 | 列出所有用户及用量 |
| `/admin setquota <id> <日token> <月token> <并发> <RPM>` | 管理员 | 设置配额（0=不限）|
| `/admin disable <id>` / `enable <id>` | 管理员 | 停用/启用用户 |
| `/admin summary` | 管理员 | 全局用量统计 |

### Web 管理后台

启动服务后访问 `http://127.0.0.1:8000/admin/dashboard`

### 管理员配置

在 `~/.vibe-trading/agent.json` 的 `channels.operators` 中添加你的飞书 open_id：

```json
{
  "channels": {
    "operators": ["ou_your_open_id_here"],
    "feishu": { ... }
  }
}
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 核心框架 | Vibe-Trading (Python) |
| IM 通道 | 飞书 WebSocket + CardKit 2.0 |
| LLM | DeepSeek API |
| 数据源 | AkShare / Tushare / yfinance |
| API 层 | FastAPI |
| 用户管理 | SQLite + 滑动窗口限流 |
| 部署 | Docker（规划中） |

## 开发路线图

- [x] 基础部署（飞书频道 + LLM + 数据源）
- [x] 用户配对认证
- [x] 流式卡片（CardKit 2.0 打字机 + COT 折叠）
- [x] 用户管理后端（用量限制 + Web 界面 + /admin 命令）
- [ ] 回测 Web 端
- [ ] 飞书远程命令（回测/策略管理）
- [ ] Docker 化上云部署

## 致谢

- [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) - HKUDS 出品的 AI 量化交易研究框架
- [飞书开放平台](https://open.feishu.cn/) - IM 通道与 CardKit

## License

MIT
