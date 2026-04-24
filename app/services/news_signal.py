"""News signal scoring service."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone, timedelta

from app.db import get_session

logger = logging.getLogger(__name__)


def get_news_score(symbol: str, hours: int = 6) -> float:
    """Return weighted sentiment score from recent symbol-related news."""
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(hours=max(hours, 1))

    try:
        with get_session() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, related_symbols, sentiment_score
                FROM news_items
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                """,
                (cutoff.isoformat(),),
            ).fetchall()
    except Exception:
        logger.exception("Failed to calculate news score for %s", symbol)
        return 0.0

    filtered: list[tuple[datetime, float]] = []
    target = symbol.upper()
    for row in rows:
        try:
            related_symbols = json.loads(row["related_symbols"] or "[]")
        except json.JSONDecodeError:
            related_symbols = []
        if target not in related_symbols:
            continue

        try:
            ts = datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        filtered.append((ts, float(row["sentiment_score"])))

    if not filtered:
        return 0.0

    weighted_sum = 0.0
    total_weight = 0.0
    for ts, score in filtered:
        age_hours = max((now - ts).total_seconds() / 3600.0, 0.0)
        weight = math.exp(-age_hours / 3.0)
        weighted_sum += weight * score
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight
