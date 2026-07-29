# ============================================================
# 手动配置飞书应用凭证 (替代 QR 扫码登录)
# 用法: 在飞书开放平台创建应用后运行此脚本
# ============================================================

$AgentJson = "$env:USERPROFILE\.vibe-trading\agent.json"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  手动配置飞书应用凭证" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  前置步骤 (在飞书开放平台完成):" -ForegroundColor Yellow
Write-Host "  1. 访问 https://open.feishu.cn 创建企业自建应用" -ForegroundColor Yellow
Write-Host "  2. 在 [凭证与基础信息] 页面获取 App ID 和 App Secret" -ForegroundColor Yellow
Write-Host "  3. 在 [应用能力] > [机器人] 中启用机器人能力" -ForegroundColor Yellow
Write-Host "  4. 在 [权限管理] 中添加权限:" -ForegroundColor Yellow
Write-Host "     - im:message (获取与发送单聊、群组消息)" -ForegroundColor Yellow
Write-Host "     - im:message.group_at_msg (接收群聊@机器人消息)" -ForegroundColor Yellow
Write-Host "     - im:resource (获取消息中的资源文件)" -ForegroundColor Yellow
Write-Host "  5. 在 [事件订阅] 中:" -ForegroundColor Yellow
Write-Host "     - 选择 [使用长连接接收事件]" -ForegroundColor Yellow
Write-Host "     - 添加事件: im.message.receive_v1" -ForegroundColor Yellow
Write-Host "  6. 发布应用版本并等待审核通过" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$appId = Read-Host "请输入 App ID (如 cli_a1b2c3d4e5f6g7h8)"
$appSecret = Read-Host "请输入 App Secret"

if (-not $appId -or $appId -eq "") {
    Write-Host "[X] App ID 不能为空" -ForegroundColor Red
    exit 1
}

# 构建 JSON
$config = @{
    channels = @{
        feishu = @{
            enabled = $true
            app_id = $appId
            app_secret = $appSecret
            domain = "feishu"
            streaming = $true
            group_policy = "mention"
            reply_to_message = $false
            topic_isolation = $true
            allow_from = @()
        }
    }
}

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
