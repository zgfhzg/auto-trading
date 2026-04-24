from __future__ import annotations

import importlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import SCHEMA_SQL

risk_manager = importlib.import_module("app.services.risk_manager")
strategy = importlib.import_module("app.services.strategy")


@pytest.fixture()
def temp_db_session(tmp_path: Path):
    db_path = tmp_path / "risk.sqlite3"
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


def test_check_daily_loss_limit_blocks_when_loss_exceeded(monkeypatch: pytest.MonkeyPatch, temp_db_session) -> None:
    monkeypatch.setattr(risk_manager, "get_session", temp_db_session)
    monkeypatch.setattr(risk_manager, "settings", SimpleNamespace(daily_max_loss_limit=100.0, max_holdings=3))

    with temp_db_session() as conn:
        conn.execute(
            """
            INSERT INTO trades(symbol, side, quantity, reason, price, gross_amount, fee, tax, net_amount, realized_pnl, is_live)
            VALUES ('AAPL', 'SELL', 1, 'loss-cut', 100, 100, 0, 0, 100, -150, 0)
            """
        )

    result = risk_manager.check_daily_loss_limit()
    assert result["blocked"] is True
    assert result["reason"] == "daily_loss_limit_exceeded"


def test_build_liquidation_candidates_uses_news_crash_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strategy, "get_news_score", lambda symbol: -0.9 if symbol == "AAPL" else 0.1)
    emitted: list[dict] = []
    monkeypatch.setattr(strategy, "publish_kakao_event", lambda event: emitted.append(event))

    candidates = strategy.build_liquidation_candidates(
        [
            {"symbol": "AAPL", "quantity": 3},
            {"symbol": "MSFT", "quantity": 2},
        ]
    )

    assert len(candidates) == 1
    assert candidates[0]["symbol"] == "AAPL"
    assert emitted
    assert emitted[0]["event_type"] == "news_crash_forced_sell"
