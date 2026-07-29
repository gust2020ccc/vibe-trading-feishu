# ============================================================
# 保存飞书凭证到 agent.json
# 用法: 在 QR 登录后运行 .\save_feishu_credentials.ps1
# ============================================================

$AgentJson = "$env:USERPROFILE\.vibe-trading\agent.json"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  保存飞书凭证" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 读取用户输入
$appId = Read-Host "请输入 App ID (cli_ 开头)"
$appSecret = Read-Host "请输入 App Secret"

if (-not $appId -or $appId -eq "") {
    Write-Host "[X] App ID 不能为空" -ForegroundColor Red
    exit 1
}
if (-not $appSecret -or $appSecret -eq "") {
    Write-Host "[X] App Secret 不能为空" -ForegroundColor Red
    exit 1
}

# 读取现有 agent.json
if (Test-Path $AgentJson) {
    $config = Get-Content $AgentJson -Raw | ConvertFrom-Json
} else {
    $config = @{}
}

# 更新飞书配置
if (-not $config.channels) {
    $config | Add-Member -NotePropertyName "channels" -NotePropertyValue @{}
}
if (-not $config.channels.feishu) {
    $config.channels | Add-Member -NotePropertyName "feishu" -NotePropertyValue @{}
}

$config.channels.feishu.enabled = $true
$config.channels.feishu.app_id = $appId
$config.channels.feishu.app_secret = $appSecret
if (-not $config.channels.feishu.domain) {
    $config.channels.feishu | Add-Member -NotePropertyName "domain" -NotePropertyValue "feishu"
}
if (-not $config.channels.feishu.streaming) {
    $config.channels.feishu | Add-Member -NotePropertyName "streaming" -NotePropertyValue $true
}
if (-not $config.channels.feishu.group_policy) {
    $config.channels.feishu | Add-Member -NotePropertyName "group_policy" -NotePropertyValue "mention"
}

# 写回文件 (无 BOM UTF-8)
$json = $config | ConvertTo-Json -Depth 10
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($AgentJson, $json, $utf8NoBom)

Write-Host ""
Write-Host "[OK] 飞书凭证已保存到 $AgentJson" -ForegroundColor Green
Write-Host ""
Write-Host "  App ID: $appId" -ForegroundColor Gray
Write-Host ""
Write-Host "  现在可以运行: .\start.ps1" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
