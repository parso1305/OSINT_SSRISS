"""SQLite storage: the only module that touches sqlite3.

Shared-schema API (runner):   init_records_table, store_records (one transaction per run), get_record,
                              count_records, content_hash
Run records (scheduler):      init_runs_table, start_run, finish_run, abandon_running_runs,
                              run_history, list_runs
Legacy API (Sections 1-4A):   init_db, store_item/store_all, get_item_by_url, count_items (table `items`)
"""

import sqlite3
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Union

from src.schema import CONTENT_FIELDS, IDENTIFIER_FIELDS, PROVENANCE_FIELDS


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


def compute_content_hash(item: Union[dict, Any]) -> str:
    """Computes a SHA256 hash across content fields to detect modifications."""
    get_fn = item.get if hasattr(item, "get") else lambda k, d=None: getattr(item, k, d)
    fields = [
        str(get_fn("title") or ""),
        str(get_fn("published_at") or ""),
        str(get_fn("venue") or ""),
        str(get_fn("description") or ""),
        str(get_fn("raw_text") or "")
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


def store_item(db_path: str, item: Union[dict, Any]) -> Literal["new", "existing", "changed"]:
    """
    Upserts an item record into the database using canonical URL as dedup key.

    Returns:
        'new': record inserted for the first time
        'existing': record already exists with identical content
        'changed': record exists with same URL but altered content
    """
    get_fn = item.get if hasattr(item, "get") else lambda k, d=None: getattr(item, k, d)
    url = get_fn("item_url")
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
                get_fn("title"),
                get_fn("published_at"),
                get_fn("date_raw"),
                get_fn("venue"),
                get_fn("description"),
                get_fn("raw_text"),
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
                    get_fn("title"),
                    get_fn("published_at"),
                    get_fn("date_raw"),
                    get_fn("venue"),
                    get_fn("description"),
                    get_fn("raw_text"),
                    content_hash,
                    now_iso,
                    url
                ))
                conn.commit()
                return "changed"


# Backwards compatibility alias for Section 1 tests
store_event = store_item


def store_all(db_path: str, items: list[Union[dict, Any]]) -> dict[str, int]:
    """
    Stores a batch of items and returns counts: {'new': int, 'existing': int, 'changed': int}.
    """
    counts = {"new": 0, "existing": 0, "changed": 0}
    for item in items:
        status = store_item(db_path, item)
        if status in counts:
            counts[status] += 1
    return counts


def count_items(db_path: str) -> int:
    """Returns the total number of items stored in the database."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items")
        return cursor.fetchone()[0]



# ---------------------------------------------------------------------------
# Shared-schema records table
# ---------------------------------------------------------------------------

_JSON_COLUMNS = ("speakers", "extras")
_RECORD_COLUMNS = IDENTIFIER_FIELDS + CONTENT_FIELDS + PROVENANCE_FIELDS + ("extras",)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def content_hash(record: dict) -> str:
    """sha256 over CONTENT fields only (schema.CONTENT_FIELDS). Provenance never feeds the hash."""
    payload = json.dumps({field: record.get(field) for field in CONTENT_FIELDS},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def init_records_table(db_path: str) -> None:
    """Creates the shared-schema `records` table keyed by canonical item_url."""
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    columns = ",\n".join(
        f"{c} {'INTEGER' if c in ('is_online', 'detail_http_status') else 'TEXT'}"
        + (" PRIMARY KEY" if c == "item_url" else "")
        for c in _RECORD_COLUMNS
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS records (
                {columns},
                content_hash TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _decode_row(row: sqlite3.Row) -> dict:
    record = dict(row)
    for column in _JSON_COLUMNS:
        if record.get(column) is not None:
            record[column] = json.loads(record[column])
    if record.get("is_online") is not None:
        record["is_online"] = bool(record["is_online"])
    return record


def get_record(db_path: str, item_url: str) -> Optional[dict]:
    """Returns the stored record for a canonical item_url, or None."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM records WHERE item_url = ?", (item_url,)).fetchone()
        return _decode_row(row) if row else None


def count_records(db_path: str, source_id: Optional[str] = None) -> int:
    with sqlite3.connect(db_path) as conn:
        if source_id:
            return conn.execute("SELECT COUNT(*) FROM records WHERE source_id = ?", (source_id,)).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def _carry_forward(record: dict, existing: dict, unparsed_fields: Iterable[str] = ()) -> dict:
    """
    A missing value is not evidence that content was removed when it is missing because of this run:
      - the detail fetch did not succeed: every empty content field keeps its stored value
        (e.g. description, speakers, ends_at);
      - the adapter could not parse the field (normalize() parse_warnings): that field keeps its stored
        value, even on an ok detail fetch. A format change must never erase data.
    A non-empty new value (e.g. starts_at from the listing fallback) still wins.
    Provenance always records this run's outcome (detail_fetch_status, ...).
    """
    detail_ok = record.get("detail_fetch_status") == "ok"
    unparsed = set(unparsed_fields)
    fields = [f for f in CONTENT_FIELDS if f in unparsed] if detail_ok else list(CONTENT_FIELDS)
    if not fields:
        return record
    kept = dict(record)
    for field in fields:
        if _is_empty(kept.get(field)) and not _is_empty(existing.get(field)):
            kept[field] = existing[field]
    if not detail_ok:
        kept["extras"] = {**(existing.get("extras") or {}), **(kept.get("extras") or {})}
    return kept


def _upsert(conn: sqlite3.Connection, record: dict, now_iso: str,
            unparsed_fields: Iterable[str] = ()) -> Literal["new", "existing", "changed"]:
    """Upserts one record on an open connection (inside the caller's transaction)."""
    item_url = record.get("item_url")
    if not item_url:
        raise ValueError("Cannot store a record without a canonical item_url")
    row = conn.execute("SELECT * FROM records WHERE item_url = ?", (item_url,)).fetchone()
    existing = _decode_row(row) if row else None
    if existing:
        record = _carry_forward(record, existing, unparsed_fields)
    digest = content_hash(record)

    values = {c: record.get(c) for c in _RECORD_COLUMNS}
    for column in _JSON_COLUMNS:
        values[column] = json.dumps(values[column] if values[column] is not None else ([] if column == "speakers" else {}),
                                    ensure_ascii=False, sort_keys=True)
    if values["is_online"] is not None:
        values["is_online"] = int(values["is_online"])

    if not existing:
        cols = list(values) + ["content_hash", "first_seen_at", "last_seen_at"]
        conn.execute(f"INSERT INTO records ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [*values.values(), digest, now_iso, now_iso])
        return "new"
    assignments = ", ".join(f"{c} = ?" for c in values if c != "item_url")
    conn.execute(f"UPDATE records SET {assignments}, content_hash = ?, last_seen_at = ? WHERE item_url = ?",
                 [*(v for c, v in values.items() if c != "item_url"), digest, now_iso, item_url])
    return "existing" if existing["content_hash"] == digest else "changed"


def store_records(db_path: str, records: list[dict],
                  unparsed_fields: Optional[dict[str, Iterable[str]]] = None) -> dict[str, int]:
    """
    Stores a run's records in ONE transaction; returns {'new', 'existing', 'changed'} counts.
    Any exception rolls back every write of this call, so a failed run leaves the table as it was.
    unparsed_fields: {item_url: fields the adapter could not parse}; their stored values are kept.
    """
    unparsed_fields = unparsed_fields or {}
    init_records_table(db_path)
    counts = {"new": 0, "existing": 0, "changed": 0}
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(db_path, isolation_level=None)  # explicit BEGIN/COMMIT below
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        for record in records:
            counts[_upsert(conn, record, now_iso, unparsed_fields.get(record.get("item_url"), ()))] += 1
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return counts


def store_record(db_path: str, record: dict) -> Literal["new", "existing", "changed"]:
    """Upserts one shared-schema record (its own transaction)."""
    counts = store_records(db_path, [record])
    return next(outcome for outcome, n in counts.items() if n)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Run records (scheduler). Written outside the data transaction so a rolled-back run is still recorded.
# ---------------------------------------------------------------------------

RUN_STATUSES = ("running", "success", "failed", "skipped")


def init_runs_table(db_path: str) -> None:
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL CHECK (status IN {RUN_STATUSES}),
                new_count INTEGER,
                existing_count INTEGER,
                changed_count INTEGER,
                failed_count INTEGER,
                error TEXT
            )
        """)
        conn.commit()


def start_run(db_path: str, source_id: str, status: str = "running", error: Optional[str] = None) -> str:
    """Inserts a run row and returns its run_id. status='skipped' rows are finished immediately."""
    init_runs_table(db_path)
    run_id = uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO runs (run_id, source_id, started_at, finished_at, status, error) VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, source_id, now_iso, now_iso if status == "skipped" else None, status, error))
        conn.commit()
    return run_id


def finish_run(db_path: str, run_id: str, status: str, counts: Optional[dict] = None,
               failed_count: int = 0, error: Optional[str] = None) -> None:
    counts = counts or {}
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""UPDATE runs SET finished_at = ?, status = ?, new_count = ?, existing_count = ?,
                        changed_count = ?, failed_count = ?, error = ? WHERE run_id = ?""",
                     (now_iso, status, counts.get("new"), counts.get("existing"), counts.get("changed"),
                      failed_count, error, run_id))
        conn.commit()


def abandon_running_runs(db_path: str, source_id: str, reason: str) -> int:
    """Marks 'running' rows of a source as failed (their process died without finishing)."""
    init_runs_table(db_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("UPDATE runs SET status = 'failed', finished_at = ?, error = ? "
                              "WHERE source_id = ? AND status = 'running'", (now_iso, reason, source_id))
        conn.commit()
        return cursor.rowcount


def run_history(db_path: str, source_id: str) -> dict:
    """
    What the scheduler needs to decide when a source is next due:
      last_started_at / last_status   latest non-skipped run (None if the source never ran)
      consecutive_failures            runs that did not succeed ('failed', or 'running' = unfinished)
                                      since the last 'success'; skipped runs are ignored
    """
    init_runs_table(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT started_at, status FROM runs WHERE source_id = ? AND status != 'skipped' "
                            "ORDER BY started_at DESC, rowid DESC", (source_id,)).fetchall()
    conn.close()
    failures = 0
    for _, status in rows:
        if status == "success":
            break
        failures += 1
    return {"last_started_at": rows[0][0] if rows else None, "last_status": rows[0][1] if rows else None,
            "consecutive_failures": failures}


def list_runs(db_path: str, source_id: Optional[str] = None) -> list[dict]:
    init_runs_table(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        query, args = "SELECT * FROM runs", ()
        if source_id:
            query, args = query + " WHERE source_id = ?", (source_id,)
        return [dict(r) for r in conn.execute(query + " ORDER BY started_at, rowid", args)]
