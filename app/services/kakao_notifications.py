"""Kakao notification payload builders for trading events."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def publish_kakao_event(event: dict) -> dict:
    """Publish Kakao event (currently logs payload as transport placeholder)."""
    logger.info("Kakao event published: %s", event)
    return event


def extreme_news_score_event(symbol: str, news_score: float) -> dict:
    direction = "positive" if news_score >= 0 else "negative"
    return {
        "event_type": "extreme_news_score",
        "symbol": symbol.upper(),
        "news_score": news_score,
        "direction": direction,
        "message": f"[{symbol.upper()}] 극단 뉴스 점수 감지: {news_score:.2f}",
    }


def news_based_trade_event(symbol: str, side: str, news_score: float, quantity: int) -> dict:
    return {
        "event_type": "news_based_trade",
        "symbol": symbol.upper(),
        "side": side.upper(),
        "quantity": quantity,
        "news_score": news_score,
        "message": (
            f"[{symbol.upper()}] 뉴스 기반 {side.upper()} 체결: 수량 {quantity}, "
            f"뉴스점수 {news_score:.2f}"
        ),
    }


def news_crash_forced_sell_event(symbol: str, news_score: float, reason: str) -> dict:
    return {
        "event_type": "news_crash_forced_sell",
        "symbol": symbol.upper(),
        "news_score": news_score,
        "reason": reason,
        "message": (
            f"[{symbol.upper()}] 뉴스 급락으로 강제매도 검토 필요 "
            f"(score={news_score:.2f}, reason={reason})"
        ),
    }


def risk_blocked_event(symbol: str, reason: str, details: dict | None = None) -> dict:
    payload = details or {}
    return {
        "event_type": "risk_blocked",
        "symbol": symbol.upper(),
        "reason": reason,
        "details": payload,
        "message": f"[{symbol.upper()}] 리스크 가드로 주문 차단: {reason}",
    }
