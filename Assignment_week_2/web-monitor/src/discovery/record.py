"""The unified discovery record (Week 3 1B): one shape for an item URL found by any discovery method.

Spec fields (to_spec_dict() returns exactly these six):
  source_name        config source_id of the source that found it
  discovered_url     canonical URL: always the output of src.urls.resolve_item_url()
  discovery_method   "html" | "rss" | "atom" | "sitemap"
  discovered_title   title as shown by the source (listing link text, feed <title>), or None (sitemaps have none)
  source_timestamp   the source's own timestamp for the item, ISO 8601 UTC "...Z", or None
  discovered_at      when this run found it, ISO 8601 UTC "...Z" (same convention as fetched_at)
Extra provenance (kept on the object, not in the spec dict):
  source_timestamp_raw   the timestamp exactly as the source wrote it, so nothing is lost when it
                         cannot be normalized (date-only, local time without an offset, free text)

A discovery record is only a candidate. It is not an event record: see
assignments/week3/01_discovery/findings.md (1A checkpoint).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlsplit

from src.schema import UTC_TIMESTAMP_RE
from src.urls import resolve_item_url

DISCOVERY_METHODS = ("html", "rss", "atom", "sitemap")
SPEC_FIELDS = ("source_name", "discovered_url", "discovery_method", "discovered_title", "source_timestamp",
               "discovered_at")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DiscoveryRecord:
    source_name: str
    discovered_url: str
    discovery_method: str
    discovered_title: Optional[str]
    source_timestamp: Optional[str]
    discovered_at: str
    source_timestamp_raw: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source_name:
            raise ValueError("source_name: required")
        if self.discovery_method not in DISCOVERY_METHODS:
            raise ValueError(f"discovery_method: expected one of {DISCOVERY_METHODS}, got {self.discovery_method!r}")
        parts = urlsplit(self.discovered_url or "")
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"discovered_url: expected an absolute http(s) URL, got {self.discovered_url!r}")
        if resolve_item_url(self.discovered_url, "") != self.discovered_url:
            # Only resolve_item_url() may produce it, so every method yields the same key for the same item.
            raise ValueError(f"discovered_url: not canonical (pass it through resolve_item_url): {self.discovered_url!r}")
        if not (isinstance(self.discovered_at, str) and UTC_TIMESTAMP_RE.match(self.discovered_at)):
            raise ValueError(f"discovered_at: expected ISO 8601 UTC 'YYYY-MM-DDTHH:MM:SSZ', got {self.discovered_at!r}")
        if self.source_timestamp is not None and not (isinstance(self.source_timestamp, str)
                                                      and UTC_TIMESTAMP_RE.match(self.source_timestamp)):
            raise ValueError(f"source_timestamp: expected ISO 8601 UTC 'YYYY-MM-DDTHH:MM:SSZ' or None, "
                             f"got {self.source_timestamp!r}")

    def to_spec_dict(self) -> dict:
        """Exactly the six spec fields (source_timestamp_raw stays on the object)."""
        return {name: getattr(self, name) for name in SPEC_FIELDS}


def make_record(source_name: str, href: Optional[str], page_url: str, method: str, title: Optional[str],
                timestamp: Optional[str], timestamp_raw: Optional[str], discovered_at: str) -> Optional[DiscoveryRecord]:
    """Builds a record from a raw href; None when the href is not an http(s) item URL (mailto:, javascript:, '')."""
    url = resolve_item_url(href, page_url)
    if not url:
        return None
    clean_title = " ".join(title.split()) if title else None
    return DiscoveryRecord(source_name=source_name, discovered_url=url, discovery_method=method,
                           discovered_title=clean_title or None, source_timestamp=timestamp,
                           discovered_at=discovered_at, source_timestamp_raw=timestamp_raw)

