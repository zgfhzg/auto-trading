"""Utilities for news related symbol serialization/parsing."""

from __future__ import annotations


def serialize_related_symbols(symbols: list[str]) -> str:
    """Serialize symbols as uppercase, unique, comma-separated values."""
    normalized = sorted({symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()})
    return ",".join(normalized)


def parse_related_symbols(value: str | None) -> list[str]:
    """Parse comma-separated related symbols into a normalized list."""
    if not value:
        return []

    return [
        symbol
        for symbol in (
            part.strip().upper()
            for part in value.split(",")
        )
        if symbol
    ]
