# ============================================================
# apply_customizations.ps1
# 将 customizations/ 中的自定义代码覆盖到 .venv 中
# 用法: 在 setup.ps1 完成后运行 .\apply_customizations.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$VenvSitePackages = "$ScriptDir\.venv\Lib\site-packages"
$CustDir = "$ScriptDir\customizations"

if (-not (Test-Path $VenvSitePackages)) {
    Write-Host "[X] 未找到 .venv，请先运行 .\setup.ps1" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $CustDir)) {
    Write-Host "[X] 未找到 customizations/ 目录" -ForegroundColor Red
    exit 1
}

Write-Host "[1/2] 应用自定义代码到 .venv..." -ForegroundColor Cyan

# 复制 customizations/ 下的所有文件到 .venv/Lib/site-packages/
$copied = 0
$failed = 0
Get-ChildItem -Path $CustDir -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Substring($CustDir.Length + 1)
    $destPath = Join-Path $VenvSitePackages $relativePath
    $destDir = Split-Path -Parent $destPath

    try {
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        Copy-Item $_.FullName $destPath -Force
        Write-Host "  OK: $relativePath" -ForegroundColor Green
        $copied++
    } catch {
        Write-Host "  FAIL: $relativePath - $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "[2/2] 清理 Python 缓存..." -ForegroundColor Cyan
Get-ChildItem -Path $VenvSitePackages -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  自定义代码应用完成!" -ForegroundColor Green
Write-Host "  成功: $copied 个文件" -ForegroundColor Gray
if ($failed -gt 0) {
    Write-Host "  失败: $failed 个文件" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  接下来运行: .\start.ps1" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
