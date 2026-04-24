"""SQLite table definitions used by the bootstrap schema initializer."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    source TEXT,
    related_symbols TEXT NOT NULL DEFAULT '[]',
    sentiment_score REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS paper_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'filled',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
