"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


def _as_bool(value: str, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str, *, default: float) -> float:
    if value is None:
        return default
    return float(value)


def _as_int(value: str, *, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _as_json_dict(value: str | None, *, default: dict[str, list[str]]) -> dict[str, list[str]]:
    if value is None:
        return {k: list(v) for k, v in default.items()}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object for SYMBOL_KEYWORDS_JSON")
    normalized: dict[str, list[str]] = {}
    for symbol, keywords in parsed.items():
        if not isinstance(symbol, str):
            raise ValueError("SYMBOL_KEYWORDS_JSON keys must be strings")
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise ValueError("SYMBOL_KEYWORDS_JSON values must be string arrays")
        normalized[symbol] = keywords
    return normalized


def _as_json_list(value: str | None, *, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Expected a JSON array of strings for NEWS_FEED_URLS_JSON")
    return parsed


DEFAULT_SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "005930": ["005930", "삼성전자", "삼성 전자", "samsung electronics", "삼전"],
    "000660": ["000660", "sk하이닉스", "sk 하이닉스", "hynix"],
    "035420": ["035420", "naver", "네이버"],
    "035720": ["035720", "kakao", "카카오"],
    "051910": ["051910", "lg화학", "lg 화학", "lg chem"],
    "207940": ["207940", "삼성바이오로직스", "삼성 바이오로직스", "samsung biologics"],
    "068270": ["068270", "셀트리온", "celltrion"],
    "105560": ["105560", "kb금융", "kb 금융", "kb financial"],
}

DEFAULT_NEWS_FEED_URLS: list[str] = [
    "https://news.google.com/rss/search?q=%EC%A3%BC%EC%8B%9D&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=%EC%BD%94%EC%8A%A4%ED%94%BC&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90&hl=ko&gl=KR&ceid=KR:ko",
    "https://finance.naver.com/news/news_list.naver?mode=RSS2D",
]


@dataclass(frozen=True)
class Settings:
    paper_trading_enabled: bool = _as_bool(
        os.getenv("PAPER_TRADING_ENABLED"), default=True
    )
    enable_live_trading: bool = _as_bool(
        os.getenv("ENABLE_LIVE_TRADING"), default=False
    )
    paper_trading_initial_cash: int = _as_int(
        os.getenv("PAPER_TRADING_INITIAL_CASH"), default=1_000_000
    )
    commission_rate: float = _as_float(os.getenv("COMMISSION_RATE"), default=0.00015)
    tax_rate: float = _as_float(os.getenv("TAX_RATE"), default=0.0018)
    trade_interval_seconds: int = _as_int(
        os.getenv("TRADE_INTERVAL_SECONDS"), default=60
    )
    daily_max_loss_limit: float = _as_float(
        os.getenv("DAILY_MAX_LOSS_LIMIT"), default=50_000.0
    )
    max_holdings: int = _as_int(os.getenv("MAX_HOLDINGS"), default=8)
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "trading.db")
    symbol_keywords: dict[str, list[str]] = _as_json_dict(
        os.getenv("SYMBOL_KEYWORDS_JSON"),
        default=DEFAULT_SYMBOL_KEYWORDS,
    )
    news_feed_urls: list[str] = _as_json_list(
        os.getenv("NEWS_FEED_URLS_JSON"),
        default=DEFAULT_NEWS_FEED_URLS,
    )

    def validate(self) -> None:
        if self.paper_trading_enabled and self.enable_live_trading:
            raise RuntimeError(
                "Unsafe startup blocked: PAPER_TRADING_ENABLED and "
                "ENABLE_LIVE_TRADING cannot both be true."
            )


settings = Settings()
