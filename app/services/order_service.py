"""Order execution routing with paper/live safety guards."""

from __future__ import annotations

from app.config import settings
from app.db import get_session
from app.services.paper_trading import simulate_buy, simulate_sell


def place_order(symbol: str, side: str, quantity: int, price: float) -> dict:
    normalized_side = side.upper()

    if settings.paper_trading_enabled:
        result = (
            simulate_buy(symbol, quantity, price)
            if normalized_side == "BUY"
            else simulate_sell(symbol, quantity, price)
        )
        return {"mode": "paper", "side": normalized_side, "summary": result}

    if not settings.enable_live_trading:
        raise RuntimeError("Live order route blocked: ENABLE_LIVE_TRADING=false")

    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")

    execution = _execute_live_order(symbol.upper(), normalized_side, quantity, price)
    _record_live_trade(symbol.upper(), normalized_side, quantity, price)
    return {"mode": "live", "execution": execution}


def _execute_live_order(symbol: str, side: str, quantity: int, price: float) -> dict:
    # 한국투자 실주문 API 연동 위치 (현재는 안전한 더미 응답)
    return {
        "broker": "koreainvestment",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "status": "submitted",
    }


def _record_live_trade(symbol: str, side: str, quantity: int, price: float) -> None:
    gross_amount = quantity * price
    with get_session() as conn:
        conn.execute(
            """
            INSERT INTO trades(symbol, side, quantity, price, gross_amount, fee, tax, net_amount, realized_pnl, is_live)
            VALUES (?, ?, ?, ?, ?, 0, 0, ?, 0, 1)
            """,
            (symbol, side, quantity, price, gross_amount, gross_amount),
        )
