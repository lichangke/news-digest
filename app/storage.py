from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import NewsItem

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
DB_PATH = STATE_DIR / "news.db"


def get_conn() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            run_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            total_candidates INTEGER DEFAULT 0,
            total_selected INTEGER DEFAULT 0,
            doc_url TEXT,
            error_message TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            run_type TEXT NOT NULL,
            title TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            event_fingerprint TEXT NOT NULL,
            summary TEXT NOT NULL,
            source TEXT NOT NULL,
            source_priority INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            original_url TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def article_exists(conn: sqlite3.Connection, run_date: str, event_fingerprint: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM articles WHERE run_date = ? AND event_fingerprint = ? LIMIT 1",
        (run_date, event_fingerprint),
    ).fetchone()
    return row is not None


def save_articles(conn: sqlite3.Connection, run_date: str, run_type: str, items: Iterable[NewsItem]) -> None:
    conn.executemany(
        """
        INSERT INTO articles (
            run_date, run_type, title, normalized_title, event_fingerprint,
            summary, source, source_priority, published_at, original_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_date,
                run_type,
                item.title,
                item.normalized_title,
                item.event_fingerprint,
                item.summary,
                item.source,
                item.source_priority,
                item.published_at.isoformat(),
                item.url,
            )
            for item in items
        ],
    )
    conn.commit()
