"""AUDIT SANDBOX adapter: Chennai Mathematical Institute seminars (custom PHP site, /activities/).

Developed only against the listing fetched once on 2026-09-26 (audit_week2/fixtures/cmi/listing.html).
Structurally different from IIT Bombay: every seminar is an <li> of <br>-separated text lines, there is
NO per-item link (the abstract is a POST form carrying a per-request nonce), dates/times are free text,
and history is split into per-year archive pages (no rel="next" pagination).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.urls import resolve_item_url

CONTAINER_SELECTOR = "div.page_content"
ITEM_SELECTOR = "li"
ABSTRACT_FORM_SELECTOR = "form[action*='show-abstract']"
DISPLAY_TIMEZONE = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30))
_HEADER_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2}|\d{4})$")
_TIME_RE = re.compile(r"(\d{1,2})(?:[.:](\d{2}))?\s*([ap])\.?\s*m\.?|(\d{1,2})[.:](\d{2})", re.IGNORECASE)


class StructuralError(ValueError):
    """Expected container is missing."""


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
        # No per-item URL exists. Identifier = the abstract endpoint + (year, ref), WITHOUT the nonce.
        synthetic = f"{form['action']}?absyear={fields.get('absyear')}&absref={fields.get('absref')}"
        speaker_el = li.select_one("strong")
        form.extract()
        lines = [l.strip() for l in li.get_text("\n").split("\n") if l.strip()]
        get = lambda prefix: next((l[len(prefix):].strip() for l in lines if l.startswith(prefix)), None)  # noqa: E731
        venue_idx = next((i for i, l in enumerate(lines) if l.startswith("Venue:")), None)
        speaker = speaker_el.get_text(" ", strip=True) if speaker_el else None
        after_speaker = lines[lines.index(speaker) + 1] if speaker in lines and lines.index(speaker) + 1 < len(lines) else None
        items.append({
            "item_url": resolve_item_url(synthetic, base_url),
            "header_date": lines[0] if lines else None,
            "series": lines[1] if len(lines) > 1 else None,
            "date_raw": get("Date:"),
            "time_raw": get("Time:"),
            "venue": get("Venue:"),
            "title": lines[venue_idx + 1] if venue_idx is not None and venue_idx + 1 < len(lines) else None,
            "speaker": speaker,
            "affiliation": after_speaker.rstrip(".") if after_speaker else None,
            "absyear": fields.get("absyear"), "absref": fields.get("absref"),
        })
    return items


def _start_utc(header_date: Optional[str], time_raw: Optional[str]) -> Optional[str]:
    """'28-09-26' or '28-09-2026' + '11.00 a.m to 12.45 p.m.' / '2.00 - 3.00 p.m.' / '3:45pm - 4:45pm' (IST)."""
    m = _HEADER_DATE_RE.match(header_date or "")
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = year + 2000 if year < 100 else year
    matches = list(_TIME_RE.finditer(time_raw or ""))
    if not matches:
        return None
    first = matches[0]
    hour = int(first.group(1) or first.group(4))
    minute = int(first.group(2) or first.group(5) or 0)
    meridiem = first.group(3) or next((mm.group(3) for mm in matches if mm.group(3)), None)  # '2.00 - 3.00 p.m.'
    if meridiem and meridiem.lower() == "p" and hour < 12:
        hour += 12
    try:
        local = datetime(year, month, day, hour, minute, tzinfo=IST)
    except ValueError:
        return None
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(record: dict) -> dict:
    speaker = record.get("speaker")
    return {
        "title": record.get("title"),
        "starts_at": _start_utc(record.get("header_date"), record.get("time_raw")),
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
