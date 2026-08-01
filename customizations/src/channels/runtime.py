"""IM channel runtime that connects MessageBus traffic to SessionService."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.channels.bus.events import InboundMessage, OutboundMessage
from src.channels.bus.queue import MessageBus
from src.channels.manager import ChannelManager
from src.channels.pairing import PAIRING_COMMAND_META_KEY, handle_pairing_command
from src.config.paths import get_data_dir
from src.session.models import Message, Session

logger = logging.getLogger(__name__)


@dataclass
class ChannelRuntimeConfig:
    """Runtime controls for IM channel processing."""

    reply_timeout_s: float = 600.0
    poll_interval_s: float = 0.25


class ChannelRuntime:
    """Route inbound channel messages into Vibe-Trading sessions."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        session_service: Any,
        manager: ChannelManager | None,
        session_map_path: Path | None = None,
        reply_timeout_s: float = 600.0,
        poll_interval_s: float = 0.25,
        operators: Iterable[str] | None = None,
        channel_operators: Mapping[str, Iterable[str]] | None = None,
        quota_checker: Any = None,
        quota_releaser: Any = None,
    ) -> None:
        self.bus = bus
        self.session_service = session_service
        self.manager = manager
        self.config = ChannelRuntimeConfig(
            reply_timeout_s=reply_timeout_s,
            poll_interval_s=poll_interval_s,
        )
        # Channel-independent (global) operators may run /pairing on any channel
        # with cross-channel authority. Per-channel operators may run /pairing
        # only on their own channel. Both empty by default → IM /pairing is
        # fail-closed and pairing is managed via the authenticated CLI/REST plane.
        self._operators: set[str] = {str(o) for o in (operators or ())}
        self._channel_operators: dict[str, set[str]] = {
            str(ch): {str(o) for o in ops}
            for ch, ops in (channel_operators or {}).items()
        }
        self.session_map_path = session_map_path or (get_data_dir() / "channels" / "sessions.json")
        self._session_map: dict[str, str] = {}
        self._consumer_task: asyncio.Task[None] | None = None
        self._manager_task: asyncio.Task[Any] | None = None
        self._handler_tasks: set[asyncio.Task[None]] = set()
        self._running = False
        # Quota enforcement callbacks (injected by state.py)
        self._quota_checker = quota_checker      # Callable[[str, str], QuotaCheckResult]
        self._quota_releaser = quota_releaser    # Callable[[str], None]

    async def start(self, *, start_manager: bool = True) -> None:
        """Start channel processing and, optionally, platform adapters."""
        if self._running:
            return
        self._session_map = self._load_session_map()
        self._running = True
        if start_manager and self.manager is not None:
            self._manager_task = asyncio.create_task(self.manager.start_all())
            await asyncio.sleep(0)
        self._consumer_task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop channel processing and platform adapters."""
        self._running = False
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._consumer_task
            self._consumer_task = None
        for task in list(self._handler_tasks):
            task.cancel()
        for task in list(self._handler_tasks):
            with suppress(asyncio.CancelledError):
                await task
        self._handler_tasks.clear()
        if self.manager is not None:
            await self.manager.stop_all()
        if self._manager_task is not None:
            with suppress(asyncio.CancelledError):
                await self._manager_task
            self._manager_task = None

    def status(self) -> dict[str, Any]:
        """Return runtime and channel status."""
        return {
            "running": self._running,
            "inbound_queue": self.bus.inbound_size,
            "outbound_queue": self.bus.outbound_size,
            "session_count": len(self._session_map),
            "channels": self.manager.get_status() if self.manager is not None else {},
        }

    async def _consume_loop(self) -> None:
        while True:
            msg = await self.bus.consume_inbound()
            task = asyncio.create_task(self._handle_inbound(msg))
            self._handler_tasks.add(task)
            task.add_done_callback(self._handler_tasks.discard)

    async def _handle_inbound(self, msg: InboundMessage) -> None:
        try:
            if self._is_pairing_command(msg.content):
                is_operator, is_global = self._resolve_operator(msg.channel, msg.sender_id)
                if not is_operator:
                    logger.warning(
                        "Rejected /pairing from non-operator %s on %s",
                        msg.sender_id,
                        msg.channel,
                    )
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=(
                                "Not authorized: pairing management is restricted to "
                                "configured operators."
                            ),
                            metadata={PAIRING_COMMAND_META_KEY: True, "unauthorized": True},
                        )
                    )
                    return
                reply = handle_pairing_command(
                    msg.channel,
                    self._pairing_subcommand_text(msg.content),
                    requesting_channel=msg.channel,
                    is_global_operator=is_global,
                )
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={PAIRING_COMMAND_META_KEY: True},
                    )
                )
                return

            if self._is_new_session_command(msg.content):
                old_id = self.reset_session(msg.session_key)
                if old_id:
                    reply = "✅ Session reset. Your next message will start a new conversation."
                else:
                    reply = "ℹ️ No active session to reset."
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={"_channel_runtime": True, "session_reset": True},
                    )
                )
                return

            # --- /admin command: user management & usage queries ---
            if self._is_admin_command(msg.content):
                is_operator, _ = self._resolve_operator(msg.channel, msg.sender_id)
                try:
                    from src.usage.admin_commands import handle_admin_command
                    reply = handle_admin_command(
                        msg.sender_id,
                        self._admin_subcommand_text(msg.content),
                        is_operator=is_operator,
                    )
                except Exception as exc:
                    logger.warning("Admin command failed: %s", exc)
                    reply = f"管理命令执行失败: {exc}"
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={"_channel_runtime": True, "_admin_command": True},
                    )
                )
                return

            # --- /backtest command: direct strategy backtesting ---
            if self._is_backtest_command(msg.content):
                try:
                    from src.backtest_commands import handle_backtest_command
                    reply = handle_backtest_command(
                        msg.sender_id,
                        self._backtest_subcommand_text(msg.content),
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        bus=self.bus,
                    )
                except Exception as exc:
                    logger.warning("Backtest command failed: %s", exc)
                    reply = f"回测命令执行失败: {exc}"
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={"_channel_runtime": True, "_backtest_command": True},
                    )
                )
                return

            # --- /strategy command: strategy management ---
            if self._is_strategy_command(msg.content):
                try:
                    from src.strategy_commands import handle_strategy_command
                    reply = handle_strategy_command(
                        msg.sender_id,
                        self._strategy_subcommand_text(msg.content),
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        bus=self.bus,
                    )
                except Exception as exc:
                    logger.warning("Strategy command failed: %s", exc)
                    reply = f"策略命令执行失败: {exc}"
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={"_channel_runtime": True, "_strategy_command": True},
                    )
                )
                return

            # --- /factor command: factor management ---
            if self._is_factor_command(msg.content):
                try:
                    from src.strategy_commands import handle_factor_command
                    reply = handle_factor_command(
                        msg.sender_id,
                        self._factor_subcommand_text(msg.content),
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        bus=self.bus,
                    )
                except Exception as exc:
                    logger.warning("Factor command failed: %s", exc)
                    reply = f"因子命令执行失败: {exc}"
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply,
                        metadata={"_channel_runtime": True, "_factor_command": True},
                    )
                )
                return

            # --- Quota check: hard block if limits exceeded ---
            if self._quota_checker is not None:
                check_result = self._quota_checker(msg.sender_id, msg.channel)
                if not check_result.allowed:
                    logger.info(
                        "Quota blocked %s on %s: %s",
                        msg.sender_id, msg.channel, check_result.reason,
                    )
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=check_result.deny_message,
                            metadata={
                                "_channel_runtime": True,
                                "_quota_blocked": True,
                                "quota_reason": check_result.reason,
                            },
                        )
                    )
                    return

            session_id = self._session_for(msg)
            wants_stream = bool(msg.metadata.get("_wants_stream"))

            result = await self.session_service.send_message(
                session_id,
                msg.content,
                include_shell_tools=False,
                sender_id=msg.sender_id,
                channel=msg.channel,
            )
            attempt_id = result.get("attempt_id") if isinstance(result, dict) else None

            if wants_stream:
                # --- Streaming path: forward text_delta events to the channel ---
                stream_meta = {
                    "_stream_delta": True,
                    "_channel_runtime": True,
                    "attempt_id": attempt_id,
                    "session_id": session_id,
                    "message_id": msg.metadata.get("message_id"),
                    "chat_type": msg.metadata.get("chat_type", "p2p"),
                }
                thinking_text, result_text = await self._stream_reply(session_id, attempt_id, msg, stream_meta)
                # Final message: close the streaming card with the final result
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=result_text or thinking_text,
                        metadata={
                            **stream_meta,
                            "_stream_delta": False,
                            "_stream_end": True,
                            "_thinking_text": thinking_text,
                            "_result_text": result_text,
                        },
                    )
                )
            else:
                # --- Batch path: wait for complete reply, send once ---
                reply = await self._wait_for_reply(session_id, attempt_id)
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=reply.content,
                        metadata={
                            "_channel_runtime": True,
                            "attempt_id": attempt_id,
                            "session_id": session_id,
                        },
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - channel errors must surface to users
            logger.exception("Channel runtime failed for %s:%s", msg.channel, msg.chat_id)
            # Release concurrency slot on error if it was acquired
            if self._quota_releaser is not None:
                try:
                    self._quota_releaser(msg.sender_id)
                except Exception:
                    pass
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=f"Channel runtime error: {type(exc).__name__}: {exc}",
                    metadata={"_channel_runtime": True, "error": True},
                )
            )

    def _session_for(self, msg: InboundMessage) -> str:
        key = msg.session_key
        existing = self._session_map.get(key)
        if existing:
            return existing
        session = self.session_service.create_session(
            title=f"{msg.channel}:{msg.chat_id}",
            config={"channel": msg.channel, "channel_chat_id": msg.chat_id},
        )
        session_id = _session_id(session)
        self._session_map[key] = session_id
        self._save_session_map()
        return session_id

    async def _wait_for_reply(self, session_id: str, attempt_id: str | None) -> Message:
        deadline = time.monotonic() + self.config.reply_timeout_s
        last_assistant: Message | None = None
        while time.monotonic() < deadline:
            messages = self.session_service.get_messages(session_id, limit=200)
            for message in reversed(messages):
                if message.role != "assistant":
                    continue
                if attempt_id and message.linked_attempt_id != attempt_id:
                    if last_assistant is None:
                        last_assistant = message
                    continue
                return message
            await asyncio.sleep(self.config.poll_interval_s)
        if last_assistant is not None:
            return last_assistant
        raise TimeoutError("timed out waiting for assistant reply")

    async def _stream_reply(
        self,
        session_id: str,
        attempt_id: str | None,
        msg: InboundMessage,
        stream_meta: dict[str, Any],
    ) -> tuple[str, str]:
        """Stream agent text_delta events to the channel while polling for completion.

        Subscribes to the session EventBus and forwards each ``text_delta`` event
        as an ``_stream_delta`` OutboundMessage.  In parallel, polls
        ``get_messages`` to detect when the assistant reply is complete.

        Returns:
            A tuple of (thinking_text, result_text) where thinking_text is the
            accumulated streaming content (narration/COT) and result_text is the
            final assistant message content (the clean answer).
        """
        thinking_text = ""
        result_text = ""
        deadline = time.monotonic() + self.config.reply_timeout_s
        event_bus = getattr(self.session_service, "event_bus", None)

        # If no EventBus available, fall back to batch polling
        if event_bus is None:
            logger.warning("No EventBus on session_service, falling back to batch reply")
            reply = await self._wait_for_reply(session_id, attempt_id)
            return reply.content, reply.content

        # Subscribe to the session event stream
        sub_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with event_bus._lock:
            if session_id not in event_bus._subscribers:
                event_bus._subscribers[session_id] = []
            event_bus._subscribers[session_id].append(sub_queue)

        try:
            while time.monotonic() < deadline:
                # --- Drain event queue (non-blocking) ---
                while True:
                    try:
                        event = sub_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if event.event_type == "text_delta":
                        delta = event.data.get("delta", "")
                        if delta:
                            thinking_text += delta
                            await self.bus.publish_outbound(
                                OutboundMessage(
                                    channel=msg.channel,
                                    chat_id=msg.chat_id,
                                    content=delta,
                                    metadata=dict(stream_meta),
                                )
                            )

                # --- Check if assistant reply is complete ---
                messages = self.session_service.get_messages(session_id, limit=200)
                for message in reversed(messages):
                    if message.role != "assistant":
                        continue
                    if attempt_id and message.linked_attempt_id != attempt_id:
                        continue
                    # Reply found — result_text is the clean final answer
                    result_text = message.content or ""
                    if not thinking_text and result_text:
                        thinking_text = result_text
                    return thinking_text, result_text

                # Brief sleep before next poll
                await asyncio.sleep(self.config.poll_interval_s)

            # Timeout: return whatever we have
            logger.warning("Streaming reply timed out for session %s", session_id)
            return thinking_text, result_text
        finally:
            # Unsubscribe
            with event_bus._lock:
                subs = event_bus._subscribers.get(session_id, [])
                if sub_queue in subs:
                    subs.remove(sub_queue)

    def _load_session_map(self) -> dict[str, str]:
        try:
            data = json.loads(self.session_map_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            logger.warning("Ignoring invalid channel session map at %s", self.session_map_path)
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items() if value}

    def _save_session_map(self) -> None:
        self.session_map_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.session_map_path.with_suffix(self.session_map_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._session_map, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.session_map_path)

    def reset_session(self, session_key: str) -> str | None:
        """Remove a session mapping so the next message creates a fresh session.

        Args:
            session_key: The channel:chat_id key to reset.

        Returns:
            The removed session_id, or None if no mapping existed.
        """
        removed = self._session_map.pop(session_key, None)
        if removed is not None:
            self._save_session_map()
        return removed

    def _resolve_operator(self, channel: str, sender_id: str | None) -> tuple[bool, bool]:
        """Resolve pairing authorization for a sender.

        Args:
            channel: The channel the command arrived on.
            sender_id: The inbound message sender id.

        Returns:
            ``(is_operator, is_global_operator)``. ``is_operator`` is ``True``
            for global operators or per-channel operators of ``channel``;
            ``is_global_operator`` is ``True`` only for channel-independent
            operators, who may act cross-channel with full request details.
        """
        sid = str(sender_id)
        is_global = sid in self._operators
        is_channel = sid in self._channel_operators.get(channel, set())
        return (is_global or is_channel, is_global)

    @staticmethod
    def operators_from_config(
        config: Mapping[str, Any] | None,
    ) -> tuple[set[str], dict[str, set[str]]]:
        """Extract global and per-channel operators from a channels config dict.

        Args:
            config: The channels config mapping (as produced by
                ``ChannelsConfig.model_dump``). Top-level ``operators`` are
                global; a per-channel section's own ``operators`` list is
                channel-scoped.

        Returns:
            ``(global_operators, channel_operators)``.
        """
        if not config:
            return set(), {}
        global_ops = {str(o) for o in (config.get("operators") or ())}
        channel_ops: dict[str, set[str]] = {}
        for key, value in config.items():
            if isinstance(value, Mapping) and value.get("operators"):
                channel_ops[str(key)] = {str(o) for o in value["operators"]}
        return global_ops, channel_ops

    @staticmethod
    def _is_pairing_command(content: str) -> bool:
        stripped = content.strip().lower()
        return stripped == "/pairing" or stripped.startswith("/pairing ")

    @staticmethod
    def _pairing_subcommand_text(content: str) -> str:
        parts = content.strip().split(None, 1)
        return parts[1] if len(parts) > 1 else "list"

    @staticmethod
    def _is_new_session_command(content: str) -> bool:
        """Check if the message is a session reset command (/new, /reset, /newsession)."""
        return content.strip().lower() in ("/new", "/reset", "/newsession")

    @staticmethod
    def _is_admin_command(content: str) -> bool:
        """Check if the message is an /admin command."""
        stripped = content.strip().lower()
        return stripped == "/admin" or stripped.startswith("/admin ")

    @staticmethod
    def _admin_subcommand_text(content: str) -> str:
        """Extract the subcommand text after /admin."""
        parts = content.strip().split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _is_backtest_command(content: str) -> bool:
        """Check if the message is a /backtest command."""
        stripped = content.strip().lower()
        return stripped == "/backtest" or stripped.startswith("/backtest ")

    @staticmethod
    def _backtest_subcommand_text(content: str) -> str:
        """Extract the subcommand text after /backtest."""
        parts = content.strip().split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _is_strategy_command(content: str) -> bool:
        """Check if the message is a /strategy command."""
        stripped = content.strip().lower()
        return stripped == "/strategy" or stripped.startswith("/strategy ")

    @staticmethod
    def _strategy_subcommand_text(content: str) -> str:
        """Extract the subcommand text after /strategy."""
        parts = content.strip().split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    @staticmethod
    def _is_factor_command(content: str) -> bool:
        """Check if the message is a /factor command."""
        stripped = content.strip().lower()
        return stripped == "/factor" or stripped.startswith("/factor ")

    @staticmethod
    def _factor_subcommand_text(content: str) -> str:
        """Extract the subcommand text after /factor."""
        parts = content.strip().split(None, 1)
        return parts[1] if len(parts) > 1 else ""


def _session_id(session: Session | dict[str, Any] | Any) -> str:
    if isinstance(session, Session):
        return session.session_id
    if isinstance(session, dict):
        return str(session["session_id"])
    return str(getattr(session, "session_id"))
