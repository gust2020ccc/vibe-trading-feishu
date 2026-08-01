"""Comprehensive unit tests for strategy_manager: validator, service, migration.

Uses an isolated temp database so production data is never touched.
Run with::

    python -m customizations.src.strategy_manager.tests.test_strategy_manager
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the customizations package is importable
_CUSTOMIZATIONS = Path(__file__).resolve().parents[4]
if str(_CUSTOMIZATIONS) not in sys.path:
    sys.path.insert(0, str(_CUSTOMIZATIONS))


# --------------------------------------------------------------------------- #
# Test fixtures
# --------------------------------------------------------------------------- #
VALID_STRATEGY_SOURCE = '''"""A valid test strategy."""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    """Test engine for unit tests."""

    def __init__(self, fast_period: int = 5, slow_period: int = 20):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {}
        for code, df in data_map.items():
            close = df["close"]
            ma_fast = close.rolling(self.fast_period).mean()
            ma_slow = close.rolling(self.slow_period).mean()
            signal = (ma_fast > ma_slow).astype(int)
            result[code] = signal.fillna(0)
        return result
'''

VALID_STRATEGY_V2 = '''"""A valid test strategy - v2 with different params."""
from typing import Dict
import pandas as pd
import numpy as np


class SignalEngine:
    """Test engine v2."""

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        result = {}
        for code, df in data_map.items():
            close = df["close"]
            ma_fast = close.rolling(self.fast_period).mean()
            ma_slow = close.rolling(self.slow_period).mean()
            signal = (ma_fast > ma_slow).astype(int)
            result[code] = signal.fillna(0)
        return result
'''

INVALID_STRATEGY_NO_CLASS = '''"""Missing SignalEngine class."""
import pandas as pd

def do_something():
    pass
'''

INVALID_STRATEGY_NO_GENERATE = '''"""Missing generate method."""
from typing import Dict
import pandas as pd


class SignalEngine:
    def __init__(self):
        pass
'''

INVALID_STRATEGY_SUBPROCESS = '''"""Forbidden import."""
import subprocess
from typing import Dict
import pandas as pd


class SignalEngine:
    def __init__(self):
        pass

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        return {}
'''

INVALID_STRATEGY_SYNTAX = '''"""Syntax error."""
class SignalEngine(
    def __init__(self):
        pass
'''

VALID_FACTOR_SOURCE = '''"""A valid alpha factor."""
from typing import Dict
import pandas as pd
import numpy as np


class Factor:
    """Test factor."""

    def __init__(self, window: int = 10):
        self.window = window

    def compute(self, panel: pd.DataFrame) -> pd.Series:
        return panel["close"].rolling(self.window).mean()
'''

VALID_FACTOR_FUNCTION = '''"""Module-level compute function factor."""
from typing import Dict
import pandas as pd


def compute(panel: pd.DataFrame) -> pd.Series:
    """Compute factor values."""
    return panel["close"].rolling(10).mean()
'''

INVALID_FACTOR_SUBPROCESS = '''"""Factor with forbidden import."""
import subprocess
import pandas as pd


class Factor:
    def compute(self, panel: pd.DataFrame) -> pd.Series:
        return panel["close"]
'''


# --------------------------------------------------------------------------- #
# Validator tests
# --------------------------------------------------------------------------- #
class TestValidator(unittest.TestCase):
    """Tests for AST-based source code validation."""

    def test_valid_strategy_passes(self):
        """A well-formed strategy source should pass validation."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(VALID_STRATEGY_SOURCE)
        self.assertTrue(result.valid, msg=f"Errors: {result.errors}")
        self.assertEqual(len(result.errors), 0)

    def test_metadata_extraction(self):
        """Validator should extract __init__ parameters as metadata."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(VALID_STRATEGY_SOURCE)
        params = result.metadata.get("parameters", [])
        self.assertEqual(len(params), 2)
        keys = {p["key"] for p in params}
        self.assertIn("fast_period", keys)
        self.assertIn("slow_period", keys)
        # Check defaults
        fast = next(p for p in params if p["key"] == "fast_period")
        self.assertEqual(fast["default"], 5)
        self.assertEqual(fast["type"], "int")

    def test_missing_signal_engine_class(self):
        """Source without SignalEngine class should fail."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(INVALID_STRATEGY_NO_CLASS)
        self.assertFalse(result.valid)
        self.assertTrue(any("SignalEngine" in e for e in result.errors))

    def test_missing_generate_method(self):
        """SignalEngine without generate method should fail."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(INVALID_STRATEGY_NO_GENERATE)
        self.assertFalse(result.valid)
        self.assertTrue(any("generate" in e for e in result.errors))

    def test_forbidden_import_subprocess(self):
        """Importing subprocess should be rejected."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(INVALID_STRATEGY_SUBPROCESS)
        self.assertFalse(result.valid)
        self.assertTrue(any("subprocess" in e for e in result.errors))

    def test_syntax_error(self):
        """Malformed Python should produce a syntax error."""
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(INVALID_STRATEGY_SYNTAX)
        self.assertFalse(result.valid)
        self.assertTrue(any("Syntax" in e for e in result.errors))

    def test_valid_factor_class(self):
        """A factor with Factor class + compute method should pass."""
        from src.strategy_manager.validator import validate_factor_source

        result = validate_factor_source(VALID_FACTOR_SOURCE)
        self.assertTrue(result.valid, msg=f"Errors: {result.errors}")

    def test_valid_factor_function(self):
        """A factor with module-level compute function should pass."""
        from src.strategy_manager.validator import validate_factor_source

        result = validate_factor_source(VALID_FACTOR_FUNCTION)
        self.assertTrue(result.valid, msg=f"Errors: {result.errors}")

    def test_invalid_factor_subprocess(self):
        """Factor importing subprocess should fail."""
        from src.strategy_manager.validator import validate_factor_source

        result = validate_factor_source(INVALID_FACTOR_SUBPROCESS)
        self.assertFalse(result.valid)

    def test_forbidden_os_system(self):
        """os.system() call should be rejected."""
        from src.strategy_manager.validator import validate_strategy_source

        source = VALID_STRATEGY_SOURCE.replace(
            "result[code] = signal.fillna(0)",
            "import os; os.system('echo hack')",
        )
        result = validate_strategy_source(source)
        self.assertFalse(result.valid)

    def test_forbidden_eval(self):
        """eval() call should be rejected."""
        from src.strategy_manager.validator import validate_strategy_source

        source = VALID_STRATEGY_SOURCE.replace(
            "result[code] = signal.fillna(0)",
            "eval('1+1')",
        )
        result = validate_strategy_source(source)
        self.assertFalse(result.valid)

    def test_forbidden_open_write(self):
        """open() with write mode should be rejected."""
        from src.strategy_manager.validator import validate_strategy_source

        source = VALID_STRATEGY_SOURCE.replace(
            "result[code] = signal.fillna(0)",
            "open('hack.txt', 'w').write('data')",
        )
        result = validate_strategy_source(source)
        self.assertFalse(result.valid)

    def test_decorators_rejected(self):
        """Decorators on methods should be rejected."""
        from src.strategy_manager.validator import validate_strategy_source

        source = VALID_STRATEGY_SOURCE.replace(
            "    def generate(",
            "    @staticmethod\n    def generate(",
        )
        result = validate_strategy_source(source)
        self.assertFalse(result.valid)
        self.assertTrue(any("decorator" in e.lower() for e in result.errors))


# --------------------------------------------------------------------------- #
# Strategy Service tests (CRUD + versioning)
# --------------------------------------------------------------------------- #
class TestStrategyService(unittest.TestCase):
    """Tests for StrategyService CRUD and version management."""

    @classmethod
    def setUpClass(cls):
        """Patch the DB path to use a temp file for all tests."""
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_strategies.db"

        # Patch get_db_path in db module
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()

        # Reset the _initialized flag so init_db runs fresh
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        """Clean strategies table before each test."""
        from src.strategy_manager import db
        conn = db.get_connection()
        try:
            conn.execute("DELETE FROM strategy_versions")
            conn.execute("DELETE FROM strategies")
            conn.execute("DELETE FROM strategy_subscriptions")
            conn.execute("DELETE FROM strategy_ratings")
            conn.commit()
        finally:
            conn.close()

    def test_create_strategy(self):
        """Creating a strategy should persist it with version 1."""
        from src.strategy_manager.service import StrategyService

        strategy, result = StrategyService.create(
            user_id="test_user",
            name="Test MA Cross",
            source_code=VALID_STRATEGY_SOURCE,
            name_en="test_ma_cross",
            description="Test strategy",
            category="trend",
            tags=["test", "ma"],
        )
        self.assertIsNotNone(strategy)
        self.assertTrue(result.valid)
        self.assertEqual(strategy.version, 1)
        self.assertEqual(strategy.name, "Test MA Cross")
        self.assertEqual(strategy.user_id, "test_user")
        self.assertEqual(set(strategy.tags), {"test", "ma"})
        # Source code excluded by default in get()
        self.assertEqual(strategy.source_code, "")

    def test_create_invalid_strategy(self):
        """Creating with invalid source should return None."""
        from src.strategy_manager.service import StrategyService

        strategy, result = StrategyService.create(
            user_id="test_user",
            name="Bad Strategy",
            source_code=INVALID_STRATEGY_NO_CLASS,
        )
        self.assertIsNone(strategy)
        self.assertFalse(result.valid)

    def test_get_strategy(self):
        """get() should return the strategy by ID."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user",
            name="Get Test",
            source_code=VALID_STRATEGY_SOURCE,
        )
        fetched = StrategyService.get(created.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Get Test")

    def test_get_strategy_include_code(self):
        """get(include_code=True) should include source code."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user",
            name="Code Test",
            source_code=VALID_STRATEGY_SOURCE,
        )
        fetched = StrategyService.get(created.id, include_code=True)
        self.assertIsNotNone(fetched)
        self.assertIn("SignalEngine", fetched.source_code)

    def test_get_nonexistent(self):
        """get() with unknown ID should return None."""
        from src.strategy_manager.service import StrategyService

        self.assertIsNone(StrategyService.get("nonexistent_id"))

    def test_list_strategies(self):
        """list() should return strategies with filters."""
        from src.strategy_manager.service import StrategyService

        StrategyService.create(
            user_id="user_a", name="A1", source_code=VALID_STRATEGY_SOURCE
        )
        StrategyService.create(
            user_id="user_b", name="B1", source_code=VALID_STRATEGY_SOURCE
        )
        StrategyService.create(
            user_id="user_a", name="A2", source_code=VALID_STRATEGY_SOURCE
        )

        all_items = StrategyService.list()
        self.assertEqual(len(all_items), 3)

        user_a_items = StrategyService.list(user_id="user_a")
        self.assertEqual(len(user_a_items), 2)

    def test_list_with_search(self):
        """list(search=...) should filter by name/description."""
        from src.strategy_manager.service import StrategyService

        StrategyService.create(
            user_id="u1", name="Momentum Burst", source_code=VALID_STRATEGY_SOURCE
        )
        StrategyService.create(
            user_id="u1", name="Mean Reversion", source_code=VALID_STRATEGY_SOURCE
        )

        results = StrategyService.list(search="Momentum")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Momentum Burst")

    def test_update_strategy_name(self):
        """Updating name (not code) should not increment version."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user", name="Original", source_code=VALID_STRATEGY_SOURCE
        )
        updated, result = StrategyService.update(created.id, name="Renamed")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.version, 1)  # no version bump

    def test_update_strategy_code(self):
        """Updating source code should increment version and save snapshot."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user", name="Version Test", source_code=VALID_STRATEGY_SOURCE
        )
        updated, result = StrategyService.update(
            created.id,
            source_code=VALID_STRATEGY_V2,
            changelog="Changed periods",
        )
        self.assertIsNotNone(updated)
        self.assertTrue(result.valid)
        self.assertEqual(updated.version, 2)

        # Check version history
        versions = StrategyService.list_versions(created.id)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version, 2)  # newest first

    def test_update_invalid_code(self):
        """Updating with invalid source should fail without modifying."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user", name="Bad Update", source_code=VALID_STRATEGY_SOURCE
        )
        updated, result = StrategyService.update(
            created.id, source_code=INVALID_STRATEGY_SUBPROCESS
        )
        # Should return existing strategy unchanged
        self.assertIsNotNone(updated)
        self.assertFalse(result.valid)
        self.assertEqual(updated.version, 1)  # unchanged

    def test_delete_strategy(self):
        """Deleting should remove the strategy."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user", name="Delete Me", source_code=VALID_STRATEGY_SOURCE
        )
        deleted = StrategyService.delete(created.id)
        self.assertTrue(deleted)
        self.assertIsNone(StrategyService.get(created.id))

    def test_delete_nonexistent(self):
        """Deleting unknown ID should return False."""
        from src.strategy_manager.service import StrategyService

        self.assertFalse(StrategyService.delete("nonexistent"))

    def test_version_rollback(self):
        """Rollback should restore old code as a new version."""
        from src.strategy_manager.service import StrategyService

        created, _ = StrategyService.create(
            user_id="test_user", name="Rollback Test", source_code=VALID_STRATEGY_SOURCE
        )
        # Update to v2
        StrategyService.update(created.id, source_code=VALID_STRATEGY_V2)
        # Rollback to v1
        rolled, result = StrategyService.rollback(created.id, 1)
        self.assertIsNotNone(rolled)
        self.assertTrue(result.valid)
        self.assertEqual(rolled.version, 3)  # new version, not old

        # Verify code matches v1
        source = StrategyService.get_source(created.id)
        self.assertIn("fast_period: int = 5", source)

    def test_version_pruning(self):
        """Old version snapshots should be pruned to MAX_VERSIONS."""
        from src.strategy_manager.service import StrategyService, MAX_VERSIONS

        created, _ = StrategyService.create(
            user_id="test_user", name="Prune Test", source_code=VALID_STRATEGY_SOURCE
        )
        # Create many versions
        for i in range(MAX_VERSIONS + 5):
            code = VALID_STRATEGY_V2.replace("fast_period: int = 10", f"fast_period: int = {10 + i}")
            StrategyService.update(created.id, source_code=code)

        versions = StrategyService.list_versions(created.id)
        self.assertLessEqual(len(versions), MAX_VERSIONS)

    def test_count_strategies(self):
        """count() should return the correct count."""
        from src.strategy_manager.service import StrategyService

        StrategyService.create(
            user_id="u1", name="C1", source_code=VALID_STRATEGY_SOURCE
        )
        StrategyService.create(
            user_id="u1", name="C2", source_code=VALID_STRATEGY_SOURCE, status="testing"
        )
        self.assertEqual(StrategyService.count(), 2)
        self.assertEqual(StrategyService.count(user_id="u1"), 2)
        self.assertEqual(StrategyService.count(status="testing"), 1)

    def test_to_dict_excludes_code(self):
        """to_dict() should exclude source_code by default."""
        from src.strategy_manager.models import Strategy

        s = Strategy(
            id="test", user_id="u", name="Test", source_code="SECRET CODE"
        )
        d = s.to_dict()
        self.assertNotIn("source_code", d)

    def test_to_dict_includes_code(self):
        """to_dict(include_code=True) should include source_code."""
        from src.strategy_manager.models import Strategy

        s = Strategy(
            id="test", user_id="u", name="Test", source_code="SECRET CODE"
        )
        d = s.to_dict(include_code=True)
        self.assertEqual(d["source_code"], "SECRET CODE")


# --------------------------------------------------------------------------- #
# Factor Service tests
# --------------------------------------------------------------------------- #
class TestFactorService(unittest.TestCase):
    """Tests for FactorService CRUD."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_factors.db"
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
            conn.execute("DELETE FROM factor_versions")
            conn.execute("DELETE FROM factors")
            conn.execute("DELETE FROM factor_subscriptions")
            conn.execute("DELETE FROM factor_ratings")
            conn.commit()
        finally:
            conn.close()

    def test_create_factor(self):
        """Creating a factor should persist it."""
        from src.strategy_manager.service import FactorService

        factor, result = FactorService.create(
            user_id="test_user",
            name="Test Factor",
            source_code=VALID_FACTOR_SOURCE,
            name_en="test_factor",
            category="momentum",
        )
        self.assertIsNotNone(factor)
        self.assertTrue(result.valid)
        self.assertEqual(factor.version, 1)

    def test_create_invalid_factor(self):
        """Creating with invalid source should fail."""
        from src.strategy_manager.service import FactorService

        factor, result = FactorService.create(
            user_id="test_user",
            name="Bad Factor",
            source_code=INVALID_FACTOR_SUBPROCESS,
        )
        self.assertIsNone(factor)
        self.assertFalse(result.valid)

    def test_update_factor_code(self):
        """Updating factor source should increment version."""
        from src.strategy_manager.service import FactorService

        created, _ = FactorService.create(
            user_id="test_user", name="Up Factor", source_code=VALID_FACTOR_SOURCE
        )
        updated, result = FactorService.update(
            created.id,
            source_code=VALID_FACTOR_SOURCE.replace("window: int = 10", "window: int = 20"),
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.version, 2)

    def test_delete_factor(self):
        """Deleting should remove the factor."""
        from src.strategy_manager.service import FactorService

        created, _ = FactorService.create(
            user_id="test_user", name="Del Factor", source_code=VALID_FACTOR_SOURCE
        )
        self.assertTrue(FactorService.delete(created.id))
        self.assertIsNone(FactorService.get(created.id))


# --------------------------------------------------------------------------- #
# Portfolio Service tests
# --------------------------------------------------------------------------- #
class TestPortfolioService(unittest.TestCase):
    """Tests for PortfolioService CRUD."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_portfolios.db"
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
            conn.execute("DELETE FROM factor_portfolios")
            conn.commit()
        finally:
            conn.close()

    def test_create_portfolio(self):
        """Creating a portfolio should persist it."""
        from src.strategy_manager.service import PortfolioService

        portfolio = PortfolioService.create(
            user_id="test_user",
            name="Test Portfolio",
            config={"factors": ["f1", "f2"], "weights": [0.5, 0.5]},
            description="Test multi-factor config",
        )
        self.assertIsNotNone(portfolio)
        self.assertEqual(portfolio.name, "Test Portfolio")
        self.assertIn("factors", portfolio.config)

    def test_get_portfolio(self):
        """get() should return the portfolio by ID."""
        from src.strategy_manager.service import PortfolioService

        created = PortfolioService.create(
            user_id="u1", name="P1", config={"factors": []}
        )
        fetched = PortfolioService.get(created.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "P1")

    def test_list_portfolios(self):
        """list() should filter by user_id."""
        from src.strategy_manager.service import PortfolioService

        PortfolioService.create(user_id="u1", name="P1", config={})
        PortfolioService.create(user_id="u2", name="P2", config={})
        PortfolioService.create(user_id="u1", name="P3", config={})

        self.assertEqual(len(PortfolioService.list(user_id="u1")), 2)
        self.assertEqual(len(PortfolioService.list()), 3)

    def test_update_portfolio(self):
        """Updating should change the config."""
        from src.strategy_manager.service import PortfolioService

        created = PortfolioService.create(
            user_id="u1", name="P1", config={"factors": ["a"]}
        )
        updated = PortfolioService.update(
            created.id, config={"factors": ["a", "b"]}, name="Updated P1"
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Updated P1")
        self.assertEqual(len(updated.config["factors"]), 2)

    def test_delete_portfolio(self):
        """Deleting should remove the portfolio."""
        from src.strategy_manager.service import PortfolioService

        created = PortfolioService.create(user_id="u1", name="Del", config={})
        self.assertTrue(PortfolioService.delete(created.id))
        self.assertIsNone(PortfolioService.get(created.id))


# --------------------------------------------------------------------------- #
# Market Service tests (publish, clone, rate, subscribe)
# --------------------------------------------------------------------------- #
class TestMarketService(unittest.TestCase):
    """Tests for MarketService marketplace operations."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_market.db"
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
            conn.execute("DELETE FROM strategy_versions")
            conn.execute("DELETE FROM strategies")
            conn.execute("DELETE FROM strategy_subscriptions")
            conn.execute("DELETE FROM strategy_ratings")
            conn.commit()
        finally:
            conn.close()

    def test_publish_strategy(self):
        """Publishing should set status=published, is_public=True."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Pub Test", source_code=VALID_STRATEGY_SOURCE
        )
        published = MarketService.publish_strategy(created.id)
        self.assertIsNotNone(published)
        self.assertEqual(published.status, "published")
        self.assertTrue(published.is_public)

    def test_archive_strategy(self):
        """Archiving should set status=archived, is_public=False."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Arch Test", source_code=VALID_STRATEGY_SOURCE
        )
        MarketService.publish_strategy(created.id)
        archived = MarketService.archive_strategy(created.id)
        self.assertEqual(archived.status, "archived")
        self.assertFalse(archived.is_public)

    def test_clone_strategy(self):
        """Cloning a published strategy should create an independent copy."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Clone Source", source_code=VALID_STRATEGY_SOURCE
        )
        MarketService.publish_strategy(created.id)

        clone, result = MarketService.clone_strategy(created.id, "cloner_user")
        self.assertIsNotNone(clone)
        self.assertTrue(result.valid)
        self.assertEqual(clone.user_id, "cloner_user")
        self.assertEqual(clone.parent_id, created.id)
        self.assertIn("clone", clone.name.lower())

        # Original clone_count should be incremented
        original = StrategyService.get(created.id)
        self.assertEqual(original.clone_count, 1)

    def test_clone_non_public_strategy(self):
        """Cloning a non-published strategy should fail."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Private", source_code=VALID_STRATEGY_SOURCE
        )
        # Not published
        clone, result = MarketService.clone_strategy(created.id, "cloner")
        self.assertIsNone(clone)
        self.assertFalse(result.valid)

    def test_rate_strategy(self):
        """Rating should update avg and count."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Rate Test", source_code=VALID_STRATEGY_SOURCE
        )
        self.assertTrue(MarketService.rate_strategy(created.id, "user1", 5))
        self.assertTrue(MarketService.rate_strategy(created.id, "user2", 3))

        rated = StrategyService.get(created.id)
        self.assertEqual(rated.rating_count, 2)
        self.assertAlmostEqual(rated.rating_avg, 4.0, places=1)

    def test_rate_strategy_upsert(self):
        """Re-rating should update, not insert."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Upsert Test", source_code=VALID_STRATEGY_SOURCE
        )
        MarketService.rate_strategy(created.id, "user1", 5)
        MarketService.rate_strategy(created.id, "user1", 2)  # change rating

        rated = StrategyService.get(created.id)
        self.assertEqual(rated.rating_count, 1)  # still 1 rater
        self.assertAlmostEqual(rated.rating_avg, 2.0, places=1)

    def test_rate_invalid_score(self):
        """Rating outside 1-5 should return False."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Invalid Rate", source_code=VALID_STRATEGY_SOURCE
        )
        self.assertFalse(MarketService.rate_strategy(created.id, "user1", 0))
        self.assertFalse(MarketService.rate_strategy(created.id, "user1", 6))

    def test_subscribe_strategy(self):
        """Subscribing should increment subscriber_count."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Sub Test", source_code=VALID_STRATEGY_SOURCE
        )
        self.assertTrue(MarketService.subscribe_strategy(created.id, "follower1"))
        subbed = StrategyService.get(created.id)
        self.assertEqual(subbed.subscriber_count, 1)

    def test_unsubscribe_strategy(self):
        """Unsubscribing should decrement subscriber_count."""
        from src.strategy_manager.service import StrategyService, MarketService

        created, _ = StrategyService.create(
            user_id="author", name="Unsub Test", source_code=VALID_STRATEGY_SOURCE
        )
        MarketService.subscribe_strategy(created.id, "follower1")
        self.assertTrue(MarketService.unsubscribe_strategy(created.id, "follower1"))
        subbed = StrategyService.get(created.id)
        self.assertEqual(subbed.subscriber_count, 0)


# --------------------------------------------------------------------------- #
# Migration tests
# --------------------------------------------------------------------------- #
class TestMigration(unittest.TestCase):
    """Tests for file-based strategy migration to DB."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_migration.db"
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
            conn.execute("DELETE FROM strategy_versions")
            conn.execute("DELETE FROM strategies")
            conn.commit()
        finally:
            conn.close()

    def test_migrate_valid_strategy(self):
        """Migrating a valid .py file should create a DB entry."""
        from src.strategy_manager.migration import migrate_custom_strategies

        # Create a temp dir with a valid strategy file
        with tempfile.TemporaryDirectory() as strat_dir:
            strat_path = Path(strat_dir) / "test_migrate.py"
            strat_path.write_text(VALID_STRATEGY_SOURCE, encoding="utf-8")

            report = migrate_custom_strategies(dirs=[Path(strat_dir)])
            self.assertEqual(report.scanned, 1)
            self.assertEqual(report.created, 1)
            self.assertEqual(report.failed, 0)

    def test_migrate_idempotent(self):
        """Re-running migration should skip already-migrated strategies."""
        from src.strategy_manager.migration import migrate_custom_strategies

        with tempfile.TemporaryDirectory() as strat_dir:
            strat_path = Path(strat_dir) / "test_idempotent.py"
            strat_path.write_text(VALID_STRATEGY_SOURCE, encoding="utf-8")

            # First run
            report1 = migrate_custom_strategies(dirs=[Path(strat_dir)])
            self.assertEqual(report1.created, 1)

            # Second run — should skip
            report2 = migrate_custom_strategies(dirs=[Path(strat_dir)])
            self.assertEqual(report2.created, 0)
            self.assertEqual(report2.skipped, 1)

    def test_migrate_invalid_strategy(self):
        """Migrating an invalid .py file should report failure."""
        from src.strategy_manager.migration import migrate_custom_strategies

        with tempfile.TemporaryDirectory() as strat_dir:
            strat_path = Path(strat_dir) / "bad_strategy.py"
            strat_path.write_text(INVALID_STRATEGY_NO_CLASS, encoding="utf-8")

            report = migrate_custom_strategies(dirs=[Path(strat_dir)])
            self.assertEqual(report.scanned, 1)
            self.assertEqual(report.failed, 1)
            self.assertEqual(report.created, 0)

    def test_migrate_dry_run(self):
        """Dry run should validate but not write to DB."""
        from src.strategy_manager.migration import migrate_custom_strategies
        from src.strategy_manager.service import StrategyService

        with tempfile.TemporaryDirectory() as strat_dir:
            strat_path = Path(strat_dir) / "dry_run_test.py"
            strat_path.write_text(VALID_STRATEGY_SOURCE, encoding="utf-8")

            report = migrate_custom_strategies(dirs=[Path(strat_dir)], dry_run=True)
            self.assertEqual(report.created, 1)
            # Nothing actually in DB
            self.assertEqual(len(StrategyService.list()), 0)

    def test_migration_report_summary(self):
        """MigrationReport.summary() should return a readable string."""
        from src.strategy_manager.migration import MigrationReport

        report = MigrationReport(scanned=5, created=2, skipped=2, failed=1)
        summary = report.summary()
        self.assertIn("5", summary)
        self.assertIn("2", summary)
        self.assertIn("1", summary)


# --------------------------------------------------------------------------- #
# DB tests
# --------------------------------------------------------------------------- #
class TestDatabase(unittest.TestCase):
    """Tests for database initialization and connection."""

    def test_init_db_idempotent(self):
        """init_db() should be safe to call multiple times."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "idempotent.db"
            with patch("src.strategy_manager.db.get_db_path", return_value=db_path):
                from src.strategy_manager import db

                db._initialized = False
                db.init_db()
                db.init_db()  # second call should be no-op
                self.assertTrue(db._initialized)

    def test_connection_wal_mode(self):
        """Connection should use WAL journal mode."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "wal_test.db"
            with patch("src.strategy_manager.db.get_db_path", return_value=db_path):
                from src.strategy_manager import db

                db._initialized = False
                db.init_db()
                conn = db.get_connection()
                try:
                    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                    self.assertEqual(mode.lower(), "wal")
                finally:
                    conn.close()

    def test_foreign_keys_enabled(self):
        """Foreign key constraints should be enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fk_test.db"
            with patch("src.strategy_manager.db.get_db_path", return_value=db_path):
                from src.strategy_manager import db

                db._initialized = False
                db.init_db()
                conn = db.get_connection()
                try:
                    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                    self.assertEqual(fk, 1)
                finally:
                    conn.close()


# --------------------------------------------------------------------------- #
# Model tests
# --------------------------------------------------------------------------- #
class TestModels(unittest.TestCase):
    """Tests for dataclass models and serialization."""

    def test_strategy_to_dict(self):
        """Strategy.to_dict() should serialize all fields."""
        from src.strategy_manager.models import Strategy

        s = Strategy(
            id="s1",
            user_id="u1",
            name="Test",
            tags=["a", "b"],
            meta={"key": "val"},
            version=3,
            status="published",
            is_public=True,
        )
        d = s.to_dict()
        self.assertEqual(d["id"], "s1")
        self.assertEqual(d["tags"], ["a", "b"])
        self.assertEqual(d["meta"], {"key": "val"})
        self.assertEqual(d["version"], 3)
        self.assertTrue(d["is_public"])
        self.assertNotIn("source_code", d)

    def test_strategy_version_to_dict(self):
        """StrategyVersion.to_dict() should serialize correctly."""
        from src.strategy_manager.models import StrategyVersion

        v = StrategyVersion(
            id="v1",
            strategy_id="s1",
            version=2,
            source_code="code",
            meta={"params": []},
            changelog="test",
        )
        d = v.to_dict()
        self.assertEqual(d["version"], 2)
        self.assertNotIn("source_code", d)
        d_code = v.to_dict(include_code=True)
        self.assertEqual(d_code["source_code"], "code")

    def test_factor_to_dict(self):
        """Factor.to_dict() should serialize all fields."""
        from src.strategy_manager.models import Factor

        f = Factor(id="f1", user_id="u1", name="Test Factor")
        d = f.to_dict()
        self.assertEqual(d["id"], "f1")
        self.assertNotIn("source_code", d)

    def test_portfolio_to_dict(self):
        """FactorPortfolio.to_dict() should serialize config."""
        from src.strategy_manager.models import FactorPortfolio

        p = FactorPortfolio(
            id="p1",
            user_id="u1",
            name="Portfolio",
            config={"weights": [0.3, 0.7]},
        )
        d = p.to_dict()
        self.assertEqual(d["config"], {"weights": [0.3, 0.7]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
