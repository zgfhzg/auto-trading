"""Pre-trade risk checks for position/capital protection."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.db import get_session


def check_daily_loss_limit(*, now: datetime | None = None) -> dict:
    """Check if realized daily PnL breaches configured max loss limit."""
    ts = now or datetime.now(tz=timezone.utc)
    day_start = ts.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    with get_session() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(realized_pnl), 0) AS daily_realized_pnl
            FROM trades
            WHERE created_at >= ?
            """,
            (day_start.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()

    daily_realized_pnl = float(row["daily_realized_pnl"] if row else 0.0)
    limit = float(settings.daily_max_loss_limit)
    blocked = daily_realized_pnl <= (-1.0 * limit)

    return {
        "blocked": blocked,
        "daily_realized_pnl": daily_realized_pnl,
        "daily_max_loss_limit": limit,
        "reason": "daily_loss_limit_exceeded" if blocked else "ok",
    }


def can_open_new_position(symbol: str) -> dict:
    """Validate whether a new BUY can open/increase a position."""
    daily_loss = check_daily_loss_limit()
    if daily_loss["blocked"]:
        return {
            "allowed": False,
            "reason": "daily_loss_limit_exceeded",
            "symbol": symbol.upper(),
            "limits": daily_loss,
        }

    with get_session() as conn:
        current_holdings = conn.execute(
            """
            SELECT COUNT(*) AS holdings
            FROM paper_positions
            WHERE quantity > 0
            """
        ).fetchone()["holdings"]
        existing = conn.execute(
            """
            SELECT 1
            FROM paper_positions
            WHERE symbol = ? AND quantity > 0
            LIMIT 1
            """,
            (symbol.upper(),),
        ).fetchone()

    max_holdings = int(settings.max_holdings)
    is_existing_symbol = existing is not None
    blocked_by_holdings = (not is_existing_symbol) and int(current_holdings) >= max_holdings

    if blocked_by_holdings:
        return {
            "allowed": False,
            "reason": "max_holdings_reached",
            "symbol": symbol.upper(),
            "limits": {
                "max_holdings": max_holdings,
                "current_holdings": int(current_holdings),
            },
        }

    return {
        "allowed": True,
        "reason": "ok",
        "symbol": symbol.upper(),
        "limits": {
            "max_holdings": max_holdings,
            "current_holdings": int(current_holdings),
            "daily_loss": daily_loss,
        },
    }
