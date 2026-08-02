"""Web Workbench for Strategy & Factor Management.

Serves a single-page HTML app at /workbench that provides:
- Strategy list with search, filter
- Create / edit strategy with code editor and AST validation
- Version history with rollback
- Marketplace browser (published strategies, clone, rate, subscribe)
- Factor management
- Factor portfolio configuration
- NL natural-language strategy generation

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
# SPA HTML — self-contained, no external dependencies
# --------------------------------------------------------------------------- #
_WORKBENCH_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>策略管理工作台 — Vibe Trading</title>
<style>
:root {
  --bg: #0b0e14; --surface: #141821; --surface2: #1c2130; --surface3: #252b3d;
  --border: #2a3045; --text: #e2e8f0; --text2: #8892b0; --text3: #5a6580;
  --accent: #6366f1; --accent2: #818cf8; --accent-dim: rgba(99,102,241,.15);
  --green: #22c55e; --green-dim: rgba(34,197,94,.12);
  --red: #ef4444; --red-dim: rgba(239,68,68,.12);
  --orange: #f59e0b; --orange-dim: rgba(245,158,11,.12);
  --radius: 10px; --radius-sm: 6px;
  --shadow: 0 4px 24px rgba(0,0,0,.3);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system,'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); overflow:hidden; }
::-webkit-scrollbar { width:6px; } ::-webkit-scrollbar-track { background:transparent; } ::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }

/* Layout */
.app { display:flex; height:100vh; }
.sidebar { width:220px; background:var(--surface); border-right:1px solid var(--border); display:flex; flex-direction:column; flex-shrink:0; }
.main { flex:1; display:flex; flex-direction:column; overflow:hidden; }

/* Sidebar */
.logo { padding:18px 20px; font-size:16px; font-weight:700; border-bottom:1px solid var(--border); color:var(--accent2); letter-spacing:.5px; }
.nav { padding:8px; flex:1; overflow-y:auto; }
.nav-section { font-size:10px; text-transform:uppercase; color:var(--text3); padding:12px 10px 4px; letter-spacing:1px; }
.nav-item { display:flex; align-items:center; gap:10px; padding:9px 12px; border-radius:var(--radius-sm); cursor:pointer; color:var(--text2); transition:all .15s; margin-bottom:1px; font-size:13px; text-decoration:none; }
.nav-item:hover { background:var(--surface2); color:var(--text); }
.nav-item.active { background:var(--accent-dim); color:var(--accent2); font-weight:500; }
.nav-icon { width:18px; text-align:center; font-size:14px; }
.sidebar-footer { padding:10px 16px; border-top:1px solid var(--border); font-size:10px; color:var(--text3); }

/* Top bar */
.topbar { padding:10px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; background:var(--surface); }
.topbar h1 { font-size:15px; font-weight:600; white-space:nowrap; }
.search-box { flex:1; max-width:360px; padding:7px 14px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius-sm); color:var(--text); font-size:13px; }
.search-box:focus { outline:none; border-color:var(--accent); }
.btn { padding:7px 14px; border:none; border-radius:var(--radius-sm); cursor:pointer; font-size:12px; transition:all .15s; white-space:nowrap; }
.btn-primary { background:var(--accent); color:#fff; }
.btn-primary:hover { background:var(--accent2); }
.btn-ghost { background:transparent; color:var(--text2); border:1px solid var(--border); }
.btn-ghost:hover { background:var(--surface2); color:var(--text); }
.btn-green { background:var(--green); color:#fff; }
.btn-red { background:var(--red); color:#fff; }
.btn-sm { padding:4px 10px; font-size:11px; }

/* Content */
.content { flex:1; overflow-y:auto; padding:16px 20px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); margin-bottom:14px; }
.card-header { padding:12px 16px; border-bottom:1px solid var(--border); font-size:13px; font-weight:600; color:var(--text2); }
.card-body { padding:16px; }

/* Table */
table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:9px 14px; font-size:11px; color:var(--text3); border-bottom:1px solid var(--border); text-transform:uppercase; letter-spacing:.5px; }
td { padding:10px 14px; border-bottom:1px solid var(--surface2); font-size:13px; }
tr:hover { background:var(--surface2); }
.tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; background:var(--surface3); color:var(--text2); margin-right:3px; }
.status-draft { color:var(--text2); } .status-published { color:var(--green); }
.status-archived { color:var(--red); } .status-testing { color:var(--orange); }
.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:500; }
.badge-green { background:var(--green-dim); color:var(--green); }
.badge-blue { background:var(--accent-dim); color:var(--accent2); }
.badge-orange { background:var(--orange-dim); color:var(--orange); }
.badge-gray { background:var(--surface3); color:var(--text2); }

/* Modal */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.65); display:flex; align-items:center; justify-content:center; z-index:1000; backdrop-filter:blur(2px); }
.modal { background:var(--surface); border:1px solid var(--border); border-radius:14px; width:92%; max-width:820px; max-height:88vh; display:flex; flex-direction:column; box-shadow:var(--shadow); }
.modal-header { padding:14px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; }
.modal-title { font-size:15px; font-weight:600; flex:1; }
.modal-body { flex:1; overflow-y:auto; padding:20px; }
.modal-footer { padding:12px 20px; border-top:1px solid var(--border); display:flex; gap:8px; justify-content:flex-end; }

/* Form */
.form-group { margin-bottom:14px; }
.form-label { display:block; font-size:11px; color:var(--text2); margin-bottom:5px; font-weight:500; }
.form-input, .form-textarea, .form-select { width:100%; padding:8px 12px; background:var(--bg); border:1px solid var(--border); border-radius:var(--radius-sm); color:var(--text); font-size:13px; }
.form-input:focus, .form-textarea:focus, .form-select:focus { outline:none; border-color:var(--accent); }
.form-textarea { font-family:'JetBrains Mono','Fira Code','Consolas',monospace; resize:vertical; min-height:280px; line-height:1.5; }
.form-row { display:flex; gap:12px; } .form-row > * { flex:1; }

/* Code editor */
.code-editor { background:#0a0d12; border:1px solid var(--border); border-radius:var(--radius-sm); font-family:'JetBrains Mono','Fira Code','Consolas',monospace; font-size:12px; line-height:1.6; color:#a5b3cc; }
.code-editor textarea { width:100%; min-height:300px; background:transparent; border:none; color:inherit; font:inherit; padding:12px; resize:vertical; outline:none; }

/* Validation */
.val-result { padding:8px 12px; border-radius:var(--radius-sm); margin-top:6px; font-size:11px; }
.val-ok { background:var(--green-dim); border:1px solid var(--green); color:var(--green); }
.val-err { background:var(--red-dim); border:1px solid var(--red); color:var(--red); }
.val-warn { background:var(--orange-dim); border:1px solid var(--orange); color:var(--orange); }

/* Empty state */
.empty { text-align:center; padding:50px 20px; color:var(--text3); }
.empty-icon { font-size:42px; margin-bottom:10px; }

/* Rating */
.stars { color:var(--orange); font-size:15px; letter-spacing:2px; }
.stars span { opacity:.25; } .stars span.active { opacity:1; }

/* Toast */
.toast-container { position:fixed; top:16px; right:16px; z-index:2000; display:flex; flex-direction:column; gap:8px; }
.toast { padding:10px 18px; border-radius:var(--radius-sm); font-size:13px; box-shadow:var(--shadow); animation:slideIn .2s ease; max-width:380px; }
.toast-success { background:var(--green); color:#fff; }
.toast-error { background:var(--red); color:#fff; }
.toast-info { background:var(--accent); color:#fff; }
@keyframes slideIn { from{transform:translateX(100%);opacity:0;} to{transform:translateX(0);opacity:1;} }

/* Loading spinner */
.spinner { display:inline-block; width:14px; height:14px; border:2px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin .6s linear infinite; }
@keyframes spin { to{transform:rotate(360deg);} }

/* Marketplace card */
.mp-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px; margin-bottom:10px; transition:border-color .15s; }
.mp-card:hover { border-color:var(--accent); }
.mp-card-title { font-size:14px; font-weight:600; margin-bottom:4px; }
.mp-card-desc { color:var(--text2); font-size:12px; margin-bottom:8px; line-height:1.5; }
.mp-card-stats { display:flex; gap:12px; font-size:11px; color:var(--text3); }

/* NL generate box */
.nl-box { background:var(--surface2); border:1px dashed var(--border); border-radius:var(--radius); padding:16px; margin-bottom:14px; }
.nl-box textarea { background:var(--bg); border:1px solid var(--border); border-radius:var(--radius-sm); color:var(--text); font-size:13px; padding:10px; width:100%; min-height:60px; resize:vertical; outline:none; }
.nl-box textarea:focus { border-color:var(--accent); }
</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <div class="logo">⚡ Vibe Trading</div>
    <div class="nav">
      <div class="nav-section">工作区</div>
      <a class="nav-item active" data-view="strategies" href="javascript:void(0)" onclick="switchView(this,'strategies')"><span class="nav-icon">📊</span>策略管理</a>
      <a class="nav-item" data-view="factors" href="javascript:void(0)" onclick="switchView(this,'factors')"><span class="nav-icon">🔬</span>因子管理</a>
      <a class="nav-item" data-view="portfolios" href="javascript:void(0)" onclick="switchView(this,'portfolios')"><span class="nav-icon">📦</span>因子组合</a>
      <div class="nav-section">发现</div>
      <a class="nav-item" data-view="marketplace" href="javascript:void(0)" onclick="switchView(this,'marketplace')"><span class="nav-icon">🏪</span>策略市场</a>
      <a class="nav-item" data-view="templates" href="javascript:void(0)" onclick="switchView(this,'templates')"><span class="nav-icon">📐</span>模板库</a>
      <div class="nav-section">工具</div>
      <a class="nav-item" data-view="nl_generate" href="javascript:void(0)" onclick="switchView(this,'nl_generate')"><span class="nav-icon">🤖</span>AI 生成策略</a>
    </div>
    <div class="sidebar-footer">v2.0 · 策略管理工作台</div>
  </div>

  <div class="main">
    <div class="topbar">
      <h1 id="page-title">策略管理</h1>
      <input class="search-box" id="search-input" placeholder="搜索..." oninput="onSearch()">
      <button class="btn btn-primary" id="create-btn" onclick="openCreateModal()">+ 新建策略</button>
      <button class="btn btn-ghost" onclick="loadData()">↻ 刷新</button>
    </div>
    <div class="content" id="content"></div>
  </div>
</div>

<div id="modal-container"></div>
<div class="toast-container" id="toast-container"></div>

<script>
// ===== State =====
var currentView = 'strategies';
var searchQuery = '';
var searchTimer = null;

// ===== Toast =====
function toast(msg, type) {
  type = type || 'info';
  var el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(function() { el.style.opacity = '0'; el.style.transform = 'translateX(100%)'; el.style.transition = 'all .3s'; }, 3000);
  setTimeout(function() { el.remove(); }, 3400);
}

// ===== Navigation =====
function switchView(el, view) {
  document.querySelectorAll('.nav-item').forEach(function(n) { n.classList.remove('active'); });
  el.classList.add('active');
  currentView = view;
  var titles = {
    strategies: '策略管理', factors: '因子管理', portfolios: '因子组合',
    marketplace: '策略市场', templates: '模板库', nl_generate: 'AI 生成策略'
  };
  document.getElementById('page-title').textContent = titles[currentView] || '';
  document.getElementById('search-input').placeholder = '搜索' + (titles[currentView] || '') + '...';
  var createBtn = document.getElementById('create-btn');
  var showCreate = (currentView === 'strategies' || currentView === 'factors' || currentView === 'portfolios');
  createBtn.style.display = showCreate ? '' : 'none';
  createBtn.textContent = currentView === 'strategies' ? '+ 新建策略' : (currentView === 'factors' ? '+ 新建因子' : '+ 新建组合');
  loadData();
}

// ===== Search =====
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(function() {
    searchQuery = document.getElementById('search-input').value.trim();
    loadData();
  }, 300);
}

// ===== API helper =====
function api(method, path, body) {
  var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  return fetch(path, opts).then(function(res) {
    if (!res.ok) {
      return res.json().catch(function() { return { detail: res.statusText }; }).then(function(err) {
        throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      });
    }
    return res.json();
  });
}

// ===== Data loading dispatcher =====
function loadData() {
  var content = document.getElementById('content');
  content.innerHTML = '<div class="empty"><div class="empty-icon"><span class="spinner"></span></div>加载中...</div>';
  var fn;
  if (currentView === 'strategies') fn = loadStrategies;
  else if (currentView === 'factors') fn = loadFactors;
  else if (currentView === 'portfolios') fn = loadPortfolios;
  else if (currentView === 'marketplace') fn = loadMarketplace;
  else if (currentView === 'templates') fn = loadTemplates;
  else if (currentView === 'nl_generate') fn = loadNLGenerate;
  else fn = function() { content.innerHTML = '<div class="empty">未知视图</div>'; return Promise.resolve(); };

  var result = fn();
  if (result && typeof result.catch === 'function') {
    result.catch(function(e) {
      content.innerHTML = '<div class="empty"><div class="empty-icon">[!]</div>加载失败: ' + esc(e.message) + '</div>';
    });
  }
}

// ===== Strategies =====
function loadStrategies() {
  var params = new URLSearchParams();
  if (searchQuery) params.set('search', searchQuery);
  params.set('limit', '200');
  return api('GET', '/strategies?' + params.toString()).then(function(data) {
    var items = data.strategies || [];
    var c = document.getElementById('content');
    if (!items.length) {
      c.innerHTML = '<div class="empty"><div class="empty-icon">📊</div>暂无策略<br><small>点击"新建策略"或用 AI 生成一个</small></div>';
      return;
    }
    var html = '<div class="card"><table><thead><tr><th>名称</th><th>分类</th><th>状态</th><th>版本</th><th>标签</th><th>更新时间</th><th>操作</th></tr></thead><tbody>';
    items.forEach(function(s) {
      var tags = (s.tags || []).map(function(t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('');
      var statusBadge = '<span class="badge badge-' + statusColor(s.status) + '">' + esc(s.status) + '</span>';
      html += '<tr>' +
        '<td><strong>' + esc(s.name) + '</strong>' + (s.name_en ? '<br><small style="color:var(--text3)">' + esc(s.name_en) + '</small>' : '') + '</td>' +
        '<td>' + esc(s.category || 'custom') + '</td>' +
        '<td>' + statusBadge + '</td>' +
        '<td>v' + s.version + '</td>' +
        '<td>' + tags + '</td>' +
        '<td>' + fmtDate(s.updated_at) + '</td>' +
        '<td>' +
          '<button class="btn btn-ghost btn-sm" onclick="openEditModal(\\''+ s.id + '\\')">编辑</button> ' +
          '<button class="btn btn-ghost btn-sm" onclick="viewVersions(\\''+ s.id + '\\')">版本</button> ' +
          '<button class="btn btn-ghost btn-sm" onclick="publishItem(\\'/strategies/'+ s.id + '/publish\\')">发布</button> ' +
          '<button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="deleteItem(\\''+ s.id + '\\', \\'strategies\\')">删除</button>' +
        '</td></tr>';
    });
    html += '</tbody></table></div>';
    c.innerHTML = html;
  });
}

// ===== Factors =====
function loadFactors() {
  var params = new URLSearchParams();
  if (searchQuery) params.set('search', searchQuery);
  params.set('limit', '200');
  return api('GET', '/factors?' + params.toString()).then(function(data) {
    var items = data.factors || [];
    var c = document.getElementById('content');
    if (!items.length) {
      c.innerHTML = '<div class="empty"><div class="empty-icon">🔬</div>暂无因子<br><small>点击"新建因子"创建</small></div>';
      return;
    }
    var html = '<div class="card"><table><thead><tr><th>名称</th><th>分类</th><th>状态</th><th>版本</th><th>标签</th><th>更新时间</th><th>操作</th></tr></thead><tbody>';
    items.forEach(function(f) {
      var tags = (f.tags || []).map(function(t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('');
      var statusBadge = '<span class="badge badge-' + statusColor(f.status) + '">' + esc(f.status) + '</span>';
      html += '<tr>' +
        '<td><strong>' + esc(f.name) + '</strong></td>' +
        '<td>' + esc(f.category || 'custom') + '</td>' +
        '<td>' + statusBadge + '</td>' +
        '<td>v' + f.version + '</td>' +
        '<td>' + tags + '</td>' +
        '<td>' + fmtDate(f.updated_at) + '</td>' +
        '<td>' +
          '<button class="btn btn-ghost btn-sm" onclick="openEditFactorModal(\\''+ f.id + '\\')">编辑</button> ' +
          '<button class="btn btn-ghost btn-sm" onclick="publishItem(\\'/factors/'+ f.id + '/publish\\')">发布</button> ' +
          '<button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="deleteItem(\\''+ f.id + '\\', \\'factors\\')">删除</button>' +
        '</td></tr>';
    });
    html += '</tbody></table></div>';
    c.innerHTML = html;
  });
}

// ===== Portfolios =====
function loadPortfolios() {
  return api('GET', '/factors/portfolios?limit=200').then(function(data) {
    var items = data.portfolios || [];
    var c = document.getElementById('content');
    if (!items.length) {
      c.innerHTML = '<div class="empty"><div class="empty-icon">📦</div>暂无因子组合</div>';
      return;
    }
    var html = '<div class="card"><table><thead><tr><th>名称</th><th>描述</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead><tbody>';
    items.forEach(function(p) {
      html += '<tr><td><strong>' + esc(p.name) + '</strong></td><td>' + esc(p.description || '') + '</td><td>' + esc(p.status || '') + '</td><td>' + fmtDate(p.created_at) + '</td>' +
        '<td><button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="deleteItem(\\''+ p.id + '\\', \\'factors/portfolios\\')">删除</button></td></tr>';
    });
    html += '</tbody></table></div>';
    c.innerHTML = html;
  });
}

// ===== Marketplace =====
function loadMarketplace() {
  var url = '/marketplace/strategies?limit=50&sort=popular';
  if (searchQuery) url += '&search=' + encodeURIComponent(searchQuery);
  return api('GET', url).then(function(data) {
    var items = data.strategies || [];
    var c = document.getElementById('content');

    // Stats bar
    return api('GET', '/marketplace/stats').then(function(stats) {
      var statsHtml = '<div class="card"><div class="card-body" style="display:flex;gap:20px;">';
      statsHtml += '<div>📈 已发布策略: <strong>' + (stats.strategies ? stats.strategies.published_count : 0) + '</strong></div>';
      statsHtml += '<div>👥 总订阅: <strong>' + (stats.strategies ? stats.strategies.total_subscribers : 0) + '</strong></div>';
      statsHtml += '<div>🔄 总克隆: <strong>' + (stats.strategies ? stats.strategies.total_clones : 0) + '</strong></div>';
      statsHtml += '<div>⭐ 平均评分: <strong>' + (stats.strategies ? stats.strategies.avg_rating : 0) + '</strong></div>';
      statsHtml += '</div></div>';

      if (!items.length) {
        c.innerHTML = statsHtml + '<div class="empty"><div class="empty-icon">🏪</div>暂无已发布策略</div>';
        return;
      }
      var html = statsHtml;
      items.forEach(function(s) {
        var stars = renderStars(s.rating_avg, s.rating_count);
        html += '<div class="mp-card">' +
          '<div class="mp-card-title">' + esc(s.name) + ' <span class="tag">' + esc(s.category || '') + '</span></div>' +
          '<div class="mp-card-desc">' + esc(s.description || '无描述') + '</div>' +
          '<div class="mp-card-stats">' +
            '<span>👥 订阅 ' + s.subscriber_count + '</span>' +
            '<span>🔄 克隆 ' + s.clone_count + '</span>' +
            '<span>' + stars + '</span>' +
          '</div>' +
          '<div style="margin-top:8px;">' +
            '<button class="btn btn-primary btn-sm" onclick="cloneStrategy(\\''+ s.id + '\\')">克隆</button> ' +
            '<button class="btn btn-ghost btn-sm" onclick="subscribeStrategy(\\''+ s.id + '\\')">订阅</button> ' +
            '<button class="btn btn-ghost btn-sm" onclick="rateStrategy(\\''+ s.id + '\\')">评分</button>' +
          '</div></div>';
      });
      c.innerHTML = html;
    });
  });
}

// ===== Templates =====
function loadTemplates() {
  return api('GET', '/strategies/templates').then(function(data) {
    var items = data.strategies || [];
    var c = document.getElementById('content');
    if (!items.length) {
      c.innerHTML = '<div class="empty"><div class="empty-icon">📐</div>暂无模板</div>';
      return;
    }
    var html = '<div class="card"><table><thead><tr><th>ID</th><th>名称</th><th>来源</th><th>分类</th><th>市场</th><th>参数</th></tr></thead><tbody>';
    items.forEach(function(t) {
      var params = (t.parameters || []).map(function(p) { return p.key; }).join(', ');
      html += '<tr><td><code>' + esc(t.id || '') + '</code></td><td>' + esc(t.name || '') + '</td><td><span class="tag">' + esc(t.source || '') + '</span></td><td>' + esc(t.category || '') + '</td><td>' + (t.markets || []).join(', ') + '</td><td style="font-size:11px;color:var(--text3)">' + esc(params) + '</td></tr>';
    });
    html += '</tbody></table></div>';
    c.innerHTML = html;
  });
}

// ===== NL Generate =====
function loadNLGenerate() {
  var c = document.getElementById('content');
  c.innerHTML =
    '<div class="card">' +
      '<div class="card-header">🤖 AI 自然语言生成策略</div>' +
      '<div class="card-body">' +
        '<div class="nl-box">' +
          '<div style="margin-bottom:8px;font-size:13px;color:var(--text2);">描述你想要的策略，AI 会自动生成 SignalEngine 代码：</div>' +
          '<textarea id="nl-desc" placeholder="例如：一个基于均线交叉的策略，当5日均线上穿20日均线时买入，下穿时卖出。参数可配置快线和慢线周期。"></textarea>' +
          '<div style="margin-top:10px;display:flex;gap:8px;">' +
            '<input class="form-input" id="nl-name" placeholder="策略名称（可选）" style="flex:1;">' +
            '<button class="btn btn-primary" onclick="generateNL()">⚡ 生成策略</button>' +
          '</div>' +
        '</div>' +
        '<div id="nl-result"></div>' +
      '</div>' +
    '</div>';
  return Promise.resolve();
}

function generateNL() {
  var desc = document.getElementById('nl-desc').value.trim();
  var name = document.getElementById('nl-name').value.trim() || 'AI Generated Strategy';
  if (!desc) { toast('请输入策略描述', 'error'); return; }

  var resultDiv = document.getElementById('nl-result');
  resultDiv.innerHTML = '<div class="empty"><span class="spinner"></span> AI 正在生成策略代码...</div>';

  api('POST', '/strategies/nl-generate', { description: desc, auto_create: true, name: name })
    .then(function(data) {
      var html = '<div class="card"><div class="card-header">✅ 生成成功</div><div class="card-body">';
      if (data.strategy_id) {
        html += '<div class="val-result val-ok">策略已保存！ID: ' + esc(data.strategy_id) + '</div>';
      }
      html += '<div class="form-group" style="margin-top:12px;"><label class="form-label">生成的代码：</label>';
      html += '<div class="code-editor"><textarea readonly style="min-height:200px;">' + esc(data.source_code || '') + '</textarea></div>';
      html += '</div></div></div>';
      resultDiv.innerHTML = html;
      toast('策略生成成功！', 'success');
    })
    .catch(function(e) {
      resultDiv.innerHTML = '<div class="val-result val-err">生成失败: ' + esc(e.message) + '</div>';
      toast('生成失败: ' + e.message, 'error');
    });
}

// ===== Create / Edit Modal =====
function openCreateModal() {
  if (currentView === 'strategies') showStrategyModal(null);
  else if (currentView === 'factors') showFactorModal(null);
  else if (currentView === 'portfolios') showPortfolioModal(null);
}

function openEditModal(id) {
  api('GET', '/strategies/' + id + '?include_code=true').then(function(data) {
    showStrategyModal(data.strategy);
  }).catch(function(e) { toast('加载失败: ' + e.message, 'error'); });
}

function openEditFactorModal(id) {
  api('GET', '/factors/' + id + '?include_code=true').then(function(data) {
    showFactorModal(data.factor);
  }).catch(function(e) { toast('加载失败: ' + e.message, 'error'); });
}

function showStrategyModal(s) {
  var isEdit = !!s;
  var modal = '<div class="modal-overlay" onclick="if(event.target===this)closeModal()">' +
    '<div class="modal"><div class="modal-header"><span class="modal-title">' + (isEdit ? '编辑策略' : '新建策略') + '</span><button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div>' +
    '<div class="modal-body">' +
      '<div class="form-row"><div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="m-name" value="' + escVal(s ? s.name : '') + '" placeholder="如：动量突破策略"></div>' +
      '<div class="form-group"><label class="form-label">英文名</label><input class="form-input" id="m-name-en" value="' + escVal(s ? s.name_en : '') + '" placeholder="如：momentum_breakout"></div></div>' +
      '<div class="form-row"><div class="form-group"><label class="form-label">分类</label><select class="form-select" id="m-category">' +
        ['custom','trend','mean_reversion','momentum','breakout','composite'].map(function(c) {
          return '<option value="' + c + '"' + (s && s.category === c ? ' selected' : '') + '>' + c + '</option>';
        }).join('') + '</select></div>' +
      '<div class="form-group"><label class="form-label">标签 (逗号分隔)</label><input class="form-input" id="m-tags" value="' + escVal(s && s.tags ? s.tags.join(', ') : '') + '" placeholder="如：动量, 趋势"></div></div>' +
      '<div class="form-group"><label class="form-label">描述</label><input class="form-input" id="m-desc" value="' + escVal(s ? s.description : '') + '" placeholder="策略描述"></div>' +
      '<div class="form-group"><label class="form-label">策略代码 (SignalEngine)</label>' +
        '<div class="code-editor"><textarea id="m-code" placeholder="class SignalEngine:\\n    def __init__(self):\\n        pass\\n    def generate(self, data_map):\\n        ...">' + escVal(s ? s.source_code : '') + '</textarea></div>' +
      '</div>' +
      '<div id="m-val"></div>' +
    '</div>' +
    '<div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button>' +
    '<button class="btn btn-ghost" onclick="previewValidation()">验证代码</button>' +
    '<button class="btn btn-primary" onclick="saveStrategy(' + (isEdit ? "'" + s.id + "'" : 'null') + ')">保存</button></div></div></div>';
  document.getElementById('modal-container').innerHTML = modal;
}

function showFactorModal(f) {
  var isEdit = !!f;
  var modal = '<div class="modal-overlay" onclick="if(event.target===this)closeModal()">' +
    '<div class="modal"><div class="modal-header"><span class="modal-title">' + (isEdit ? '编辑因子' : '新建因子') + '</span><button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div>' +
    '<div class="modal-body">' +
      '<div class="form-row"><div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="m-name" value="' + escVal(f ? f.name : '') + '"></div>' +
      '<div class="form-group"><label class="form-label">英文名</label><input class="form-input" id="m-name-en" value="' + escVal(f ? f.name_en : '') + '"></div></div>' +
      '<div class="form-row"><div class="form-group"><label class="form-label">分类</label><select class="form-select" id="m-category">' +
        ['custom','momentum','value','quality','volatility','volume'].map(function(c) {
          return '<option value="' + c + '"' + (f && f.category === c ? ' selected' : '') + '>' + c + '</option>';
        }).join('') + '</select></div>' +
      '<div class="form-group"><label class="form-label">标签</label><input class="form-input" id="m-tags" value="' + escVal(f && f.tags ? f.tags.join(', ') : '') + '"></div></div>' +
      '<div class="form-group"><label class="form-label">描述</label><input class="form-input" id="m-desc" value="' + escVal(f ? f.description : '') + '"></div>' +
      '<div class="form-group"><label class="form-label">因子代码 (Factor)</label>' +
        '<div class="code-editor"><textarea id="m-code" placeholder="class Factor:\\n    def compute(self, panel):\\n        ...">' + escVal(f ? f.source_code : '') + '</textarea></div>' +
      '</div>' +
      '<div id="m-val"></div>' +
    '</div>' +
    '<div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button>' +
    '<button class="btn btn-primary" onclick="saveFactor(' + (isEdit ? "'" + f.id + "'" : 'null') + ')">保存</button></div></div></div>';
  document.getElementById('modal-container').innerHTML = modal;
}

function showPortfolioModal() {
  var modal = '<div class="modal-overlay" onclick="if(event.target===this)closeModal()">' +
    '<div class="modal" style="max-width:560px;"><div class="modal-header"><span class="modal-title">新建因子组合</span><button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div>' +
    '<div class="modal-body">' +
      '<div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="m-name" placeholder="如：多因子动量组合"></div>' +
      '<div class="form-group"><label class="form-label">描述</label><input class="form-input" id="m-desc"></div>' +
      '<div class="form-group"><label class="form-label">配置 (JSON)</label><textarea class="form-textarea" id="m-config" style="min-height:120px;" placeholder=&quot;{&quot;factors&quot;: [], &quot;weights&quot;: {}}&quot;>{}</textarea></div>' +
    '</div>' +
    '<div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button>' +
    '<button class="btn btn-primary" onclick="savePortfolio()">保存</button></div></div></div>';
  document.getElementById('modal-container').innerHTML = modal;
}

function closeModal() {
  document.getElementById('modal-container').innerHTML = '';
}

// ===== Validation preview =====
function previewValidation() {
  var code = document.getElementById('m-code').value;
  if (!code.trim()) { toast('请输入代码', 'error'); return; }
  var valDiv = document.getElementById('m-val');
  valDiv.innerHTML = '<div class="val-result val-warn"><span class="spinner"></span> 验证中...</div>';
  // Use the create endpoint with dry validation by creating and deleting
  api('POST', '/strategies', { name: '__validation_preview__', source_code: code })
    .then(function(data) {
      var v = data.validation;
      if (v.valid) {
        valDiv.innerHTML = '<div class="val-result val-ok">✅ 验证通过' +
          (v.warnings.length ? '<br>⚠️ ' + v.warnings.join('; ') : '') +
          (v.metadata && v.metadata.parameters ? '<br>参数: ' + v.metadata.parameters.map(function(p) { return p.key + '=' + p.default; }).join(', ') : '') +
          '</div>';
      } else {
        valDiv.innerHTML = '<div class="val-result val-err">❌ 验证失败<ul class="validation-errors">' +
          v.errors.map(function(e) { return '<li>' + esc(e) + '</li>'; }).join('') + '</ul></div>';
      }
      // Delete the temp strategy
      if (data.strategy) api('DELETE', '/strategies/' + data.strategy.id).catch(function() {});
    })
    .catch(function(e) {
      valDiv.innerHTML = '<div class="val-result val-err">❌ ' + esc(e.message) + '</div>';
    });
}

// ===== Save =====
function saveStrategy(id) {
  var name = document.getElementById('m-name').value.trim();
  var code = document.getElementById('m-code').value;
  if (!name) { toast('请输入名称', 'error'); return; }
  if (!code.trim()) { toast('请输入策略代码', 'error'); return; }

  var tags = document.getElementById('m-tags').value.split(',').map(function(t) { return t.trim(); }).filter(Boolean);
  var body = {
    name: name,
    name_en: document.getElementById('m-name-en').value.trim(),
    description: document.getElementById('m-desc').value.trim(),
    category: document.getElementById('m-category').value,
    tags: tags,
    source_code: code
  };

  if (id) {
    api('PUT', '/strategies/' + id, body).then(function() { toast('策略已更新', 'success'); closeModal(); loadData(); })
      .catch(function(e) { toast('更新失败: ' + e.message, 'error'); });
  } else {
    api('POST', '/strategies', body).then(function() { toast('策略创建成功', 'success'); closeModal(); loadData(); })
      .catch(function(e) { toast('创建失败: ' + e.message, 'error'); });
  }
}

function saveFactor(id) {
  var name = document.getElementById('m-name').value.trim();
  var code = document.getElementById('m-code').value;
  if (!name) { toast('请输入名称', 'error'); return; }
  if (!code.trim()) { toast('请输入因子代码', 'error'); return; }

  var tags = document.getElementById('m-tags').value.split(',').map(function(t) { return t.trim(); }).filter(Boolean);
  var body = {
    name: name,
    name_en: document.getElementById('m-name-en').value.trim(),
    description: document.getElementById('m-desc').value.trim(),
    category: document.getElementById('m-category').value,
    tags: tags,
    source_code: code
  };

  if (id) {
    api('PUT', '/factors/' + id, body).then(function() { toast('因子已更新', 'success'); closeModal(); loadData(); })
      .catch(function(e) { toast('更新失败: ' + e.message, 'error'); });
  } else {
    api('POST', '/factors', body).then(function() { toast('因子创建成功', 'success'); closeModal(); loadData(); })
      .catch(function(e) { toast('创建失败: ' + e.message, 'error'); });
  }
}

function savePortfolio() {
  var name = document.getElementById('m-name').value.trim();
  if (!name) { toast('请输入名称', 'error'); return; }
  var configStr = document.getElementById('m-config').value;
  var config;
  try { config = JSON.parse(configStr); } catch(e) { toast('配置 JSON 格式错误', 'error'); return; }

  api('POST', '/factors/portfolios', { name: name, description: document.getElementById('m-desc').value, config: config })
    .then(function() { toast('组合创建成功', 'success'); closeModal(); loadData(); })
    .catch(function(e) { toast('创建失败: ' + e.message, 'error'); });
}

// ===== Delete =====
function deleteItem(id, type) {
  if (!confirm('确认删除？此操作不可撤销。')) return;
  api('DELETE', '/' + type + '/' + id).then(function() {
    toast('已删除', 'success'); loadData();
  }).catch(function(e) { toast('删除失败: ' + e.message, 'error'); });
}

// ===== Publish =====
function publishItem(path) {
  api('POST', path).then(function() { toast('已发布到市场', 'success'); loadData(); })
    .catch(function(e) { toast('发布失败: ' + e.message, 'error'); });
}

// ===== Versions =====
function viewVersions(id) {
  api('GET', '/strategies/' + id + '/versions').then(function(data) {
    var versions = data.versions || [];
    var html = '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-header"><span class="modal-title">版本历史 (' + versions.length + ')</span><button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div><div class="modal-body">';
    if (!versions.length) { html += '<div class="empty">暂无版本记录</div>'; }
    else {
      html += '<table><thead><tr><th>版本</th><th>时间</th><th>变更说明</th><th>操作</th></tr></thead><tbody>';
      versions.forEach(function(v) {
        html += '<tr><td>v' + v.version + '</td><td>' + fmtDate(v.created_at) + '</td><td>' + esc(v.changelog || '') + '</td>' +
          '<td><button class="btn btn-ghost btn-sm" onclick="rollbackVersion(\\''+ id + '\\',' + v.version + ')">回滚</button></td></tr>';
      });
      html += '</tbody></table>';
    }
    html += '</div><div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">关闭</button></div></div></div>';
    document.getElementById('modal-container').innerHTML = html;
  }).catch(function(e) { toast('加载版本失败: ' + e.message, 'error'); });
}

function rollbackVersion(id, ver) {
  if (!confirm('确认回滚到 v' + ver + '？将创建新版本。')) return;
  api('POST', '/strategies/' + id + '/rollback/' + ver).then(function() {
    toast('已回滚到 v' + ver, 'success'); closeModal(); loadData();
  }).catch(function(e) { toast('回滚失败: ' + e.message, 'error'); });
}

// ===== Marketplace actions =====
function cloneStrategy(id) {
  api('POST', '/strategies/' + id + '/clone').then(function() { toast('克隆成功！已添加到你的策略', 'success'); })
    .catch(function(e) { toast('克隆失败: ' + e.message, 'error'); });
}

function subscribeStrategy(id) {
  api('POST', '/strategies/' + id + '/subscribe').then(function() { toast('订阅成功', 'success'); })
    .catch(function(e) { toast('订阅失败: ' + e.message, 'error'); });
}

function rateStrategy(id) {
  var html = '<div class="modal-overlay" onclick="if(event.target===this)closeModal()"><div class="modal" style="max-width:360px;"><div class="modal-header"><span class="modal-title">评分</span><button class="btn btn-ghost btn-sm" onclick="closeModal()">✕</button></div><div class="modal-body" style="text-align:center;">' +
    '<div class="stars" id="rate-stars" style="font-size:28px;cursor:pointer;">' +
    '<span data-v="1" onclick="setRate(1)">★</span><span data-v="2" onclick="setRate(2)">★</span><span data-v="3" onclick="setRate(3)">★</span><span data-v="4" onclick="setRate(4)">★</span><span data-v="5" onclick="setRate(5)">★</span></div>' +
    '<div id="rate-val" style="margin-top:8px;color:var(--text2);">点击星星评分</div>' +
    '</div><div class="modal-footer"><button class="btn btn-primary" onclick="submitRate(\\''+ id + '\\')">提交</button></div></div></div>';
  document.getElementById('modal-container').innerHTML = html;
}

var currentRate = 0;
function setRate(v) {
  currentRate = v;
  document.querySelectorAll('#rate-stars span').forEach(function(s) {
    s.classList.toggle('active', parseInt(s.dataset.v) <= v);
  });
  document.getElementById('rate-val').textContent = v + ' 星';
}

function submitRate(id) {
  if (!currentRate) { toast('请先选择评分', 'error'); return; }
  api('POST', '/strategies/' + id + '/rate', { rating: currentRate }).then(function() {
    toast('评分成功', 'success'); closeModal(); loadData();
  }).catch(function(e) { toast('评分失败: ' + e.message, 'error'); });
}

// ===== Helpers =====
function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escVal(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function fmtDate(s) {
  if (!s) return '';
  try { var d = new Date(s); return d.toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }); }
  catch(e) { return s; }
}
function statusColor(status) {
  var m = { draft: 'gray', published: 'green', testing: 'orange', archived: 'gray' };
  return m[status] || 'gray';
}
function renderStars(avg, count) {
  var html = '<span class="stars">';
  for (var i = 1; i <= 5; i++) {
    html += '<span class="' + (i <= Math.round(avg) ? 'active' : '') + '">★</span>';
  }
  html += '</span> <span style="font-size:11px;color:var(--text3)">' + (avg ? avg.toFixed(1) : '0.0') + ' (' + (count || 0) + ')</span>';
  return html;
}

// ===== Init =====
loadData();
</script>
</body>
</html>"""
