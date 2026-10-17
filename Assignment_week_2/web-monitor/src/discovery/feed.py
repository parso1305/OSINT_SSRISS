"""RSS 2.0 / Atom parsing for discovery. Takes document content (bytes or text); never fetches.

feedparser.parse() fetches by itself when it is given a URL (and opens a local file when given a path), which
would bypass the project's HTTP client (timeout, robots.txt, User-Agent, logging). So parse_feed():
  * rejects anything that does not look like an XML document (a URL, a path, empty input) with ValueError;
  * always hands feedparser bytes, which it can only treat as document content.
Fetching is the caller's job, through src.fetcher.Fetcher.
"""

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

import feedparser

from src.discovery.record import DiscoveryRecord, make_record, utc_now
from src.discovery.timestamps import format_utc, to_utc_z


class FeedParseError(ValueError):
    """The content is not a readable RSS/Atom document."""


@dataclass(frozen=True)
class FeedEntry:
    link: Optional[str]                # as written in the feed (not yet canonical)
    title: Optional[str]
    entry_id: Optional[str]            # RSS <guid> / Atom <id>
    published: Optional[str]           # UTC Z, or None
    published_raw: Optional[str]       # original string
    updated: Optional[str]
    updated_raw: Optional[str]

    @property
    def timestamp(self) -> Optional[str]:
        """published if present, else updated (discovery's source_timestamp)."""
        return self.published or self.updated

    @property
    def timestamp_raw(self) -> Optional[str]:
        return self.published_raw if self.published_raw else self.updated_raw


@dataclass(frozen=True)
class FeedResult:
    kind: str                          # "rss" or "atom" (discovery_method)
    version: str                       # feedparser's version string, e.g. "rss20", "atom10"
    feed_link: Optional[str]
    entries: list


def _ensure_document(content: Union[bytes, str]) -> bytes:
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError(f"parse_feed expects document content (bytes or str), got {type(content).__name__}")
    head = bytes(content[:512]).lstrip(b"\xef\xbb\xbf \t\r\n")
    if not head.startswith(b"<"):
        # A URL ("https://...") or a file path: feedparser would fetch/open it itself. Refuse.
        raise ValueError("parse_feed expects feed XML content, not a URL or path; fetch it with the "
                         f"project's HTTP client first (got {head[:60]!r})")
    return bytes(content)


def _struct_to_utc(parsed) -> Optional[str]:
    if not parsed:
        return None
    return format_utc(datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc))


def _timestamp(entry, key: str) -> tuple[Optional[str], Optional[str]]:
    # dict.get bypasses feedparser's deprecated published<->updated aliasing: an RSS item has only a pubDate,
    # and reporting it again as "updated" would invent a second timestamp.
    raw = dict.get(entry, key)
    if not raw:
        return None, None
    # feedparser already converts RFC 822 and ISO 8601 dates to a UTC struct_time; fall back to our parser.
    return (_struct_to_utc(dict.get(entry, f"{key}_parsed")) or to_utc_z(raw)), raw


def parse_feed(content: Union[bytes, str]) -> FeedResult:
    """Parses RSS 2.0 or Atom content. Raises ValueError for URL/path input, FeedParseError if unreadable."""
    data = feedparser.parse(_ensure_document(content))
    version = data.get("version") or ""
    if not version:
        problem = data.get("bozo_exception")
        raise FeedParseError(f"not an RSS/Atom feed ({type(problem).__name__ if problem else 'unknown format'}: "
                             f"{problem or 'no <rss> or <feed> root'})")
    kind = "atom" if version.startswith("atom") else "rss"
    entries = []
    for e in data.entries:
        published, published_raw = _timestamp(e, "published")
        updated, updated_raw = _timestamp(e, "updated")
        entries.append(FeedEntry(link=e.get("link"), title=(e.get("title") or None), entry_id=e.get("id"),
                                 published=published, published_raw=published_raw,
                                 updated=updated, updated_raw=updated_raw))
    return FeedResult(kind=kind, version=version, feed_link=data.feed.get("link"), entries=entries)


def feed_records(content: Union[bytes, str], source_name: str, feed_url: str,
                 discovered_at: Optional[str] = None) -> list[DiscoveryRecord]:
    """Feed entries as DiscoveryRecords (method "rss" or "atom"). Relative links resolve against the feed URL.
    Entries whose link is missing or not http(s) are skipped (nothing to discover)."""
    discovered_at = discovered_at or utc_now()
    feed = parse_feed(content)
    records = []
    for entry in feed.entries:
        record = make_record(source_name, entry.link, feed_url, feed.kind, entry.title,
                             entry.timestamp, entry.timestamp_raw, discovered_at)
        if record is not None:
            records.append(record)
    return records
