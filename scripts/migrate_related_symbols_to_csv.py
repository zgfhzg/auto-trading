"""Migrate news_items.related_symbols from JSON array text to comma-separated text."""

from __future__ import annotations

import json

from app.db import get_session
from app.services.news_symbols import serialize_related_symbols


def _to_symbol_list(value: str | None) -> list[str]:
    if not value:
        return []

    raw = value.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(symbol) for symbol in parsed]
        return []

    return [part for part in (token.strip() for token in raw.split(",")) if part]


def migrate_related_symbols_to_csv() -> int:
    updated = 0
    with get_session() as conn:
        rows = conn.execute("SELECT id, related_symbols FROM news_items").fetchall()
        for row in rows:
            symbol_list = _to_symbol_list(row["related_symbols"])
            csv_value = serialize_related_symbols(symbol_list)
            if csv_value == (row["related_symbols"] or ""):
                continue
            conn.execute(
                "UPDATE news_items SET related_symbols = ? WHERE id = ?",
                (csv_value, row["id"]),
            )
            updated += 1
    return updated


if __name__ == "__main__":
    changed = migrate_related_symbols_to_csv()
    print(f"updated_rows={changed}")
