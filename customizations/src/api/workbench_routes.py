"""Web Workbench for Strategy & Factor Management.

Serves a single-page HTML app at /workbench that provides:
- Strategy list with search, filter, and pagination
- Create / edit strategy with live code editor and AST validation preview
- Version history with diff and rollback
- Marketplace browser (published strategies, clone, rate, subscribe)
- Factor management (parallel to strategies)
- Factor portfolio configuration

The HTML is self-contained (no external CDN dependencies) to work in
air-gapped environments.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def register_workbench_routes(app: FastAPI, require_auth=None) -> None:
    """Mount /workbench route — serves the SPA HTML."""

    if require_auth is None:
        import sys as _sys
        _host = _sys.modules.get("api_server")
        if _host is not None:
            require_auth = getattr(_host, "require_auth", None)
        if require_auth is None:
            def require_auth():  # type: ignore[no-redef]
                return None

    from fastapi import Depends

    @app.get("/workbench", dependencies=[Depends(require_auth)])
    async def workbench_page():
        """Serve the strategy management workbench SPA."""
        return HTMLResponse(content=_WORKBENCH_HTML)


# --------------------------------------------------------------------------- #
# SPA HTML (self-contained, no external dependencies)
# --------------------------------------------------------------------------- #
_WORKBENCH_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>策略管理工作台 — Vibe Trading</title>
<style>
:root {
  --bg: #0f1117; --surface: #1a1d27; --surface2: #222632;
  --border: #2d3142; --text: #e1e4ed; --text2: #8b90a0;
  --accent: #5b8def; --accent2: #4c6ef5; --green: #37b24d;
  --red: #e03131; --orange: #f59f00; --radius: 8px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); }
a { color:var(--accent); text-decoration:none; }

/* Layout */
.app { display:flex; height:100vh; }
.sidebar { width:240px; background:var(--surface); border-right:1px solid var(--border); display:flex; flex-direction:column; }
.main { flex:1; display:flex; flex-direction:column; overflow:hidden; }

/* Sidebar */
.logo { padding:20px; font-size:18px; font-weight:700; border-bottom:1px solid var(--border); }
.nav { padding:8px; flex:1; }
.nav-item { display:flex; align-items:center; gap:10px; padding:10px 14px; border-radius:var(--radius); cursor:pointer; color:var(--text2); transition:all .15s; margin-bottom:2px; }
.nav-item:hover { background:var(--surface2); color:var(--text); }
.nav-item.active { background:var(--accent2); color:#fff; }
.nav-icon { width:20px; text-align:center; }
.nav-badge { margin-left:auto; background:var(--border); padding:1px 8px; border-radius:10px; font-size:11px; }

/* Top bar */
.topbar { padding:12px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:16px; }
.topbar h1 { font-size:16px; font-weight:600; }
.search-box { flex:1; max-width:400px; padding:8px 14px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); color:var(--text); }
.search-box:focus { outline:none; border-color:var(--accent); }
.btn { padding:8px 16px; border:none; border-radius:var(--radius); cursor:pointer; font-size:13px; transition:all .15s; }
.btn-primary { background:var(--accent2); color:#fff; }
.btn-primary:hover { background:var(--accent); }
.btn-ghost { background:transparent; color:var(--text2); border:1px solid var(--border); }
.btn-ghost:hover { background:var(--surface2); color:var(--text); }
.btn-sm { padding:4px 10px; font-size:12px; }

/* Content area */
.content { flex:1; overflow-y:auto; padding:20px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); margin-bottom:16px; }
.card-header { padding:14px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px; }
.card-body { padding:18px; }

/* Table */
table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:10px 14px; font-size:12px; color:var(--text2); border-bottom:1px solid var(--border); text-transform:uppercase; }
td { padding:12px 14px; border-bottom:1px solid var(--border); font-size:13px; }
tr:hover { background:var(--surface2); }
.tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; background:var(--surface2); color:var(--text2); margin-right:4px; }
.status-draft { color:var(--text2); }
.status-published { color:var(--green); }
.status-archived { color:var(--red); }
.status-testing { color:var(--orange); }

/* Modal */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:center; justify-content:center; z-index:1000; }
.modal { background:var(--surface); border:1px solid var(--border); border-radius:12px; width:90%; max-width:800px; max-height:85vh; display:flex; flex-direction:column; }
.modal-header { padding:16px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; }
.modal-title { font-size:16px; font-weight:600; flex:1; }
.modal-body { flex:1; overflow-y:auto; padding:20px; }
.modal-footer { padding:14px 20px; border-top:1px solid var(--border); display:flex; gap:10px; justify-content:flex-end; }

/* Form */
.form-group { margin-bottom:16px; }
.form-label { display:block; font-size:12px; color:var(--text2); margin-bottom:6px; }
.form-input, .form-textarea, .form-select { width:100%; padding:8px 12px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); color:var(--text); font-size:13px; }
.form-input:focus, .form-textarea:focus { outline:none; border-color:var(--accent); }
.form-textarea { font-family:'Fira Code',monospace; resize:vertical; min-height:300px; }
.form-row { display:flex; gap:12px; }
.form-row > * { flex:1; }

/* Validation */
.validation-result { padding:10px 14px; border-radius:var(--radius); margin-top:8px; font-size:12px; }
.validation-ok { background:rgba(55,178,77,.1); border:1px solid var(--green); color:var(--green); }
.validation-err { background:rgba(224,49,49,.1); border:1px solid var(--red); color:var(--red); }
.validation-warn { background:rgba(245,159,0,.1); border:1px solid var(--orange); color:var(--orange); }
.validation-errors { margin-top:6px; }
.validation-errors li { margin-left:16px; }

/* Empty state */
.empty { text-align:center; padding:60px 20px; color:var(--text2); }
.empty-icon { font-size:48px; margin-bottom:12px; }

/* Rating */
.stars { color:var(--orange); cursor:pointer; font-size:16px; }
.stars span { opacity:.3; }
.stars span.active { opacity:1; }

/* Hidden */
.hidden { display:none !important; }

/* Pagination */
.pagination { display:flex; align-items:center; gap:8px; justify-content:center; padding:12px; }
.pagination button { padding:4px 10px; background:var(--surface); border:1px solid var(--border); border-radius:4px; color:var(--text); cursor:pointer; }
.pagination button:disabled { opacity:.4; cursor:default; }
</style>
</head>
<body>
<div class="app">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="logo">Vibe Trading</div>
    <div class="nav">
      <div class="nav-item active" data-view="strategies"><span class="nav-icon">S</span>策略管理</div>
      <div class="nav-item" data-view="factors"><span class="nav-icon">F</span>因子管理</div>
      <div class="nav-item" data-view="portfolios"><span class="nav-icon">P</span>因子组合</div>
      <div class="nav-item" data-view="marketplace"><span class="nav-icon">M</span>策略市场</div>
      <div class="nav-item" data-view="templates"><span class="nav-icon">T</span>模板库</div>
    </div>
    <div style="padding:12px; border-top:1px solid var(--border); font-size:11px; color:var(--text2);">
      Sprint 2 · Web Workbench
    </div>
  </div>

  <!-- Main -->
  <div class="main">
    <div class="topbar">
      <h1 id="page-title">策略管理</h1>
      <input class="search-box" id="search-input" placeholder="搜索策略名称或描述..." oninput="onSearch()">
      <button class="btn btn-primary" onclick="openCreateModal()">+ 新建策略</button>
      <button class="btn btn-ghost" onclick="loadData()">刷新</button>
    </div>
    <div class="content" id="content">
      <!-- Dynamic content injected here -->
    </div>
  </div>
</div>

<!-- Modal container -->
<div id="modal-container"></div>

<script>
// ------------------------------------------------------------------
// State
// ------------------------------------------------------------------
let currentView = 'strategies';
let allItems = [];
let searchQuery = '';
let editingId = null;

// ------------------------------------------------------------------
// Navigation
// ------------------------------------------------------------------
document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    currentView = el.dataset.view;
    const titles = {
      strategies: '策略管理', factors: '因子管理',
      portfolios: '因子组合', marketplace: '策略市场', templates: '模板库'
    };
    document.getElementById('page-title').textContent = titles[currentView];
    document.getElementById('search-input').placeholder = `搜索${titles[currentView]}...`;
    const btn = document.querySelector('.btn-primary');
    btn.textContent = currentView === 'strategies' ? '+ 新建策略' : currentView === 'factors' ? '+ 新建因子' : currentView === 'portfolios' ? '+ 新建组合' : '';
    btn.style.display = (currentView === 'strategies' || currentView === 'factors' || currentView === 'portfolios') ? '' : 'none';
    loadData();
  });
});

// ------------------------------------------------------------------
// API helpers
// ------------------------------------------------------------------
async function api(method, path, body) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({detail: res.statusText}));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

// ------------------------------------------------------------------
// Data loading
// ------------------------------------------------------------------
async function loadData() {
  const content = document.getElementById('content');
  content.innerHTML = '<div class="empty"><div class="empty-icon">⟳</div>加载中...</div>';
  try {
    if (currentView === 'strategies') await loadStrategies();
    else if (currentView === 'factors') await loadFactors();
    else if (currentView === 'portfolios') await loadPortfolios();
    else if (currentView === 'marketplace') await loadMarketplace();
    else if (currentView === 'templates') await loadTemplates();
  } catch(e) {
    content.innerHTML = `<div class="empty"><div class="empty-icon">⚠</div>加载失败: ${e.message}</div>`;
  }
}

async function loadStrategies() {
  const params = new URLSearchParams();
  if (searchQuery) params.set('search', searchQuery);
  params.set('limit', '200');
  const data = await api('GET', `/strategies?${params}`);
  allItems = data.strategies || [];
  renderStrategyTable(allItems);
}

function renderStrategyTable(items) {
  const content = document.getElementById('content');
  if (!items.length) {
    content.innerHTML = '<div class="empty"><div class="empty-icon">📋</div>暂无策略，点击"新建策略"创建第一个</div>';
    return;
  }
  let html = `<div class="card"><table><thead><tr>
    <th>名称</th><th>分类</th><th>状态</th><th>版本</th><th>标签</th><th>更新时间</th><th>操作</th>
  </tr></thead><tbody>`;
  for (const s of items) {
    const tags = (s.tags||[]).map(t => `<span class="tag">${t}</span>`).join('');
    html += `<tr>
      <td><strong>${esc(s.name)}</strong>${s.name_en ? `<br><small style="color:var(--text2)">${esc(s.name_en)}</small>`:''}</td>
      <td>${esc(s.category||'custom')}</td>
      <td class="status-${s.status}">${s.status}</td>
      <td>v${s.version}</td>
      <td>${tags}</td>
      <td>${fmtDate(s.updated_at)}</td>
      <td>
        <button class="btn btn-ghost btn-sm" onclick="openEditModal('${s.id}')">编辑</button>
        <button class="btn btn-ghost btn-sm" onclick="viewVersions('${s.id}')">版本</button>
        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${s.id}','strategies')">删除</button>
      </td>
    </tr>`;
  }
  html += '</tbody></table></div>';
  content.innerHTML = html;
}

// ------------------------------------------------------------------
// Factors
// ------------------------------------------------------------------
async function loadFactors() {
  const params = new URLSearchParams();
  if (searchQuery) params.set('search', searchQuery);
  params.set('limit', '200');
  const data = await api('GET', `/factors?${params}`);
  allItems = data.factors || [];
  const content = document.getElementById('content');
  if (!allItems.length) {
    content.innerHTML = '<div class="empty"><div class="empty-icon">📊</div>暂无因子</div>';
    return;
  }
  let html = `<div class="card"><table><thead><tr>
    <th>名称</th><th>分类</th><th>状态</th><th>版本</th><th>操作</th>
  </tr></thead><tbody>`;
  for (const f of allItems) {
    html += `<tr>
      <td><strong>${esc(f.name)}</strong></td>
      <td>${esc(f.category||'custom')}</td>
      <td class="status-${f.status}">${f.status}</td>
      <td>v${f.version}</td>
      <td>
        <button class="btn btn-ghost btn-sm" onclick="openEditFactorModal('${f.id}')">编辑</button>
        <button class="btn btn-ghost btn-sm" onclick="deleteItem('${f.id}','factors')">删除</button>
      </td>
    </tr>`;
  }
  html += '</tbody></table></div>';
  content.innerHTML = html;
}

// ------------------------------------------------------------------
// Portfolios
// ------------------------------------------------------------------
async function loadPortfolios() {
  const data = await api('GET', '/factors/portfolios?limit=200');
  allItems = data.portfolios || [];
  const content = document.getElementById('content');
  if (!allItems.length) {
    content.innerHTML = '<div class="empty"><div class="empty-icon">📦</div>暂无因子组合</div>';
    return;
  }
  let html = `<div class="card"><table><thead><tr>
    <th>名称</th><th>描述</th><th>状态</th><th>创建时间</th><th>操作</th>
  </tr></thead><tbody>`;
  for (const p of allItems) {
    html += `<tr>
      <td><strong>${esc(p.name)}</strong></td>
      <td>${esc(p.description||'')}</td>
      <td class="status-${p.status}">${p.status}</td>
      <td>${fmtDate(p.created_at)}</td>
      <td><button class="btn btn-ghost btn-sm" onclick="deleteItem('${p.id}','factors/portfolios')">删除</button></td>
    </tr>`;
  }
  html += '</tbody></table></div>';
  content.innerHTML = html;
}

// ------------------------------------------------------------------
// Marketplace
// ------------------------------------------------------------------
async function loadMarketplace() {
  const data = await api('GET', '/strategies?is_public=true&limit=200');
  allItems = data.strategies || [];
  const content = document.getElementById('content');
  if (!allItems.length) {
    content.innerHTML = '<div class="empty"><div class="empty-icon">🏪</div>暂无已发布策略</div>';
    return;
  }
  let html = '<div class="card"><div class="card-header">策略市场</div><div class="card-body">';
  for (const s of allItems) {
    const stars = renderStars(s.rating_avg, s.rating_count);
    html += `<div style="border:1px solid var(--border); border-radius:var(--radius); padding:14px; margin-bottom:12px;">
      <div style="display:flex; align-items:center; gap:8px;">
        <strong style="font-size:15px;">${esc(s.name)}</strong>
        <span class="tag">${esc(s.category||'')}</span>
        <span style="margin-left:auto; font-size:12px; color:var(--text2);">
          👥 ${s.subscriber_count} · 🔄 ${s.clone_count}
        </span>
      </div>
      <p style="color:var(--text2); margin:6px 0; font-size:13px;">${esc(s.description||'无描述')}</p>
      <div style="display:flex; align-items:center; gap:10px; margin-top:8px;">
        ${stars}
        <button class="btn btn-primary btn-sm" onclick="cloneStrategy('${s.id}')">克隆</button>
        <button class="btn btn-ghost btn-sm" onclick="subscribeStrategy('${s.id}')">订阅</button>
      </div>
    </div>`;
  }
  html += '</div></div>';
  content.innerHTML = html;
}

function renderStars(avg, count) {
  let html = '<span class="stars">';
  for (let i = 1; i <= 5; i++) {
    html += `<span class="${i <= Math.round(avg) ? 'active' : ''}">★</span>`;
  }
  html += `</span><span style="font-size:12px;color:var(--text2)">${avg.toFixed(1)} (${count})</span>`;
  return html;
}

// ------------------------------------------------------------------
// Templates
// ------------------------------------------------------------------
async function loadTemplates() {
  const data = await api('GET', '/strategies/templates');
  allItems = data.strategies || [];
  const content = document.getElementById('content');
  if (!allItems.length) {
    content.innerHTML = '<div class="empty"><div class="empty-icon">📐</div>暂无模板</div>';
    return;
  }
  let html = `<div class="card"><table><thead><tr>
    <th>ID</th><th>名称</th><th>来源</th><th>分类</th><th>市场</th><th>参数</th>
  </tr></thead><tbody>`;
  for (const t of allItems) {
    const params = (t.parameters || []).map(p => p.key).join(', ');
    html += `<tr>
      <td><code>${esc(t.id||'')}</code></td>
      <td>${esc(t.name||'')}</td>
      <td><span class="tag">${esc(t.source||'')}</span></td>
      <td>${esc(t.category||'')}</td>
      <td>${(t.markets||[]).join(', ')}</td>
      <td style="font-size:12px;color:var(--text2)">${params}</td>
    </tr>`;
  }
  html += '</tbody></table></div>';
  content.innerHTML = html;
}

// ------------------------------------------------------------------
// Create / Edit modal
// ------------------------------------------------------------------
function openCreateModal() {
  editingId = null;
  if (currentView === 'strategies') {
    showStrategyModal(null);
  } else if (currentView === 'factors') {
    showFactorModal(null);
  } else if (currentView === 'portfolios') {
    showPortfolioModal(null);
  }
}

async function openEditModal(id) {
  const data = await api('GET', `/strategies/${id}?include_code=true`);
  showStrategyModal(data.strategy);
}

async function openEditFactorModal(id) {
  const data = await api('GET', `/factors/${id}?include_code=true`);
  showFactorModal(data.factor);
}

function showStrategyModal(s) {
  const isEdit = !!s;
  const modal = `
  <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${isEdit ? '编辑策略' : '新建策略'}</span>
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body">
        <div class="form-row">
          <div class="form-group"><label class="form-label">名称 *</label>
            <input class="form-input" id="f-name" value="${esc(s?.name||'')}" placeholder="如：动量突破策略">
          </div>
          <div class="form-group"><label class="form-label">英文名 (ID)</label>
            <input class="form-input" id="f-name-en" value="${esc(s?.name_en||'')}" placeholder="如：momentum_breakout">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group"><label class="form-label">分类</label>
            <select class="form-select" id="f-category">
              ${['custom','trend','mean_reversion','momentum','breakout','composite'].map(c =>
                `<option value="${c}" ${s?.category===c?'selected':''}>${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group"><label class="form-label">状态</label>
            <select class="form-select" id="f-status">
              ${['draft','testing','published','archived'].map(c =>
                `<option value="${c}" ${s?.status===c?'selected':''}>${c}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="form-group"><label class="form-label">描述</label>
          <input class="form-input" id="f-desc" value="${esc(s?.description||'')}" placeholder="策略简介">
        </div>
        <div class="form-group"><label class="form-label">标签 (逗号分隔)</label>
          <input class="form-input" id="f-tags" value="${(s?.tags||[]).join(', ')}" placeholder="如: 短线, A股">
        </div>
        <div class="form-group"><label class="form-label">源代码 (signal_engine.py)</label>
          <textarea class="form-textarea" id="f-code" placeholder='class SignalEngine:\n    def generate(self, data_map):\n        ...'>${esc(s?.source_code||'')​​​​}</textarea>
        </div>
        <div id="validation-preview"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="closeModal()">取消</button>
        <button class="btn btn-ghost" onclick="previewValidation()">验证代码</button>
        <button class="btn btn-primary" onclick="saveStrategy(${isEdit ? `'${s.id}'` : 'null'})">保存</button>
      </div>
    </div>
  </div>`;
  document.getElementById('modal-container').innerHTML = modal;
}

function showFactorModal(f) {
  const isEdit = !!f;
  const modal = `
  <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${isEdit ? '编辑因子' : '新建因子'}</span>
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body">
        <div class="form-row">
          <div class="form-group"><label class="form-label">名称 *</label>
            <input class="form-input" id="f-name" value="${esc(f?.name||'')}" placeholder="如：动量因子">
          </div>
          <div class="form-group"><label class="form-label">英文名</label>
            <input class="form-input" id="f-name-en" value="${esc(f?.name_en||'')}" placeholder="如：momentum">
          </div>
        </div>
        <div class="form-group"><label class="form-label">描述</label>
          <input class="form-input" id="f-desc" value="${esc(f?.description||'')}">
        </div>
        <div class="form-group"><label class="form-label">源代码</label>
          <textarea class="form-textarea" id="f-code" placeholder='class Factor:\n    def compute(self, panel):\n        ...'>${esc(f?.source_code||'')​​​​}</textarea>
        </div>
        <div id="validation-preview"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="saveFactor(${isEdit ? `'${f.id}'` : 'null'})">保存</button>
      </div>
    </div>
  </div>`;
  document.getElementById('modal-container').innerHTML = modal;
}

function showPortfolioModal(p) {
  const modal = `
  <div class="modal-overlay" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">新建因子组合</span>
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body">
        <div class="form-group"><label class="form-label">名称 *</label>
          <input class="form-input" id="f-name" placeholder="如：三因子动量组合">
        </div>
        <div class="form-group"><label class="form-label">描述</label>
          <input class="form-input" id="f-desc">
        </div>
        <div class="form-group"><label class="form-label">配置 (JSON)</label>
          <textarea class="form-textarea" id="f-config" style="min-height:150px;" placeholder='{"factors": ["f1","f2"], "weights": [0.5, 0.5]}'>{"factors": [], "weights": []}</textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="closeModal()">取消</button>
        <button class="btn btn-primary" onclick="savePortfolio()">保存</button>
      </div>
    </div>
  </div>`;
  document.getElementById('modal-container').innerHTML = modal;
}

function closeModal() {
  document.getElementById('modal-container').innerHTML = '';
}

async function previewValidation() {
  const code = document.getElementById('f-code').value;
  if (!code.trim()) return;
  // Temporarily create to validate (will be discarded)
  try {
    const body = { name: 'validation_preview', source_code: code, status: 'draft' };
    const data = await api('POST', '/strategies', body);
    // If created successfully, delete it immediately
    if (data.strategy?.id) {
      await api('DELETE', `/strategies/${data.strategy.id}`);
    }
    const v = data.validation;
    showValidationResult(v, true);
  } catch(e) {
    try {
      const err = JSON.parse(e.message);
      showValidationResult({valid: false, errors: err.errors || [e.message]}, false);
    } catch {
      showValidationResult({valid: false, errors: [e.message]}, false);
    }
  }
}

function showValidationResult(v, created) {
  const el = document.getElementById('validation-preview');
  if (v.valid) {
    let html = `<div class="validation-result validation-ok">✓ 代码验证通过</div>`;
    if (v.warnings?.length) {
      html += `<div class="validation-result validation-warn">⚠ ${v.warnings.join('; ')}</div>`;
    }
    if (v.metadata?.parameters?.length) {
      html += `<div class="validation-result validation-ok">参数: ${v.metadata.parameters.map(p => `${p.key}=${p.default}(${p.type})`).join(', ')}</div>`;
    }
    el.innerHTML = html;
  } else {
    el.innerHTML = `<div class="validation-result validation-err">✗ 验证失败<ul class="validation-errors">${(v.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`;
  }
}

async function saveStrategy(id) {
  const name = document.getElementById('f-name').value.trim();
  const code = document.getElementById('f-code').value.trim();
  if (!name || !code) { alert('名称和源代码不能为空'); return; }
  const body = {
    name,
    source_code: code,
    name_en: document.getElementById('f-name-en').value.trim(),
    description: document.getElementById('f-desc').value.trim(),
    category: document.getElementById('f-category').value,
    status: document.getElementById('f-status').value,
    tags: document.getElementById('f-tags').value.split(',').map(t=>t.trim()).filter(Boolean),
  };
  try {
    if (id) {
      await api('PUT', `/strategies/${id}`, body);
    } else {
      await api('POST', '/strategies', body);
    }
    closeModal();
    loadData();
  } catch(e) { alert('保存失败: ' + e.message); }
}

async function saveFactor(id) {
  const name = document.getElementById('f-name').value.trim();
  const code = document.getElementById('f-code').value.trim();
  if (!name || !code) { alert('名称和源代码不能为空'); return; }
  const body = {
    name,
    source_code: code,
    name_en: document.getElementById('f-name-en').value.trim(),
    description: document.getElementById('f-desc').value.trim(),
  };
  try {
    if (id) {
      await api('PUT', `/factors/${id}`, body);
    } else {
      await api('POST', '/factors', body);
    }
    closeModal();
    loadData();
  } catch(e) { alert('保存失败: ' + e.message); }
}

async function savePortfolio() {
  const name = document.getElementById('f-name').value.trim();
  const configStr = document.getElementById('f-config').value.trim();
  if (!name) { alert('名称不能为空'); return; }
  let config;
  try { config = JSON.parse(configStr); } catch { alert('配置 JSON 格式错误'); return; }
  try {
    await api('POST', '/factors/portfolios', { name, config, description: document.getElementById('f-desc').value.trim() });
    closeModal();
    loadData();
  } catch(e) { alert('保存失败: ' + e.message); }
}

// ------------------------------------------------------------------
// Actions
// ------------------------------------------------------------------
async function deleteItem(id, type) {
  if (!confirm('确认删除？此操作不可撤销。')) return;
  try {
    await api('DELETE', `/${type}/${id}`);
    loadData();
  } catch(e) { alert('删除失败: ' + e.message); }
}

async function viewVersions(id) {
  try {
    const data = await api('GET', `/strategies/${id}/versions`);
    const versions = data.versions || [];
    let html = `<div class="modal-overlay" onclick="if(event.target===this)closeModal()">
      <div class="modal">
        <div class="modal-header"><span class="modal-title">版本历史 (${versions.length})</span>
          <button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div>
        <div class="modal-body">`;
    if (!versions.length) {
      html += '<div class="empty">暂无版本记录</div>';
    } else {
      html += '<table><thead><tr><th>版本</th><th>变更说明</th><th>时间</th><th>操作</th></tr></thead><tbody>';
      for (const v of versions) {
        html += `<tr>
          <td>v${v.version}</td>
          <td>${esc(v.changelog||'')}</td>
          <td>${fmtDate(v.created_at)}</td>
          <td><button class="btn btn-ghost btn-sm" onclick="rollbackVersion('${id}',${v.version})">回滚到此版本</button></td>
        </tr>`;
      }
      html += '</tbody></table>';
    }
    html += `</div><div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">关闭</button></div></div></div>`;
    document.getElementById('modal-container').innerHTML = html;
  } catch(e) { alert('加载版本失败: ' + e.message); }
}

async function rollbackVersion(id, ver) {
  if (!confirm(`确认回滚到 v${ver}？将创建新版本。`)) return;
  try {
    await api('POST', `/strategies/${id}/rollback/${ver}`);
    closeModal();
    loadData();
  } catch(e) { alert('回滚失败: ' + e.message); }
}

async function cloneStrategy(id) {
  try {
    await api('POST', `/strategies/${id}/clone`, { user_id: 'web_user' });
    alert('克隆成功！已添加到你的策略列表。');
  } catch(e) { alert('克隆失败: ' + e.message); }
}

async function subscribeStrategy(id) {
  try {
    await api('POST', `/strategies/${id}/subscribe`, { user_id: 'web_user' });
    alert('订阅成功！');
  } catch(e) { alert('订阅失败: ' + e.message); }
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function onSearch() {
  searchQuery = document.getElementById('search-input').value.trim();
  loadData();
}

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(s) {
  if (!s) return '';
  try {
    const d = new Date(s);
    return d.toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
  } catch { return s; }
}

// Initial load
loadData();
</script>
</body>
</html>
"""
