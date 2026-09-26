"""IIT Bombay adapter: HSS Department "Seminars and Talks" (Drupal 9 Views listing + event nodes).

Contains only selectors/constants, parse_listing, parse_detail and normalize. Fetching, pagination,
enrichment, validation and storage are generic (src/). Selectors verified against live HTML fetched
2026-09-25/26 (fixtures/iit_bombay_hss/).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.urls import resolve_item_url

# Listing page (Drupal Views)
CONTAINER_SELECTOR = ".view-seminars-and-talks .view-content"
CARD_SELECTOR = ".event-card-wrapper"
TITLE_LINK_SELECTOR = ".event-name a"
CATEGORY_SELECTOR = ".event-category span"
CARD_DETAIL_SELECTOR = ".event-room-details li"
NEXT_PAGE_SELECTOR = "a[rel~='next']"  # <a href="?page=1" ... rel="next">, live_page_1.html:739

# Detail page (Drupal node--type-events)
DETAIL_ARTICLE_SELECTOR = "article.node--type-events"
DETAIL_FIELD_SELECTOR = ".field--name-field-event-{name} .field__item"
DETAIL_BODY_SELECTOR = ".field--name-body"

# Normalization rules (each observed on the 10 live records reviewed in assignments/06_schema)
SITE_TITLE_SUFFIX = " | Humanities and Social Sciences"
DISPLAY_TIMEZONE = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30))  # India observes no DST
HONORIFIC_RE = re.compile(r"^(?:Prof(?:essor)?|Dr)\.?\s+", re.IGNORECASE)
DESCRIPTION_LABEL_RE = re.compile(r"^(?:Abstract|Description)\s*:\s*", re.IGNORECASE)
ONLINE_VENUE_RE = re.compile(r"\bonline\b", re.IGNORECASE)
_ORDINAL_RE = re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b", re.IGNORECASE)


class StructuralError(ValueError):
    """Expected container is missing: the site was redesigned or this is not an event page."""


def parse_listing(html: str, base_url: str) -> list[dict]:
    """Parses one listing page into raw dicts; item_url is canonicalized with resolve_item_url."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(CONTAINER_SELECTOR)
    if not container:
        raise StructuralError(
            f"Structural layout mismatch: Target container '{CONTAINER_SELECTOR}' not found in HTML. "
            "Site structure may have changed."
        )

    items = []
    for card in container.select(CARD_SELECTOR):
        link_el = card.select_one(TITLE_LINK_SELECTOR)
        raw_href = link_el.get("href") if link_el else None
        category_el = card.select_one(CATEGORY_SELECTOR)

        # Card detail rows are identified by icon class: calendar, time, marker (venue)
        details = {}
        for li in card.select(CARD_DETAIL_SELECTOR):
            icon = li.select_one("i.icon")
            classes = icon.get("class", []) if icon else []
            text = li.get_text(" ", strip=True)
            if "icon-calendar" in classes:
                details["date_raw"] = text
            elif "icon-time" in classes:
                details["time_raw"] = text
            elif "icon-marker" in classes:
                details["venue"] = text

        items.append({
            "title": link_el.get_text(" ", strip=True) if link_el else None,
            "raw_href": raw_href,
            "item_url": resolve_item_url(raw_href, base_url) if raw_href else None,
            "category": category_el.get_text(" ", strip=True) if category_el else None,
            "date_raw": details.get("date_raw"),
            "time_raw": details.get("time_raw"),
            "venue": details.get("venue"),
            "raw_text": card.get_text(" ", strip=True),
        })
    return items


def parse_detail(html: str, item_url: str) -> dict:
    """
    Parses one event detail page into the fields present there (raw; cleaning is normalize's job).

    title comes from <title> (still carrying the site suffix), NOT field-event-title: that field is
    typed separately by editors and is wrong on at least one live page ("Echoes of Translation:
    Echoes of Translation:Audibility..."), while <title> matches the listing. Because the generic
    merge lets detail values win, reading field-event-title would overwrite a correct listing title.
    starts_at/ends_at are the <time datetime> attributes (UTC, "Z"); the visible text is IST.

    Raises:
        StructuralError: If the event article is absent.
    """
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(DETAIL_ARTICLE_SELECTOR)
    if not article:
        raise StructuralError(
            f"Structural layout mismatch: detail container '{DETAIL_ARTICLE_SELECTOR}' not found on {item_url}."
        )

    def field_text(name: str) -> Optional[str]:
        el = article.select_one(DETAIL_FIELD_SELECTOR.format(name=name))
        return el.get_text(" ", strip=True) or None if el else None

    def field_datetime(name: str) -> Optional[str]:
        el = article.select_one(DETAIL_FIELD_SELECTOR.format(name=name) + " time")
        return el.get("datetime") if el else None

    title_el = soup.select_one("title")
    body_el = article.select_one(DETAIL_BODY_SELECTOR)
    image_el = article.select_one(DETAIL_FIELD_SELECTOR.format(name="image") + " img")
    canonical_el = soup.select_one("link[rel='canonical']")

    return {
        "title": title_el.get_text(strip=True) or None if title_el else None,
        "speaker": field_text("speaker"),
        "starts_at": field_datetime("date"),
        "ends_at": field_datetime("end-date"),
        "venue": field_text("location"),
        "event_type": field_text("type"),
        "description": body_el.get_text(" ", strip=True) or None if body_el else None,
        "image_url": resolve_item_url(image_el.get("src"), item_url) or None if image_el else None,
        "detail_canonical_url": resolve_item_url(canonical_el.get("href"), item_url) or None if canonical_el else None,
        "node_id": article.get("data-history-node-id"),
    }


def _clean(text: Optional[str]) -> Optional[str]:
    return re.sub(r"\s+", " ", text).strip() or None if text else None


def _to_utc(value: Optional[str]) -> Optional[str]:
    """'2025-09-25T10:00:00Z' (or any offset-aware ISO value) -> UTC 'Z' string; naive values -> None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _listing_start_utc(date_raw: Optional[str], time_raw: Optional[str]) -> Optional[str]:
    """Listing fallback: '25th Sep 2025' + '15:30 PM' (IST; 24-hour clock with a stray PM) -> UTC 'Z'."""
    if not date_raw or not time_raw:
        return None
    cleaned = _ORDINAL_RE.sub(r"\1", date_raw).strip()
    day = None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            day = datetime.strptime(cleaned, fmt)
            break
        except ValueError:
            continue
    match = _TIME_RE.search(time_raw)
    if day is None or not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), (match.group(3) or "").upper()
    if meridiem == "PM" and hour < 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    local = day.replace(hour=hour, minute=minute, tzinfo=IST)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _speakers(raw: Optional[str]) -> list[dict]:
    """'Prof Salvatore Babones, University of Sydney' -> [{'name': 'Salvatore Babones', 'affiliation': 'University of Sydney'}]."""
    text = _clean(raw)
    if not text:
        return []
    name, _, affiliation = text.partition(", ")
    name = HONORIFIC_RE.sub("", name).strip()
    return [{"name": name, "affiliation": affiliation.strip() or None}] if name else []


def normalize(record: dict) -> dict:
    """Source-specific cleaning of a merged listing(+detail) record into shared-schema content fields.

    A date that is present but unparseable is reported in parse_warnings {field: raw} (logged by the runner;
    storage keeps the stored value) and treated as no value, so the listing fallback applies.
    """
    title = _clean(record.get("title"))
    venue = _clean(record.get("venue"))
    description = _clean(record.get("description"))
    parse_warnings: dict[str, str] = {}

    def utc(field: str) -> Optional[str]:
        raw = record.get(field)
        value = _to_utc(raw)
        if raw and value is None:
            parse_warnings[field] = raw
        return value

    starts_at = utc("starts_at") or _listing_start_utc(record.get("date_raw"), record.get("time_raw"))
    if starts_at is None and record.get("date_raw"):
        parse_warnings.setdefault("starts_at", f"{record.get('date_raw')} {record.get('time_raw') or ''}".strip())
    return {
        "parse_warnings": parse_warnings,
        "title": title.removesuffix(SITE_TITLE_SUFFIX) if title else None,
        "starts_at": starts_at,
        "ends_at": utc("ends_at"),
        "timezone": DISPLAY_TIMEZONE,
        "speakers": _speakers(record.get("speaker")),
        "venue": venue,
        "is_online": True if venue and ONLINE_VENUE_RE.search(venue) else None,
        "event_type": _clean(record.get("event_type") or record.get("category")),
        "description": DESCRIPTION_LABEL_RE.sub("", description) or None if description else None,
        "extras": {key: record.get(key) for key in (
            "node_id", "detail_canonical_url", "date_raw", "time_raw", "raw_href", "raw_text",
            "discovered_on_url", "discovered_on_page",
        ) if record.get(key) is not None},
    }
