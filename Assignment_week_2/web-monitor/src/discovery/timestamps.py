"""Timestamp normalization for discovery: every source timestamp becomes ISO 8601 UTC with a Z, or None.

Same convention as fetched_at ("YYYY-MM-DDTHH:MM:SSZ"). The original string is always kept next to the result
(source_timestamp_raw), so a value this module cannot read is never lost, only left un-normalized.

Accepted inputs:
  RFC 822 / 1123 (RSS pubDate)     "Fri, 16 Oct 2026 09:44:35 +0000", "... GMT", "... +0530"
  ISO 8601 with an offset or Z     "2026-10-16T09:44:35Z", "2026-10-16T15:14:35+05:30" (Atom, sitemap lastmod)
  ISO 8601 without an offset       "2026-10-21T17:15:00": local wall-clock time; converted only when the caller
                                   passes the source's fixed UTC offset (e.g. "+05:30"), else None
  date only                        "2026-10-16" -> None: a calendar date has no UTC instant (same rule as
                                   schema.event_start), the raw string is kept
"""

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

_OFFSET_RE = re.compile(r"^([+-])(\d{2}):?(\d{2})$")
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_utc_offset(offset: Optional[str]) -> Optional[timezone]:
    """'+05:30' / '+0530' / 'Z' -> a fixed tzinfo. None for None/empty. Raises ValueError for anything else."""
    if not offset:
        return None
    if offset in ("Z", "+00:00", "UTC"):
        return timezone.utc
    m = _OFFSET_RE.match(offset.strip())
    if not m:
        raise ValueError(f"not a UTC offset: {offset!r}")
    sign = 1 if m.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc_z(raw: Optional[str], default_utc_offset: Optional[str] = None) -> Optional[str]:
    """Normalizes one timestamp string to 'YYYY-MM-DDTHH:MM:SSZ'; None when it cannot be read as an instant."""
    if raw is None:
        return None
    text = " ".join(str(raw).split())
    if not text or _DATE_ONLY_RE.match(text):
        return None
    dt: Optional[datetime] = None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
    if dt.tzinfo is None:
        tz = parse_utc_offset(default_utc_offset)
        if tz is None:
            return None  # local time with no known offset: not an instant we can state in UTC
        dt = dt.replace(tzinfo=tz)
    return format_utc(dt)
