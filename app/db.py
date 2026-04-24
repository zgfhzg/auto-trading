"""SQLite connection/session helpers and schema bootstrap."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import settings
from app.models import SCHEMA_SQL


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.sqlite_db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_trades_is_live_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(trades)").fetchall()
    if not columns:
        return
    has_is_live = any(col[1] == "is_live" for col in columns)
    if not has_is_live:
        conn.execute("ALTER TABLE trades ADD COLUMN is_live INTEGER NOT NULL DEFAULT 0")


def _ensure_trades_reason_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(trades)").fetchall()
    if not columns:
        return
    has_reason = any(col[1] == "reason" for col in columns)
    if not has_reason:
        conn.execute("ALTER TABLE trades ADD COLUMN reason TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    with get_session() as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_trades_is_live_column(conn)
        _ensure_trades_reason_column(conn)
