"""RSS news collection service."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from xml.etree import ElementTree

import requests

from app.config import settings
from app.db import get_session
from app.services.news_symbols import serialize_related_symbols

logger = logging.getLogger(__name__)

POSITIVE_TERMS = {
    "호재",
    "상승",
    "급등",
    "강세",
    "성장",
    "흑자",
    "개선",
    "최고",
    "돌파",
    "매수",
}
NEGATIVE_TERMS = {
    "악재",
    "하락",
    "급락",
    "약세",
    "적자",
    "부진",
    "손실",
    "최저",
    "이탈",
    "매도",
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
                    serialize_related_symbols(item.related_symbols),
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
    try:
        normalized_text = _normalize_sentiment_text(text)
        compact_text = normalized_text.replace(" ", "")
        tokens = set(normalized_text.split())

        pos_hits = _count_sentiment_hits(POSITIVE_TERMS, compact_text, tokens)
        neg_hits = _count_sentiment_hits(NEGATIVE_TERMS, compact_text, tokens)

        total_hits = pos_hits + neg_hits
        score = (pos_hits - neg_hits) / max(total_hits, 1)
        return _clamp(score, lower=-1.0, upper=1.0)
    except Exception:
        logger.exception("Sentiment analysis failed. Returning neutral score.")
        return 0.0


def _normalize_sentiment_text(text: str) -> str:
    lowered = text.lower().replace("-", " ")
    normalized = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _count_sentiment_hits(
    terms: set[str],
    compact_text: str,
    tokens: set[str],
) -> int:
    hits = 0
    for term in terms:
        normalized_term = _normalize_sentiment_text(term)
        if not normalized_term:
            continue
        compact_term = normalized_term.replace(" ", "")
        token_match = normalized_term in tokens
        substring_match = compact_term and compact_term in compact_text
        if token_match or substring_match:
            hits += 1
    return hits


def _clamp(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


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
