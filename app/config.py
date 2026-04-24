"""Application configuration loaded from environment variables."""

from __future__ import annotations

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
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "trading.db")

    def validate(self) -> None:
        if self.paper_trading_enabled and self.enable_live_trading:
            raise RuntimeError(
                "Unsafe startup blocked: PAPER_TRADING_ENABLED and "
                "ENABLE_LIVE_TRADING cannot both be true."
            )


settings = Settings()
