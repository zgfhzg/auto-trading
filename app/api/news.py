"""News API router."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from app.config import settings
from app.db import get_session
from app.services.news_collector import RssNewsSource, collect_and_store
from app.services.news_signal import get_news_score

router = APIRouter(prefix="/news", tags=["news"])

@router.get("")
def list_news(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    with get_session() as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, title, content, source,
                   related_symbols, sentiment_score, created_at
            FROM news_items
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return {"items": [_row_to_dict(row) for row in rows]}


@router.get("/score/{symbol}")
def news_score(symbol: str, hours: int = Query(default=6, ge=1, le=72)) -> dict:
    return {"symbol": symbol.upper(), "hours": hours, "score": get_news_score(symbol, hours)}


@router.get("/{symbol}")
def list_news_by_symbol(
    symbol: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    symbol_upper = symbol.upper()
    with get_session() as conn:
        rows = conn.execute(
            """
            SELECT id, timestamp, title, content, source,
                   related_symbols, sentiment_score, created_at
            FROM news_items
            WHERE timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (f"-{hours} hours", limit),
        ).fetchall()

    filtered = []
    for row in rows:
        item = _row_to_dict(row)
        if symbol_upper in item["related_symbols"]:
            filtered.append(item)
    return {"symbol": symbol_upper, "items": filtered}


@router.post("/collect")
def collect_news() -> dict:
    source = RssNewsSource(feed_urls=settings.news_feed_urls)
    inserted = collect_and_store(source)
    return {"inserted": inserted}


def _row_to_dict(row) -> dict:
    related_symbols = row["related_symbols"]
    if isinstance(related_symbols, str):
        related_symbols = json.loads(related_symbols)

    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "title": row["title"],
        "content": row["content"],
        "source": row["source"],
        "related_symbols": related_symbols,
        "sentiment_score": row["sentiment_score"],
        "created_at": row["created_at"],
    }
