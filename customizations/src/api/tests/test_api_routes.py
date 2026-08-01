"""Integration tests for Sprint 2 API routes.

Tests the strategy/factor/workbench API routes using FastAPI TestClient
with an isolated temp database.  No external server needed.

Run with::

    python -m customizations.src.api.tests.test_api_routes
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


# Test fixture — a valid strategy source
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

_INVALID_SOURCE = '''"""Invalid - no SignalEngine."""
import pandas as pd
def foo(): pass
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


class TestStrategyAPIRoutes(unittest.TestCase):
    """Integration tests for /strategies/* API routes."""

    @classmethod
    def setUpClass(cls):
        """Create a FastAPI app with strategy routes and temp DB."""
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_api.db"

        # Patch DB path
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()

        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

        from fastapi import FastAPI
        from src.api.strategy_routes import register_strategy_routes
        from src.api.factor_routes import register_factor_routes

        cls.app = FastAPI()
        register_strategy_routes(cls.app)
        register_factor_routes(cls.app)

        from fastapi.testclient import TestClient
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        """Clean DB before each test."""
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

    # ------------------------------------------------------------------ #
    # Strategy CRUD
    # ------------------------------------------------------------------ #
    def test_create_strategy_via_api(self):
        """POST /strategies should create a strategy."""
        resp = self.client.post("/strategies", json={
            "name": "API Test Strategy",
            "source_code": _VALID_SOURCE,
            "name_en": "api_test",
            "description": "Created via API test",
            "category": "trend",
            "tags": ["test", "api"],
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("strategy", data)
        self.assertEqual(data["strategy"]["name"], "API Test Strategy")
        self.assertTrue(data["validation"]["valid"])

    def test_create_invalid_strategy_via_api(self):
        """POST /strategies with invalid code should return 422."""
        resp = self.client.post("/strategies", json={
            "name": "Bad Strategy",
            "source_code": _INVALID_SOURCE,
        })
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertIn("errors", data["detail"])

    def test_list_strategies_via_api(self):
        """GET /strategies should return a list."""
        # Create two strategies
        self.client.post("/strategies", json={"name": "S1", "source_code": _VALID_SOURCE})
        self.client.post("/strategies", json={"name": "S2", "source_code": _VALID_SOURCE})

        resp = self.client.get("/strategies")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["strategies"]), 2)
        self.assertEqual(data["total"], 2)

    def test_get_strategy_by_id(self):
        """GET /strategies/{id} should return the strategy."""
        create = self.client.post("/strategies", json={
            "name": "Get Me", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.get(f"/strategies/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["strategy"]["name"], "Get Me")

    def test_get_strategy_not_found(self):
        """GET /strategies/{nonexistent} should return 404."""
        resp = self.client.get("/strategies/nonexistent_id")
        self.assertEqual(resp.status_code, 404)

    def test_update_strategy_via_api(self):
        """PUT /strategies/{id} should update name without version bump."""
        create = self.client.post("/strategies", json={
            "name": "Original", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.put(f"/strategies/{sid}", json={"name": "Renamed"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["strategy"]["name"], "Renamed")
        self.assertEqual(resp.json()["strategy"]["version"], 1)

    def test_update_strategy_code_via_api(self):
        """PUT with source_code should increment version."""
        create = self.client.post("/strategies", json={
            "name": "Version API", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        updated_code = _VALID_SOURCE.replace("fast: int = 5", "fast: int = 10")
        resp = self.client.put(f"/strategies/{sid}", json={
            "source_code": updated_code, "changelog": "Changed fast param"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["strategy"]["version"], 2)

    def test_delete_strategy_via_api(self):
        """DELETE /strategies/{id} should remove it."""
        create = self.client.post("/strategies", json={
            "name": "Delete Me", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.delete(f"/strategies/{sid}")
        self.assertEqual(resp.status_code, 200)

        # Verify gone
        resp2 = self.client.get(f"/strategies/{sid}")
        self.assertEqual(resp2.status_code, 404)

    # ------------------------------------------------------------------ #
    # Version management
    # ------------------------------------------------------------------ #
    def test_list_versions_via_api(self):
        """GET /strategies/{id}/versions should return version history."""
        create = self.client.post("/strategies", json={
            "name": "Versioned", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        # Update to create v2
        self.client.put(f"/strategies/{sid}", json={
            "source_code": _VALID_SOURCE.replace("5", "10")
        })

        resp = self.client.get(f"/strategies/{sid}/versions")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 2)
        # Newest first
        self.assertEqual(data["versions"][0]["version"], 2)

    def test_rollback_via_api(self):
        """POST /strategies/{id}/rollback/{ver} should create new version."""
        create = self.client.post("/strategies", json={
            "name": "Rollback API", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        # Create v2
        self.client.put(f"/strategies/{sid}", json={
            "source_code": _VALID_SOURCE.replace("5", "10")
        })

        # Rollback to v1
        resp = self.client.post(f"/strategies/{sid}/rollback/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["strategy"]["version"], 3)
        self.assertEqual(resp.json()["rolled_back_to"], 1)

    # ------------------------------------------------------------------ #
    # Marketplace
    # ------------------------------------------------------------------ #
    def test_publish_strategy_via_api(self):
        """POST /strategies/{id}/publish should set status=published."""
        create = self.client.post("/strategies", json={
            "name": "Publish Me", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.post(f"/strategies/{sid}/publish")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["strategy"]["status"], "published")
        self.assertTrue(resp.json()["strategy"]["is_public"])

    def test_clone_strategy_via_api(self):
        """POST /strategies/{id}/clone should create a copy."""
        create = self.client.post("/strategies", json={
            "name": "Clone Source", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        # Publish first
        self.client.post(f"/strategies/{sid}/publish")

        # Clone
        resp = self.client.post(f"/strategies/{sid}/clone", json={"user_id": "cloner"})
        self.assertEqual(resp.status_code, 200)
        clone = resp.json()["strategy"]
        self.assertEqual(clone["user_id"], "cloner")
        self.assertEqual(clone["parent_id"], sid)

    def test_clone_non_public_via_api(self):
        """Cloning a non-published strategy should fail with 422."""
        create = self.client.post("/strategies", json={
            "name": "Private", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.post(f"/strategies/{sid}/clone", json={"user_id": "cloner"})
        self.assertEqual(resp.status_code, 422)

    def test_rate_strategy_via_api(self):
        """POST /strategies/{id}/rate should update rating."""
        create = self.client.post("/strategies", json={
            "name": "Rate Me", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.post(f"/strategies/{sid}/rate", json={"rating": 5})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["rated"])
        self.assertAlmostEqual(resp.json()["rating_avg"], 5.0)

    def test_rate_invalid_score_via_api(self):
        """Rating outside 1-5 should fail."""
        create = self.client.post("/strategies", json={
            "name": "Bad Rate", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        resp = self.client.post(f"/strategies/{sid}/rate", json={"rating": 0})
        self.assertEqual(resp.status_code, 422)

    def test_subscribe_unsubscribe_via_api(self):
        """Subscribe then unsubscribe should work."""
        create = self.client.post("/strategies", json={
            "name": "Sub Test", "source_code": _VALID_SOURCE
        })
        sid = create.json()["strategy"]["id"]

        # Subscribe
        resp = self.client.post(f"/strategies/{sid}/subscribe", json={"user_id": "follower"})
        self.assertEqual(resp.status_code, 200)

        # Unsubscribe
        resp2 = self.client.delete(f"/strategies/{sid}/subscribe?user_id=follower")
        self.assertEqual(resp2.status_code, 200)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def test_search_strategies(self):
        """GET /strategies?search= should filter results."""
        self.client.post("/strategies", json={"name": "Momentum Burst", "source_code": _VALID_SOURCE})
        self.client.post("/strategies", json={"name": "Mean Reversion", "source_code": _VALID_SOURCE})

        resp = self.client.get("/strategies?search=Momentum")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["strategies"]), 1)
        self.assertEqual(data["strategies"][0]["name"], "Momentum Burst")


class TestFactorAPIRoutes(unittest.TestCase):
    """Integration tests for /factors/* API routes."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_factor_api.db"
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

        from fastapi import FastAPI
        from src.api.factor_routes import register_factor_routes
        cls.app = FastAPI()
        register_factor_routes(cls.app)

        from fastapi.testclient import TestClient
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        from src.strategy_manager import db
        conn = db.get_connection()
        try:
            for t in ["factor_versions", "factors", "factor_subscriptions",
                       "factor_ratings", "factor_portfolios"]:
                conn.execute(f"DELETE FROM {t}")
            conn.commit()
        finally:
            conn.close()

    def test_create_factor(self):
        """POST /factors should create a factor."""
        resp = self.client.post("/factors", json={
            "name": "Test Factor",
            "source_code": _VALID_FACTOR,
            "category": "momentum",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["factor"]["name"], "Test Factor")

    def test_list_factors(self):
        """GET /factors should list all factors."""
        self.client.post("/factors", json={"name": "F1", "source_code": _VALID_FACTOR})
        self.client.post("/factors", json={"name": "F2", "source_code": _VALID_FACTOR})

        resp = self.client.get("/factors")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["factors"]), 2)

    def test_delete_factor(self):
        """DELETE /factors/{id} should remove it."""
        create = self.client.post("/factors", json={"name": "Del", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        resp = self.client.delete(f"/factors/{fid}")
        self.assertEqual(resp.status_code, 200)

    def test_create_portfolio(self):
        """POST /factors/portfolios should create a portfolio."""
        resp = self.client.post("/factors/portfolios", json={
            "name": "Test Portfolio",
            "config": {"factors": ["f1", "f2"], "weights": [0.5, 0.5]},
            "description": "Test config",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["portfolio"]["name"], "Test Portfolio")

    def test_list_portfolios(self):
        """GET /factors/portfolios should list portfolios."""
        self.client.post("/factors/portfolios", json={
            "name": "P1", "config": {}
        })
        self.client.post("/factors/portfolios", json={
            "name": "P2", "config": {}
        })

        resp = self.client.get("/factors/portfolios")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["portfolios"]), 2)

    def test_delete_portfolio(self):
        """DELETE /factors/portfolios/{id} should remove it."""
        create = self.client.post("/factors/portfolios", json={
            "name": "Del P", "config": {}
        })
        pid = create.json()["portfolio"]["id"]

        resp = self.client.delete(f"/factors/portfolios/{pid}")
        self.assertEqual(resp.status_code, 200)

    def test_publish_factor(self):
        """POST /factors/{id}/publish should publish it."""
        create = self.client.post("/factors", json={"name": "Pub", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        resp = self.client.post(f"/factors/{fid}/publish")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["factor"]["status"], "published")

    def test_factor_version_management(self):
        """Factor version list + rollback via API."""
        create = self.client.post("/factors", json={"name": "Ver Factor", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        # Update to create v2
        updated = _VALID_FACTOR.replace("window: int = 10", "window: int = 20")
        self.client.put(f"/factors/{fid}", json={"source_code": updated})

        # List versions
        resp = self.client.get(f"/factors/{fid}/versions")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 2)
        self.assertEqual(resp.json()["versions"][0]["version"], 2)

        # Rollback to v1
        resp2 = self.client.post(f"/factors/{fid}/rollback/1")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["factor"]["version"], 3)
        self.assertEqual(resp2.json()["rolled_back_to"], 1)

    def test_factor_get_version(self):
        """GET /factors/{id}/versions/{ver} should return specific version."""
        create = self.client.post("/factors", json={"name": "GV Factor", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        resp = self.client.get(f"/factors/{fid}/versions/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["version"]["version"], 1)


class TestWorkbenchRoute(unittest.TestCase):
    """Test the /workbench HTML route."""

    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI
        from src.api.workbench_routes import register_workbench_routes
        cls.app = FastAPI()
        register_workbench_routes(cls.app)

        from fastapi.testclient import TestClient
        cls.client = TestClient(cls.app)

    def test_workbench_returns_html(self):
        """GET /workbench should return HTML content."""
        resp = self.client.get("/workbench")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("策略管理工作台", resp.text)
        self.assertIn("SignalEngine", resp.text)


class TestFactorSubscriptionAPI(unittest.TestCase):
    """Tests for factor subscribe/unsubscribe API (Sprint 4.3)."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_factor_sub.db"
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

        from fastapi import FastAPI
        from src.api.factor_routes import register_factor_routes
        cls.app = FastAPI()
        register_factor_routes(cls.app)

        from fastapi.testclient import TestClient
        cls.client = TestClient(cls.app)

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

    def test_subscribe_factor(self):
        """POST /factors/{id}/subscribe should subscribe a user."""
        create = self.client.post("/factors", json={"name": "SubFac", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        resp = self.client.post(f"/factors/{fid}/subscribe", json={"user_id": "sub_user"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["subscribed"])

    def test_unsubscribe_factor(self):
        """DELETE /factors/{id}/subscribe should unsubscribe."""
        create = self.client.post("/factors", json={"name": "UnsubFac", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        # Subscribe first
        self.client.post(f"/factors/{fid}/subscribe", json={"user_id": "sub_user"})

        # Unsubscribe
        resp = self.client.delete(f"/factors/{fid}/subscribe?user_id=sub_user")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["unsubscribed"])

    def test_unsubscribe_not_found(self):
        """Unsubscribing without prior subscription should return 404."""
        create = self.client.post("/factors", json={"name": "NoSub", "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]

        resp = self.client.delete(f"/factors/{fid}/subscribe?user_id=ghost")
        self.assertEqual(resp.status_code, 404)


class TestMarketplaceAPI(unittest.TestCase):
    """Tests for marketplace browsing API (Sprint 4.2)."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmpdir.name) / "test_marketplace.db"
        cls._patcher = patch(
            "src.strategy_manager.db.get_db_path",
            return_value=cls._db_path,
        )
        cls._patcher.start()
        from src.strategy_manager import db
        db._initialized = False
        db.init_db()

        from fastapi import FastAPI
        from src.api.strategy_routes import register_strategy_routes
        from src.api.factor_routes import register_factor_routes
        from src.api.marketplace_routes import register_marketplace_routes
        cls.app = FastAPI()
        register_strategy_routes(cls.app)
        register_factor_routes(cls.app)
        register_marketplace_routes(cls.app)

        from fastapi.testclient import TestClient
        cls.client = TestClient(cls.app)

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

    def _create_and_publish_strategy(self, name="MarketStrat"):
        """Helper: create + publish a strategy."""
        create = self.client.post("/strategies", json={"name": name, "source_code": _VALID_SOURCE})
        sid = create.json()["strategy"]["id"]
        self.client.post(f"/strategies/{sid}/publish")
        return sid

    def _create_and_publish_factor(self, name="MarketFactor"):
        """Helper: create + publish a factor."""
        create = self.client.post("/factors", json={"name": name, "source_code": _VALID_FACTOR})
        fid = create.json()["factor"]["id"]
        self.client.post(f"/factors/{fid}/publish")
        return fid

    def test_browse_strategies_empty(self):
        """GET /marketplace/strategies with no published should return empty."""
        resp = self.client.get("/marketplace/strategies")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    def test_browse_published_strategies(self):
        """GET /marketplace/strategies should return published ones."""
        self._create_and_publish_strategy("Published One")
        # Create but don't publish
        self.client.post("/strategies", json={"name": "Draft", "source_code": _VALID_SOURCE})

        resp = self.client.get("/marketplace/strategies")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["strategies"][0]["name"], "Published One")

    def test_browse_strategies_sort_by_name(self):
        """GET /marketplace/strategies?sort=name should sort alphabetically."""
        self._create_and_publish_strategy("Zebra")
        self._create_and_publish_strategy("Alpha")

        resp = self.client.get("/marketplace/strategies?sort=name")
        self.assertEqual(resp.status_code, 200)
        names = [s["name"] for s in resp.json()["strategies"]]
        self.assertEqual(names, ["Alpha", "Zebra"])

    def test_browse_strategies_search(self):
        """GET /marketplace/strategies?search= should filter."""
        self._create_and_publish_strategy("Momentum Hunter")
        self._create_and_publish_strategy("Mean Reversion")

        resp = self.client.get("/marketplace/strategies?search=Momentum")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_browse_factors(self):
        """GET /marketplace/factors should return published factors."""
        self._create_and_publish_factor("Pub Factor")
        resp = self.client.get("/marketplace/factors")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_featured_strategies(self):
        """GET /marketplace/strategies/featured should return lists."""
        sid = self._create_and_publish_strategy("Featured")
        # Rate it
        self.client.post(f"/strategies/{sid}/rate", json={"rating": 5})

        resp = self.client.get("/marketplace/strategies/featured")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("top_rated", data)
        self.assertIn("top_subscribed", data)
        self.assertIn("top_cloned", data)
        self.assertGreaterEqual(len(data["top_rated"]), 1)

    def test_featured_factors(self):
        """GET /marketplace/factors/featured should return lists."""
        self._create_and_publish_factor("Featured Factor")

        resp = self.client.get("/marketplace/factors/featured")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("top_rated", data)
        self.assertIn("top_subscribed", data)

    def test_marketplace_stats(self):
        """GET /marketplace/stats should return overview stats."""
        self._create_and_publish_strategy("Stat S")
        self._create_and_publish_factor("Stat F")

        resp = self.client.get("/marketplace/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("strategies", data)
        self.assertIn("factors", data)
        self.assertGreaterEqual(data["strategies"]["published_count"], 1)
        self.assertGreaterEqual(data["factors"]["published_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
