"""RSS news collection service."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from xml.etree import ElementTree

import requests

from app.config import settings
from app.db import get_session

logger = logging.getLogger(__name__)

POSITIVE_TERMS = {
    "beats",
    "surge",
    "record",
    "upgrade",
    "growth",
    "profit",
    "bullish",
    "strong",
    "outperform",
    "win",
}
NEGATIVE_TERMS = {
    "miss",
    "drop",
    "downgrade",
    "lawsuit",
    "loss",
    "bearish",
    "weak",
    "fraud",
    "cut",
    "decline",
}


@dataclass(frozen=True)
class NewsItem:
    timestamp: str
    title: str
    content: str
    source: str
    related_symbols: list[str]
    sentiment_score: float
    title_hash: str


class NewsSource(Protocol):
    """Source contract for collecting news items."""

    def fetch(self) -> list[NewsItem]:
        """Fetch and normalize news items."""


class RssNewsSource:
    """RSS implementation with retry/backoff."""

    def __init__(
        self,
        feed_urls: list[str],
        *,
        user_agent: str = "auto-trading-news-bot/1.0",
        timeout: int = 10,
        retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.feed_urls = feed_urls
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        seen_hashes: set[str] = set()
        for url in self.feed_urls:
            try:
                xml_text = self._get_with_retry(url)
            except requests.RequestException:
                logger.exception("RSS fetch failed: %s", url)
                continue
            items.extend(self._parse_items(xml_text, seen_hashes))
        return items

    def _get_with_retry(self, url: str) -> str:
        headers = {"User-Agent": self.user_agent}
        for attempt in range(1, self.retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response.text
            except requests.RequestException:
                if attempt >= self.retries:
                    raise
                sleep_for = self.backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_for)
        raise RuntimeError("unreachable")

    def _parse_items(self, xml_text: str, seen_hashes: set[str]) -> list[NewsItem]:
        root = ElementTree.fromstring(xml_text)
        parsed: list[NewsItem] = []
        for node in root.findall(".//item"):
            title = _node_text(node, "title")
            if not title:
                continue
            title_hash = _hash_title(title)
            if title_hash in seen_hashes:
                continue
            seen_hashes.add(title_hash)

            content = _node_text(node, "description")
            source = _node_text(node, "source") or _node_text(node, "link")
            timestamp = _normalize_timestamp(_node_text(node, "pubDate"))
            symbols = _extract_symbols(f"{title} {content}")
            sentiment = _rule_based_sentiment(f"{title} {content}")
            parsed.append(
                NewsItem(
                    timestamp=timestamp,
                    title=title,
                    content=content,
                    source=source,
                    related_symbols=symbols,
                    sentiment_score=sentiment,
                    title_hash=title_hash,
                )
            )
        return parsed


def store_news_items(items: list[NewsItem]) -> int:
    """Persist normalized news items. Returns inserted row count."""
    if not items:
        return 0

    inserted = 0
    with get_session() as conn:
        for item in items:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO news_items (
                    timestamp, title, content, source,
                    related_symbols, sentiment_score, title_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.timestamp,
                    item.title,
                    item.content,
                    item.source,
                    json.dumps(item.related_symbols, ensure_ascii=False),
                    item.sentiment_score,
                    item.title_hash,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def collect_and_store(source: NewsSource) -> int:
    items = source.fetch()
    _log_related_symbols_sample(items, sample_size=20)
    return store_news_items(items)


def _hash_title(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


def _extract_symbols(text: str) -> list[str]:
    lowered = text.lower()
    compact = lowered.replace(" ", "")
    matched = [
        symbol
        for symbol, keywords in settings.symbol_keywords.items()
        if any(_keyword_match(keyword, lowered, compact) for keyword in keywords)
    ]
    return sorted(set(matched))


def _keyword_match(keyword: str, lowered: str, compact: str) -> bool:
    normalized = keyword.lower().strip()
    if not normalized:
        return False
    normalized_compact = normalized.replace(" ", "")
    return normalized in lowered or normalized_compact in compact


def _log_related_symbols_sample(items: list[NewsItem], sample_size: int = 20) -> None:
    if not items:
        logger.info("Related symbol mapping sample skipped: no news items.")
        return

    logger.info(
        "Related symbol mapping quality sample (size=%s, total=%s)",
        min(len(items), sample_size),
        len(items),
    )
    for index, item in enumerate(items[:sample_size], start=1):
        logger.info(
            "[sample:%02d] symbols=%s title=%s",
            index,
            ",".join(item.related_symbols) or "-",
            item.title,
        )


def _rule_based_sentiment(text: str) -> float:
    words = text.lower().replace("-", " ").split()
    pos_hits = sum(1 for word in words if word in POSITIVE_TERMS)
    neg_hits = sum(1 for word in words if word in NEGATIVE_TERMS)
    score = (pos_hits - neg_hits) / max(pos_hits + neg_hits, 1)
    return max(-1.0, min(1.0, score))


def _normalize_timestamp(value: str) -> str:
    if not value:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return datetime.now(tz=timezone.utc).isoformat()


def _node_text(node: ElementTree.Element, tag_name: str) -> str:
    child = node.find(tag_name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()
