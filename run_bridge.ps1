# ============================================================
# 启动飞书桥接服务
# 用法: 在 PowerShell 中运行 .\run_bridge.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# 检查 .env
if (-not (Test-Path "$ScriptDir\.env")) {
    Write-Host "❌ 未找到 .env 配置文件" -ForegroundColor Red
    Write-Host "   请先复制 .env.example 为 .env 并填入飞书凭据:" -ForegroundColor Yellow
    Write-Host "   Copy-Item .env.example .env" -ForegroundColor Cyan
    exit 1
}

# 选择 Python（优先 venv）
$Python = "$ScriptDir\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    # 回退到系统 python
    $Python = "python"
    Write-Host "⚠️  未找到 .venv，使用系统 python。建议先运行 .\setup.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vibe-Trading 飞书桥接服务" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Python: $Python" -ForegroundColor Gray
Write-Host "  按 Ctrl+C 停止" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& $Python "$ScriptDir\feishu_bridge.py"
