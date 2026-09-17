"""SQLite storage layer with URL deduplication and content hash change detection."""

import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def init_db(db_path: str) -> None:
    """Initializes the SQLite database with the items schema."""
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                published_at TEXT,
                date_raw TEXT,
                venue TEXT,
                description TEXT,
                raw_text TEXT,
                content_hash TEXT,
                first_seen DATETIME NOT NULL,
                last_seen DATETIME NOT NULL
            )
        """)
        conn.commit()


def compute_content_hash(item: dict) -> str:
    """Computes a SHA256 hash across content fields to detect modifications."""
    fields = [
        str(item.get("title") or ""),
        str(item.get("published_at") or ""),
        str(item.get("venue") or ""),
        str(item.get("description") or ""),
        str(item.get("raw_text") or "")
    ]
    payload = "|".join(fields).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_item_by_url(db_path: str, url: str) -> Optional[dict]:
    """Fetches an existing item by canonical URL."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE url = ?", (url,))
        row = cursor.fetchone()
        return dict(row) if row else None


def store_event(db_path: str, item: dict) -> str:
    """
    Upserts an event record into the database.
    Returns:
        'new': record inserted for the first time
        'existing': record already exists with identical content
        'changed': record exists with same URL but altered content
    """
    url = item.get("item_url")
    if not url:
        raise ValueError("Cannot store item without a canonical 'item_url'")

    now_iso = datetime.now(timezone.utc).isoformat()
    content_hash = compute_content_hash(item)

    existing = get_item_by_url(db_path, url)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if not existing:
            cursor.execute("""
                INSERT INTO items (
                    url, title, published_at, date_raw, venue, description,
                    raw_text, content_hash, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                item.get("title"),
                item.get("published_at"),
                item.get("date_raw"),
                item.get("venue"),
                item.get("description"),
                item.get("raw_text"),
                content_hash,
                now_iso,
                now_iso
            ))
            conn.commit()
            return "new"
        else:
            if existing.get("content_hash") == content_hash:
                cursor.execute("UPDATE items SET last_seen = ? WHERE url = ?", (now_iso, url))
                conn.commit()
                return "existing"
            else:
                cursor.execute("""
                    UPDATE items SET
                        title = ?,
                        published_at = ?,
                        date_raw = ?,
                        venue = ?,
                        description = ?,
                        raw_text = ?,
                        content_hash = ?,
                        last_seen = ?
                    WHERE url = ?
                """, (
                    item.get("title"),
                    item.get("published_at"),
                    item.get("date_raw"),
                    item.get("venue"),
                    item.get("description"),
                    item.get("raw_text"),
                    content_hash,
                    now_iso,
                    url
                ))
                conn.commit()
                return "changed"


def store_all(db_path: str, items: list[dict]) -> dict[str, int]:
    """
    Stores a batch of items and returns counts: {'new': int, 'existing': int, 'changed': int}.
    """
    counts = {"new": 0, "existing": 0, "changed": 0}
    for item in items:
        status = store_event(db_path, item)
        if status in counts:
            counts[status] += 1
    return counts


def count_items(db_path: str) -> int:
    """Returns the total number of items stored in the database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items")
        return cursor.fetchone()[0]
