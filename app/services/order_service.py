"""Order execution routing with paper/live safety guards."""

from __future__ import annotations

from app.config import settings
from app.db import get_session
from app.services.kakao_notifications import publish_kakao_event, risk_blocked_event
from app.services.paper_trading import simulate_buy, simulate_sell
from app.services.risk_manager import can_open_new_position


def place_order(symbol: str, side: str, quantity: int, price: float, reason: str = "manual") -> dict:
    normalized_side = side.upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")

    if normalized_side == "BUY":
        risk_check = can_open_new_position(symbol)
        if not risk_check["allowed"]:
            publish_kakao_event(
                risk_blocked_event(
                    symbol=symbol,
                    reason=risk_check["reason"],
                    details=risk_check.get("limits", {}),
                )
            )
            raise RuntimeError(f"BUY blocked by risk manager: {risk_check['reason']}")

    if settings.paper_trading_enabled:
        result = (
            simulate_buy(symbol, price, quantity * price, reason)
            if normalized_side == "BUY"
            else simulate_sell(symbol, price, quantity, reason)
        )
        return {"mode": "paper", "side": normalized_side, "summary": result}

    if not settings.enable_live_trading:
        raise RuntimeError("Live order route blocked: ENABLE_LIVE_TRADING=false")

    execution = _execute_live_order(symbol.upper(), normalized_side, quantity, price)
    _record_live_trade(symbol.upper(), normalized_side, quantity, price, reason)
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


def _record_live_trade(symbol: str, side: str, quantity: int, price: float, reason: str) -> None:
    gross_amount = quantity * price
    with get_session() as conn:
        conn.execute(
            """
            INSERT INTO trades(symbol, side, quantity, reason, price, gross_amount, fee, tax, net_amount, realized_pnl, is_live)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 0, 1)
            """,
            (symbol, side, quantity, reason, price, gross_amount, gross_amount),
        )
