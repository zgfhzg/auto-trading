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


def init_db() -> None:
    with get_session() as conn:
        conn.executescript(SCHEMA_SQL)
