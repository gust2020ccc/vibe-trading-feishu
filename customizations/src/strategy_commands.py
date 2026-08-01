"""Feishu /strategy and /factor command handlers.

Commands:
    /strategy                                   Show help
    /strategy list                              List my strategies
    /strategy show <id>                         Show strategy details
    /strategy create <name> <code...>           Create from pasted code
    /strategy nl <name> <description...>        Create from natural language
    /strategy publish <id>                      Publish to marketplace
    /strategy delete <id>                       Delete a strategy
    /strategy market [search]                   Browse marketplace

    /factor                                     Show help
    /factor list                                List my factors
    /factor show <id>                           Show factor details
    /factor create <name> <code...>             Create from pasted code
    /factor publish <id>                        Publish to marketplace
"""

from __future__ import annotations

import logging
import textwrap

logger = logging.getLogger(__name__)

_SEP = "━━━━━━━━━━━━━━━━━━"
_MAX_LIST = 10


# --------------------------------------------------------------------------- #
# /strategy command
# --------------------------------------------------------------------------- #
def handle_strategy_command(
    sender_id: str,
    subcommand_text: str,
    *,
    channel: str = "feishu",
    chat_id: str = "",
    bus=None,
) -> str:
    """Execute a /strategy subcommand and return the reply text.

    Args:
        sender_id: The sender's channel ID (e.g. Feishu open_id).
        subcommand_text: The text after /strategy.
        channel: Channel name.
        chat_id: Chat identifier.
        bus: Optional message bus.
    """
    # Split into at most 3 parts: subcommand, name/arg, rest (code/description)
    parts = subcommand_text.split(None, 2)

    if not parts or not parts[0]:
        return _strategy_help()

    sub = parts[0].lower()

    if sub in ("help", "?", "h"):
        return _strategy_help()

    if sub == "list":
        return _strategy_list(sender_id)

    if sub == "show" and len(parts) >= 2:
        return _strategy_show(parts[1])

    if sub == "create" and len(parts) >= 3:
        return _strategy_create(sender_id, parts[1], parts[2])

    if sub == "nl" and len(parts) >= 3:
        return _strategy_nl_create(sender_id, parts[1], parts[2])

    if sub == "publish" and len(parts) >= 2:
        return _strategy_publish(parts[1])

    if sub == "delete" and len(parts) >= 2:
        return _strategy_delete(sender_id, parts[1])

    if sub == "market":
        search = parts[1] if len(parts) > 1 else None
        return _strategy_market(search)

    return _strategy_help()


# --------------------------------------------------------------------------- #
# /factor command
# --------------------------------------------------------------------------- #
def handle_factor_command(
    sender_id: str,
    subcommand_text: str,
    *,
    channel: str = "feishu",
    chat_id: str = "",
    bus=None,
) -> str:
    """Execute a /factor subcommand and return the reply text."""
    # Split into at most 3 parts: subcommand, name/arg, rest (code)
    parts = subcommand_text.split(None, 2)

    if not parts or not parts[0]:
        return _factor_help()

    sub = parts[0].lower()

    if sub in ("help", "?", "h"):
        return _factor_help()

    if sub == "list":
        return _factor_list(sender_id)

    if sub == "show" and len(parts) >= 2:
        return _factor_show(parts[1])

    if sub == "create" and len(parts) >= 3:
        return _factor_create(sender_id, parts[1], parts[2])

    if sub == "publish" and len(parts) >= 2:
        return _factor_publish(parts[1])

    return _factor_help()


# --------------------------------------------------------------------------- #
# Strategy subcommands
# --------------------------------------------------------------------------- #
def _strategy_help() -> str:
    return textwrap.dedent("""\
        📋 策略管理命令

        /strategy list                          查看我的策略
        /strategy show <id>                     查看策略详情
        /strategy create <name> <code>          从代码创建策略
        /strategy nl <name> <description>       自然语言生成策略
        /strategy publish <id>                  发布到市场
        /strategy delete <id>                   删除策略
        /strategy market [search]               浏览策略市场
    """)


def _strategy_list(user_id: str) -> str:
    from src.strategy_manager.service import StrategyService

    items = StrategyService.list(user_id=user_id, limit=_MAX_LIST)
    if not items:
        return "📝 你还没有创建任何策略。\n用 /strategy nl <名称> <描述> 来自然语言生成一个吧！"

    lines = [f"📋 我的策略 (共{StrategyService.count(user_id=user_id)}个)", _SEP]
    for s in items:
        status_emoji = {"draft": "📝", "testing": "🧪", "published": "🌐", "archived": "📦"}.get(
            s.status, "❓"
        )
        lines.append(f"{status_emoji} {s.name}  [v{s.version}]")
        lines.append(f"   ID: {s.id}")
        lines.append(f"   状态: {s.status}  分类: {s.category}")
        if s.tags:
            lines.append(f"   标签: {', '.join(s.tags)}")
        lines.append("")
    return "\n".join(lines)


def _strategy_show(strategy_id: str) -> str:
    from src.strategy_manager.service import StrategyService

    s = StrategyService.get(strategy_id, include_code=False)
    if s is None:
        return f"❌ 策略 {strategy_id} 不存在"

    lines = [
        f"📋 策略详情: {s.name}",
        _SEP,
        f"ID: {s.id}",
        f"版本: v{s.version}",
        f"状态: {s.status}",
        f"分类: {s.category}",
        f"所有者: {s.user_id}",
    ]
    if s.description:
        lines.append(f"描述: {s.description}")
    if s.tags:
        lines.append(f"标签: {', '.join(s.tags)}")
    if s.is_public:
        lines.append(f"🌐 已发布 | 订阅: {s.subscriber_count} | 克隆: {s.clone_count} | 评分: {s.rating_avg:.1f}({s.rating_count})")
    lines.append(f"创建: {s.created_at}")
    lines.append(f"更新: {s.updated_at}")
    lines.append("")
    lines.append("💡 用 /backtest " + s.name_en + " 来回测此策略" if s.name_en else "")
    return "\n".join(lines)


def _strategy_create(user_id: str, name: str, code: str) -> str:
    from src.strategy_manager.service import StrategyService

    strategy, result = StrategyService.create(
        user_id=user_id,
        name=name,
        source_code=code,
    )
    if strategy is None:
        return f"❌ 创建失败:\n" + "\n".join(f"  - {e}" for e in result.errors)
    return (
        f"✅ 策略创建成功!\n"
        f"名称: {strategy.name}\n"
        f"ID: {strategy.id}\n"
        f"版本: v{strategy.version}\n"
        f"\n验证结果: {'通过' if result.valid else '失败'}"
    )


def _strategy_nl_create(user_id: str, name: str, description: str) -> str:
    """Generate strategy code from natural language and create it."""
    from src.strategy_manager.nl_generator import generate_strategy_from_nl

    code, error = generate_strategy_from_nl(description)
    if error:
        return f"❌ 自然语言生成失败:\n{error}"

    return _strategy_create(user_id, name, code)


def _strategy_publish(strategy_id: str) -> str:
    from src.strategy_manager.service import MarketService

    strategy = MarketService.publish_strategy(strategy_id)
    if strategy is None:
        return f"❌ 策略 {strategy_id} 不存在"
    return (
        f"🌐 策略已发布到市场!\n"
        f"名称: {strategy.name}\n"
        f"ID: {strategy.id}\n"
        f"现在其他用户可以克隆和订阅你的策略了。"
    )


def _strategy_delete(user_id: str, strategy_id: str) -> str:
    from src.strategy_manager.service import StrategyService

    # Check ownership
    s = StrategyService.get(strategy_id)
    if s is None:
        return f"❌ 策略 {strategy_id} 不存在"
    if s.user_id != user_id:
        return "❌ 无权删除: 你不是此策略的所有者"

    deleted = StrategyService.delete(strategy_id)
    if deleted:
        return f"✅ 策略 {s.name} 已删除"
    return f"❌ 删除失败"


def _strategy_market(search: str | None = None) -> str:
    from src.strategy_manager import db
    from src.strategy_manager.service import _row_to_strategy

    db.ensure_db()
    clauses = ["is_public = 1", "status = 'published'"]
    params: list = []
    if search:
        clauses.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " WHERE " + " AND ".join(clauses)
    conn = db.get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM strategies{where} ORDER BY subscriber_count DESC LIMIT {_MAX_LIST}",
            params,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "📝 市场上暂无策略。" + (f" (搜索: {search})" if search else "")

    items = [_row_to_strategy(r) for r in rows]
    lines = ["🌐 策略市场" + (f" (搜索: {search})" if search else ""), _SEP]
    for s in items:
        rating_str = f"⭐{s.rating_avg:.1f}" if s.rating_count > 0 else "暂无评分"
        lines.append(f"📊 {s.name}  [v{s.version}]")
        lines.append(f"   ID: {s.id}")
        lines.append(f"   订阅: {s.subscriber_count} | 克隆: {s.clone_count} | {rating_str}")
        if s.description:
            desc = s.description[:60] + "..." if len(s.description) > 60 else s.description
            lines.append(f"   {desc}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Factor subcommands
# --------------------------------------------------------------------------- #
def _factor_help() -> str:
    return textwrap.dedent("""\
        📋 因子管理命令

        /factor list                             查看我的因子
        /factor show <id>                        查看因子详情
        /factor create <name> <code>             从代码创建因子
        /factor publish <id>                     发布到市场
    """)


def _factor_list(user_id: str) -> str:
    from src.strategy_manager.service import FactorService

    items = FactorService.list(user_id=user_id, limit=_MAX_LIST)
    if not items:
        return "📝 你还没有创建任何因子。"

    lines = [f"📋 我的因子 (共{len(items)}个)", _SEP]
    for f in items:
        status_emoji = {"draft": "📝", "testing": "🧪", "published": "🌐"}.get(
            f.status, "❓"
        )
        lines.append(f"{status_emoji} {f.name}  [v{f.version}]")
        lines.append(f"   ID: {f.id}")
        lines.append(f"   状态: {f.status}  分类: {f.category}")
        lines.append("")
    return "\n".join(lines)


def _factor_show(factor_id: str) -> str:
    from src.strategy_manager.service import FactorService

    f = FactorService.get(factor_id, include_code=False)
    if f is None:
        return f"❌ 因子 {factor_id} 不存在"

    lines = [
        f"📋 因子详情: {f.name}",
        _SEP,
        f"ID: {f.id}",
        f"版本: v{f.version}",
        f"状态: {f.status}",
        f"分类: {f.category}",
    ]
    if f.description:
        lines.append(f"描述: {f.description}")
    if f.is_public:
        lines.append(f"🌐 已发布 | 订阅: {f.subscriber_count} | 克隆: {f.clone_count}")
    return "\n".join(lines)


def _factor_create(user_id: str, name: str, code: str) -> str:
    from src.strategy_manager.service import FactorService

    factor, result = FactorService.create(
        user_id=user_id,
        name=name,
        source_code=code,
    )
    if factor is None:
        return f"❌ 创建失败:\n" + "\n".join(f"  - {e}" for e in result.errors)
    return (
        f"✅ 因子创建成功!\n"
        f"名称: {factor.name}\n"
        f"ID: {factor.id}\n"
        f"版本: v{factor.version}"
    )


def _factor_publish(factor_id: str) -> str:
    from src.strategy_manager.service import MarketService

    factor = MarketService.publish_factor(factor_id)
    if factor is None:
        return f"❌ 因子 {factor_id} 不存在"
    return (
        f"🌐 因子已发布到市场!\n"
        f"名称: {factor.name}\n"
        f"ID: {factor.id}"
    )
