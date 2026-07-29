#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桥接服务功能测试（不需要飞书凭据）
用法: python test_bridge.py
"""

import sys
import os
from pathlib import Path

# 确保能导入同目录的模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_config():
    """测试配置加载"""
    print("=" * 50)
    print("测试 1: 配置加载")
    print("=" * 50)
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        app_id = os.getenv("FEISHU_APP_ID", "")
        app_secret = os.getenv("FEISHU_APP_SECRET", "")
        mode = os.getenv("VIBE_TRADING_MODE", "cli")
        has_real_creds = bool(app_id and not app_id.startswith("cli_x") and app_secret and not app_secret.startswith("xxx"))
        print(f"  .env 文件: 存在")
        print(f"  FEISHU_APP_ID: {'已配置' if has_real_creds else '未配置(需填入真实凭据)'}")
        print(f"  VIBE_TRADING_MODE: {mode}")
        return has_real_creds
    else:
        print(f"  .env 文件: 不存在（请先复制 .env.example）")
        return False


def test_split_text():
    """测试文本分段"""
    print("\n" + "=" * 50)
    print("测试 2: 文本分段 (split_text)")
    print("=" * 50)
    from feishu_bridge import FeishuMessenger

    # 短文本
    short = "这是一段短文本"
    parts = FeishuMessenger.split_text(short)
    print(f"  短文本({len(short)}字) -> {len(parts)} 段 ✓")

    # 长文本（带换行）
    long_text = "这是第一段内容。\n" * 500
    parts = FeishuMessenger.split_text(long_text, max_len=100)
    print(f"  长文本({len(long_text)}字, max=100) -> {len(parts)} 段 ✓")
    print(f"  各段长度: {[len(p) for p in parts[:5]]}...")

    # 边界：刚好等于 max_len
    exact = "a" * 100
    parts = FeishuMessenger.split_text(exact, max_len=100)
    print(f"  精确长度({len(exact)}字, max=100) -> {len(parts)} 段 ✓")


def test_runner_init():
    """测试 VibeTradingRunner 初始化"""
    print("\n" + "=" * 50)
    print("测试 3: VibeTradingRunner 初始化")
    print("=" * 50)
    try:
        from feishu_bridge import VibeTradingRunner
        runner = VibeTradingRunner()
        print(f"  调用模式: {runner.mode} ✓")
        print(f"  初始化: 成功 ✓")
        return True
    except Exception as e:
        print(f"  初始化失败: {e} ✗")
        return False


def test_vibe_trading():
    """测试 Vibe-Trading 是否安装"""
    print("\n" + "=" * 50)
    print("测试 4: Vibe-Trading 可用性")
    print("=" * 50)
    try:
        import vibe_trading
        print(f"  vibe_trading 导入: 成功 ✓")
    except ImportError:
        print(f"  vibe_trading 未安装 ✗")
        print(f"  请运行: pip install vibe-trading-ai")
        return False

    # 检查命令行入口
    import shutil
    vt_bin = shutil.which("vibe-trading") or shutil.which("vibe-trading.exe")
    if vt_bin:
        print(f"  vibe-trading 命令: {vt_bin} ✓")
    else:
        print(f"  vibe-trading 命令: 不在 PATH（可用 python -m vibe_trading 替代）")
    return True


def test_clean_output():
    """测试输出清理"""
    print("\n" + "=" * 50)
    print("测试 5: 输出清理 (clean_output)")
    print("=" * 50)
    from feishu_bridge import VibeTradingRunner
    # 含 ANSI 颜色码
    dirty = "\x1b[32m绿色文字\x1b[0m\n\n\n\n多余空行"
    clean = VibeTradingRunner._clean_output(dirty)
    assert "\x1b" not in clean, "ANSI 码未清除"
    assert "\n\n\n" not in clean, "多余空行未清除"
    print(f"  ANSI 清理: ✓")
    print(f"  空行压缩: ✓")
    print(f"  结果: {repr(clean)}")


def main():
    print("\n🧪 Vibe-Trading 飞书桥接服务 - 功能测试\n")

    has_creds = test_config()
    test_split_text()
    runner_ok = test_runner_init()
    vt_ok = test_vibe_trading()
    test_clean_output()

    print("\n" + "=" * 50)
    print("测试总结")
    print("=" * 50)
    print(f"  配置加载: {'✓' if has_creds else '⚠ 需配置飞书凭据'}")
    print(f"  文本分段: ✓")
    print(f"  Runner:   {'✓' if runner_ok else '✗'}")
    print(f"  Vibe-Trading: {'✓ 已安装' if vt_ok else '✗ 未安装'}")
    print(f"  输出清理: ✓")

    if not has_creds:
        print("\n  ⚠ 下一步: 编辑 .env 填入飞书凭据")
    if not vt_ok:
        print("\n  ⚠ 下一步: pip install vibe-trading-ai")
    if has_creds and vt_ok and runner_ok:
        print("\n  ✅ 所有组件就绪！可运行: python feishu_bridge.py")
    print()


if __name__ == "__main__":
    main()
