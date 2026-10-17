"""SQLite storage: the only module that touches sqlite3.

Shared-schema API (runner):   init_records_table, store_records / store_records_detailed (one
                              transaction per run, INSERT ... ON CONFLICT upsert), get_record, count_records,
                              count_not_seen, content_hash. Record states: new / changed / unchanged
                              (+ not_seen_this_run, a query; nothing is ever deleted)
Entities (Week 3):            init_entity_tables, write_entity_links (inside store_records_detailed's
                              transaction via extra_writes), list_entities, add_alias_candidates (review queue),
                              entity_counts, query
Discovered items (Week 3):    init_discovered_items_table, upsert_discovered_items (run transaction),
                              get_discovered_item
Run records (scheduler):      init_runs_table, start_run, finish_run (+ Week 3 run metrics columns),
                              abandon_running_runs, run_history, get_run, list_runs, last_runs
Legacy API (Sections 1-4A):   init_db, store_item/store_all, get_item_by_url, count_items (table `items`)
"""

import sqlite3
import uuid
import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, Optional, Union

from src.schema import CONTENT_FIELDS, IDENTIFIER_FIELDS, PROVENANCE_FIELDS


def _open(db_path: str, **kwargs) -> sqlite3.Connection:
    """Every connection in this module is opened here, so per-connection settings live in one place.

    PRAGMA foreign_keys=ON (Week 3 Section 6): SQLite enforces REFERENCES clauses only when this is set on the
    connection, and it is off by default. With it, an entity link to an item_url that is not in records is
    rejected instead of silently stored."""
    conn = sqlite3.connect(db_path, **kwargs)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _connect(db_path: str) -> Iterator[sqlite3.Connection]:
    """Opens a connection, commits (or rolls back on error) and always closes it.

    sqlite3's own `with sqlite3.connect(...)` only manages the transaction; it never closes the connection
    (open handles keep the file locked on Windows and raise ResourceWarning).
    """
    conn = _open(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    """Initializes the SQLite database with the items schema."""
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)

    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
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

    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items")
        return cursor.fetchone()[0]



# ---------------------------------------------------------------------------
# Shared-schema records table
# ---------------------------------------------------------------------------

_JSON_COLUMNS = ("speakers", "organizations", "extras")
# Stored instead of NULL, so a reader can always json.loads() a column and get the right container type.
_JSON_EMPTY = {"speakers": [], "organizations": [], "extras": {}}
_INTEGER_COLUMNS = ("is_online", "http_status", "detail_http_status")
_RECORD_COLUMNS = IDENTIFIER_FIELDS + CONTENT_FIELDS + PROVENANCE_FIELDS + ("extras",)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _speaker_sort_key(speaker: Any) -> tuple:
    if isinstance(speaker, dict):
        return (str(speaker.get("name") or ""), str(speaker.get("affiliation") or ""))
    return (str(speaker), "")


def _hash_view(record: dict) -> dict:
    """The CONTENT fields as hashed. List fields are sorted (Week 3 Section 4): speakers by (name, affiliation),
    organizations alphabetically, so a page that only reorders them is not a change. Stored values keep the
    page's order; only the hash input is sorted."""
    view = {field: record.get(field) for field in CONTENT_FIELDS}
    if isinstance(view.get("speakers"), list):
        view["speakers"] = sorted(view["speakers"], key=_speaker_sort_key)
    if isinstance(view.get("organizations"), list):
        view["organizations"] = sorted(view["organizations"], key=str)
    return view


def content_hash(record: dict) -> str:
    """sha256 over CONTENT fields only (schema.CONTENT_FIELDS), list fields sorted. Provenance never feeds the hash."""
    payload = json.dumps(_hash_view(record), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def init_records_table(db_path: str) -> None:
    """Creates the shared-schema `records` table keyed by canonical item_url."""
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    columns = ",\n".join(
        f"{c} {'INTEGER' if c in _INTEGER_COLUMNS else 'TEXT'}"
        + (" PRIMARY KEY" if c == "item_url" else "")
        for c in _RECORD_COLUMNS
    )
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM records WHERE item_url = ?", (item_url,)).fetchone()
        return _decode_row(row) if row else None


def count_records(db_path: str, source_name: Optional[str] = None) -> int:
    """Row count, optionally for one source (records.source_name holds the config's source_id)."""
    with _connect(db_path) as conn:
        if source_name:
            return conn.execute("SELECT COUNT(*) FROM records WHERE source_name = ?", (source_name,)).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def _carry_forward(record: dict, existing: dict, unparsed_fields: Iterable[str] = ()) -> dict:
    """
    A missing value is not evidence that content was removed when it is missing because of this run:
      - the detail fetch did not succeed: every empty content field keeps its stored value
        (e.g. description, speakers, event_end);
      - the adapter could not parse the field (normalize() parse_warnings): that field keeps its stored
        value, even on an ok detail fetch. A format change must never erase data.
    A non-empty new value (e.g. event_start from the listing fallback) still wins.
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


RECORD_STATES = ("new", "changed", "unchanged")   # + not_seen_this_run, which is a query (count_not_seen), not a write


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _upsert(conn: sqlite3.Connection, record: dict, now_iso: str, unparsed_fields: Iterable[str] = (),
            rediscovery_cutoff: Optional[str] = None) -> tuple[str, bool]:
    """Upserts one record on an open connection (inside the caller's transaction).

    Returns (state, rediscovered): state is "new" | "changed" | "unchanged" by content hash;
    rediscovered = the row existed but its last_seen_at is older than rediscovery_cutoff (the previous run's
    started_at for this source, D6): it was absent from at least one run and is back. It is still counted by its
    hash (unchanged or changed), never as new.
    One INSERT ... ON CONFLICT(item_url) DO UPDATE statement: first_seen_at is written only on insert.
    """
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
        values[column] = json.dumps(values[column] if values[column] is not None else _JSON_EMPTY[column],
                                    ensure_ascii=False, sort_keys=True)
    if values["is_online"] is not None:
        values["is_online"] = int(values["is_online"])

    cols = list(values) + ["content_hash", "first_seen_at", "last_seen_at"]
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("item_url", "first_seen_at"))
    conn.execute(f"INSERT INTO records ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                 f"ON CONFLICT(item_url) DO UPDATE SET {updates}",
                 [*values.values(), digest, now_iso, now_iso])
    if not existing:
        return "new", False
    rediscovered = bool(rediscovery_cutoff and existing.get("last_seen_at")
                        and existing["last_seen_at"] < rediscovery_cutoff)
    return ("unchanged" if existing["content_hash"] == digest else "changed"), rediscovered


@dataclass
class StoreResult:
    counts: dict                                         # {"new", "unchanged", "changed"}
    states: dict = field(default_factory=dict)           # item_url -> state
    rediscovered: list = field(default_factory=list)     # item_urls back after an absence (D6)


def store_records_detailed(db_path: str, records: list[dict],
                           unparsed_fields: Optional[dict[str, Iterable[str]]] = None,
                           now_iso: Optional[str] = None, rediscovery_cutoff: Optional[str] = None,
                           extra_writes: Optional[Callable[[sqlite3.Connection], None]] = None) -> StoreResult:
    """
    Stores a run's records in ONE transaction (BEGIN IMMEDIATE ... COMMIT); any exception rolls back every
    write of this call, so a failed run leaves the tables as they were.
      unparsed_fields     {item_url: fields the adapter could not parse}; their stored values are kept
      now_iso             the run's timestamp for first_seen_at / last_seen_at (default: now). The scheduler
                          passes the run's started_at, so not_seen_this_run = last_seen_at < started_at (D6)
      rediscovery_cutoff  previous run's started_at for this source (D6, rediscovered)
      extra_writes        callback run on the same connection inside the same transaction (the aggregator's
                          discovered_items and entity rows), so records and their links commit or roll back together
    """
    unparsed_fields = unparsed_fields or {}
    init_records_table(db_path)
    result = StoreResult(counts={state: 0 for state in ("new", "unchanged", "changed")})
    now_iso = now_iso or _utc_now()
    conn = _open(db_path, isolation_level=None)  # explicit BEGIN/COMMIT below
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        for record in records:
            state, rediscovered = _upsert(conn, record, now_iso, unparsed_fields.get(record.get("item_url"), ()),
                                          rediscovery_cutoff)
            result.counts[state] += 1
            result.states[record["item_url"]] = state
            if rediscovered:
                result.rediscovered.append(record["item_url"])
        if extra_writes is not None:
            extra_writes(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return result


def store_records(db_path: str, records: list[dict],
                  unparsed_fields: Optional[dict[str, Iterable[str]]] = None) -> dict[str, int]:
    """Stores a run's records in ONE transaction; returns {'new', 'unchanged', 'changed'} counts."""
    return store_records_detailed(db_path, records, unparsed_fields).counts


def store_record(db_path: str, record: dict) -> Literal["new", "unchanged", "changed"]:
    """Upserts one shared-schema record (its own transaction)."""
    counts = store_records(db_path, [record])
    return next(outcome for outcome, n in counts.items() if n)  # type: ignore[return-value]


def count_not_seen(db_path: str, source_name: str, run_started_at: str) -> int:
    """not_seen_this_run (D6): rows of this source whose last_seen_at is older than this run's started_at.
    Nothing is deleted: absence from one listing does not prove an item is gone."""
    init_records_table(db_path)
    with _connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM records WHERE source_name = ? AND last_seen_at < ?",
                            (source_name, run_started_at)).fetchone()[0]


# ---------------------------------------------------------------------------
# Entities (Week 3 Section 6): people / organizations + links to records(item_url) (D4, D5)
# ---------------------------------------------------------------------------

ENTITY_DDL = (
    """CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY,
        normalized_name TEXT NOT NULL UNIQUE,      -- name_key(name without honorific): the identity claim (D5)
        display_name TEXT NOT NULL,                -- as first seen
        honorific TEXT,
        profile_url TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS organizations (
        id INTEGER PRIMARY KEY,
        normalized_name TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        org_type TEXT,
        url TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS item_people (
        item_url TEXT NOT NULL REFERENCES records(item_url),
        person_id INTEGER NOT NULL REFERENCES people(id),
        role TEXT NOT NULL,
        affiliation_raw TEXT,                      -- per event, as written next to the name (D5)
        source_text TEXT NOT NULL,
        PRIMARY KEY (item_url, person_id, role)
    )""",
    """CREATE TABLE IF NOT EXISTS item_organizations (
        item_url TEXT NOT NULL REFERENCES records(item_url),
        organization_id INTEGER NOT NULL REFERENCES organizations(id),
        role TEXT NOT NULL,
        source_text TEXT NOT NULL,
        PRIMARY KEY (item_url, organization_id, role)
    )""",
    # normalized_name is UNIQUE, which already gives each table an index on it (sqlite_autoindex_*); these two
    # serve the reverse lookups "every event of this person / organization".
    # Section 7 review queue: pairs that MIGHT be one entity. Never merged by code; a reviewer sets status.
    """CREATE TABLE IF NOT EXISTS entity_alias_candidates (
        kind TEXT NOT NULL CHECK (kind IN ('person', 'organization')),
        a_id INTEGER NOT NULL,
        b_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'needs_review',
        PRIMARY KEY (kind, a_id, b_id),
        CHECK (a_id < b_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_item_people_person ON item_people(person_id)",
    "CREATE INDEX IF NOT EXISTS idx_item_organizations_org ON item_organizations(organization_id)",
)


def init_entity_tables(db_path: str) -> None:
    init_records_table(db_path)
    with _connect(db_path) as conn:
        for statement in ENTITY_DDL:
            conn.execute(statement)
        conn.commit()


def _entity_id(conn: sqlite3.Connection, table: str, normalized_name: str, display_name: str,
               extra: dict) -> int:
    """Inserts the entity if its normalized_name is new (first display form wins), returns its id."""
    cols = ["normalized_name", "display_name", *extra]
    conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                 f"ON CONFLICT(normalized_name) DO NOTHING", [normalized_name, display_name, *extra.values()])
    return conn.execute(f"SELECT id FROM {table} WHERE normalized_name = ?", (normalized_name,)).fetchone()[0]


def write_entity_links(conn: sqlite3.Connection, item_url: str, people: Iterable[dict], orgs: Iterable[dict],
                       replace: bool = True) -> dict:
    """Writes one item's people / organization links on an open connection (inside the caller's transaction).

    people: {normalized_name, display_name, honorific, profile_url, role, affiliation_raw, source_text}
    orgs:   {normalized_name, display_name, org_type, url, role, source_text}
    replace=True (the item's detail page was parsed this run): the item's previous links are replaced by what the
    page states now, so a removed speaker does not linger. replace=False (detail fetch failed): existing links are
    kept and only missing ones added. Links are keyed (item_url, entity_id, role): a re-run never duplicates them.
    Returns {"people_links": rows added, "organization_links": rows added} (net of the replaced ones).
    """
    before_p = conn.execute("SELECT COUNT(*) FROM item_people WHERE item_url = ?", (item_url,)).fetchone()[0]
    before_o = conn.execute("SELECT COUNT(*) FROM item_organizations WHERE item_url = ?", (item_url,)).fetchone()[0]
    if replace:
        conn.execute("DELETE FROM item_people WHERE item_url = ?", (item_url,))
        conn.execute("DELETE FROM item_organizations WHERE item_url = ?", (item_url,))
    for p in people:
        person_id = _entity_id(conn, "people", p["normalized_name"], p["display_name"],
                               {"honorific": p.get("honorific"), "profile_url": p.get("profile_url")})
        conn.execute("INSERT OR IGNORE INTO item_people (item_url, person_id, role, affiliation_raw, source_text) "
                     "VALUES (?, ?, ?, ?, ?)", (item_url, person_id, p["role"], p.get("affiliation_raw"),
                                                p["source_text"]))
    for o in orgs:
        org_id = _entity_id(conn, "organizations", o["normalized_name"], o["display_name"],
                            {"org_type": o.get("org_type"), "url": o.get("url")})
        conn.execute("INSERT OR IGNORE INTO item_organizations (item_url, organization_id, role, source_text) "
                     "VALUES (?, ?, ?, ?)", (item_url, org_id, o["role"], o["source_text"]))
    after_p = conn.execute("SELECT COUNT(*) FROM item_people WHERE item_url = ?", (item_url,)).fetchone()[0]
    after_o = conn.execute("SELECT COUNT(*) FROM item_organizations WHERE item_url = ?", (item_url,)).fetchone()[0]
    return {"people_links": after_p - before_p, "organization_links": after_o - before_o}


def list_entities(conn: sqlite3.Connection, kind: str) -> list[tuple[int, str]]:
    """[(id, display_name)] of every person ('person') or organization ('organization')."""
    table = {"person": "people", "organization": "organizations"}[kind]
    return [(row[0], row[1]) for row in conn.execute(f"SELECT id, display_name FROM {table} ORDER BY id")]


def add_alias_candidates(conn: sqlite3.Connection, kind: str, pairs: Iterable[tuple[int, int, str]]) -> int:
    """Queues (a_id, b_id, reason) pairs for review; an existing pair (and its status) is left as it is.
    Returns the number of new candidates. Nothing is merged."""
    added = 0
    for a_id, b_id, reason in pairs:
        cursor = conn.execute("INSERT OR IGNORE INTO entity_alias_candidates (kind, a_id, b_id, reason) "
                              "VALUES (?, ?, ?, ?)", (kind, min(a_id, b_id), max(a_id, b_id), reason))
        added += cursor.rowcount
    return added


def entity_counts(db_path: str) -> dict:
    init_entity_tables(db_path)
    with _connect(db_path) as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("people", "organizations", "item_people", "item_organizations")}


def query(db_path: str, sql: str, params: tuple = ()) -> list[tuple]:
    """Read-only helper for docs, CLIs and tests (storage stays the only sqlite3 user)."""
    with _connect(db_path) as conn:
        return conn.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# Discovered items (Week 3 Section 8): every discovery candidate, in scope or not, with its routing decision
# ---------------------------------------------------------------------------

DISCOVERED_ITEMS_DDL = """CREATE TABLE IF NOT EXISTS discovered_items (
    discovered_url TEXT PRIMARY KEY,           -- canonical (resolve_item_url)
    source_name TEXT NOT NULL,
    discovery_methods TEXT NOT NULL,           -- JSON list, e.g. ["html", "rss"]
    discovered_title TEXT,
    source_timestamp TEXT,
    source_timestamp_raw TEXT,
    first_discovered_at TEXT NOT NULL,
    last_discovered_at TEXT NOT NULL,
    in_scope INTEGER NOT NULL,
    scope_reason TEXT NOT NULL,
    content_class TEXT NOT NULL,               -- event | announcement | faculty | pdf_document | external_link | unknown
    class_reason TEXT NOT NULL
)"""
DISCOVERED_ITEM_COLUMNS = ("discovered_url", "source_name", "discovery_methods", "discovered_title",
                           "source_timestamp", "source_timestamp_raw", "first_discovered_at", "last_discovered_at",
                           "in_scope", "scope_reason", "content_class", "class_reason")


def init_discovered_items_table(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(DISCOVERED_ITEMS_DDL)
        conn.commit()


def upsert_discovered_items(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    """Upserts candidates on an open connection (inside the run transaction). first_discovered_at is kept from the
    first time a URL was seen; every other column reflects this run. Returns the number of rows written."""
    conn.execute(DISCOVERED_ITEMS_DDL)
    cols = DISCOVERED_ITEM_COLUMNS
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("discovered_url", "first_discovered_at"))
    n = 0
    for row in rows:
        values = dict(row)
        values["discovery_methods"] = json.dumps(list(values.get("discovery_methods") or []))
        values["in_scope"] = int(bool(values.get("in_scope")))
        values.setdefault("first_discovered_at", values.get("last_discovered_at"))
        conn.execute(f"INSERT INTO discovered_items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                     f"ON CONFLICT(discovered_url) DO UPDATE SET {updates}", [values.get(c) for c in cols])
        n += 1
    return n


def get_discovered_item(db_path: str, url: str) -> Optional[dict]:
    init_discovered_items_table(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM discovered_items WHERE discovered_url = ?", (url,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["discovery_methods"] = json.loads(item["discovery_methods"])
    item["in_scope"] = bool(item["in_scope"])
    return item


# ---------------------------------------------------------------------------
# Run records (scheduler). Written outside the data transaction so a rolled-back run is still recorded.
# ---------------------------------------------------------------------------

RUN_STATUSES = ("running", "success", "failed", "skipped")
RUN_METRIC_COLUMNS = (
    ("http_status", "INTEGER"), ("pages_fetched", "INTEGER"), ("items_discovered", "INTEGER"),
    ("items_parsed", "INTEGER"), ("not_seen_count", "INTEGER"), ("parse_failures", "INTEGER"),
    ("detail_failures", "INTEGER"), ("people_extracted", "INTEGER"), ("organizations_extracted", "INTEGER"),
    ("pct_with_date", "REAL"), ("pct_with_speaker", "REAL"), ("pct_with_org", "REAL"),
)


def init_runs_table(db_path: str) -> None:
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL CHECK (status IN {RUN_STATUSES}),
                new_count INTEGER,
                unchanged_count INTEGER,
                changed_count INTEGER,
                failed_count INTEGER,
                error TEXT
            )
        """)
        _migrate_runs_table(conn)
        conn.commit()


def _migrate_runs_table(conn: sqlite3.Connection) -> None:
    """Brings a runs table created by older code up to date in place (no data loss).
    Week 3 Section 4: the state 'existing' was renamed 'unchanged', so existing_count -> unchanged_count."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "existing_count" in columns and "unchanged_count" not in columns:
        conn.execute("ALTER TABLE runs RENAME COLUMN existing_count TO unchanged_count")
    # Week 3 Section 9: run metrics live on the same runs table (no second run table). Added in place, NULL for
    # older rows and for the Week 2 listing pipeline where a metric does not apply.
    for column, sql_type in RUN_METRIC_COLUMNS:
        if column not in columns:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {column} {sql_type}")


def start_run(db_path: str, source_id: str, status: str = "running", error: Optional[str] = None) -> str:
    """Inserts a run row and returns its run_id. status='skipped' rows are finished immediately."""
    init_runs_table(db_path)
    run_id = uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO runs (run_id, source_id, started_at, finished_at, status, error) VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, source_id, now_iso, now_iso if status == "skipped" else None, status, error))
        conn.commit()
    return run_id


def finish_run(db_path: str, run_id: str, status: str, counts: Optional[dict] = None,
               failed_count: int = 0, error: Optional[str] = None, metrics: Optional[dict] = None) -> None:
    """metrics: any of RUN_METRIC_COLUMNS (Week 3 Section 9); unknown keys are ignored, missing ones stay NULL."""
    counts = counts or {}
    metrics = {k: v for k, v in (metrics or {}).items() if k in dict(RUN_METRIC_COLUMNS)}
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    extra = "".join(f", {column} = ?" for column in metrics)
    with _connect(db_path) as conn:
        conn.execute(f"""UPDATE runs SET finished_at = ?, status = ?, new_count = ?, unchanged_count = ?,
                         changed_count = ?, failed_count = ?, error = ?{extra} WHERE run_id = ?""",
                     (now_iso, status, counts.get("new"), counts.get("unchanged"), counts.get("changed"),
                      failed_count, error, *metrics.values(), run_id))
        conn.commit()


def last_runs(db_path: str, source_id: Optional[str] = None, status: Optional[str] = None,
              limit: int = 1) -> list[dict]:
    """Most recent finished (non-running, non-skipped) runs first, optionally for one source / status."""
    init_runs_table(db_path)
    where, args = ["status NOT IN ('running', 'skipped')"], []
    if source_id:
        where.append("source_id = ?"); args.append(source_id)
    if status:
        where.append("status = ?"); args.append(status)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM runs WHERE {' AND '.join(where)} ORDER BY started_at DESC, rowid DESC "
                            f"LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


def abandon_running_runs(db_path: str, source_id: str, reason: str) -> int:
    """Marks 'running' rows of a source as failed (their process died without finishing)."""
    init_runs_table(db_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect(db_path) as conn:
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
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT started_at, status FROM runs WHERE source_id = ? AND status != 'skipped' "
                            "ORDER BY started_at DESC, rowid DESC", (source_id,)).fetchall()
    failures = 0
    for _, status in rows:
        if status == "success":
            break
        failures += 1
    return {"last_started_at": rows[0][0] if rows else None, "last_status": rows[0][1] if rows else None,
            "consecutive_failures": failures}


def get_run(db_path: str, run_id: str) -> Optional[dict]:
    init_runs_table(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def list_runs(db_path: str, source_id: Optional[str] = None) -> list[dict]:
    init_runs_table(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        query, args = "SELECT * FROM runs", ()
        if source_id:
            query, args = query + " WHERE source_id = ?", (source_id,)
        return [dict(r) for r in conn.execute(query + " ORDER BY started_at, rowid", args)]
