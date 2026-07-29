# ============================================================
# Vibe-Trading 飞书渠道一键启动脚本
# 用法: 在 PowerShell 中运行 .\start.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$VenvPython = "$ScriptDir\.venv\Scripts\python.exe"
$VibeTrading = "$ScriptDir\.venv\Scripts\vibe-trading.exe"
$EnvFile = "$env:USERPROFILE\.vibe-trading\.env"
$AgentJson = "$env:USERPROFILE\.vibe-trading\agent.json"

# ---- 检查虚拟环境 ----
if (-not (Test-Path $VibeTrading)) {
    Write-Host "[X] 未找到 vibe-trading，请先运行 .\setup.ps1" -ForegroundColor Red
    exit 1
}

# ---- 检查 .env 配置 ----
if (-not (Test-Path $EnvFile)) {
    Write-Host "[X] 未找到 ~/.vibe-trading/.env 配置文件" -ForegroundColor Red
    Write-Host "    请运行: vibe-trading init" -ForegroundColor Yellow
    exit 1
}

# ---- 检查 API Key 是否已配置 ----
$envContent = Get-Content $EnvFile -Raw
if ($envContent -match "sk-在此填入") {
    Write-Host "[!] 警告: DeepSeek API Key 未配置" -ForegroundColor Yellow
    Write-Host "    请编辑 $EnvFile" -ForegroundColor Yellow
    Write-Host "    将 DEEPSEEK_API_KEY 替换为你的实际 API Key" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "    仍然继续启动? (y/N)"
    if ($continue -ne "y") { exit 0 }
}

# ---- 检查飞书凭证 ----
$agentContent = Get-Content $AgentJson -Raw
if ($agentContent -match '"app_id":\s*""') {
    Write-Host "[!] 警告: 飞书 app_id 未配置" -ForegroundColor Yellow
    Write-Host "    请先运行飞书登录: .\login_feishu.ps1" -ForegroundColor Yellow
    Write-Host "    或手动在飞书开放平台创建应用后填入凭证" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "    仍然继续启动? (y/N)"
    if ($continue -ne "y") { exit 0 }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vibe-Trading + 飞书渠道 启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CLI:       $VibeTrading" -ForegroundColor Gray
Write-Host "  Config:    $EnvFile" -ForegroundColor Gray
Write-Host "  Channels:  $AgentJson" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---- 启动 API 服务器 (后台) ----
$port = 8000
Write-Host "[1/3] 启动 API 服务器 (端口 $port)..." -ForegroundColor Green
$apiProcess = Start-Process -FilePath $VibeTrading `
    -ArgumentList "serve", "--port", $port `
    -PassThru -NoNewWindow

# 等待 API 就绪
Write-Host "[2/3] 等待 API 就绪..." -ForegroundColor Green
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/system/ping" -Method GET -TimeoutSec 3 -ErrorAction Stop
        $ready = $true
        Write-Host "      API 服务器已就绪" -ForegroundColor Green
        break
    } catch {
        Write-Host "      等待中... ($($i+1)/15)" -ForegroundColor Gray
    }
}

if (-not $ready) {
    Write-Host "[X] API 服务器启动超时" -ForegroundColor Red
    Write-Host "    请检查 ~/.vibe-trading/.env 中的 LLM 配置" -ForegroundColor Yellow
    exit 1
}

# ---- 启动飞书渠道 ----
Write-Host "[3/3] 启动飞书渠道..." -ForegroundColor Green
& $VibeTrading channels start

# ---- 保持运行 ----
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  服务已启动!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  API:     http://127.0.0.1:$port" -ForegroundColor Gray
Write-Host "  飞书:    已连接 (WebSocket 长连接)" -ForegroundColor Gray
Write-Host ""
Write-Host "  在飞书中向机器人发送消息即可开始对话" -ForegroundColor Yellow
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

# 等待 API 进程退出
try {
    $apiProcess.WaitForExit()
} catch {
    # 用户按 Ctrl+C
}
