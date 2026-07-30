"""Self-contained HTML Dashboard for user management and usage tracking."""

from __future__ import annotations


def get_dashboard_html() -> str:
    """Return the dashboard HTML as a string."""
    return _DASHBOARD_HTML


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vibe-Trading 用户管理</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 30px; }
.header h1 { font-size: 24px; font-weight: 600; }
.header p { opacity: 0.8; margin-top: 4px; font-size: 14px; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.stat-card .label { font-size: 13px; color: #888; margin-bottom: 4px; }
.stat-card .value { font-size: 28px; font-weight: 700; color: #333; }
.stat-card .sub { font-size: 12px; color: #aaa; margin-top: 4px; }
.card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 24px; }
.card-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 12px 8px; border-bottom: 2px solid #f0f0f0; font-size: 13px; color: #888; font-weight: 600; }
td { padding: 12px 8px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.badge.active { background: #e6f7ed; color: #52c41a; }
.badge.disabled { background: #fff1f0; color: #ff4d4f; }
.btn { display: inline-block; padding: 4px 12px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn-primary { background: #667eea; color: white; }
.btn-primary:hover { background: #5568d3; }
.btn-sm { padding: 3px 8px; font-size: 12px; }
.btn-outline { background: transparent; border: 1px solid #ddd; color: #666; }
.btn-outline:hover { border-color: #667eea; color: #667eea; }
.btn-danger { background: transparent; border: 1px solid #ff4d4f; color: #ff4d4f; }
.btn-danger:hover { background: #ff4d4f; color: white; }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 1000; justify-content: center; align-items: center; }
.modal-overlay.show { display: flex; }
.modal { background: white; border-radius: 12px; padding: 28px; width: 480px; max-width: 90%; }
.modal h3 { margin-bottom: 20px; font-size: 18px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; color: #666; margin-bottom: 4px; }
.form-group input { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.form-group .hint { font-size: 12px; color: #aaa; margin-top: 2px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.loading { text-align: center; padding: 40px; color: #aaa; }
.api-key-bar { background: #fff; padding: 10px 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px; }
.api-key-bar input { padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; width: 300px; }
.token-bar { height: 4px; background: #f0f0f0; border-radius: 2px; margin-top: 4px; overflow: hidden; }
.token-bar-fill { height: 100%; background: #52c41a; border-radius: 2px; transition: width 0.3s; }
.token-bar-fill.warn { background: #faad14; }
.token-bar-fill.danger { background: #ff4d4f; }
</style>
</head>
<body>

<div class="header">
    <h1>Vibe-Trading 用户管理</h1>
    <p>用量追踪 · 配额管理 · 用户控制</p>
</div>

<div class="api-key-bar">
    <span style="font-size:13px;color:#666;">API Key:</span>
    <input type="password" id="apiKey" placeholder="输入 API Key 以访问管理接口" oninput="onApiKeyChange()">
    <button class="btn btn-primary btn-sm" onclick="loadAll()">刷新</button>
</div>

<div class="container">
    <!-- Stats Cards -->
    <div class="stats-row" id="statsRow">
        <div class="stat-card"><div class="label">总用户</div><div class="value" id="totalUsers">-</div></div>
        <div class="stat-card"><div class="label">活跃用户</div><div class="value" id="activeUsers">-</div></div>
        <div class="stat-card"><div class="label">今日 Token</div><div class="value" id="todayTokens">-</div></div>
        <div class="stat-card"><div class="label">本月 Token</div><div class="value" id="monthTokens">-</div></div>
    </div>

    <!-- User Table -->
    <div class="card">
        <div class="card-title">
            <span>用户列表</span>
            <button class="btn btn-primary btn-sm" onclick="showAddUserModal()">+ 添加用户</button>
        </div>
        <div id="userTableContainer">
            <div class="loading">加载中...</div>
        </div>
    </div>
</div>

<!-- Edit Quota Modal -->
<div class="modal-overlay" id="quotaModal">
    <div class="modal">
        <h3>编辑配额</h3>
        <p style="margin-bottom:16px;color:#888;font-size:13px;" id="quotaModalUser"></p>
        <div class="form-group">
            <label>日 Token 上限 (0=不限)</label>
            <input type="number" id="qDailyToken" value="0">
        </div>
        <div class="form-group">
            <label>月 Token 上限 (0=不限)</label>
            <input type="number" id="qMonthlyToken" value="0">
        </div>
        <div class="form-group">
            <label>并发会话数 (0=不限)</label>
            <input type="number" id="qConcurrent" value="3">
        </div>
        <div class="form-group">
            <label>每分钟请求数 (0=不限)</label>
            <input type="number" id="qRpm" value="20">
        </div>
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="closeModal('quotaModal')">取消</button>
            <button class="btn btn-primary" onclick="saveQuota()">保存</button>
        </div>
    </div>
</div>

<!-- Add User Modal -->
<div class="modal-overlay" id="addUserModal">
    <div class="modal">
        <h3>添加用户</h3>
        <div class="form-group">
            <label>用户 ID (飞书 open_id)</label>
            <input type="text" id="newUserId" placeholder="ou_xxxxxxxxxxxx">
        </div>
        <div class="form-group">
            <label>名称 (可选)</label>
            <input type="text" id="newUserName" placeholder="用户昵称">
        </div>
        <div class="form-group">
            <label>角色</label>
            <input type="text" id="newUserRole" value="user" placeholder="user / admin">
        </div>
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="closeModal('addUserModal')">取消</button>
            <button class="btn btn-primary" onclick="addUser()">添加</button>
        </div>
    </div>
</div>

<script>
let apiKey = localStorage.getItem('vt_api_key') || '';
document.getElementById('apiKey').value = apiKey;
let currentQuotaUserId = null;

function onApiKeyChange() {
    apiKey = document.getElementById('apiKey').value;
    localStorage.setItem('vt_api_key', apiKey);
}

async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['Authorization'] = 'Bearer ' + apiKey;
    const resp = await fetch(path, { ...options, headers });
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(resp.status + ': ' + text);
    }
    return resp.json();
}

function fmt(n) {
    if (n === undefined || n === null) return '-';
    return Number(n).toLocaleString();
}

function shortId(id) {
    if (!id) return '-';
    return id.length > 20 ? id.substring(0, 20) + '...' : id;
}

async function loadAll() {
    try {
        const [summary, users] = await Promise.all([
            api('/admin/usage/summary'),
            api('/admin/users')
        ]);
        renderStats(summary);
        renderUsers(users);
    } catch (e) {
        document.getElementById('userTableContainer').innerHTML = '<div class="loading" style="color:#ff4d4f;">加载失败: ' + e.message + '</div>';
    }
}

function renderStats(s) {
    document.getElementById('totalUsers').textContent = s.total_users || 0;
    document.getElementById('activeUsers').textContent = s.active_users || 0;
    document.getElementById('todayTokens').textContent = fmt(s.today_tokens);
    document.getElementById('monthTokens').textContent = fmt(s.month_tokens);
}

function renderUsers(users) {
    if (!users || users.length === 0) {
        document.getElementById('userTableContainer').innerHTML = '<div class="loading">暂无用户</div>';
        return;
    }
    let html = '<table><thead><tr>';
    html += '<th>用户</th><th>状态</th><th>角色</th><th>今日Token</th><th>本月Token</th><th>日配额</th><th>操作</th>';
    html += '</tr></thead><tbody>';
    for (const u of users) {
        const isActive = u.status === 'active';
        const todayT = u.today_tokens || 0;
        const dailyLimit = u.daily_token_limit || 0;
        const pct = dailyLimit > 0 ? Math.min(100, todayT / dailyLimit * 100) : 0;
        const barClass = pct > 90 ? 'danger' : pct > 70 ? 'warn' : '';
        const limitText = dailyLimit > 0 ? fmt(dailyLimit) : '不限';

        html += '<tr>';
        html += '<td><div style="font-weight:500;">' + (u.name || shortId(u.user_id)) + '</div>';
        html += '<div style="font-size:12px;color:#aaa;">' + shortId(u.user_id) + '</div></td>';
        html += '<td><span class="badge ' + u.status + '">' + (isActive ? '活跃' : '停用') + '</span></td>';
        html += '<td>' + (u.role || 'user') + '</td>';
        html += '<td>' + fmt(todayT) + '</td>';
        html += '<td>' + fmt(u.month_tokens || 0) + '</td>';
        html += '<td>' + limitText;
        if (dailyLimit > 0) {
            html += '<div class="token-bar"><div class="token-bar-fill ' + barClass + '" style="width:' + pct + '%"></div></div>';
        }
        html += '</td>';
        html += '<td style="white-space:nowrap;">';
        html += '<button class="btn btn-outline btn-sm" onclick="editQuota(\\'' + u.user_id + '\\',\\'' + (u.name || shortId(u.user_id)) + '\\')">配额</button> ';
        if (isActive) {
            html += '<button class="btn btn-danger btn-sm" onclick="toggleUser(\\'' + u.user_id + '\\',\\'disabled\\')">停用</button>';
        } else {
            html += '<button class="btn btn-primary btn-sm" onclick="toggleUser(\\'' + u.user_id + '\\',\\'active\\')">启用</button>';
        }
        html += '</td>';
        html += '</tr>';
    }
    html += '</tbody></table>';
    document.getElementById('userTableContainer').innerHTML = html;
}

function showAddUserModal() {
    document.getElementById('addUserModal').classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

async function addUser() {
    const userId = document.getElementById('newUserId').value.trim();
    const name = document.getElementById('newUserName').value.trim();
    const role = document.getElementById('newUserRole').value.trim() || 'user';
    if (!userId) { alert('请输入用户 ID'); return; }
    try {
        await api('/admin/users', {
            method: 'POST',
            body: JSON.stringify({ user_id: userId, name: name, role: role })
        });
        closeModal('addUserModal');
        document.getElementById('newUserId').value = '';
        document.getElementById('newUserName').value = '';
        loadAll();
    } catch (e) { alert('添加失败: ' + e.message); }
}

function editQuota(userId, userName) {
    currentQuotaUserId = userId;
    document.getElementById('quotaModalUser').textContent = userName + ' (' + shortId(userId) + ')';
    api('/admin/users/' + userId + '/quota').then(q => {
        document.getElementById('qDailyToken').value = q.daily_token_limit || 0;
        document.getElementById('qMonthlyToken').value = q.monthly_token_limit || 0;
        document.getElementById('qConcurrent').value = q.concurrent_session_limit || 0;
        document.getElementById('qRpm').value = q.rate_limit_per_minute || 0;
        document.getElementById('quotaModal').classList.add('show');
    }).catch(e => alert('加载配额失败: ' + e.message));
}

async function saveQuota() {
    const data = {
        daily_token_limit: parseInt(document.getElementById('qDailyToken').value) || 0,
        monthly_token_limit: parseInt(document.getElementById('qMonthlyToken').value) || 0,
        concurrent_session_limit: parseInt(document.getElementById('qConcurrent').value) || 0,
        rate_limit_per_minute: parseInt(document.getElementById('qRpm').value) || 0,
    };
    try {
        await api('/admin/users/' + currentQuotaUserId + '/quota', {
            method: 'PUT', body: JSON.stringify(data)
        });
        closeModal('quotaModal');
        loadAll();
    } catch (e) { alert('保存失败: ' + e.message); }
}

async function toggleUser(userId, status) {
    try {
        await api('/admin/users/' + userId, {
            method: 'PUT', body: JSON.stringify({ status: status })
        });
        loadAll();
    } catch (e) { alert('操作失败: ' + e.message); }
}

// Auto-load on page open
loadAll();
</script>

</body>
</html>"""
