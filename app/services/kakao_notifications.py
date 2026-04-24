"""Kakao notification payload builders and transport helpers for trading events."""

from __future__ import annotations

import json
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def publish_kakao_event(event: dict) -> dict:
    """Publish Kakao event using configured token/URL.

    Delivery failures are intentionally non-fatal and only emitted as warnings.
    """
    logger.info("Kakao event queued: %s", event)

    access_token = settings.kakao_access_token.strip()
    if not access_token:
        logger.warning("Kakao event skipped (missing KAKAO_ACCESS_TOKEN). event_type=%s", event.get("event_type"))
        return event

    request_url = settings.kakao_api_url.strip() or DEFAULT_KAKAO_SEND_URL
    payload = _build_default_template_payload(event)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.post(
            request_url,
            data={"template_object": json.dumps(payload, ensure_ascii=False)},
            headers=headers,
            timeout=settings.kakao_timeout_seconds,
        )
        response.raise_for_status()
        logger.info("Kakao event sent successfully. event_type=%s", event.get("event_type"))
    except Exception as exc:  # noqa: BLE001 - transport failures must never interrupt trading flow
        logger.warning(
            "Kakao event send failed (non-fatal). event_type=%s error=%s",
            event.get("event_type"),
            exc,
        )

    return event


def _build_default_template_payload(event: dict) -> dict:
    message = str(event.get("message") or "자동매매 이벤트 알림")
    return {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com",
        },
    }


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


def high_risk_news_crash_event(symbol: str, news_score: float, reason: str) -> dict:
    return {
        "event_type": "high_risk_news_crash",
        "severity": "high",
        "symbol": symbol.upper(),
        "news_score": news_score,
        "reason": reason,
        "message": (
            f"[고위험][{symbol.upper()}] 뉴스 급락 강제매도 트리거 발생 "
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
