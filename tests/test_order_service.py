from __future__ import annotations

import importlib
import sqlite3
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import SCHEMA_SQL

sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(
        settings=SimpleNamespace(
            paper_trading_enabled=True,
            enable_live_trading=False,
            paper_trading_initial_cash=1_000_000,
            commission_rate=0.00015,
            tax_rate=0.0018,
        )
    ),
)
sys.modules.setdefault("app.db", types.SimpleNamespace(get_session=lambda: None))

order_service = importlib.import_module("app.services.order_service")
paper_trading = importlib.import_module("app.services.paper_trading")


@pytest.fixture()
def temp_db_session(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

    @contextmanager
    def _session():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    return _session


def test_place_order_validates_side_before_any_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        order_service,
        "settings",
        SimpleNamespace(paper_trading_enabled=True, enable_live_trading=False),
    )
    monkeypatch.setattr(order_service, "simulate_buy", lambda *args, **kwargs: pytest.fail("BUY route should not be called"))
    monkeypatch.setattr(order_service, "simulate_sell", lambda *args, **kwargs: pytest.fail("SELL route should not be called"))

    with pytest.raises(ValueError, match="side must be BUY or SELL"):
        order_service.place_order("AAPL", "INVALID", 1, 100.0)


def test_paper_mode_never_calls_live_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        order_service,
        "settings",
        SimpleNamespace(paper_trading_enabled=True, enable_live_trading=True),
    )
    monkeypatch.setattr(order_service, "simulate_buy", lambda *args, **kwargs: {"cash": 1_000_000})
    monkeypatch.setattr(
        order_service,
        "_execute_live_order",
        lambda *args, **kwargs: pytest.fail("live api must never run when paper mode is enabled"),
    )

    result = order_service.place_order("AAPL", "BUY", 2, 100.0, reason="signal:test")

    assert result["mode"] == "paper"
    assert result["side"] == "BUY"


def test_simulate_buy_budget_calculates_quantity_and_records_reason(
    monkeypatch: pytest.MonkeyPatch,
    temp_db_session,
) -> None:
    monkeypatch.setattr(paper_trading, "get_session", temp_db_session)
    monkeypatch.setattr(
        paper_trading,
        "settings",
        SimpleNamespace(
            paper_trading_initial_cash=1_000,
            commission_rate=0.00015,
            tax_rate=0.0018,
        ),
    )

    paper_trading.initialize_account(initial_cash=1_000, reset=True)

    with pytest.raises(ValueError, match="too small"):
        paper_trading.simulate_buy("AAPL", price=100.0, budget=50.0, reason="budget-too-low")

    paper_trading.simulate_buy("AAPL", price=100.0, budget=500.0, reason="signal:breakout")
    paper_trading.simulate_sell("AAPL", price=120.0, quantity=2, reason="signal:take-profit")

    with temp_db_session() as conn:
        rows = conn.execute(
            "SELECT side, quantity, reason, is_live FROM trades ORDER BY id"
        ).fetchall()

    assert len(rows) == 2
    assert dict(rows[0]) == {
        "side": "BUY",
        "quantity": 4,
        "reason": "signal:breakout",
        "is_live": 0,
    }
    assert dict(rows[1]) == {
        "side": "SELL",
        "quantity": 2,
        "reason": "signal:take-profit",
        "is_live": 0,
    }
