# 策略/因子管理产品化规划

> **状态**: 远期规划（预研阶段）
> **更新**: 2026-07-31
> **背景**: 当前系统策略/因子管理偏向个人工具，需向多用户平台演进

---

## 1. 现状分析

### 1.1 策略管理现状

| 维度 | 现状 | 问题 |
|------|------|------|
| 存储方式 | 系统策略硬编码在 `templates.py`；定制策略放在 `~/.vibe-trading/custom_strategies/` | 无数据库持久化，无版本管理 |
| 用户隔离 | 无 | 所有用户共享同一策略目录 |
| 生命周期 | 无 | 策略文件放进去即生效，无审核/发布流程 |
| 参数调优 | 系统策略支持界面调参；定制策略使用默认参数 | 定制策略无法通过界面调参 |
| 分类标记 | system(标准) / custom(高级) | 分类粒度粗，缺乏标签/搜索 |
| 权限控制 | 无 | 任何用户可执行任何策略 |

### 1.2 因子管理现状

| 维度 | 现状 | 问题 |
|------|------|------|
| 存储方式 | 预置因子库在 `src/factors/zoo/`（Alpha101, GTJA191, 学术因子等） | 无用户自定义因子入口 |
| 用户隔离 | 无 | 无用户级因子空间 |
| 复用机制 | `ZooSignalEngine` 可组合多因子 | 组合配置不可持久化、不可分享 |
| 注册机制 | 自动扫描 `zoo/` 目录 | 无审核、无元数据校验 |

---

## 2. 目标架构

### 2.1 核心概念

```
用户空间 (User Workspace)
├── 我的策略 (My Strategies)        ← 用户私有，可发布到平台
├── 我的因子 (My Factors)           ← 用户私有，可发布到平台
├── 我的组合 (My Portfolios)        ← 因子组合配置，可分享
└── 回测历史 (Backtest History)     ← 用户级回测记录

平台公共区 (Platform Public)
├── 系统策略 (System Strategies)    ← 平台维护，所有用户可用
├── 公共因子库 (Public Factor Zoo)  ← Alpha101/GTJA191等 + 用户贡献
├── 策略市场 (Strategy Market)      ← 用户发布的策略，可订阅/克隆
└── 因子市场 (Factor Market)        ← 用户发布的因子，可订阅/克隆
```

### 2.2 策略生命周期

```
     ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
     │  草稿   │────→│  测试中  │────→│  已发布  │────→│  已归档  │
     │ (draft) │     │ (testing)│     │(published)│    │(archived)│
     └─────────┘     └──────────┘     └──────────┘     └──────────┘
          │               │                │
          │               └── 回测验证 ──→ 通过/不通过
          │
          └── 可回滚到任意历史版本
```

### 2.3 数据模型设计（草案）

```sql
-- 用户策略表
CREATE TABLE user_strategies (
    id          TEXT PRIMARY KEY,          -- UUID
    user_id     TEXT NOT NULL,             -- 用户 open_id
    name        TEXT NOT NULL,
    description TEXT,
    category    TEXT DEFAULT 'custom',     -- trend/reversal/momentum/...
    source_code TEXT NOT NULL,             -- signal_engine.py 源码
    meta_json   TEXT,                      -- 参数定义、市场标签等
    version     INTEGER DEFAULT 1,         -- 版本号
    status      TEXT DEFAULT 'draft',      -- draft/testing/published/archived
    parent_id   TEXT,                      -- fork 来源（克隆的策略）
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 策略版本历史
CREATE TABLE strategy_versions (
    id          TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    version     INTEGER NOT NULL,
    source_code TEXT NOT NULL,
    meta_json   TEXT,
    changelog   TEXT,                      -- 版本变更说明
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES user_strategies(id)
);

-- 用户因子表
CREATE TABLE user_factors (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    source_code TEXT NOT NULL,             -- compute(panel) 实现
    meta_json   TEXT,                      -- 因子元数据
    category    TEXT DEFAULT 'custom',     -- momentum/value/volatility/...
    status      TEXT DEFAULT 'draft',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 因子组合配置
CREATE TABLE factor_portfolios (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    factor_ids  TEXT NOT NULL,             -- JSON: [{id, weight, direction}]
    selection   TEXT,                      -- 选股规则 (top_n, threshold)
    rebalance   TEXT,                      -- 调仓频率
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 3. 分阶段实施路线

### Phase 1: 策略持久化与版本管理（本地阶段）

**目标**: 将策略从文件系统迁移到数据库，支持版本管理

**关键任务**:
- 创建 `strategy_store` SQLite 表（复用现有 `usage.db`）
- 实现 Strategy CRUD API（`/api/strategies/*`）
- 策略导入：从 `signal_engine.py` 文件导入，自动解析参数
- 策略版本：每次编辑保存新版本，支持查看 diff 和回滚
- Web 界面：策略管理页面（列表/编辑/版本对比）
- 迁移现有 `custom_strategies/` 文件到数据库

**不涉及**: 多用户隔离、发布流程

### Phase 2: 用户空间与权限隔离

**目标**: 每个用户有独立的策略/因子空间

**关键任务**:
- 用户策略表关联 `user_id`
- API 层强制用户隔离（只能操作自己的策略）
- 因子管理：用户可上传自定义因子脚本
- 因子组合：可视化因子组合编辑器
- Web 界面：个人工作台 Dashboard

**权限模型**:
| 角色 | 系统策略 | 自己的策略 | 他人发布策略 | 公共因子 |
|------|---------|-----------|-------------|---------|
| 普通用户 | 查看/回测 | 增删改查 | 查看/克隆 | 查看/计算 |
| 管理员 | 全部 | 全部 | 全部 | 增删改查 |

### Phase 3: 策略/因子市场

**目标**: 用户可发布策略和因子供他人使用

**关键任务**:
- 发布流程：草稿 → 提交审核 → 审核通过 → 发布
- 策略市场页面：搜索/筛选/评分/克隆
- 因子市场页面：同上
- 订阅机制：订阅后策略更新自动通知
- 评分与评论

**发布流程**:
```
用户编辑策略 → 提交审核 → 管理员审核 → 发布到市场
                                    ↓
                              审核不通过 → 退回修改
```

### Phase 4: 云端协作（远期）

**目标**: 多实例部署、云端同步

**关键任务**:
- 策略/因子云端存储（PostgreSQL）
- 实时协作编辑（类似 Google Docs）
- 策略绩效排行
- API 开放平台（第三方接入）

---

## 4. 技术选型建议

| 组件 | 当前 | 目标 | 备注 |
|------|------|------|------|
| 策略存储 | 文件系统 | SQLite → PostgreSQL | 渐进迁移 |
| 版本管理 | 无 | strategy_versions 表 | 简单版本控制，非 Git |
| 代码编辑 | 无 | Monaco Editor (Web) | VS Code 同款编辑器 |
| 代码校验 | AST 解析 | AST + 沙箱执行 | 防止恶意代码 |
| 搜索 | 无 | SQLite FTS5 → Elasticsearch | 全文搜索 |
| 权限 | 无 | RBAC | 基于角色的访问控制 |

---

## 5. 与当前架构的兼容性

### 5.1 向下兼容

- 现有 `custom_strategies/` 目录扫描机制保留，作为"本地导入"入口
- 现有 `STRATEGY_TEMPLATES` 硬编码策略标记为 `system` 来源
- 现有 `list_strategies()` / `get_strategy()` API 保持不变，新增数据库策略合并返回

### 5.2 渐进迁移路径

```
Phase 0 (当前)
  custom_strategies/*.py ──→ _scan_custom_strategies() ──→ list_strategies()

Phase 1
  DB: user_strategies ──→ _scan_db_strategies() ──┐
  custom_strategies/*.py ──→ _scan_custom_strategies() ──┤── merge ──→ list_strategies()
  STRATEGY_TEMPLATES (硬编码) ──────────────────────────┘

Phase 2+
  DB: user_strategies (per-user) ──→ _scan_user_strategies(user_id) ──┐
  DB: published_strategies ──→ _scan_market_strategies() ──────────────┤── merge ──→ list_strategies()
  STRATEGY_TEMPLATES (硬编码) ─────────────────────────────────────────┘
```

---

## 6. 风险与约束

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 代码安全 | 用户上传恶意 Python 代码 | AST 校验 + 沙箱执行 + 限制 import |
| 性能 | 策略过多导致列表缓慢 | 分页 + 缓存 + 懒加载 |
| 数据迁移 | 现有文件策略丢失 | 迁移脚本 + 保留文件扫描 fallback |
| 复杂度 | 过度设计 | 严格按 Phase 迭代，不过早实现 |

---

## 7. 近期可落地的改进

在正式进入 Phase 1 之前，以下改进可以快速实施：

1. **定制策略参数化**: 解析 `__init__` 的默认参数，支持界面调参（当前仅系统策略支持）
2. **策略标签**: 增加 `tags` 字段，支持按标签筛选
3. **策略搜索**: 在 `/backtest/strategies` API 增加搜索参数
4. **策略删除**: 支持 `/backtest/strategies/{id}` DELETE 删除定制策略
5. **策略导入 API**: `POST /backtest/strategies/import` 上传 `.py` 文件自动注册
