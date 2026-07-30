"""Backtest web dashboard — self-contained HTML page.

Provides a single-page interface for:
  - Browsing available strategy templates
  - Running direct backtests with parameter customization
  - Viewing recent backtest runs and their results
  - Displaying equity/drawdown charts

The HTML is returned by :func:`get_backtest_dashboard_html` and served at
``GET /backtest/dashboard`` by ``src.api.backtest_routes``.
"""

from __future__ import annotations


def get_backtest_dashboard_html() -> str:
    """Return the self-contained HTML for the backtest dashboard."""
    return _HTML_TEMPLATE


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vibe-Trading 回测平台</title>
<style>
:root {
  --bg: #0f1117;
  --card: #1a1d28;
  --card-hover: #22263a;
  --border: #2d3142;
  --text: #e0e0e0;
  --text-dim: #888fa0;
  --primary: #4f8cff;
  --primary-hover: #6a9eff;
  --success: #4caf50;
  --danger: #f44336;
  --warning: #ff9800;
  --radius: 10px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  padding: 20px;
}
.container { max-width: 1200px; margin: 0 auto; }
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px;
}
header h1 { font-size: 22px; font-weight: 600; }
header .badge {
  background: var(--primary); color: #fff; padding: 4px 12px;
  border-radius: 20px; font-size: 12px; font-weight: 600;
}
.grid { display: grid; gap: 20px; }
.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: 1fr 1fr 1fr; }
@media (max-width: 768px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px;
}
.card h2 { font-size: 16px; margin-bottom: 16px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }
.form-group select, .form-group input {
  width: 100%; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 14px;
}
.form-group select:focus, .form-group input:focus { outline: none; border-color: var(--primary); }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.btn {
  padding: 10px 24px; border: none; border-radius: 6px; font-size: 14px;
  font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.params-container { margin-top: 8px; }
.param-item {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
  padding: 6px 10px; background: var(--bg); border-radius: 6px;
}
.param-item label { min-width: 100px; font-size: 13px; }
.param-item input { flex: 1; padding: 4px 8px; background: var(--card); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-size: 13px; }
.strategy-desc { font-size: 13px; color: var(--text-dim); margin-top: 4px; line-height: 1.5; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
table th { text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--border); color: var(--text-dim); }
table td { padding: 8px; border-bottom: 1px solid var(--border); }
table tr:hover td { background: var(--card-hover); }
.status-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-success { background: rgba(76,175,80,0.2); color: var(--success); }
.status-error { background: rgba(244,67,54,0.2); color: var(--danger); }
.status-unknown { background: rgba(136,143,160,0.2); color: var(--text-dim); }
.result-area { margin-top: 16px; }
.result-card {
  background: var(--card); border-radius: var(--radius); padding: 16px;
  margin-bottom: 12px; border: 1px solid var(--border);
}
.metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.metric-box { background: var(--bg); border-radius: 8px; padding: 12px; text-align: center; }
.metric-box .label { font-size: 12px; color: var(--text-dim); }
.metric-box .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
.metric-box.positive .value { color: var(--success); }
.metric-box.negative .value { color: var(--danger); }
.chart-img { width: 100%; border-radius: 8px; margin-top: 12px; }
.spinner {
  display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border);
  border-top-color: var(--primary); border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-overlay { display: none; text-align: center; padding: 40px; color: var(--text-dim); }
.loading-overlay.active { display: block; }
.toast {
  position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px;
  font-size: 14px; z-index: 9999; opacity: 0; transition: opacity 0.3s;
}
.toast.show { opacity: 1; }
.toast.success { background: var(--success); color: #fff; }
.toast.error { background: var(--danger); color: #fff; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📊 Vibe-Trading 回测平台</h1>
    <span class="badge">Phase 2</span>
  </header>

  <div class="grid grid-2">
    <!-- Left: Strategy Selection & Config -->
    <div class="card">
      <h2>策略配置</h2>
      <div class="form-group">
        <label>选择策略</label>
        <select id="strategySelect" onchange="onStrategyChange()">
          <option value="">-- 请选择 --</option>
        </select>
        <div id="strategyDesc" class="strategy-desc"></div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>标的代码 (逗号分隔)</label>
          <input type="text" id="codes" placeholder="000001.SZ 或 000001,600519.SH" value="000001.SZ">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>开始日期</label>
          <input type="date" id="startDate" value="2024-01-01">
        </div>
        <div class="form-group">
          <label>结束日期</label>
          <input type="date" id="endDate" value="2024-12-31">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>数据源</label>
          <select id="source">
            <option value="akshare" selected>akshare (A股免费，推荐)</option>
            <option value="auto">auto (自动，需配置tushare)</option>
            <option value="tushare">tushare (需token)</option>
            <option value="yfinance">yfinance (美股)</option>
            <option value="baostock">baostock</option>
          </select>
        </div>
        <div class="form-group">
          <label>初始资金</label>
          <input type="number" id="initialCash" value="1000000" step="100000">
        </div>
      </div>
      <div id="paramsContainer" class="params-container"></div>
      <button class="btn btn-primary" id="runBtn" onclick="runBacktest()" style="margin-top: 12px;">
        ▶ 运行回测
      </button>
    </div>

    <!-- Right: Recent Runs -->
    <div class="card">
      <h2>历史回测</h2>
      <div style="max-height: 400px; overflow-y: auto;">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>策略</th>
              <th>标的</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="runsTable"></tbody>
        </table>
      </div>
      <button class="btn btn-primary" onclick="loadRuns()" style="margin-top: 12px; padding: 6px 16px; font-size: 12px;">刷新</button>
    </div>
  </div>

  <!-- Results Area -->
  <div class="result-area" id="resultArea"></div>
</div>

<div class="toast" id="toast"></div>

<script>
let strategies = [];
let currentStrategy = null;

// --- Init ---
async function init() {
  await loadStrategies();
  await loadRuns();
}

async function loadStrategies() {
  try {
    const res = await fetch('/backtest/strategies');
    strategies = await res.json();
    const sel = document.getElementById('strategySelect');
    strategies.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.name + ' (' + s.name_en + ')';
      sel.appendChild(opt);
    });
  } catch (e) {
    showToast('加载策略列表失败: ' + e.message, 'error');
  }
}

function onStrategyChange() {
  const id = document.getElementById('strategySelect').value;
  currentStrategy = strategies.find(s => s.id === id);
  const descEl = document.getElementById('strategyDesc');
  const paramsEl = document.getElementById('paramsContainer');
  paramsEl.innerHTML = '';
  if (!currentStrategy) { descEl.textContent = ''; return; }
  descEl.textContent = currentStrategy.description;
  if (currentStrategy.parameters) {
    currentStrategy.parameters.forEach(p => {
      const div = document.createElement('div');
      div.className = 'param-item';
      div.innerHTML = `<label>${p.label}</label><input type="${p.type === 'int' ? 'number' : 'text'}" id="param_${p.key}" value="${p.default}" ${p.min !== undefined ? 'min="' + p.min + '"' : ''} ${p.max !== undefined ? 'max="' + p.max + '"' : ''} step="${p.type === 'float' ? '0.1' : '1'}">`;
      paramsEl.appendChild(div);
    });
  }
}

async function runBacktest() {
  const strategyId = document.getElementById('strategySelect').value;
  if (!strategyId) { showToast('请先选择策略', 'error'); return; }
  const codes = document.getElementById('codes').value.trim();
  if (!codes) { showToast('请输入标的代码', 'error'); return; }

  const params = {};
  if (currentStrategy && currentStrategy.parameters) {
    currentStrategy.parameters.forEach(p => {
      const el = document.getElementById('param_' + p.key);
      if (el) {
        let val = el.value;
        if (p.type === 'int') val = parseInt(val);
        else if (p.type === 'float') val = parseFloat(val);
        params[p.key] = val;
      }
    });
  }

  const body = {
    strategy_id: strategyId,
    codes: codes.split(',').map(c => c.trim()).filter(Boolean),
    start_date: document.getElementById('startDate').value,
    end_date: document.getElementById('endDate').value,
    params: params,
    source: document.getElementById('source').value,
    initial_cash: parseFloat(document.getElementById('initialCash').value),
    interval: '1D',
    generate_chart: true,
  };

  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 回测中...';
  document.getElementById('resultArea').innerHTML = '<div class="loading-overlay active"><div class="spinner" style="width:32px;height:32px;border-width:3px;"></div><p style="margin-top:12px;">正在执行回测，请稍候...</p></div>';

  try {
    const res = await fetch('/backtest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || '回测失败');
    }
    displayResult(data, currentStrategy);
    showToast('回测完成!', 'success');
    loadRuns();
  } catch (e) {
    document.getElementById('resultArea').innerHTML = '<div class="result-card" style="border-color:var(--danger);"><p style="color:var(--danger);">❌ ' + e.message + '</p></div>';
    showToast('回测失败: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '▶ 运行回测';
  }
}

function displayResult(data, strategy) {
  const area = document.getElementById('resultArea');
  const m = data.metrics || {};
  const pct = (v) => { try { let f = parseFloat(v); if (Math.abs(f) <= 1) f *= 100; return (f >= 0 ? '+' : '') + f.toFixed(2) + '%'; } catch { return 'N/A'; } };
  const num = (v, d=2) => { try { return parseFloat(v).toFixed(d); } catch { return 'N/A'; } };

  const name = strategy ? strategy.name : data.run_id;
  let html = '<div class="result-card">';
  html += '<h2 style="color:var(--text);">📊 回测结果: ' + name + '</h2>';
  html += '<p style="color:var(--text-dim);font-size:13px;">Run ID: ' + (data.run_id || 'N/A') + '</p>';
  html += '<div class="metrics-grid">';
  html += metricBox('总收益', pct(m.total_return), m.total_return >= 0);
  html += metricBox('年化收益', pct(m.annual_return), m.annual_return >= 0);
  html += metricBox('夏普比率', num(m.sharpe), m.sharpe >= 0);
  html += metricBox('最大回撤', pct(m.max_drawdown), false);
  html += metricBox('胜率', pct(m.win_rate), m.win_rate >= 0.5);
  html += metricBox('交易次数', m.trade_count != null ? parseInt(m.trade_count) : 'N/A', true);
  html += '</div>';
  if (data.chart_path || (data.run_id)) {
    html += '<img class="chart-img" src="/backtest/runs/' + data.run_id + '/chart?t=' + Date.now() + '" alt="回测图表" onerror="this.style.display=\'none\'">';
  }
  html += '</div>';
  area.innerHTML = html;
}

function metricBox(label, value, positive) {
  const cls = positive === true ? 'positive' : (positive === false ? 'negative' : '');
  return '<div class="metric-box ' + cls + '"><div class="label">' + label + '</div><div class="value">' + value + '</div></div>';
}

async function loadRuns() {
  try {
    const res = await fetch('/backtest/runs?limit=20');
    const runs = await res.json();
    const tbody = document.getElementById('runsTable');
    tbody.innerHTML = '';
    if (!runs || runs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-dim);">暂无回测记录</td></tr>';
      return;
    }
    runs.forEach(r => {
      const tr = document.createElement('tr');
      const statusCls = r.status === 'success' ? 'status-success' : (r.status === 'error' ? 'status-error' : 'status-unknown');
      const time = r.created_at ? r.created_at.substring(5) : r.run_id.substring(4, 12);
      tr.innerHTML = '<td>' + time + '</td><td>' + (r.strategy || '-') + '</td><td>' + (r.codes || []).join(',').substring(0, 15) + '</td><td><span class="status-badge ' + statusCls + '">' + r.status + '</span></td><td>' + (r.has_chart ? '<a href="/backtest/runs/' + r.run_id + '/chart" target="_blank" style="color:var(--primary);">图表</a>' : '-') + '</td>';
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error('loadRuns error:', e);
  }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => { t.className = 'toast ' + type; }, 3000);
}

init();
</script>
</body>
</html>"""
