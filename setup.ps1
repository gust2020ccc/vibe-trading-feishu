<#
.SYNOPSIS
    Vibe-Trading 飞书桥接服务 - 一键部署脚本
.DESCRIPTION
    1. 检查/安装 Python 3.11+
    2. 创建虚拟环境
    3. 安装 Vibe-Trading + 桥接服务依赖
    4. 初始化 Vibe-Trading 配置
    5. 引导配置 .env
.NOTES
    在 PowerShell 中运行: .\setup.ps1
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

function Write-Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  ✗ $msg" -ForegroundColor Red }

Write-Host "`n========================================" -ForegroundColor Magenta
Write-Host "  Vibe-Trading 飞书桥接服务 部署脚本" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta

# ---------------------------------------------------------------
# 1. 检查 Python 版本 (需要 3.11+)
# ---------------------------------------------------------------
Write-Step "检查 Python 环境（需要 3.11+）"

$PyExe = $null
$candidates = @()

# 查找 venv
if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $candidates += "$ScriptDir\.venv\Scripts\python.exe"
}
# 查找系统 python
$candidates += "python"
$candidates += "python3"
# 常见安装路径
$candidates += "C:\Python312\python.exe"
$candidates += "C:\Python311\python.exe"
$candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$candidates += "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"

foreach ($c in $candidates) {
    try {
        $verOut = & $c --version 2>&1
        if ($verOut -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 11) {
                $PyExe = $c
                Write-OK "找到 Python $major.$minor ($c)"
                break
            }
        }
    } catch { }
}

if (-not $PyExe) {
    Write-Warn "未找到 Python 3.11+，尝试用 winget 安装 Python 3.12…"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  正在安装 Python 3.12（可能需要确认）…"
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        # 刷新 PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $newPy = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        if (Test-Path $newPy) {
            $PyExe = $newPy
            Write-OK "Python 3.12 安装成功"
        }
    }
    if (-not $PyExe) {
        Write-Err "无法自动安装 Python 3.11+"
        Write-Host ""
        Write-Host "请手动安装:" -ForegroundColor Yellow
        Write-Host "  方式1: 访问 https://www.python.org/downloads/ 下载 Python 3.12 并安装（勾选 Add to PATH）" -ForegroundColor White
        Write-Host "  方式2: winget install Python.Python.3.12" -ForegroundColor White
        Write-Host "  安装后重新运行本脚本。" -ForegroundColor White
        exit 1
    }
}

# ---------------------------------------------------------------
# 2. 创建虚拟环境
# ---------------------------------------------------------------
Write-Step "创建虚拟环境 (.venv)"

if (-not (Test-Path "$ScriptDir\.venv")) {
    & $PyExe -m venv "$ScriptDir\.venv"
    Write-OK "虚拟环境已创建"
} else {
    Write-OK "虚拟环境已存在"
}
$VenvPy = "$ScriptDir\.venv\Scripts\python.exe"

# ---------------------------------------------------------------
# 3. 安装依赖
# ---------------------------------------------------------------
Write-Step "安装桥接服务依赖 (lark-oapi, python-dotenv)"

& $VenvPy -m pip install --upgrade pip --quiet
& $VenvPy -m pip install -r "$ScriptDir\requirements.txt" --quiet
if ($LASTEXITCODE -eq 0) {
    Write-OK "桥接服务依赖安装完成"
} else {
    Write-Err "依赖安装失败，请检查网络"
    exit 1
}

# ---------------------------------------------------------------
# 4. 安装 Vibe-Trading
# ---------------------------------------------------------------
Write-Step "安装 Vibe-Trading (vibe-trading-ai)"

$vtInstalled = & $VenvPy -c "import vibe_trading; print('ok')" 2>&1
if ($vtInstalled -ne "ok") {
    & $VenvPy -m pip install vibe-trading-ai --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Vibe-Trading 安装完成"
    } else {
        Write-Warn "Vibe-Trading 安装失败，可能需要稍后重试: pip install vibe-trading-ai"
    }
} else {
    Write-OK "Vibe-Trading 已安装"
}

# ---------------------------------------------------------------
# 5. 初始化 Vibe-Trading 配置
# ---------------------------------------------------------------
Write-Step "初始化 Vibe-Trading 配置"

$VtEnv = "$env:USERPROFILE\.vibe-trading\.env"
if (-not (Test-Path $VtEnv)) {
    Write-Host "  即将运行 vibe-trading init（交互式配置 LLM 和数据源）…"
    Write-Host "  如果你已有 DeepSeek/OpenAI 的 API Key，可以现在配置。" -ForegroundColor Yellow
    $ans = Read-Host "  现在运行 vibe-trading init? (Y/n)"
    if ($ans -ne "n") {
        & $VenvPy -m vibe_trading init
    } else {
        Write-Warn "跳过初始化，稍后可手动运行: .venv\Scripts\python.exe -m vibe_trading init"
    }
} else {
    Write-OK "Vibe-Trading 配置已存在 ($VtEnv)"
}

# ---------------------------------------------------------------
# 6. 配置 .env
# ---------------------------------------------------------------
Write-Step "检查桥接服务 .env 配置"

if (-not (Test-Path "$ScriptDir\.env")) {
    Copy-Item "$ScriptDir\.env.example" "$ScriptDir\.env"
    Write-OK "已从模板创建 .env"
    Write-Host ""
    Write-Host "  ⚠ 请编辑 .env 填入飞书应用凭据:" -ForegroundColor Yellow
    Write-Host "    notepad $ScriptDir\.env" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  必填项:" -ForegroundColor Yellow
    Write-Host "    FEISHU_APP_ID     - 飞书应用 App ID" -ForegroundColor White
    Write-Host "    FEISHU_APP_SECRET - 飞书应用 App Secret" -ForegroundColor White
} else {
    Write-OK ".env 已存在"
}

# ---------------------------------------------------------------
# 7. 验证
# ---------------------------------------------------------------
Write-Step "验证安装"

# 验证 vibe-trading
$vtVer = & $VenvPy -m vibe_trading --version 2>&1
if ($vtVer) { Write-OK "Vibe-Trading: $vtVer" }

# 验证 lark-oapi
$larkOk = & $VenvPy -c "import lark_oapi; print(lark_oapi.__version__)" 2>&1
if ($larkOk) { Write-OK "lark-oapi: $larkOk" }

# ---------------------------------------------------------------
# 完成
# ---------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 在飞书开放平台创建自建应用并启用机器人" -ForegroundColor White
Write-Host "     (详见部署方案文档中的「飞书应用配置」章节)" -ForegroundColor Gray
Write-Host "  2. 编辑 .env 填入 FEISHU_APP_ID 和 FEISHU_APP_SECRET" -ForegroundColor White
Write-Host "  3. 运行启动脚本:" -ForegroundColor White
Write-Host "     .\run_bridge.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  4. 在飞书中给机器人发消息测试" -ForegroundColor White
Write-Host ""
