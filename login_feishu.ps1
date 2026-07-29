# ============================================================
# 飞书渠道登录脚本 (QR 扫码自动创建飞书应用)
# 用法: 在 PowerShell 中运行 .\login_feishu.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VibeTrading = "$ScriptDir\.venv\Scripts\vibe-trading.exe"
$AgentJson = "$env:USERPROFILE\.vibe-trading\agent.json"

if (-not (Test-Path $VibeTrading)) {
    Write-Host "[X] 未找到 vibe-trading，请先运行 .\setup.ps1" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  飞书渠道 QR 扫码登录" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  此命令将:" -ForegroundColor Yellow
Write-Host "  1. 在终端显示一个 QR 码" -ForegroundColor Yellow
Write-Host "  2. 用飞书手机 App 扫码授权" -ForegroundColor Yellow
Write-Host "  3. 自动创建一个飞书机器人应用" -ForegroundColor Yellow
Write-Host "  4. 获取 App ID 和 App Secret" -ForegroundColor Yellow
Write-Host ""
Write-Host "  注意: 登录完成后，凭证显示在终端输出中" -ForegroundColor Red
Write-Host "  请记下 App ID 和 App Secret" -ForegroundColor Red
Write-Host "  然后运行 .\save_feishu_credentials.ps1 保存凭证" -ForegroundColor Red
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& $VibeTrading channels login feishu --force

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($LASTEXITCODE -eq 0) {
    Write-Host "  登录成功!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  请从上方输出中复制 App ID 和 App Secret" -ForegroundColor Yellow
    Write-Host "  然后运行: .\save_feishu_credentials.ps1" -ForegroundColor Yellow
} else {
    Write-Host "  登录失败" -ForegroundColor Red
    Write-Host "  请检查网络连接后重试" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
