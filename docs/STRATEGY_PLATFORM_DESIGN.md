# 策略/因子管理平台 — 详细技术方案

> **状态**: 实施方案（已确认）
> **范围**: Phase 1+2+3（持久化 + 用户隔离 + 市场）
> **更新**: 2026-08-02

---

## 1. 确认的设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 开发范围 | Phase 1+2+3 | 一步到位，避免后期重构 |
| 代码编辑 | Monaco Editor + 可选 NL 生成 | 最佳编辑体验 + AI 亮点 |
| 因子管理 | 策略 + 因子都做 | 完整的量化研究闭环 |
| 操作渠道 | Web 为主 + 飞书命令 | Web 做重操作，飞书做轻查询 |
| 数据库 | 新建 strategies.db | 与 usage.db 解耦 |
| 市场模式 | 克隆 + 订阅 | 克隆 = 独立 Fork；订阅 = 跟随更新 |
| 版本控制 | 限量快照（保留最近 10 个） | 简单可靠，自动清理 |
| 代码安全 | AST 校验（复用现有） | 无需引入新依赖 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     用户接入层                           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 飞书 Bot  │  │ Web 界面     │  │ API (REST)       │  │
│  │ /strategy │  │ Monaco编辑器 │  │ /api/strategies  │  │
│  │ /factor   │  │ 策略工作台   │  │ /api/factors     │  │
│  │ /market   │  │ 因子工作台   │  │ /api/market      │  │
│  │ /backtest │  │ 市场/仪表盘  │  │ /api/portfolios  │  │
│  └─────┬────┘  └──────┬───────┘  └────────┬─────────┘  │
└────────┼──────────────┼────────────────────┼────────────┘
         │              │                    │
┌────────▼──────────────▼────────────────────▼────────────┐
│                     服务层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐    │
│  │ StrategyStore│  │ FactorStore │  │ MarketService│    │
│  │ CRUD+版本   │  │ CRUD+版本   │  │ 克隆+订阅    │    │
│  │ AST校验     │  │ AST校验     │  │ 评分+评论    │    │
│  │ 参数解析    │  │ 组合管理    │  │ 搜索+筛选    │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘    │
│         │                │                │              │
│  ┌──────▼────────────────▼────────────────▼───────┐    │
│  │              BacktestEngine (现有)              │    │
│  │  generate_signal_engine() → run_backtest()     │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     数据层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ strategies.db│  │ usage.db     │  │ 文件系统     │  │
│  │ (策略/因子)  │  │ (用户/配额)  │  │ (回测产物)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 策略数据流

```
用户编写策略代码 (Web Monaco / 文件上传 / NL生成)
  │
  ▼
AST 校验 ← backtest.runner._validate_signal_engine_source()
  │ 通过
  ▼
存入 strategies.db (strategies 表 + strategy_versions 表)
  │
  ▼
templates.py._get_all_strategies() 合并 DB 策略
  │
  ├──→ list_strategies() → Web/飞书 策略列表
  │
  └──→ generate_signal_engine() → direct_runner → 回测执行
```

---

## 3. 数据库设计 (strategies.db)

### 3.1 完整 Schema

```sql
-- ============================================================
-- 策略表
-- ============================================================
CREATE TABLE IF NOT EXISTS strategies (
    id              TEXT PRIMARY KEY,          -- UUID
    user_id         TEXT NOT NULL,             -- 所有者 (Feishu open_id)
    name            TEXT NOT NULL,
    name_en         TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    category        TEXT DEFAULT 'custom',     -- trend/reversal/momentum/mean_reversion/breakout/composite
    tags            TEXT DEFAULT '[]',         -- JSON array: ["放量", "突破", "RSI"]
    source_code     TEXT NOT NULL,             -- signal_engine.py 完整源码
    meta_json       TEXT DEFAULT '{}',         -- {parameters: [...], markets: [...]}
    version         INTEGER DEFAULT 1,         -- 当前版本号
    status          TEXT DEFAULT 'draft',      -- draft/testing/published/archived
    parent_id       TEXT,                      -- 克隆来源 strategy_id (NULL=原创)
    is_public       INTEGER DEFAULT 0,         -- 是否发布到市场
    market_desc     TEXT DEFAULT '',           -- 市场展示描述
    subscriber_count INTEGER DEFAULT 0,        -- 订阅数
    clone_count     INTEGER DEFAULT 0,         -- 克隆数
    rating_avg      REAL DEFAULT 0,            -- 平均评分 (1-5)
    rating_count    INTEGER DEFAULT 0,         -- 评分人数
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_status ON strategies(status);
CREATE INDEX IF NOT EXISTS idx_strategies_public ON strategies(is_public) WHERE is_public = 1;
CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies(category);

-- ============================================================
-- 策略版本历史 (限量快照，保留最近 10 个)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_versions (
    id              TEXT PRIMARY KEY,          -- UUID
    strategy_id     TEXT NOT NULL,
    version         INTEGER NOT NULL,
    source_code     TEXT NOT NULL,
    meta_json       TEXT DEFAULT '{}',
    changelog       TEXT DEFAULT '',           -- 版本变更说明
    created_at      TEXT NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_strat_versions ON strategy_versions(strategy_id, version DESC);

-- ============================================================
-- 策略订阅 (用户订阅他人发布的策略，跟随更新)
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_subscriptions (
    user_id         TEXT NOT NULL,
    strategy_id     TEXT NOT NULL,
    subscribed_at   TEXT NOT NULL,
    PRIMARY KEY (user_id, strategy_id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);

-- ============================================================
-- 策略评分
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_ratings (
    user_id         TEXT NOT NULL,
    strategy_id     TEXT NOT NULL,
    rating          INTEGER NOT NULL,          -- 1-5
    comment         TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (user_id, strategy_id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE
);

-- ============================================================
-- 因子表 (结构同策略表，source_code 存 compute(panel) 实现)
-- ============================================================
CREATE TABLE IF NOT EXISTS factors (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    name_en         TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    category        TEXT DEFAULT 'custom',     -- momentum/value/volatility/volume/technical/fundamental
    tags            TEXT DEFAULT '[]',
    source_code     TEXT NOT NULL,             -- compute(panel) 实现
    meta_json       TEXT DEFAULT '{}',         -- {inputs: [...], outputs: [...]}
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    parent_id       TEXT,
    is_public       INTEGER DEFAULT 0,
    market_desc     TEXT DEFAULT '',
    subscriber_count INTEGER DEFAULT 0,
    clone_count     INTEGER DEFAULT 0,
    rating_avg      REAL DEFAULT 0,
    rating_count    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_factors_user ON factors(user_id);
CREATE INDEX IF NOT EXISTS idx_factors_public ON factors(is_public) WHERE is_public = 1;

CREATE TABLE IF NOT EXISTS factor_versions (
    id              TEXT PRIMARY KEY,
    factor_id       TEXT NOT NULL,
    version         INTEGER NOT NULL,
    source_code     TEXT NOT NULL,
    meta_json       TEXT DEFAULT '{}',
    changelog       TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS factor_subscriptions (
    user_id         TEXT NOT NULL,
    factor_id       TEXT NOT NULL,
    subscribed_at   TEXT NOT NULL,
    PRIMARY KEY (user_id, factor_id),
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS factor_ratings (
    user_id         TEXT NOT NULL,
    factor_id       TEXT NOT NULL,
    rating          INTEGER NOT NULL,
    comment         TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (user_id, factor_id),
    FOREIGN KEY (factor_id) REFERENCES factors(id) ON DELETE CASCADE
);

-- ============================================================
-- 因子组合配置 (多因子策略)
-- ============================================================
CREATE TABLE IF NOT EXISTS factor_portfolios (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    config_json     TEXT NOT NULL,             -- 见下方 JSON 结构
    status          TEXT DEFAULT 'draft',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON factor_portfolios(user_id);
```

### 3.2 factor_portfolios.config_json 结构

```json
{
  "factors": [
    {"id": "uuid-xxx", "weight": 0.3, "direction": "long"},
    {"id": "uuid-yyy", "weight": 0.7, "direction": "long"}
  ],
  "selection": {
    "method": "top_n",
    "value": 10
  },
  "rebalance": "weekly",
  "universe": ["HS300", "ZZ500"]
}
```

### 3.3 连接管理（复用 usage/db.py 模式）

```python
# strategy_store/db.py
_LOCK = threading.Lock()
_initialized = False

def get_db_path() -> Path:
    return get_data_dir() / "strategies.db"  # ~/.vibe-trading/strategies.db

def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    # 双重检查锁，同 usage/db.py
```

---

## 4. 服务层设计

### 4.1 文件结构

```
customizations/src/
├── strategy_store/
│   ├── __init__.py
│   ├── db.py                 # SQLite 连接 + Schema
│   ├── models.py             # 数据类 (Strategy, StrategyVersion, Factor, ...)
│   ├── service.py            # Strategy CRUD + 版本管理 + 发布
│   ├── validator.py          # AST 校验 (复用 backtest.runner)
│   └── migration.py          # 从 custom_strategies/ 迁移到 DB
├── factor_store/
│   ├── __init__.py
│   ├── db.py                 # 复用 strategy_store/db.py (同一个 strategies.db)
│   ├── models.py
│   ├── service.py            # Factor CRUD + 版本 + 组合管理
│   └── validator.py
├── market/
│   ├── __init__.py
│   └── service.py            # 克隆/订阅/评分/搜索
├── api/
│   ├── strategy_routes.py    # /api/strategies/*
│   ├── factor_routes.py      # /api/factors/*
│   ├── market_routes.py      # /api/market/*
│   └── portfolio_routes.py   # /api/portfolios/*
├── web/
│   ├── __init__.py
│   ├── strategies_page.py    # 策略工作台 HTML
│   ├── factors_page.py       # 因子工作台 HTML
│   ├── market_page.py        # 市场页面 HTML
│   └── workspace_page.py     # 个人仪表盘 HTML
├── strategy_commands.py      # 飞书 /strategy /factor /market 命令
```

### 4.2 StrategyStore Service 核心接口

```python
# strategy_store/service.py

class StrategyStoreService:
    """策略管理服务：CRUD + 版本 + 发布 + 校验"""

    # --- CRUD ---
    def create_strategy(self, user_id, name, source_code, **kwargs) -> dict
    def get_strategy(self, strategy_id, user_id=None) -> dict | None
    def update_strategy(self, strategy_id, user_id, **fields) -> dict
    def delete_strategy(self, strategy_id, user_id) -> bool
    def list_user_strategies(self, user_id, status=None, category=None) -> list[dict]

    # --- 版本管理 ---
    def list_versions(self, strategy_id, user_id, limit=10) -> list[dict]
    def get_version(self, strategy_id, version, user_id) -> dict | None
    def rollback_to_version(self, strategy_id, version, user_id) -> dict
    def _save_version_snapshot(self, strategy_id, version, source_code, meta, changelog)
    def _prune_old_versions(self, strategy_id, keep=10)  # 限量快照清理

    # --- 校验 ---
    def validate_source(self, source_code) -> tuple[bool, str]
    # 内部调用 backtest.runner._validate_signal_engine_source()

    # --- 导入 ---
    def import_from_file(self, user_id, filename, source_code) -> dict
    # 自动解析 __init__ 参数 → meta_json

    # --- 发布/取消发布 ---
    def publish(self, strategy_id, user_id, market_desc) -> dict
    def unpublish(self, strategy_id, user_id) -> dict

    # --- 参数解析 ---
    def _parse_parameters(self, source_code) -> list[dict]
    # AST 解析 SignalEngine.__init__ 的参数签名
```

### 4.3 MarketService 核心接口

```python
# market/service.py

class MarketService:
    """策略/因子市场：克隆/订阅/评分/搜索"""

    # --- 浏览 ---
    def list_published_strategies(self, category=None, sort="recent", page=1, size=20) -> dict
    def list_published_factors(self, category=None, sort="recent", page=1, size=20) -> dict
    def search(self, query, type="strategy") -> list[dict]  # 简单 LIKE 搜索

    # --- 克隆 ---
    def clone_strategy(self, strategy_id, user_id) -> dict
    # 创建副本：parent_id=原策略, status=draft, 独立维护
    def clone_factor(self, factor_id, user_id) -> dict

    # --- 订阅 ---
    def subscribe_strategy(self, strategy_id, user_id) -> dict
    def unsubscribe_strategy(self, strategy_id, user_id) -> bool
    def get_subscribed_strategies(self, user_id) -> list[dict]
    # 订阅后：原作者更新时，订阅者获得副本更新通知

    # --- 评分 ---
    def rate_strategy(self, strategy_id, user_id, rating, comment) -> dict
    def get_ratings(self, strategy_id, page=1, size=10) -> dict
```

---

## 5. API 设计

### 5.1 策略管理 API

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/strategies` | 列出我的策略（支持筛选） | require_auth |
| POST | `/api/strategies` | 创建策略 | require_auth |
| GET | `/api/strategies/{id}` | 策略详情 | require_auth |
| PUT | `/api/strategies/{id}` | 更新策略（自动存版本） | require_auth |
| DELETE | `/api/strategies/{id}` | 删除策略 | require_auth |
| POST | `/api/strategies/import` | 从 .py 文件导入 | require_auth |
| POST | `/api/strategies/validate` | 校验源码（不保存） | require_auth |
| GET | `/api/strategies/{id}/versions` | 版本列表 | require_auth |
| GET | `/api/strategies/{id}/versions/{ver}` | 获取特定版本 | require_auth |
| POST | `/api/strategies/{id}/rollback/{ver}` | 回滚到版本 | require_auth |
| POST | `/api/strategies/{id}/publish` | 发布到市场 | require_auth |
| POST | `/api/strategies/{id}/unpublish` | 从市场下架 | require_auth |

### 5.2 因子管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/factors` | 列出我的因子 |
| POST | `/api/factors` | 创建因子 |
| GET | `/api/factors/{id}` | 因子详情 |
| PUT | `/api/factors/{id}` | 更新因子 |
| DELETE | `/api/factors/{id}` | 删除因子 |
| POST | `/api/factors/import` | 导入因子 |
| POST | `/api/factors/validate` | 校验因子源码 |
| GET | `/api/factors/{id}/versions` | 版本列表 |
| POST | `/api/factors/{id}/rollback/{ver}` | 回滚 |
| POST | `/api/factors/{id}/publish` | 发布 |
| GET | `/api/factors/zoo` | 浏览预置因子库 (Alpha101/GTJA191) |

### 5.3 因子组合 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/portfolios` | 列出我的组合 |
| POST | `/api/portfolios` | 创建组合 |
| PUT | `/api/portfolios/{id}` | 更新组合 |
| DELETE | `/api/portfolios/{id}` | 删除组合 |
| POST | `/api/portfolios/{id}/generate-strategy` | 从组合生成策略代码 |

### 5.4 市场 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/market/strategies` | 浏览已发布策略 |
| GET | `/api/market/factors` | 浏览已发布因子 |
| GET | `/api/market/search` | 搜索 (?q=xxx&type=strategy) |
| POST | `/api/market/strategies/{id}/clone` | 克隆策略 |
| POST | `/api/market/strategies/{id}/subscribe` | 订阅策略 |
| DELETE | `/api/market/strategies/{id}/subscribe` | 取消订阅 |
| POST | `/api/market/strategies/{id}/rate` | 评分 (body: {rating, comment}) |
| GET | `/api/market/strategies/{id}/ratings` | 查看评分 |

### 5.5 用户身份获取

API 需要知道当前操作者是谁。方案：

```python
# 从 require_auth 返回的 request 中提取用户标识
# 方案 A: 通过 API Key 关联到用户（需要在 users 表中存储 api_key）
# 方案 B: 新增 X-User-Id header（适合当前本地部署场景）
# 方案 C: 从 Bearer token 解析（需要扩展认证系统）

# 推荐方案 B (当前阶段最简单):
@app.get("/api/strategies", dependencies=[Depends(require_auth)])
async def list_strategies(request: Request):
    user_id = request.headers.get("X-User-Id", "local")
    return strategy_service.list_user_strategies(user_id)
```

---

## 6. Web 前端设计

### 6.1 页面规划

```
/workspace          → 个人仪表盘 (概览 + 快捷入口)
/strategies         → 策略工作台 (列表 + Monaco 编辑器)
/strategies/{id}    → 策略编辑/详情
/factors            → 因子工作台
/factors/{id}       → 因子编辑/详情
/portfolios         → 因子组合管理
/market             → 策略/因子市场
/market/strategy/{id} → 市场策略详情
```

### 6.2 策略工作台布局

```
┌─────────────────────────────────────────────────────────┐
│  Vibe-Trading 策略工作台          [仪表盘] [市场] [退出] │
├──────────────┬──────────────────────────────────────────┤
│ 策略列表     │  ┌─[编辑]─[版本]─[回测]─[发布]──────────┐│
│              │  │                                      ││
│ [🔍 搜索]    │  │  策略名称: [_______________]         ││
│ [+ 新建策略] │  │  分类: [趋势 v]  标签: [RSI,突破]    ││
│              │  │  描述: [______________________]     ││
│ 📁 我的策略  │  │                                      ││
│  • 砖型图反转│  │  ┌─ Monaco Editor ─────────────────┐ ││
│  • 均线交叉  │  │  │ 1  """策略文档"""               │ ││
│  • RSI反转   │  │  │ 2                              │ ││
│              │  │  │ 3  class SignalEngine:          │ ││
│ 📢 订阅策略  │  │  │ 4      def __init__(self):     │ ││
│  • 动量精选  │  │  │ 5          ...                  │ ││
│              │  │  └────────────────────────────────┘ ││
│ ─────────── │  │                                      ││
│ 状态: draft  │  │  [保存] [校验] [回测] [发布到市场]  ││
│              │  └──────────────────────────────────────┘│
└──────────────┴──────────────────────────────────────────┘
```

### 6.3 Monaco Editor 集成

```html
<!-- CDN 加载 Monaco Editor (无需 npm build) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js"></script>
<script>
  require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }});
  require(['vs/editor/editor.main'], function () {
    const editor = monaco.editor.create(document.getElementById('editor'), {
      value: '',  // 从 API 加载
      language: 'python',
      theme: 'vs-dark',
      automaticLayout: true,
      minimap: { enabled: true },
      fontSize: 13,
      tabSize: 4,
      scrollBeyondLastLine: false,
    });
    window.strategyEditor = editor;
  });
</script>
```

### 6.4 前端技术栈

| 组件 | 方案 | 说明 |
|------|------|------|
| 样式 | 内联 CSS (复用现有 dashboard 风格) | 暗色主题，与 backtest dashboard 一致 |
| 编辑器 | Monaco Editor (CDN) | 无需 npm build，CDN 加载 |
| 交互 | 原生 JS + fetch | 不引入框架，保持轻量 |
| 页面 | Python 后端生成 HTML | 复用 `get_dashboard_html()` 模式 |

---

## 7. 飞书命令设计

### 7.1 命令列表

```
/strategy                    → 策略命令帮助
/strategy list               → 列出我的策略
/strategy list published     → 列出已发布策略
/strategy import <name>      → 导入策略 (提示上传文件)
/strategy publish <id>       → 发布策略到市场
/strategy delete <id>        → 删除策略

/factor                      → 因子命令帮助
/factor list                 → 列出我的因子
/factor zoo                  → 浏览预置因子库

/market                      → 市场帮助
/market strategies           → 浏览策略市场
/market factors              → 浏览因子市场
/market clone <id>           → 克隆策略
/market subscribe <id>       → 订阅策略
/market rate <id> <1-5>      → 评分
```

### 7.2 命令分发集成

在 `channels/runtime.py` 的 `_handle_inbound()` 中新增 3 个命令分发块：

```python
# --- /strategy 命令 ---
if self._is_strategy_command(msg.content):
    from src.strategy_commands import handle_strategy_command
    reply = handle_strategy_command(msg.sender_id, ...)
    ...

# --- /factor 命令 ---
if self._is_factor_command(msg.content):
    from src.strategy_commands import handle_factor_command
    ...

# --- /market 命令 ---
if self._is_market_command(msg.content):
    from src.strategy_commands import handle_market_command
    ...
```

---

## 8. 与现有回测系统集成

### 8.1 templates.py 改造

在 `_get_all_strategies()` 中新增 DB 策略合并：

```python
def _get_all_strategies() -> dict[str, dict[str, Any]]:
    """Return merged system + custom + DB strategies."""
    merged = dict(STRATEGY_TEMPLATES)           # 系统策略
    merged.update(_scan_custom_strategies())     # 文件策略 (向后兼容)
    merged.update(_scan_db_strategies())         # 数据库策略 (新增)
    return merged

def _scan_db_strategies() -> dict[str, dict[str, Any]]:
    """从 strategies.db 加载用户策略，合并到策略列表。"""
    try:
        from src.strategy_store.service import StrategyStoreService
        svc = StrategyStoreService()
        db_strategies = svc.list_all_active_strategies()  # 所有用户的策略
        result = {}
        for s in db_strategies:
            result[s["id"]] = {
                "name": s["name"],
                "name_en": s.get("name_en", s["id"]),
                "description": s["description"],
                "category": s["category"],
                "source": "user",         # 新来源标记
                "tier": "advanced",
                "markets": s.get("meta", {}).get("markets", ["a_share"]),
                "parameters": s.get("meta", {}).get("parameters", []),
                "code_source": s["source_code"],
            }
        return result
    except Exception:
        logger.exception("Failed to scan DB strategies")
        return {}
```

### 8.2 策略 ID 命名空间

为避免 ID 冲突：
- 系统策略: `ma_cross`, `rsi_reversal` (短名)
- 文件策略: `brick_reversal` (文件名)
- DB 策略: `uuid-xxxx-xxxx` (UUID，绝不冲突)

回测时 `strategy_id` 优先查 DB，再查文件，再查系统模板。

---

## 9. 实施计划 (Sprint 分解)

### Sprint 1: 数据层 + 策略 CRUD (核心基础)

**目标**: 策略存入数据库，替代文件系统

| 任务 | 文件 | 预估 |
|------|------|------|
| 数据库 Schema + 连接管理 | `strategy_store/db.py`, `models.py` | 2h |
| StrategyStore Service (CRUD + 版本) | `strategy_store/service.py` | 4h |
| AST 校验器 (复用 backtest.runner) | `strategy_store/validator.py` | 1h |
| 参数自动解析 (AST 解析 __init__) | `strategy_store/service.py` | 2h |
| 迁移脚本 (custom_strategies/ → DB) | `strategy_store/migration.py` | 1h |
| templates.py 集成 (_scan_db_strategies) | `backtest/templates.py` | 1h |
| 单元测试 | 测试脚本 | 2h |

**Sprint 1 交付**: 策略可通过 API 存入数据库，回测时可从 DB 读取执行

### Sprint 2: 策略 API + Web 策略工作台

**目标**: Web 界面创建/编辑/回测策略

| 任务 | 文件 | 预估 |
|------|------|------|
| 策略 CRUD API (11 个端点) | `api/strategy_routes.py` | 3h |
| 策略工作台 HTML (含 Monaco) | `web/strategies_page.py` | 4h |
| 版本管理界面 (版本列表/回滚) | 同上 | 2h |
| 文件上传导入 | API + 前端 | 1h |
| api_server.py 路由注册 | `api_server.py` | 0.5h |
| 集成测试 | - | 2h |

**Sprint 2 交付**: 完整的 Web 策略管理工作台

### Sprint 3: 因子管理 + 因子组合

**目标**: 因子 CRUD + 因子组合生成策略

| 任务 | 文件 | 预估 |
|------|------|------|
| FactorStore Service | `factor_store/service.py` | 3h |
| 因子 API | `api/factor_routes.py` | 2h |
| 因子工作台 HTML | `web/factors_page.py` | 3h |
| 因子组合 API + 生成策略 | `api/portfolio_routes.py` | 3h |
| 预置因子库浏览 API | `factor_store/service.py` | 1h |
| 集成测试 | - | 2h |

**Sprint 3 交付**: 完整的因子管理工作台 + 组合策略生成

### Sprint 4: 用户隔离 + 市场

**目标**: 用户空间隔离 + 策略/因子市场

| 任务 | 文件 | 预估 |
|------|------|------|
| 用户隔离 (所有查询加 user_id) | Service 层改造 | 2h |
| MarketService (克隆/订阅/评分) | `market/service.py` | 4h |
| 市场 API | `api/market_routes.py` | 2h |
| 市场页面 HTML | `web/market_page.py` | 3h |
| 个人仪表盘 HTML | `web/workspace_page.py` | 2h |
| 集成测试 | - | 2h |

**Sprint 4 交付**: 多用户隔离 + 完整市场功能

### Sprint 5: 飞书命令 + NL 生成

**目标**: 飞书命令集成 + 自然语言生成策略

| 任务 | 文件 | 预估 |
|------|------|------|
| 飞书 /strategy /factor /market 命令 | `strategy_commands.py` | 3h |
| runtime.py 命令分发集成 | `channels/runtime.py` | 1h |
| NL 生成策略 API (调用 LLM) | `api/strategy_routes.py` | 2h |
| NL 生成前端入口 | `web/strategies_page.py` | 1h |
| 端到端测试 | - | 2h |

**Sprint 5 交付**: 飞书命令 + AI 生成策略

### 总预估

| Sprint | 内容 | 预估工时 |
|--------|------|---------|
| 1 | 数据层 + 策略 CRUD | ~13h |
| 2 | 策略 API + Web 工作台 | ~12.5h |
| 3 | 因子管理 + 组合 | ~14h |
| 4 | 用户隔离 + 市场 | ~15h |
| 5 | 飞书命令 + NL 生成 | ~9h |
| **合计** | | **~63.5h** |

---

## 10. 关键实现细节

### 10.1 参数自动解析 (AST)

```python
import ast

def _parse_parameters(source_code: str) -> list[dict]:
    """从 SignalEngine.__init__ 的参数签名解析参数定义。"""
    tree = ast.parse(source_code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SignalEngine":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    params = []
                    for arg in item.args.args:
                        if arg.arg == "self":
                            continue
                        # 解析类型注解
                        type_str = _annotation_to_str(arg.annotation)
                        # 解析默认值
                        default = _get_default(item.args.defaults, arg, item.args.args)
                        params.append({
                            "key": arg.arg,
                            "label": arg.arg.replace("_", " ").title(),
                            "type": type_str,
                            "default": default,
                        })
                    return params
    return []
```

### 10.2 版本快照管理

```python
def update_strategy(self, strategy_id, user_id, source_code=None, **fields):
    # 1. 获取当前策略
    strategy = self.get_strategy(strategy_id, user_id)
    old_version = strategy["version"]

    # 2. 如果源码变更，保存旧版本快照
    if source_code and source_code != strategy["source_code"]:
        self._save_version_snapshot(
            strategy_id, old_version,
            strategy["source_code"], strategy["meta_json"],
            changelog="before update"
        )
        # 校验新代码
        ok, msg = self.validate_source(source_code)
        if not ok:
            raise ValueError(f"AST validation failed: {msg}")
        fields["source_code"] = source_code
        fields["version"] = old_version + 1

    # 3. 更新策略记录
    fields["updated_at"] = _now()
    # ... SQL UPDATE ...

    # 4. 清理旧版本（保留最近 10 个）
    self._prune_old_versions(strategy_id, keep=10)
```

### 10.3 克隆 vs 订阅

```python
def clone_strategy(self, strategy_id, user_id):
    """克隆：创建独立副本，与原策略无关。"""
    original = self.get_strategy(strategy_id)  # 公开策略
    if not original or not original["is_public"]:
        raise ValueError("Strategy not found or not published")

    # 创建副本
    clone = self.create_strategy(
        user_id=user_id,
        name=f"{original['name']} (克隆)",
        source_code=original["source_code"],
        parent_id=strategy_id,          # 记录来源
        category=original["category"],
        meta_json=original["meta_json"],
    )

    # 增加原策略的 clone_count
    self._increment_count(strategy_id, "clone_count")
    return clone

def subscribe_strategy(self, strategy_id, user_id):
    """订阅：不创建副本，标记关注，原策略更新时通知。"""
    # 订阅者回测时直接引用原策略 source_code
    # 原策略更新时，通过订阅表通知所有订阅者
    # 订阅者可以选择 "同步到最新版本" 或保持当前版本
```

### 10.4 用户身份传递

```python
# api/strategy_routes.py

def _get_user_id(request: Request) -> str:
    """从请求中提取用户 ID。"""
    # 优先从 header 获取
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return user_id
    # 降级：从 API Key 关联的用户获取
    # 最低降级：本地开发模式
    return "local"
```

---

## 11. 向下兼容与迁移

### 11.1 迁移策略

1. **保留文件扫描**: `_scan_custom_strategies()` 继续工作，作为"本地导入"入口
2. **启动时迁移**: 服务启动时自动将 `~/.vibe-trading/custom_strategies/*.py` 导入 DB
3. **ID 映射**: 文件策略导入 DB 后用 UUID 作为新 ID，旧 ID 保留在 `meta_json.legacy_id` 中
4. **回退机制**: 如果 DB 不可用，自动降级到文件扫描

### 11.2 迁移脚本

```python
# strategy_store/migration.py

def migrate_custom_strategies():
    """将 custom_strategies/ 目录下的策略迁移到数据库。"""
    custom_dir = _get_custom_strategies_dir()
    if not custom_dir.exists():
        return {"migrated": 0, "skipped": 0}

    svc = StrategyStoreService()
    migrated = 0
    skipped = 0

    for py_file in sorted(custom_dir.glob("*.py")):
        # 读取 meta.json
        meta_file = custom_dir / f"{py_file.stem}.meta.json"
        meta = json.loads(meta_file.read_text("utf-8-sig")) if meta_file.exists() else {}

        # 检查是否已迁移 (通过 legacy_id)
        existing = svc.find_by_legacy_id(py_file.stem)
        if existing:
            skipped += 1
            continue

        # 导入到 DB
        svc.create_strategy(
            user_id="local",  # 迁移的策略归属 "local" 用户
            name=meta.get("name", py_file.stem),
            source_code=py_file.read_text("utf-8-sig"),
            meta_json=meta,
        )
        migrated += 1

    return {"migrated": migrated, "skipped": skipped}
```

---

## 12. 测试计划

### 12.1 单元测试

```python
# tests/test_strategy_store.py
- test_create_strategy
- test_get_strategy
- test_update_strategy_creates_version
- test_rollback_to_version
- test_validate_source_rejects_decorator
- test_validate_source_rejects_import_os
- test_parse_parameters_from_init
- test_prune_old_versions_keeps_10
- test_delete_strategy_cascades_versions

# tests/test_factor_store.py
- test_create_factor
- test_factor_validate
- test_portfolio_create
- test_portfolio_generate_strategy

# tests/test_market.py
- test_publish_strategy
- test_clone_creates_independent_copy
- test_subscribe_does_not_create_copy
- test_rate_strategy_updates_avg
- test_user_isolation
```

### 12.2 集成测试

```python
# tests/test_integration.py
- test_create_strategy_via_api
- test_update_strategy_via_api
- test_backtest_db_strategy  # 创建策略 → 回测 → 验证结果
- test_clone_and_modify      # 克隆 → 修改 → 回测
- test_market_publish_clone_flow
```
