"""Tests for Feishu /strategy and /factor command handlers (Sprint 5).

Tests command parsing, formatting, and integration with the strategy
manager service using an isolated temp database.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure customizations package is importable
_CUSTOMIZATIONS = Path(__file__).resolve().parents[4]
if str(_CUSTOMIZATIONS) not in sys.path:
    sys.path.insert(0, str(_CUSTOMIZATIONS))


_VALID_SOURCE = '''"""Valid test strategy."""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    def __init__(self, fast: int = 5, slow: int = 20):
        self.fast = fast
        self.slow = slow

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {}
        for code, df in data_map.items():
            close = df["close"]
            ma_f = close.rolling(self.fast).mean()
            ma_s = close.rolling(self.slow).mean()
            result[code] = (ma_f > ma_s).astype(int).fillna(0)
        return result
'''

_VALID_FACTOR = '''"""Valid factor."""
from typing import Dict
import pandas as pd


class Factor:
    def __init__(self, window: int = 10):
        self.window = window

    def compute(self, panel: pd.DataFrame) -> pd.Series:
        return panel["close"].rolling(self.window).mean()
'''


class TestStrategyCommands(unittest.TestCase):
    """Tests for /strategy command handler."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_commands.db"
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        from src.strategy_manager import db
        conn = db.get_connection()
        try:
            for t in ["strategy_versions", "strategies", "strategy_subscriptions",
                       "strategy_ratings", "factor_versions", "factors",
                       "factor_subscriptions", "factor_ratings", "factor_portfolios"]:
                conn.execute(f"DELETE FROM {t}")
            conn.commit()
        finally:
            conn.close()

    def test_strategy_help(self):
        """ /strategy with no args should return help."""
        from src.strategy_commands import handle_strategy_command
        reply = handle_strategy_command("user1", "")
        self.assertIn("策略管理命令", reply)
        self.assertIn("list", reply)

    def test_strategy_list_empty(self):
        """/strategy list with no strategies should show empty message."""
        from src.strategy_commands import handle_strategy_command
        reply = handle_strategy_command("user1", "list")
        self.assertIn("还没有", reply)

    def test_strategy_list_with_data(self):
        """/strategy list should show created strategies."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService

        StrategyService.create(user_id="user1", name="Test Strat", source_code=_VALID_SOURCE)
        reply = handle_strategy_command("user1", "list")
        self.assertIn("Test Strat", reply)
        self.assertIn("我的策略", reply)

    def test_strategy_show(self):
        """/strategy show <id> should display details."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService

        s, _ = StrategyService.create(user_id="user1", name="Show Me", source_code=_VALID_SOURCE)
        reply = handle_strategy_command("user1", f"show {s.id}")
        self.assertIn("Show Me", reply)
        self.assertIn(s.id, reply)

    def test_strategy_show_not_found(self):
        """/strategy show with bad ID should show error."""
        from src.strategy_commands import handle_strategy_command
        reply = handle_strategy_command("user1", "show nonexistent")
        self.assertIn("不存在", reply)

    def test_strategy_create(self):
        """/strategy create should create a strategy from code."""
        from src.strategy_commands import handle_strategy_command
        reply = handle_strategy_command("user1", f"create TestCreate {_VALID_SOURCE}")
        self.assertIn("创建成功", reply)
        self.assertIn("TestCreate", reply)

    def test_strategy_create_invalid(self):
        """/strategy create with bad code should show validation errors."""
        from src.strategy_commands import handle_strategy_command
        bad_code = "import os\nos.system('rm -rf /')"
        reply = handle_strategy_command("user1", f"create BadCreate {bad_code}")
        self.assertIn("创建失败", reply)

    def test_strategy_publish(self):
        """/strategy publish should publish to marketplace."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService

        s, _ = StrategyService.create(user_id="user1", name="PubTest", source_code=_VALID_SOURCE)
        reply = handle_strategy_command("user1", f"publish {s.id}")
        self.assertIn("已发布", reply)

    def test_strategy_delete(self):
        """/strategy delete should remove the strategy."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService

        s, _ = StrategyService.create(user_id="user1", name="DelTest", source_code=_VALID_SOURCE)
        reply = handle_strategy_command("user1", f"delete {s.id}")
        self.assertIn("已删除", reply)

    def test_strategy_delete_not_owner(self):
        """/strategy delete by non-owner should be rejected."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService

        s, _ = StrategyService.create(user_id="owner", name="OwnerStrat", source_code=_VALID_SOURCE)
        reply = handle_strategy_command("hacker", f"delete {s.id}")
        self.assertIn("无权", reply)

    def test_strategy_market_empty(self):
        """/strategy market with no published should show empty."""
        from src.strategy_commands import handle_strategy_command
        reply = handle_strategy_command("user1", "market")
        self.assertIn("暂无", reply)

    def test_strategy_market_with_data(self):
        """/strategy market should show published strategies."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService, MarketService

        s, _ = StrategyService.create(user_id="user1", name="MarketStrat", source_code=_VALID_SOURCE)
        MarketService.publish_strategy(s.id)
        reply = handle_strategy_command("user2", "market")
        self.assertIn("MarketStrat", reply)
        self.assertIn("策略市场", reply)

    def test_strategy_market_search(self):
        """/strategy market <search> should filter results."""
        from src.strategy_commands import handle_strategy_command
        from src.strategy_manager.service import StrategyService, MarketService

        s1, _ = StrategyService.create(user_id="u", name="Momentum Hunter", source_code=_VALID_SOURCE)
        s2, _ = StrategyService.create(user_id="u", name="Mean Reversion", source_code=_VALID_SOURCE)
        MarketService.publish_strategy(s1.id)
        MarketService.publish_strategy(s2.id)

        reply = handle_strategy_command("user2", "market Momentum")
        self.assertIn("Momentum", reply)
        self.assertNotIn("Mean Reversion", reply)


class TestFactorCommands(unittest.TestCase):
    """Tests for /factor command handler."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_factor_commands.db"
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        from src.strategy_manager import db
        conn = db.get_connection()
        try:
            for t in ["factor_versions", "factors",
                       "factor_subscriptions", "factor_ratings", "factor_portfolios"]:
                conn.execute(f"DELETE FROM {t}")
            conn.commit()
        finally:
            conn.close()

    def test_factor_help(self):
        """/factor with no args should return help."""
        from src.strategy_commands import handle_factor_command
        reply = handle_factor_command("user1", "")
        self.assertIn("因子管理命令", reply)

    def test_factor_list_empty(self):
        """/factor list with no factors should show empty message."""
        from src.strategy_commands import handle_factor_command
        reply = handle_factor_command("user1", "list")
        self.assertIn("还没有", reply)

    def test_factor_list_with_data(self):
        """/factor list should show created factors."""
        from src.strategy_commands import handle_factor_command
        from src.strategy_manager.service import FactorService

        FactorService.create(user_id="user1", name="TestFactor", source_code=_VALID_FACTOR)
        reply = handle_factor_command("user1", "list")
        self.assertIn("TestFactor", reply)

    def test_factor_show(self):
        """/factor show <id> should display details."""
        from src.strategy_commands import handle_factor_command
        from src.strategy_manager.service import FactorService

        f, _ = FactorService.create(user_id="user1", name="ShowFactor", source_code=_VALID_FACTOR)
        reply = handle_factor_command("user1", f"show {f.id}")
        self.assertIn("ShowFactor", reply)

    def test_factor_create(self):
        """/factor create should create a factor from code."""
        from src.strategy_commands import handle_factor_command
        reply = handle_factor_command("user1", f"create TestFac {_VALID_FACTOR}")
        self.assertIn("创建成功", reply)

    def test_factor_publish(self):
        """/factor publish should publish to marketplace."""
        from src.strategy_commands import handle_factor_command
        from src.strategy_manager.service import FactorService

        f, _ = FactorService.create(user_id="user1", name="PubFactor", source_code=_VALID_FACTOR)
        reply = handle_factor_command("user1", f"publish {f.id}")
        self.assertIn("已发布", reply)


class TestNLGenerator(unittest.TestCase):
    """Tests for NL generator code extraction logic."""

    def test_extract_code_from_block(self):
        """Should extract code from ```python block."""
        from src.strategy_manager.nl_generator import _extract_code

        raw = 'Here is the code:\n```python\nclass SignalEngine:\n    pass\n```\nDone.'
        code = _extract_code(raw)
        self.assertIn("class SignalEngine", code)
        self.assertNotIn("```", code)
        self.assertNotIn("Done.", code)

    def test_extract_code_from_bare_block(self):
        """Should extract code from bare ``` block."""
        from src.strategy_manager.nl_generator import _extract_code

        raw = '```\nclass SignalEngine:\n    pass\n```'
        code = _extract_code(raw)
        self.assertIn("class SignalEngine", code)

    def test_extract_code_bare_text(self):
        """Should handle bare text with SignalEngine."""
        from src.strategy_manager.nl_generator import _extract_code

        raw = "class SignalEngine:\n    def generate(self, data_map):\n        pass"
        code = _extract_code(raw)
        self.assertIn("class SignalEngine", code)

    def test_generate_strategy_from_nl_mock(self):
        """Test NL generation with mocked LLM."""
        from src.strategy_manager.nl_generator import generate_strategy_from_nl

        # Mock LLM that returns valid code
        class MockResponse:
            content = f"```python\n{_VALID_SOURCE}\n```"

        class MockLLM:
            def invoke(self, messages):
                return MockResponse()

        code, error = generate_strategy_from_nl("MA crossover strategy", llm=MockLLM())
        self.assertIsNone(error)
        self.assertIsNotNone(code)
        self.assertIn("class SignalEngine", code)
        self.assertIn("def generate", code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
