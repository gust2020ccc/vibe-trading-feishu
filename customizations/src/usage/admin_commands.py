"""Feishu /admin command handler for user management and usage queries.

Commands:
    /admin                       View your own usage and quota (all users)
    /admin help                  Show command help
    /admin list                  List all users and today's usage (admin only)
    /admin user <open_id>        View specific user's usage (admin only)
    /admin quota <open_id>       View user's quota (admin only)
    /admin setquota <id> <dt> <mt> <cs> <rpm>   Set quota (admin only, 0=unlimited)
    /admin disable <open_id>     Disable user (admin only)
    /admin enable <open_id>      Enable user (admin only)
    /admin summary               Global usage summary (admin only)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _get_service():
    """Lazy import to avoid circular dependencies."""
    from src.api.state import _get_usage_service
    return _get_usage_service()


def handle_admin_command(
    sender_id: str,
    subcommand_text: str,
    *,
    is_operator: bool = False,
) -> str:
    """Execute an /admin subcommand and return the reply text.

    Args:
        sender_id: The sender's channel ID (e.g. Feishu open_id).
        subcommand_text: The text after /admin (e.g. "list", "user ou_xxx").
        is_operator: Whether the sender is a configured operator/admin.

    Returns:
        Plain text reply suitable for Feishu message.
    """
    svc = _get_service()
    if svc is None:
        return "用量管理系统未启用。"

    parts = subcommand_text.split()
    sub = parts[0].lower() if parts else ""

    # No subcommand → show own usage
    if not sub or sub == "me":
        return _format_self_summary(svc, sender_id)

    if sub == "help":
        return _format_help()

    # All remaining commands require operator privileges
    if not is_operator:
        return "无权限：此命令仅管理员可用。发送 /admin 查看自己的用量。"

    if sub == "list":
        return _format_user_list(svc)

    if sub == "user" and len(parts) >= 2:
        uid = parts[1]
        return _format_user_detail(svc, uid)

    if sub == "quota" and len(parts) >= 2:
        uid = parts[1]
        return _format_quota(svc, uid)

    if sub == "setquota" and len(parts) >= 6:
        uid = parts[1]
        try:
            svc.set_quota(
                uid,
                daily_token_limit=int(parts[2]),
                monthly_token_limit=int(parts[3]),
                concurrent_session_limit=int(parts[4]),
                rate_limit_per_minute=int(parts[5]),
            )
            return f"已更新 {uid} 的配额设置。"
        except ValueError:
            return "参数错误：所有配额值必须为整数。用法: /admin setquota <id> <日token> <月token> <并发> <RPM>"

    if sub == "disable" and len(parts) >= 2:
        uid = parts[1]
        user = svc.update_user(uid, status="disabled")
        if user:
            return f"已停用用户 {uid}。"
        return f"用户 {uid} 不存在。"

    if sub == "enable" and len(parts) >= 2:
        uid = parts[1]
        user = svc.update_user(uid, status="active")
        if user:
            return f"已启用用户 {uid}。"
        return f"用户 {uid} 不存在。"

    if sub == "summary":
        return _format_global_summary(svc)

    return _format_help()


def _format_self_summary(svc, user_id: str) -> str:
    """Format the user's own usage summary."""
    summary = svc.get_usage_summary(user_id)
    user = svc.get_user(user_id)
    name = user.name if user and user.name else user_id[:16]

    lines = [
        f"📊 我的用量统计 ({name})",
        f"",
        f"今日 Token: {summary.today_tokens:,}",
        f"今日请求: {summary.today_requests}",
        f"本月 Token: {summary.month_tokens:,}",
        f"本月请求: {summary.month_requests}",
    ]

    if summary.quota:
        q = summary.quota
        lines.append("")
        lines.append("📋 我的配额:")
        dt = f"{q.daily_token_limit:,}" if q.daily_token_limit > 0 else "不限"
        mt = f"{q.monthly_token_limit:,}" if q.monthly_token_limit > 0 else "不限"
        cs = str(q.concurrent_session_limit) if q.concurrent_session_limit > 0 else "不限"
        rpm = str(q.rate_limit_per_minute) if q.rate_limit_per_minute > 0 else "不限"
        lines.append(f"  日Token上限: {dt}")
        lines.append(f"  月Token上限: {mt}")
        lines.append(f"  并发会话数: {cs}")
        lines.append(f"  每分钟请求: {rpm}")

    return "\n".join(lines)


def _format_user_list(svc) -> str:
    """Format the list of all users with usage."""
    users = svc.get_users_with_usage()
    if not users:
        return "暂无注册用户。"

    lines = ["👥 用户列表", ""]
    for u in users:
        status_icon = "✅" if u.get("status") == "active" else "❌"
        name = u.get("name") or u.get("user_id", "")[:16]
        today = u.get("today_tokens", 0)
        month = u.get("month_tokens", 0)
        lines.append(f"{status_icon} {name}")
        lines.append(f"   今日: {today:,} token | 本月: {month:,} token")
        uid_short = u.get("user_id", "")[:20]
        lines.append(f"   ID: {uid_short}...")
        lines.append("")

    summary = svc.get_global_summary()
    lines.append(f"━━━ 全局统计 ━━━")
    lines.append(f"总用户: {summary['total_users']} | 活跃: {summary['active_users']}")
    lines.append(f"今日总Token: {summary['today_tokens']:,} | 本月总Token: {summary['month_tokens']:,}")

    return "\n".join(lines)


def _format_user_detail(svc, user_id: str) -> str:
    """Format detailed usage for a specific user."""
    user = svc.get_user(user_id)
    if not user:
        return f"用户 {user_id} 不存在。"

    summary = svc.get_usage_summary(user_id)
    lines = [
        f"👤 用户详情",
        f"",
        f"ID: {user.user_id}",
        f"名称: {user.name or '(未设置)'}",
        f"渠道: {user.channel}",
        f"角色: {user.role}",
        f"状态: {'活跃' if user.status == 'active' else '已停用'}",
        f"",
        f"📊 用量统计:",
        f"  今日 Token: {summary.today_tokens:,} ({summary.today_requests} 请求)",
        f"  本月 Token: {summary.month_tokens:,} ({summary.month_requests} 请求)",
    ]

    if summary.quota:
        q = summary.quota
        lines.append("")
        lines.append("📋 配额:")
        dt = f"{q.daily_token_limit:,}" if q.daily_token_limit > 0 else "不限"
        mt = f"{q.monthly_token_limit:,}" if q.monthly_token_limit > 0 else "不限"
        cs = str(q.concurrent_session_limit) if q.concurrent_session_limit > 0 else "不限"
        rpm = str(q.rate_limit_per_minute) if q.rate_limit_per_minute > 0 else "不限"
        lines.append(f"  日Token: {dt} | 月Token: {mt}")
        lines.append(f"  并发: {cs} | RPM: {rpm}")

    return "\n".join(lines)


def _format_quota(svc, user_id: str) -> str:
    """Format quota for a specific user."""
    user = svc.get_user(user_id)
    if not user:
        return f"用户 {user_id} 不存在。"

    q = svc.get_quota(user_id)
    lines = [
        f"📋 配额设置 ({user.name or user_id[:16]})",
        f"",
        f"日Token上限: {q.daily_token_limit:,}" if q.daily_token_limit > 0 else "日Token上限: 不限",
        f"月Token上限: {q.monthly_token_limit:,}" if q.monthly_token_limit > 0 else "月Token上限: 不限",
        f"并发会话数: {q.concurrent_session_limit}" if q.concurrent_session_limit > 0 else "并发会话数: 不限",
        f"每分钟请求: {q.rate_limit_per_minute}" if q.rate_limit_per_minute > 0 else "每分钟请求: 不限",
        f"",
        f"修改配额: /admin setquota {user_id} <日token> <月token> <并发> <RPM>",
    ]
    return "\n".join(lines)


def _format_global_summary(svc) -> str:
    """Format global usage summary."""
    s = svc.get_global_summary()
    lines = [
        "📈 全局用量统计",
        "",
        f"总用户数: {s['total_users']}",
        f"活跃用户: {s['active_users']}",
        f"今日 Token: {s['today_tokens']:,}",
        f"今日请求: {s['today_requests']}",
        f"本月 Token: {s['month_tokens']:,}",
        f"本月请求: {s['month_requests']}",
    ]
    return "\n".join(lines)


def _format_help() -> str:
    """Format the help text for /admin commands."""
    return (
        "📖 /admin 命令帮助\n"
        "\n"
        "所有用户:\n"
        "  /admin              查看自己的用量与配额\n"
        "  /admin help         显示此帮助\n"
        "\n"
        "管理员:\n"
        "  /admin list         列出所有用户及用量\n"
        "  /admin user <id>    查看指定用户详情\n"
        "  /admin quota <id>   查看用户配额\n"
        "  /admin setquota <id> <日token> <月token> <并发> <RPM>\n"
        "                      设置配额 (0=不限)\n"
        "  /admin disable <id> 停用用户\n"
        "  /admin enable <id>  启用用户\n"
        "  /admin summary      全局用量统计"
    )
