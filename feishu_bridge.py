#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书 ↔ Vibe-Trading 桥接服务
=============================
通过飞书自建应用机器人（WebSocket 长连接）接收用户消息，
调用 Vibe-Trading 进行股票分析/投研判断，并将结果返回飞书。

架构:
  用户飞书App ←(WebSocket长连接)→ 本桥接服务 ←(subprocess/API)→ Vibe-Trading ← LLM + 数据源

用法:
  1. 配好 .env（复制 .env.example 填入凭据）
  2. python feishu_bridge.py

依赖:
  pip install lark-oapi python-dotenv
"""

import os
import sys
import json
import re
import subprocess
import threading
import logging
import time
import traceback
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

# 优先加载脚本同目录的 .env
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "").strip()
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "").strip()

# Vibe-Trading 调用模式: cli (subprocess) 或 api (HTTP)
VIBE_TRADING_MODE = os.getenv("VIBE_TRADING_MODE", "cli").strip().lower()
VIBE_TRADING_API_URL = os.getenv("VIBE_TRADING_API_URL", "http://localhost:8899").strip()
VIBE_TRADING_API_KEY = os.getenv("VIBE_TRADING_API_KEY", "").strip()
VIBE_TRADING_BIN = os.getenv("VIBE_TRADING_BIN", "vibe-trading").strip()
VIBE_TRADING_TIMEOUT = int(os.getenv("VIBE_TRADING_TIMEOUT", "600"))
VIBE_TRADING_PYTHON = os.getenv("VIBE_TRADING_PYTHON", "").strip()  # 可选: 指定 python 解释器

# 消息设置
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "3500"))  # 单条消息最大字符(飞书文本上限较大，但分段更易读)
ACK_MESSAGE = os.getenv("ACK_MESSAGE", "⏳ 正在分析，请稍候…（复杂回测可能需要数分钟）")
WELCOME_TEXT = (
    "👋 你好！我是 Vibe-Trading 投研助手。\n\n"
    "直接发送自然语言指令即可，例如：\n"
    "• 分析一下贵州茅台的基本面和近期走势\n"
    "• 回测 BTC-USDT 的 20/50 均线交叉策略（2024年）\n"
    "• 帮我看看宁德时代最近有什么新闻\n"
    "• /help  查看帮助\n"
    "• /status  查看服务状态\n"
)

# 允许使用机器人的用户（open_id 白名单，逗号分隔；留空=不限制）
ALLOWED_OPEN_IDS = {
    s.strip() for s in os.getenv("ALLOWED_OPEN_IDS", "").split(",") if s.strip()
}

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("feishu_bridge")

# ---------------------------------------------------------------------------
# 导入飞书 SDK
# ---------------------------------------------------------------------------
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        ReplyMessageRequest,
        ReplyMessageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
    )
except ImportError:
    logger.error("缺少依赖 lark-oapi，请运行: pip install lark-oapi")
    sys.exit(1)


# ===========================================================================
# Vibe-Trading 调用层
# ===========================================================================
class VibeTradingRunner:
    """封装对 Vibe-Trading 的调用，支持 CLI(subprocess) 和 API(HTTP) 两种模式。"""

    def __init__(self):
        self.mode = VIBE_TRADING_MODE
        logger.info("Vibe-Trading 调用模式: %s", self.mode)
        if self.mode == "api":
            logger.info("API 地址: %s", VIBE_TRADING_API_URL)

    def analyze(self, prompt: str) -> str:
        """提交自然语言 prompt，返回分析结果文本。"""
        prompt = prompt.strip()
        if not prompt:
            return "请输入分析指令。"
        logger.info("开始分析, prompt=%s", prompt[:100])
        if self.mode == "api":
            return self._via_api(prompt)
        return self._via_cli(prompt)

    # --- CLI 模式 ---
    def _via_cli(self, prompt: str) -> str:
        cmd = self._build_cli_cmd(prompt)
        logger.info("执行命令: %s", " ".join(cmd[:3]) + " ...")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=VIBE_TRADING_TIMEOUT,
                encoding="utf-8",
                errors="replace",
                cwd=str(Path.home()),
            )
        except subprocess.TimeoutExpired:
            return f"⏱ 分析超时（{VIBE_TRADING_TIMEOUT}秒）。请简化指令或增加超时时间。"
        except FileNotFoundError:
            return (
                f"❌ 未找到命令 `{VIBE_TRADING_BIN}`。\n"
                "请确认 Vibe-Trading 已安装: pip install vibe-trading-ai\n"
                "或在 .env 中设置 VIBE_TRADING_BIN 为完整路径。"
            )

        output = ""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr and not output:
            output += proc.stderr
        output = self._clean_output(output)
        if not output.strip():
            output = "（分析完成，但未产生输出。请检查 Vibe-Trading 配置。）"
        return output

    def _build_cli_cmd(self, prompt: str) -> list:
        if VIBE_TRADING_PYTHON:
            return [VIBE_TRADING_PYTHON, "-m", "vibe_trading", "run", "-p", prompt]
        return [VIBE_TRADING_BIN, "run", "-p", prompt]

    # --- API 模式（预留，需确认 Vibe-Trading API Server 的 chat 接口） ---
    def _via_api(self, prompt: str) -> str:
        import urllib.request
        import urllib.error

        url = VIBE_TRADING_API_URL.rstrip("/") + "/run"
        payload = json.dumps({"prompt": prompt}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if VIBE_TRADING_API_KEY:
            headers["Authorization"] = f"Bearer {VIBE_TRADING_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=VIBE_TRADING_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("result") or data.get("output") or json.dumps(data, ensure_ascii=False, indent=2)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            return f"❌ API 调用失败 (HTTP {e.code}): {body}\n\n提示: 若 API Server 无 /run 接口，请在 .env 中设置 VIBE_TRADING_MODE=cli"
        except urllib.error.URLError as e:
            return f"❌ 无法连接 API Server ({VIBE_TRADING_API_URL}): {e.reason}\n请确认已运行: vibe-trading serve"

    @staticmethod
    def _clean_output(text: str) -> str:
        """清理终端输出中的 ANSI 颜色码等控制字符。"""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        text = ansi_escape.sub("", text)
        # 去除过多空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


# ===========================================================================
# 飞书消息工具
# ===========================================================================
class FeishuMessenger:
    """封装飞书消息的发送/回复。"""

    def __init__(self):
        self.client = (
            lark.Client.builder()
            .app_id(FEISHU_APP_ID)
            .app_secret(FEISHU_APP_SECRET)
            .log_level(lark.LogLevel.INFO)
            .build()
        )

    def reply_text(self, message_id: str, text: str) -> bool:
        """以文本消息回复指定消息。"""
        return self._reply(message_id, "text", json.dumps({"text": text}))

    def reply_markdown(self, message_id: str, title: str, content: str) -> bool:
        """以交互卡片（含 markdown）回复。"""
        elements = []
        if title:
            header = {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title},
            }
        else:
            header = None
        # 飞书 markdown 元素
        elements.append({"tag": "markdown", "content": content})
        card = {"elements": elements}
        if header:
            card["header"] = header
        return self._reply(message_id, "interactive", json.dumps(card))

    def send_text(self, receive_id: str, receive_id_type: str, text: str) -> bool:
        """主动发送文本消息给用户/群。"""
        return self._send(receive_id, receive_id_type, "text", json.dumps({"text": text}))

    def _reply(self, message_id: str, msg_type: str, content: str) -> bool:
        req = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        resp = self.client.im.v1.message.reply(req)
        if not resp.success():
            logger.warning("回复失败: code=%s msg=%s", resp.code, resp.msg)
            return False
        return True

    def _send(self, receive_id: str, receive_id_type: str, msg_type: str, content: str) -> bool:
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        resp = self.client.im.v1.message.create(req)
        if not resp.success():
            logger.warning("发送失败: code=%s msg=%s", resp.code, resp.msg)
            return False
        return True

    @staticmethod
    def split_text(text: str, max_len: int = MAX_TEXT_LENGTH) -> list:
        """将长文本按段落边界切分为多段。"""
        if len(text) <= max_len:
            return [text]
        parts = []
        while text:
            if len(text) <= max_len:
                parts.append(text)
                break
            # 尝试在换行处切分
            cut = text.rfind("\n", 0, max_len)
            if cut < max_len // 2:
                cut = max_len
            parts.append(text[:cut])
            text = text[cut:].lstrip("\n")
        return parts


# ===========================================================================
# 主机器人逻辑
# ===========================================================================
class VibeTradingFeishuBot:
    """飞书机器人主逻辑：接收消息 → 调用 Vibe-Trading → 返回结果。"""

    def __init__(self):
        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            logger.error("缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，请在 .env 中配置。")
            sys.exit(1)
        self.runner = VibeTradingRunner()
        self.messenger = FeishuMessenger()
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="analyze")
        self._active_tasks = 0
        self._lock = threading.Lock()
        self._start_time = time.time()
        logger.info("飞书桥接服务初始化完成")

    # --- 飞书事件回调 ---
    def on_message_receive(self, data) -> None:
        """处理 im.message.receive_v1 事件。"""
        try:
            event = data.event
            msg = event.message
            sender = event.sender

            # 白名单校验
            open_id = sender.sender_id.open_id if sender and sender.sender_id else ""
            if ALLOWED_OPEN_IDS and open_id and open_id not in ALLOWED_OPEN_IDS:
                logger.warning("用户 %s 不在白名单，忽略", open_id)
                return

            # 仅处理文本消息
            if msg.message_type != "text":
                self.messenger.reply_text(
                    msg.message_id,
                    "目前仅支持文本消息。请直接输入分析指令。",
                )
                return

            content = json.loads(msg.content) if msg.content else {}
            text = (content.get("text") or "").strip()
            # 去掉 @机器人 的前缀
            text = re.sub(r"@_user_\d+\s*", "", text).strip()
            if not text:
                return

            logger.info("收到消息: sender=%s chat=%s text=%s", open_id, msg.chat_id, text[:80])

            # 命令处理
            if text.startswith("/"):
                self._handle_command(msg, text)
                return

            # 提交异步分析
            self.messenger.reply_text(msg.message_id, ACK_MESSAGE)
            with self._lock:
                self._active_tasks += 1
            self.executor.submit(self._analyze_and_reply, msg, text)

        except Exception:
            logger.error("处理消息异常:\n%s", traceback.format_exc())

    def _handle_command(self, msg, text: str) -> None:
        cmd = text.lower().split()[0]
        if cmd in ("/help", "/h", "/？", "/?"):
            self.messenger.reply_text(msg.message_id, WELCOME_TEXT)
        elif cmd in ("/status", "/s"):
            uptime = int(time.time() - self._start_time)
            h, rem = divmod(uptime, 3600)
            m, s = divmod(rem, 60)
            info = (
                f"✅ 服务运行中\n"
                f"运行时长: {h}h {m}m {s}s\n"
                f"当前并发任务: {self._active_tasks}\n"
                f"调用模式: {self.runner.mode}\n"
            )
            if self.runner.mode == "api":
                info += f"API 地址: {VIBE_TRADING_API_URL}\n"
            self.messenger.reply_text(msg.message_id, info)
        else:
            self.messenger.reply_text(
                msg.message_id, f"未知命令: {cmd}\n输入 /help 查看帮助。"
            )

    def _analyze_and_reply(self, msg, prompt: str) -> None:
        """异步执行分析并回复结果。"""
        message_id = msg.message_id
        try:
            result = self.runner.analyze(prompt)
            self._send_result(message_id, prompt, result)
        except Exception as e:
            logger.error("分析异常:\n%s", traceback.format_exc())
            self.messenger.reply_text(message_id, f"❌ 分析出错: {e}")
        finally:
            with self._lock:
                self._active_tasks = max(0, self._active_tasks - 1)

    def _send_result(self, message_id: str, prompt: str, result: str) -> None:
        """发送分析结果，长文本自动分段。"""
        parts = FeishuMessenger.split_text(result)
        total = len(parts)
        for i, part in enumerate(parts, 1):
            title = f"📊 分析结果 ({i}/{total})" if total > 1 else "📊 分析结果"
            # 用 markdown 卡片发送，排版更好
            ok = self.messenger.reply_markdown(message_id, title, part)
            if not ok:
                # 卡片失败则降级为纯文本
                self.messenger.reply_text(message_id, f"{title}\n\n{part}")
            if i < total:
                time.sleep(0.3)  # 避免触发限频

    # --- 启动 ---
    def start(self) -> None:
        """启动 WebSocket 长连接。"""
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.on_message_receive)
            .build()
        )
        ws_client = lark.ws.Client(
            FEISHU_APP_ID,
            FEISHU_APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )
        logger.info("=" * 60)
        logger.info("Vibe-Trading 飞书桥接服务启动中…")
        logger.info("调用模式: %s", self.runner.mode)
        if ALLOWED_OPEN_IDS:
            logger.info("用户白名单: %d 人", len(ALLOWED_OPEN_IDS))
        else:
            logger.info("用户白名单: 未限制（所有可访问机器人的用户均可使用）")
        logger.info("=" * 60)
        # 阻塞运行
        ws_client.start()


# ===========================================================================
# 入口
# ===========================================================================
def main():
    bot = VibeTradingFeishuBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出。")
    except Exception:
        logger.error("服务异常退出:\n%s", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
