"""Shared cross-team record schema (Assignment 6, section c) and validation.

Record layout for item_type "event". Field names follow the team's Week 2 event schema, so two interns'
records of the same item type go into one shared table without renaming (Week 2 Section 6 checkpoint):
  IDENTIFIERS   item_url, source_name, institution
  CONTENT       item_type, title, event_start, event_end, timezone, speakers, location, is_online,
                event_type, organizations, description
  PROVENANCE    source_url, raw_text, fetched_at, http_status, detail_fetched_at, detail_fetch_status,
                detail_http_status, detail_error
  STORAGE       content_hash, first_seen_at, last_seen_at (added by storage)
  extras        dict of source-specific fields (never shared columns)

source_name / item_type hold the config values source_id / content_type: config keys describe a source,
record fields describe an item, so only the record side was renamed.

Dates (event_start, event_end):
  "YYYY-MM-DDTHH:MM:SSZ"   an instant, always UTC
  "YYYY-MM-DD"             date-only: the event's local calendar date in `timezone` (all-day, or the site
                           gives no time). Never converted to UTC (a date without a time has no UTC instant).
                           Requires `timezone`; event_end, if present, must then be date-only too.
  A convention rather than an all_day column: the value describes itself, and existing rows and their
  content_hash stay unchanged.

item_url for items without a URL of their own (no per-item link, POST-only detail, ...):
  build it with src.urls.synthetic_item_url(listing_url, <stable identity>): the listing URL plus
  "#/item/<hash>". Prefer an id the site assigns; fall back to title + start date. Never use a value that
  changes per request (a nonce, a session id). Keep supports_detail off: the identifier is not fetchable.

The legacy NormalizedItem / normalize_event(s) at the bottom serve the Section 1-4A fixture
adapter (sources/*_legacy.py) and its tests only.
"""

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Any
from src.urls import resolve_item_url

IDENTIFIER_FIELDS = ("item_url", "source_name", "institution")
# content_hash covers CONTENT_FIELDS only, so raw_text, fetched_at, http_status and detail_* never make a re-fetch look "changed".
CONTENT_FIELDS = (
    "item_type", "title", "event_start", "event_end", "timezone", "speakers", "location",
    "is_online", "event_type", "organizations", "description",
)
PROVENANCE_FIELDS = (
    "source_url", "raw_text", "fetched_at", "http_status",
    "detail_fetched_at", "detail_fetch_status", "detail_http_status", "detail_error",
)
STORAGE_FIELDS = ("content_hash", "first_seen_at", "last_seen_at")
RECORD_FIELDS = IDENTIFIER_FIELDS + CONTENT_FIELDS + PROVENANCE_FIELDS + ("extras",)

REQUIRED_FIELDS = ("item_url", "source_name", "source_url", "institution", "item_type",
                   "title", "event_start", "fetched_at", "http_status")
DETAIL_FETCH_STATUSES = ("ok", "failed", "not_attempted")
ITEM_TYPES = ("event",)   # was CONTENT_TYPES; Week 3 Section 8 widens it
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_STRING_FIELDS = ("source_name", "source_url", "institution", "item_type", "title", "timezone", "location",
                  "event_type", "description", "raw_text", "detail_error")
_EVENT_TIME_FIELDS = ("event_start", "event_end")          # UTC timestamp or date-only
_FETCH_TIME_FIELDS = ("fetched_at", "detail_fetched_at")    # always UTC timestamps


def is_date_only(value: Any) -> bool:
    """True for a valid ISO calendar date 'YYYY-MM-DD' (the date-only form of event_start / event_end)."""
    if not isinstance(value, str) or not ISO_DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def assemble_record(config: Any, merged: dict, normalized: dict) -> dict:
    """
    Builds a shared-schema record from generic inputs:
      item_url       always the listing's canonical URL (merged["item_url"]), never from the adapter
      identity       source_name / institution / item_type from config (config keys source_id /
                     content_type): they describe the source, so no adapter can get them wrong
      organizations  from the adapter when the page names an organiser, else [config.organizer]
      content        from the adapter's normalize()
      provenance     from the fetch/enrich stages (merged record: raw_text, fetched_at, http_status,
                     detail_*); source_url is the configured listing URL (the page an item was found on
                     is extras.discovered_on_url / discovered_on_page)
    """
    record = {field: normalized.get(field) for field in CONTENT_FIELDS}
    record["item_url"] = merged.get("item_url")
    record["source_name"] = config.source_id
    record["institution"] = config.institution
    record["item_type"] = config.content_type
    record["organizations"] = normalized.get("organizations") or ([config.organizer] if config.organizer else [])
    record["speakers"] = normalized.get("speakers") or []
    for field in PROVENANCE_FIELDS:
        record[field] = merged.get(field)
    record["source_url"] = config.listing_url
    record["extras"] = dict(normalized.get("extras") or {})
    return record


def validate_record(record: dict) -> list[str]:
    """Returns a list of schema errors (empty list = valid)."""
    errors: list[str] = []

    unknown = set(record) - set(RECORD_FIELDS) - set(STORAGE_FIELDS)
    if unknown:
        errors.append(f"unknown fields: {sorted(unknown)}")

    for field in REQUIRED_FIELDS:
        if record.get(field) in (None, "", []):
            errors.append(f"{field}: required")

    for field in _STRING_FIELDS:
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field}: expected str, got {type(value).__name__}")

    for field in _FETCH_TIME_FIELDS:
        value = record.get(field)
        if value is not None and not (isinstance(value, str) and UTC_TIMESTAMP_RE.match(value)):
            errors.append(f"{field}: expected ISO 8601 UTC 'YYYY-MM-DDTHH:MM:SSZ', got {value!r}")
    for field in _EVENT_TIME_FIELDS:
        value = record.get(field)
        if value is not None and not (is_date_only(value) or (isinstance(value, str) and UTC_TIMESTAMP_RE.match(value))):
            errors.append(f"{field}: expected ISO 8601 UTC 'YYYY-MM-DDTHH:MM:SSZ' or date-only 'YYYY-MM-DD', got {value!r}")

    item_url = record.get("item_url")
    if item_url and resolve_item_url(item_url, "") != item_url:
        errors.append(f"item_url: not canonical ({item_url!r})")

    if record.get("item_type") not in (None, *ITEM_TYPES):
        errors.append(f"item_type: expected one of {ITEM_TYPES}")

    event_start, event_end = record.get("event_start"), record.get("event_end")
    if is_date_only(event_start) and not record.get("timezone"):
        errors.append("timezone: required when event_start is date-only (it is a local calendar date)")
    if isinstance(event_start, str) and isinstance(event_end, str):
        if is_date_only(event_start) != is_date_only(event_end):
            errors.append("event_end: must be date-only exactly when event_start is")
        elif event_end < event_start:
            errors.append("event_end: earlier than event_start")

    speakers = record.get("speakers")
    if speakers is not None:
        if not isinstance(speakers, list):
            errors.append("speakers: expected list")
        else:
            for i, speaker in enumerate(speakers):
                if not isinstance(speaker, dict) or set(speaker) != {"name", "affiliation"}:
                    errors.append(f"speakers[{i}]: expected {{'name', 'affiliation'}}")
                elif not isinstance(speaker["name"], str) or not speaker["name"]:
                    errors.append(f"speakers[{i}].name: required str")
                elif speaker["affiliation"] is not None and not isinstance(speaker["affiliation"], str):
                    errors.append(f"speakers[{i}].affiliation: expected str or null")

    # A list rather than one string: the shared schema allows several organisers per item.
    organizations = record.get("organizations")
    if organizations is not None:
        if not isinstance(organizations, list):
            errors.append("organizations: expected list")
        else:
            for i, org in enumerate(organizations):
                if not isinstance(org, str) or not org:
                    errors.append(f"organizations[{i}]: expected non-empty str")

    if record.get("is_online") not in (None, True, False):
        errors.append("is_online: expected bool or null")

    if record.get("detail_fetch_status") not in DETAIL_FETCH_STATUSES:
        errors.append(f"detail_fetch_status: expected one of {DETAIL_FETCH_STATUSES}")
    # bool is a subclass of int in Python; True must not pass as a status code.
    http_status = record.get("http_status")
    if http_status is not None and (not isinstance(http_status, int) or isinstance(http_status, bool)):
        errors.append("http_status: expected int")
    status = record.get("detail_http_status")
    if status is not None and not isinstance(status, int):
        errors.append("detail_http_status: expected int or null")

    if not isinstance(record.get("extras", {}), dict):
        errors.append("extras: expected dict")

    return errors


# ---------------------------------------------------------------------------
# Legacy (Sections 1-4A fixture adapter only)
# ---------------------------------------------------------------------------

@dataclass
class NormalizedItem:
    """Legacy normalized item shape (Sections 1-4A)."""
    source_name: str
    source_url: str
    item_url: str
    item_type: str = "event"
    title: Optional[str] = None
    raw_text: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    fetched_at: Optional[str] = None
    http_status: Optional[int] = 200
    date_raw: Optional[str] = None
    published_at: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self):
        return asdict(self).keys()


def normalize_event(raw_item: dict, base_url: str) -> dict:
    """Legacy: normalizes a raw parsed event dict (whitespace, canonical URL, ISO date)."""
    raw_title = raw_item.get("title")
    raw_url = raw_item.get("item_url")
    raw_date = raw_item.get("date_raw")
    raw_venue = raw_item.get("venue")
    raw_desc = raw_item.get("description")
    raw_text = raw_item.get("raw_text")

    published_at = None
    candidate_date = raw_item.get("date_datetime") or (raw_date.strip() if raw_date else None)
    if candidate_date:
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
            try:
                published_at = datetime.strptime(candidate_date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    return {
        "title": re.sub(r"\s+", " ", raw_title).strip() if raw_title else None,
        "item_url": resolve_item_url(raw_url, base_url) if raw_url else None,
        "date_raw": raw_date.strip() if raw_date else None,
        "published_at": published_at,
        "venue": re.sub(r"\s+", " ", raw_venue).strip() if raw_venue else None,
        "description": re.sub(r"\s+", " ", raw_desc).strip() if raw_desc else None,
        "raw_text": raw_text.strip() if raw_text else None,
    }


def normalize_events(raw_items: list[dict], base_url: str) -> list[dict]:
    """Legacy: normalizes a batch of raw event items."""
    return [normalize_event(item, base_url=base_url) for item in raw_items]
