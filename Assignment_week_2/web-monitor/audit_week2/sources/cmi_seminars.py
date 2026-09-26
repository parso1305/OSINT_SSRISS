"""AUDIT SANDBOX adapter: Chennai Mathematical Institute seminars (custom PHP site, /activities/).

Developed only against the listing fetched once on 2026-09-26 (audit_week2/fixtures/cmi/listing.html).
Structurally different from IIT Bombay: every seminar is an <li> of <br>-separated text lines, there is
NO per-item link (the abstract is a POST form carrying a per-request nonce), dates/times are free text,
and history is split into per-year archive pages (no rel="next" pagination).

Line layout of one item (135 in the fixture; the labelled lines come in varying order and may be absent):
  header date (dd-mm-yy) | series | [Speaker: ..] [Date: ..] [Time: ..] [schedule lines] [Venue: ..]
  | title (may be missing, or split by a stray backslash-newline) | <strong>speaker</strong> | affiliation
Times: "Time: 3:30 p.m." on one line, or a blank "Time:" / a format line followed by schedule lines
("11:00 - 11:30 am: Pre-seminar"). Multi-session series list several sessions; the header date is the
session the entry is listed under, so starts_at = header date + the first time given (full schedule kept
in extras.time_raw).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.urls import synthetic_item_url

CONTAINER_SELECTOR = "div.page_content"
ITEM_SELECTOR = "li"
ABSTRACT_FORM_SELECTOR = "form[action*='show-abstract']"
DISPLAY_TIMEZONE = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30))
_LABEL_RE = re.compile(r"^(Speaker|Date|Dates|Date of lecture \d+|Time|Venue)\s*:", re.IGNORECASE)
_HEADER_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2}|\d{4})$")
_TIME_RE = re.compile(r"(\d{1,2})(?:[.:](\d{2}))?\s*([ap])\.?\s*m\.?|(\d{1,2})[.:](\d{2})", re.IGNORECASE)


class StructuralError(ValueError):
    """Expected container is missing."""


def _title(lines: list[str]) -> Optional[str]:
    """The unlabelled lines between the last labelled line and the speaker; a trailing '\\' joins a split line."""
    text = ""
    for line in lines:
        text = text[:-1] + line if text.endswith("\\") else (f"{text} {line}" if text else line)
    return text.strip() or None


def parse_listing(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(CONTAINER_SELECTOR)
    if not container:
        raise StructuralError(f"container '{CONTAINER_SELECTOR}' not found")
    items = []
    for li in container.select(ITEM_SELECTOR):
        form = li.select_one(ABSTRACT_FORM_SELECTOR)
        if not form:
            continue                                   # year links etc.
        fields = {i["name"]: i.get("value") for i in form.select("input[type=hidden][name]")}
        speaker_el = li.select_one("strong")
        form.extract()
        lines = [l.strip() for l in li.get_text("\n").split("\n") if l.strip()]
        get = lambda prefix: next((l[len(prefix):].strip() for l in lines if l.startswith(prefix)), None)  # noqa: E731
        speaker = speaker_el.get_text(" ", strip=True) if speaker_el else None
        speaker_idx = lines.index(speaker, 2) if speaker in lines[2:] else len(lines)
        labelled = [i for i in range(2, speaker_idx) if _LABEL_RE.match(lines[i])]
        body_end = labelled[-1] + 1 if labelled else 2
        # Schedule: unlabelled lines before the title + the text of "Time:" lines (a blank "Time:" is followed by
        # the schedule), skipping Speaker/Date/Venue lines.
        schedule = [re.sub(r"^Time\s*:\s*", "", l, flags=re.IGNORECASE) for l in lines[2:body_end]
                    if not _LABEL_RE.match(l) or l.lower().startswith("time")]
        items.append({
            # No per-item URL exists: identity = the site's own abstract record (year, ref), never the nonce.
            "item_url": synthetic_item_url(base_url, fields.get("absyear"), fields.get("absref")),
            "header_date": lines[0] if lines else None,
            "series": lines[1] if len(lines) > 1 else None,
            "date_raw": get("Date:"),
            "time_raw": " | ".join(s for s in schedule if s) or None,
            "venue": get("Venue:"),
            "title": _title(lines[body_end:speaker_idx]),
            "speaker": speaker,
            "affiliation": lines[speaker_idx + 1].rstrip(".") if speaker_idx + 1 < len(lines) else None,
            "absyear": fields.get("absyear"), "absref": fields.get("absref"),
        })
    return items


def _start(record: dict) -> tuple[Optional[str], Optional[str]]:
    """(starts_at, None), or (None, the raw text that could not be turned into a start).

    Header date '28-09-26' + the first time in the schedule ('11.00 a.m to 12.45 p.m.', '2.00 - 3.00 p.m.',
    '11:00 - 11:30 am: Pre-seminar | ...'), IST -> UTC. A header date with no time anywhere -> date-only 'YYYY-MM-DD'.
    """
    time_raw = record.get("time_raw") or ""
    m = _HEADER_DATE_RE.match(record.get("header_date") or "")
    if not m:
        return None, record.get("header_date") or ""
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = year + 2000 if year < 100 else year
    matches = next((found for found in (list(_TIME_RE.finditer(seg)) for seg in time_raw.split(" | ")) if found), None)
    try:
        if not matches:
            return datetime(year, month, day).strftime("%Y-%m-%d"), None      # date-only
        first = matches[0]
        hour = int(first.group(1) or first.group(4))
        minute = int(first.group(2) or first.group(5) or 0)
        meridiem = first.group(3) or next((mm.group(3) for mm in matches if mm.group(3)), None)  # '2.00 - 3.00 p.m.'
        if meridiem and meridiem.lower() == "p" and hour < 12:
            hour += 12
        local = datetime(year, month, day, hour, minute, tzinfo=IST)
    except ValueError:
        return None, f"{record.get('header_date')} {time_raw}".strip()
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), None


def normalize(record: dict) -> dict:
    speaker = record.get("speaker")
    starts_at, unparsed = _start(record)
    return {
        "parse_warnings": {"starts_at": unparsed} if unparsed else {},
        "title": record.get("title"),
        "starts_at": starts_at,
        "ends_at": None,
        "timezone": DISPLAY_TIMEZONE,
        "speakers": [{"name": speaker, "affiliation": record.get("affiliation")}] if speaker else [],
        "venue": record.get("venue"),
        "is_online": True if record.get("venue") and re.search(r"online|zoom", record["venue"], re.I) else None,
        "event_type": record.get("series"),
        "description": None,                 # abstract only via POST + nonce: not fetchable with GET
        "extras": {k: record.get(k) for k in ("header_date", "date_raw", "time_raw", "absyear", "absref")
                   if record.get(k) is not None},
    }
