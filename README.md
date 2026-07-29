# Vibe-Trading Feishu Bot

基于 [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) 的 AI 量化交易飞书机器人。

通过飞书 IM 随时随地获取股票分析、投研判断和策略回测，支持自然语言交互。

## 功能特性

- **自然语言投研**：直接在飞书中发送问题，AI 自动分析股票（如"分析一下贵州茅台"）
- **流式卡片回复**：基于飞书 CardKit 2.0 的打字机效果，实时显示生成进度
- **WebSocket 长连接**：无需公网 IP 或域名，本地直接运行
- **多数据源支持**：AkShare（A股）、Tushare、yfinance
- **量化因子库**：内置 Alpha101、学术因子、基本面因子、国泰君安191 因子
- **用户配对认证**：原生配对码白名单机制，控制访问权限

## 快速开始

### 1. 环境要求

- Python 3.11+
- 飞书开放平台账号（创建自建应用）
- DeepSeek API Key（或其他 LLM）

### 2. 安装

```powershell
# 克隆仓库
git clone https://github.com/<your-username>/vibe-trading-feishu.git
cd vibe-trading-feishu

# 运行安装脚本
.\setup.ps1
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
- `纳斯达克指数最近怎么样`

## 项目结构

```
vibe-trading-feishu/
├── .env.example          # 配置模板（不含密钥）
├── .gitignore
├── README.md
├── start.ps1             # 一键启动
├── setup.ps1             # 环境初始化
├── requirements.txt      # Python 依赖
├── login_feishu.ps1      # 飞书扫码登录
└── config_feishu_manual.ps1  # 手动配置飞书凭据
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 核心框架 | Vibe-Trading (Python) |
| IM 通道 | 飞书 WebSocket + CardKit 2.0 |
| LLM | DeepSeek API |
| 数据源 | AkShare / Tushare / yfinance |
| API 层 | FastAPI |
| 部署 | Docker（规划中） |

## 开发路线图

- [x] 基础部署（飞书频道 + LLM + 数据源）
- [x] 用户配对认证
- [ ] 流式卡片验证与调优
- [ ] 用户管理后端（用量限制）
- [ ] Docker 化上云部署
- [ ] 回测 Web 端
- [ ] 飞书远程命令（回测/策略管理）

## 致谢

- [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) - HKUDS 出品的 AI 量化交易研究框架
- [飞书开放平台](https://open.feishu.cn/) - IM 通道与 CardKit

## License

MIT
