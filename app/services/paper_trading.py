"""Paper-trading service layer."""

from __future__ import annotations

from datetime import date

from app.config import settings
from app.db import get_session


def initialize_account(initial_cash: float | None = None, *, reset: bool = False) -> dict:
    seed_cash = float(initial_cash or settings.paper_trading_initial_cash)

    with get_session() as conn:
        if reset:
            conn.execute("DELETE FROM paper_positions")
            conn.execute("DELETE FROM paper_daily_snapshots")
            conn.execute("DELETE FROM trades WHERE is_live = 0")
            conn.execute("DELETE FROM paper_account")

        row = conn.execute("SELECT * FROM paper_account WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO paper_account (id, starting_cash, cash, realized_pnl, total_fees, total_taxes)
                VALUES (1, ?, ?, 0, 0, 0)
                """,
                (seed_cash, seed_cash),
            )

    return get_account_summary()


def simulate_buy(symbol: str, quantity: int, price: float) -> dict:
    _validate_order_inputs(symbol, quantity, price)
    symbol_upper = symbol.upper()
    gross_amount = quantity * price
    fee = gross_amount * settings.commission_rate
    tax = gross_amount * settings.tax_rate
    required_cash = gross_amount + fee + tax

    with get_session() as conn:
        _ensure_account(conn)
        account = conn.execute("SELECT * FROM paper_account WHERE id = 1").fetchone()
        if account["cash"] < required_cash:
            raise ValueError("Insufficient cash for paper buy order")

        position = conn.execute(
            "SELECT * FROM paper_positions WHERE symbol = ?", (symbol_upper,)
        ).fetchone()
        if position:
            new_quantity = int(position["quantity"]) + quantity
            new_avg_price = (
                (position["avg_price"] * position["quantity"]) + gross_amount
            ) / new_quantity
            conn.execute(
                """
                UPDATE paper_positions
                SET quantity = ?, avg_price = ?, market_price = ?,
                    unrealized_pnl = (?-?) * ?, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
                """,
                (
                    new_quantity,
                    new_avg_price,
                    price,
                    price,
                    new_avg_price,
                    new_quantity,
                    symbol_upper,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO paper_positions(symbol, quantity, avg_price, market_price, unrealized_pnl)
                VALUES (?, ?, ?, ?, 0)
                """,
                (symbol_upper, quantity, price, price),
            )

        conn.execute(
            """
            UPDATE paper_account
            SET cash = cash - ?, total_fees = total_fees + ?, total_taxes = total_taxes + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (required_cash, fee, tax),
        )

        _record_trade(
            conn,
            symbol=symbol_upper,
            side="BUY",
            quantity=quantity,
            price=price,
            gross_amount=gross_amount,
            fee=fee,
            tax=tax,
            net_amount=required_cash,
            realized_pnl=0.0,
            is_live=False,
        )

    return get_account_summary()


def simulate_sell(symbol: str, quantity: int, price: float) -> dict:
    _validate_order_inputs(symbol, quantity, price)
    symbol_upper = symbol.upper()
    gross_amount = quantity * price
    fee = gross_amount * settings.commission_rate
    tax = gross_amount * settings.tax_rate
    net_amount = gross_amount - fee - tax

    with get_session() as conn:
        _ensure_account(conn)
        position = conn.execute(
            "SELECT * FROM paper_positions WHERE symbol = ?", (symbol_upper,)
        ).fetchone()
        if position is None or position["quantity"] < quantity:
            raise ValueError("Insufficient quantity for paper sell order")

        avg_price = float(position["avg_price"])
        realized_pnl = (price - avg_price) * quantity - fee - tax
        remaining_qty = int(position["quantity"]) - quantity

        if remaining_qty == 0:
            conn.execute("DELETE FROM paper_positions WHERE symbol = ?", (symbol_upper,))
        else:
            conn.execute(
                """
                UPDATE paper_positions
                SET quantity = ?, market_price = ?,
                    unrealized_pnl = (?-avg_price) * ?, updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
                """,
                (remaining_qty, price, price, remaining_qty, symbol_upper),
            )

        conn.execute(
            """
            UPDATE paper_account
            SET cash = cash + ?, realized_pnl = realized_pnl + ?,
                total_fees = total_fees + ?, total_taxes = total_taxes + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (net_amount, realized_pnl, fee, tax),
        )

        _record_trade(
            conn,
            symbol=symbol_upper,
            side="SELL",
            quantity=quantity,
            price=price,
            gross_amount=gross_amount,
            fee=fee,
            tax=tax,
            net_amount=net_amount,
            realized_pnl=realized_pnl,
            is_live=False,
        )

    return get_account_summary()


def update_valuation(prices: dict[str, float]) -> dict:
    with get_session() as conn:
        _ensure_account(conn)
        for symbol, market_price in prices.items():
            normalized = symbol.upper()
            conn.execute(
                """
                UPDATE paper_positions
                SET market_price = ?, unrealized_pnl = (? - avg_price) * quantity,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = ?
                """,
                (float(market_price), float(market_price), normalized),
            )
    return get_account_summary()


def get_account_summary() -> dict:
    with get_session() as conn:
        _ensure_account(conn)
        account = conn.execute("SELECT * FROM paper_account WHERE id = 1").fetchone()
        rows = conn.execute(
            """
            SELECT symbol, quantity, avg_price, market_price, unrealized_pnl
            FROM paper_positions
            ORDER BY symbol
            """
        ).fetchall()

    positions = [dict(row) for row in rows]
    market_value = sum(float(p["market_price"]) * int(p["quantity"]) for p in positions)
    unrealized = sum(float(p["unrealized_pnl"]) for p in positions)
    cash = float(account["cash"])
    equity = cash + market_value
    starting_cash = float(account["starting_cash"])

    return {
        "mode": "paper",
        "starting_cash": starting_cash,
        "cash": cash,
        "market_value": market_value,
        "equity": equity,
        "realized_pnl": float(account["realized_pnl"]),
        "unrealized_pnl": unrealized,
        "total_fees": float(account["total_fees"]),
        "total_taxes": float(account["total_taxes"]),
        "cumulative_return": ((equity - starting_cash) / starting_cash) if starting_cash else 0.0,
        "positions": positions,
        "commission_rate": settings.commission_rate,
        "tax_rate": settings.tax_rate,
    }


def get_return_report(limit: int = 30) -> dict:
    with get_session() as conn:
        snapshots = conn.execute(
            """
            SELECT snapshot_date, equity, cash, market_value, realized_pnl,
                   unrealized_pnl, daily_return, cumulative_return
            FROM paper_daily_snapshots
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (max(limit, 1),),
        ).fetchall()

    return {
        "summary": get_account_summary(),
        "daily_snapshots": [dict(row) for row in snapshots],
    }


def create_daily_snapshot(snapshot_date: date | None = None) -> dict:
    summary = get_account_summary()
    snapshot_key = (snapshot_date or date.today()).isoformat()

    with get_session() as conn:
        previous = conn.execute(
            """
            SELECT equity FROM paper_daily_snapshots
            WHERE snapshot_date < ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (snapshot_key,),
        ).fetchone()

        prev_equity = float(previous["equity"]) if previous else summary["starting_cash"]
        daily_return = (
            (summary["equity"] - prev_equity) / prev_equity if prev_equity else 0.0
        )

        conn.execute(
            """
            INSERT INTO paper_daily_snapshots(
                snapshot_date, equity, cash, market_value, realized_pnl,
                unrealized_pnl, daily_return, cumulative_return
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date) DO UPDATE SET
                equity = excluded.equity,
                cash = excluded.cash,
                market_value = excluded.market_value,
                realized_pnl = excluded.realized_pnl,
                unrealized_pnl = excluded.unrealized_pnl,
                daily_return = excluded.daily_return,
                cumulative_return = excluded.cumulative_return
            """,
            (
                snapshot_key,
                summary["equity"],
                summary["cash"],
                summary["market_value"],
                summary["realized_pnl"],
                summary["unrealized_pnl"],
                daily_return,
                summary["cumulative_return"],
            ),
        )

    return {"snapshot_date": snapshot_key, **summary}


def list_positions() -> list[dict]:
    return get_account_summary()["positions"]


def _ensure_account(conn) -> None:
    account = conn.execute("SELECT id FROM paper_account WHERE id = 1").fetchone()
    if account is None:
        conn.execute(
            """
            INSERT INTO paper_account (id, starting_cash, cash, realized_pnl, total_fees, total_taxes)
            VALUES (1, ?, ?, 0, 0, 0)
            """,
            (float(settings.paper_trading_initial_cash), float(settings.paper_trading_initial_cash)),
        )


def _record_trade(
    conn,
    *,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    gross_amount: float,
    fee: float,
    tax: float,
    net_amount: float,
    realized_pnl: float,
    is_live: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO trades(symbol, side, quantity, price, gross_amount, fee, tax, net_amount, realized_pnl, is_live)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol,
            side,
            quantity,
            price,
            gross_amount,
            fee,
            tax,
            net_amount,
            realized_pnl,
            1 if is_live else 0,
        ),
    )


def _validate_order_inputs(symbol: str, quantity: int, price: float) -> None:
    if not symbol or not symbol.strip():
        raise ValueError("symbol is required")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if price <= 0:
        raise ValueError("price must be positive")
