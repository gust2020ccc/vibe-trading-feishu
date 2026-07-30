# Vibe-Trading Feishu Bot

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) 的 AI 量化交易飞书机器人。

通过飞书 IM 随时随地获取股票分析、投研判断和策略回测，支持自然语言交互。

## 功能特性

- **自然语言投研**：直接在飞书中发送问题，AI 自动分析股票（如"分析一下贵州茅台"）
- **流式卡片回复**：基于飞书 CardKit 2.0 的打字机效果，实时显示生成进度，COT 思考过程折叠展示
- **WebSocket 长连接**：无需公网 IP 或域名，本地直接运行
- **多数据源支持**：AkShare（A股免费）、Tushare（需Token）、yfinance（美股）
- **量化因子库**：内置 Alpha101、学术因子、基本面因子、国泰君安191 因子
- **用户配对认证**：原生配对码白名单机制，控制访问权限
- **用户管理后台**：SQLite 用量追踪 + 配额限制 + Web 管理界面 + 飞书 /admin 命令
- **策略回测**：6种内置因子策略模板，绕过 LLM 直接执行回测，飞书 /backtest 命令 + Web 界面

## 快速开始

### 1. 环境要求

- Python 3.11+
- Git（需在 PATH 中或指定路径）
- 飞书开放平台账号（创建自建应用）
- DeepSeek API Key（或其他 LLM）
- Tushare Token（可选，AkShare 可作为免费替代）

### 2. 安装

```powershell
# 克隆仓库
git clone https://github.com/gust2020ccc/vibe-trading-feishu.git
cd vibe-trading-feishu

# 运行安装脚本（创建虚拟环境 + 安装 vibe-trading）
.\setup.ps1

# 应用自定义代码补丁（流式卡片 + 用户管理 + 回测等功能）
.\apply_customizations.ps1
```

> **注意**：如果 `apply_customizations.ps1` 因路径权限报错，使用 Python 手动复制：
> ```powershell
> & .\.venv\Scripts\python.exe -c "import shutil; shutil.copy2(r'customizations\src\backtest\direct_runner.py', r'.venv\Lib\site-packages\src\backtest\direct_runner.py')"
> ```
> 或运行项目根目录的 `apply_patch.py` 脚本。

### 3. 配置

配置文件位于 `~/.vibe-trading/.env`（即 `C:\Users\<用户名>\.vibe-trading\.env`）：

```powershell
# 初始化配置（如果尚未配置）
& .\.venv\Scripts\vibe-trading.exe init
```

编辑 `.env` 文件，填入你的 API Key：

```ini
# LLM 配置
LANGCHAIN_PROVIDER=deepseek
LANGCHAIN_MODEL_NAME=deepseek-chat
DEEPSEEK_API_KEY=sk-你的API密钥

# A股数据源（可选，AkShare 免费无需Token）
TUSHARE_TOKEN=你的TushareToken

# 搜索引擎（国内环境优化）
VIBE_TRADING_SEARCH_CN_FIRST=1
VIBE_TRADING_SEARCH_BING_FALLBACK=1

# 请求超时
TIMEOUT_SECONDS=300
MAX_RETRIES=2
```

飞书应用配置请参考 [飞书开放平台文档](https://open.feishu.cn/document/home/index) 创建自建应用，并将 `App ID`、`App Secret` 填入 `~/.vibe-trading/agent.json`。

### 4. 启动

```powershell
.\start.ps1
```

启动脚本会自动：
- 清除系统代理（`NO_PROXY=*`），确保数据源连接正常
- 配置 SSL 证书路径
- 启动 API 服务器（端口 8000）
- 启动飞书 WebSocket 长连接

### 5. 测试

在飞书中搜索你的机器人，发送消息：
- `分析一下贵州茅台` — 自然语言投研
- `帮我看看比亚迪的技术面` — 技术分析
- `/admin` — 查看自己的用量统计
- `/admin help` — 显示管理命令帮助
- `/backtest` — 显示回测命令帮助
- `/backtest list` — 列出可用策略
- `/backtest ma_cross 000001 2024-01-01 2024-12-31` — 运行均线交叉回测

## 新机器部署流程

```powershell
# 1. 克隆仓库
git clone https://github.com/gust2020ccc/vibe-trading-feishu.git
cd vibe-trading-feishu

# 2. 安装环境
.\setup.ps1

# 3. 应用自定义代码（必须！）
.\apply_customizations.ps1

# 4. 配置 ~/.vibe-trading/.env 和 agent.json
& .\.venv\Scripts\vibe-trading.exe init
# 编辑 ~/.vibe-trading/.env 填入 API Key
# 编辑 ~/.vibe-trading/agent.json 填入飞书凭据

# 5. 启动服务
.\start.ps1
```

> **重要**：`apply_customizations.ps1` 必须在 `setup.ps1` 之后、`start.ps1` 之前运行，否则流式卡片、用户管理、回测等功能不可用。

## 项目结构

```
vibe-trading-feishu/
├── .env.example             # 配置模板（不含密钥）
├── .gitignore
├── README.md
├── start.ps1                # 一键启动（含代理清除 + SSL 配置）
├── setup.ps1                # 环境初始化
├── apply_customizations.ps1 # 应用自定义代码补丁
├── apply_patch.py           # Python 版补丁应用（绕过 PS 路径限制）
├── requirements.txt         # Python 依赖
├── login_feishu.ps1         # 飞书扫码登录
├── config_feishu_manual.ps1 # 手动配置飞书凭据
└── customizations/          # 自定义代码（git 跟踪）
    ├── api_server.py        # 注册 admin + backtest 路由
    └── src/
        ├── usage/           # 用户管理模块
        │   ├── __init__.py
        │   ├── db.py            # SQLite 数据层
        │   ├── models.py        # 数据模型
        │   ├── rate_limiter.py  # 限流 + 并发控制
        │   ├── service.py       # 核心服务
        │   ├── admin_commands.py # 飞书 /admin 命令
        │   ├── admin_routes.py  # Web API 路由
        │   └── dashboard.py     # HTML 管理界面
        ├── backtest/         # 回测模块
        │   ├── __init__.py
        │   ├── templates.py     # 6种策略模板库 + 代码规范化
        │   ├── direct_runner.py # 直接回测执行器（绕过 LLM）
        │   ├── charts.py        # 净值/回撤图表生成
        │   └── dashboard.py     # HTML 回测界面
        ├── backtest_commands.py # 飞书 /backtest 命令
        ├── channels/
        │   └── runtime.py       # 集成配额检查 + /backtest 命令
        ├── session/
        │   └── service.py       # 集成用量回调
        └── api/
            ├── backtest_routes.py # 回测 Web API 路由
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

## 回测功能

### 内置策略

| 策略 ID | 名称 | 类型 | 参数 |
|---------|------|------|------|
| `ma_cross` | 均线交叉策略 | 趋势跟踪 | fast_period, slow_period |
| `rsi_reversal` | RSI超买超卖策略 | 均值回归 | rsi_period, oversold, overbought |
| `macd_cross` | MACD交叉策略 | 趋势跟踪 | fast, slow, signal |
| `bollinger_breakout` | 布林带突破策略 | 突破 | bb_window, bb_std |
| `dual_momentum` | 双动量策略 | 动量 | lookback, threshold |
| `multi_factor_vote` | 多因子投票策略 | 复合 | ema_fast, ema_slow, rsi_period, bb_window |

### 飞书命令

| 命令 | 功能 |
|------|------|
| `/backtest` | 显示帮助 |
| `/backtest list` | 列出可用策略 |
| `/backtest <策略> <代码> <开始> <结束> [参数=值 ...]` | 运行回测 |

示例：
```
/backtest ma_cross 000001 2024-01-01 2024-12-31
/backtest rsi_reversal 600519 2023-01-01 2024-12-31 rsi_period=10 oversold=25
/backtest multi_factor_vote 515050 2026-05-01 2026-07-30
```

> 标的代码支持自动规范化：裸代码 `000001` 会自动添加 `.SZ` 后缀，`515050` 会添加 `.SH` 后缀。

### Web 回测界面

启动服务后访问 `http://127.0.0.1:8000/backtest/dashboard`

### 数据源说明

| 数据源 | 适用市场 | 是否免费 | 说明 |
|--------|---------|---------|------|
| akshare | A股/ETF/基金 | 免费 | 推荐首选，无需配置 |
| tushare | A股/ETF/基金 | 需积分 | 需配置 Token，数据更稳定 |
| yfinance | 美股/港股 | 免费 | 国内网络可能不稳定 |
| auto | 自动选择 | - | 自动路由到合适的数据源 |

默认使用 `akshare`，tushare 作为 fallback。配置 `TUSHARE_TOKEN` 后可使用 tushare 获取更稳定的数据。

## 故障排查

### 回测失败：`Exception: api init error`

**原因**：Tushare Token 未配置或无效。

**解决**：在 `~/.vibe-trading/.env` 中设置 `TUSHARE_TOKEN=你的Token`，或使用默认的 akshare 数据源。

### 回测失败：`RemoteDisconnected` / 连接被拒绝

**原因**：系统代理拦截了数据源的 HTTP 请求。

**解决**：`start.ps1` 已自动清除代理（`NO_PROXY=*`）。如果手动启动服务，需先执行：
```powershell
$env:HTTP_PROXY = ""; $env:HTTPS_PROXY = ""; $env:NO_PROXY = "*"
```

### 回测失败：`[Errno 22] Invalid argument`

**原因**：父进程控制台句柄损坏（通常因强制终止父进程导致）。

**解决**：停止所有 Python 进程后重新启动服务：
```powershell
Get-Process python,vibe-trading -ErrorAction SilentlyContinue | Stop-Process -Force
.\start.ps1
```

### 飞书消息无响应

1. 检查 `~/.vibe-trading/agent.json` 中飞书凭据是否正确
2. 检查 API 服务器是否运行：访问 `http://127.0.0.1:8000/health`
3. 检查飞书渠道是否连接：`vibe-trading channels status`
4. 查看控制台日志是否有 WebSocket 错误

### yfinance SSL 错误

**原因**：curl-cffi 证书路径问题。

**解决**：`start.ps1` 已自动配置 `CURL_CA_BUNDLE` 和 `REQUESTS_CA_BUNDLE`。yfinance 在国内网络下可能仍不可用，不影响 A 股回测功能。

### PowerShell 脚本报编码错误

**原因**：Windows PowerShell 5.1 读取 UTF-8 无 BOM 文件时编码异常。

**解决**：将脚本重新保存为 UTF-8 with BOM：
```powershell
$content = [System.IO.File]::ReadAllText("start.ps1", [System.Text.Encoding]::UTF8)
[System.IO.File]::WriteAllText("start.ps1", $content, [System.Text.UTF8Encoding]::new($true))
```

### `apply_customizations.ps1` 复制失败

**原因**：沙箱路径限制，PowerShell 无法写入 `.venv` 目录。

**解决**：使用 Python 直接复制：
```powershell
& .\.venv\Scripts\python.exe -c "import shutil; shutil.copy2(r'customizations\src\backtest\direct_runner.py', r'.venv\Lib\site-packages\src\backtest\direct_runner.py')"
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
| 回测引擎 | Vibe-Trading backtest runner |
| 部署 | Docker（规划中） |

## 开发路线图

- [x] 基础部署（飞书频道 + LLM + 数据源）
- [x] 用户配对认证
- [x] 流式卡片（CardKit 2.0 打字机 + COT 折叠）
- [x] 用户管理后端（用量限制 + Web 界面 + /admin 命令）
- [x] 回测 Web 端（策略模板 + 直接执行 + 图表 + Web 界面）
- [x] 飞书远程命令（/backtest 回测命令）
- [x] 数据源故障排查与修复（代理清除 + 代码规范化 + 错误处理）
- [ ] Docker 化上云部署

## 致谢

- [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) - HKUDS 出品的 AI 量化交易研究框架
- [飞书开放平台](https://open.feishu.cn/) - IM 通道与 CardKit
- [AkShare](https://akshare.akfamily.xyz/) - 免费 A 股数据源
- [Tushare](https://tushare.pro/) - A 股金融数据

## License

MIT
