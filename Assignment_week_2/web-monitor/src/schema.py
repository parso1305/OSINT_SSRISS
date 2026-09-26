"""Shared cross-team record schema (Assignment 6, section c) and validation.

Record layout for content_type "event":
  IDENTIFIERS   item_url, source_id, institution
  CONTENT       content_type, title, starts_at, ends_at, timezone, speakers, venue, is_online,
                event_type, organizer, description
  PROVENANCE    listing_fetched_at, detail_fetched_at, detail_fetch_status, detail_http_status,
                detail_error (+ content_hash, first_seen_at, last_seen_at, added by storage)
  extras        dict of source-specific fields (never shared columns)

Dates (starts_at, ends_at):
  "YYYY-MM-DDTHH:MM:SSZ"   an instant, always UTC
  "YYYY-MM-DD"             date-only: the event's local calendar date in `timezone` (all-day, or the site
                           gives no time). Never converted to UTC (a date without a time has no UTC instant).
                           Requires `timezone`; ends_at, if present, must then be date-only too.
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

IDENTIFIER_FIELDS = ("item_url", "source_id", "institution")
CONTENT_FIELDS = (
    "content_type", "title", "starts_at", "ends_at", "timezone", "speakers", "venue",
    "is_online", "event_type", "organizer", "description",
)
PROVENANCE_FIELDS = (
    "listing_fetched_at", "detail_fetched_at", "detail_fetch_status", "detail_http_status", "detail_error",
)
STORAGE_FIELDS = ("content_hash", "first_seen_at", "last_seen_at")
RECORD_FIELDS = IDENTIFIER_FIELDS + CONTENT_FIELDS + PROVENANCE_FIELDS + ("extras",)

REQUIRED_FIELDS = ("item_url", "source_id", "institution", "content_type", "title", "starts_at")
DETAIL_FETCH_STATUSES = ("ok", "failed", "not_attempted")
CONTENT_TYPES = ("event",)
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_STRING_FIELDS = ("source_id", "institution", "content_type", "title", "timezone", "venue",
                  "event_type", "organizer", "description", "detail_error")
_EVENT_TIME_FIELDS = ("starts_at", "ends_at")                  # UTC timestamp or date-only
_FETCH_TIME_FIELDS = ("listing_fetched_at", "detail_fetched_at")  # always UTC timestamps


def is_date_only(value: Any) -> bool:
    """True for a valid ISO calendar date 'YYYY-MM-DD' (the date-only form of starts_at / ends_at)."""
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
      item_url    always the listing's canonical URL (merged["item_url"]), never from the adapter
      identity    source_id / institution / content_type from config; organizer from adapter or config
      content     from the adapter's normalize()
      provenance  from the fetch/enrich stages (merged record)
    """
    record = {field: normalized.get(field) for field in CONTENT_FIELDS}
    record["item_url"] = merged.get("item_url")
    record["source_id"] = config.source_id
    record["institution"] = config.institution
    record["content_type"] = config.content_type
    record["organizer"] = normalized.get("organizer") or config.organizer
    record["speakers"] = normalized.get("speakers") or []
    for field in PROVENANCE_FIELDS:
        record[field] = merged.get(field)
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

    if record.get("content_type") not in (None, *CONTENT_TYPES):
        errors.append(f"content_type: expected one of {CONTENT_TYPES}")

    starts_at, ends_at = record.get("starts_at"), record.get("ends_at")
    if is_date_only(starts_at) and not record.get("timezone"):
        errors.append("timezone: required when starts_at is date-only (it is a local calendar date)")
    if isinstance(starts_at, str) and isinstance(ends_at, str):
        if is_date_only(starts_at) != is_date_only(ends_at):
            errors.append("ends_at: must be date-only exactly when starts_at is")
        elif ends_at < starts_at:
            errors.append("ends_at: earlier than starts_at")

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

    if record.get("is_online") not in (None, True, False):
        errors.append("is_online: expected bool or null")

    if record.get("detail_fetch_status") not in DETAIL_FETCH_STATUSES:
        errors.append(f"detail_fetch_status: expected one of {DETAIL_FETCH_STATUSES}")
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
