"""Adapter: IIT Bombay institute events calendar (Week 3 central aggregator target, D1).

Site-specific values only: listing selectors, label patterns, router patterns and the detail-page parser.
Everything generic (discovery, scope, routing, fetching, storage, entity helpers, metrics) lives in src/.

Discovery (HTML), two ways, chosen by the source's config:
  * live source iit_bombay_events (repair R1, D33): the /events calendar. Its items exist only as JSON inside
    drupal-settings-json (FullCalendar), decoded by calendar_entries() below; the lecture-type title filter and the
    ordering come from the config's listing_options.
  * offline source local_aggregator_fixture: LISTING_SELECTORS on the homepage events block (D11, superseded for the
    live source).

Detail pages (/event/<slug>): Drupal field classes for title, event type, date range and venue; people only in the
body as labelled lines ("Speaker: Prof. X, Affiliation", "Organizer: Prof. Y — ...").
Timestamp trap: the detail <time datetime="2026-09-03T17:15:00Z"> is IST wall-clock time mislabelled as UTC (the
homepage block gives 11:45Z for the same 17:15 IST lecture). The trailing Z is dropped and the value is read as
IST (+05:30, no DST) before converting to UTC.
"""

import html as html_lib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.discovery.timestamps import parse_utc_offset
from src.entities import block_lines, collapse, extract_mentions, organizations_field, speakers_field

TIMEZONE = "Asia/Kolkata"
UTC_OFFSET = timedelta(hours=5, minutes=30)   # IST has no daylight saving time

# The homepage events block: one .views-row per event, <time datetime> in correct UTC (e.g. 17:15 IST ->
# "2026-09-03T11:45:00Z"), the title link inside .views-field-title.
LISTING_SELECTORS = {
    "item": ".homepage-events .views-row",
    "link": ".views-field-title a",
    "date": ".views-field-field-event-date time",
    "date_attr": "datetime",
}

# Labels this site actually uses (20 saved detail pages, 2026-10-16/17): "Speaker:" (12 pages), "Organizer:"
# (1 page, a person). The other roles' usual labels are listed so a page that uses them is read, never guessed.
LABELS = {
    "speaker": ["Speaker", "Speakers", "Guest Speaker", "Keynote Speaker"],
    "chair": ["Chair", "Chairperson", "Session Chair", "Chaired by"],
    "moderator": ["Moderator", "Moderated by"],
    "host": ["Host", "Hosted by"],
    "organizer": ["Organizer", "Organiser", "Organizers", "Organisers", "Organized by", "Organised by"],
    "co-organizer": ["Co-organizer", "Co-organiser", "Co-organized by", "Co-organised by"],
}


def _text(node) -> Optional[str]:
    return collapse(node.get_text(" ")) or None if node is not None else None


def _ist_to_utc(datetime_attr: Optional[str]) -> Optional[str]:
    """'2026-09-03T17:15:00Z' (IST mislabelled as Z) -> '2026-09-03T11:45:00Z'."""
    if not datetime_attr:
        return None
    try:
        local = datetime.strptime(datetime_attr.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return (local - UTC_OFFSET).replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_event_detail(html: str, item_url: str) -> dict:
    """Detail page -> {"fields": shared-schema content fields, "people": [PersonMention], "orgs": [OrgMention],
    "parse_warnings": {field: raw}}. Never fetches."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.node--type-event")
    if article is None:
        raise ValueError("no <article class='node--type-event'>: not an event detail page (layout changed?)")
    times = article.select(".field--name-field-event-date time")
    raw_start = times[0].get("datetime") if times else None
    raw_end = times[1].get("datetime") if len(times) > 1 else None
    start, end = _ist_to_utc(raw_start), _ist_to_utc(raw_end)
    warnings = {}
    if raw_start and not start:
        warnings["event_start"] = raw_start
    if raw_end and not end:
        warnings["event_end"] = raw_end
    body = article.select_one(".field--name-body")
    people, orgs = extract_mentions(block_lines(body), LABELS) if body is not None else ([], [])
    venue = article.select_one(".field--name-field-vanue .field__item") or article.select_one(".field--name-field-vanue")
    location = _text(venue)
    if location and location.startswith("Venue "):
        location = location[len("Venue "):]
    fields = {
        "title": _text(article.select_one(".field--name-title")),
        "event_start": start,
        "event_end": end,
        "timezone": TIMEZONE,
        "location": location,
        "event_type": _text(article.select_one(".field--name-field-event-type")),
        "description": _text(body),
        "speakers": speakers_field(people),
        "organizations": organizations_field(orgs),
        "is_online": None,
        "extras": {"event_datetime_raw": [raw_start, raw_end]},
    }
    return {"fields": fields, "people": people, "orgs": orgs, "parse_warnings": warnings}


# -- calendar listing hook (repair R1; config listing_options, generic change G10) ------------------------------
# /events draws its calendar with FullCalendar from JSON embedded in the page:
#   <script type="application/json" data-drupal-selector="drupal-settings-json"> ... "fullCalendarView": [{
#     "calendar_options": "{... \"timeZone\": \"Asia/Kolkata\", \"events\": [{title, url, start, eid, ...}] ...}"}]
# Each entry has only title, url, start (local IST, no offset) and node id: no event type, speaker or organizer.

def calendar_entries(html: str, page_url: str, options: dict, now_iso: str) -> list[dict]:
    """Calendar entries whose title contains one of options["include_title_keywords"] (case-insensitive), one per
    URL, ordered upcoming first (soonest first), then past ones (most recent first). Never fetches."""
    script = BeautifulSoup(html, "html.parser").find("script", attrs={"data-drupal-selector": "drupal-settings-json"})
    if script is None or not script.string:
        raise ValueError("no drupal-settings-json script: calendar layout changed?")
    settings = json.loads(script.string)
    try:
        calendar = json.loads(settings["fullCalendarView"][0]["calendar_options"])
        events = calendar["events"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ValueError(f"fullCalendarView events not found in drupal-settings-json: {e!r}") from e
    keywords = [k.casefold() for k in options.get("include_title_keywords", [])]
    offset = parse_utc_offset(options.get("utc_offset") or "+05:30")
    upcoming, past = [], []
    for event in events:
        title = " ".join(html_lib.unescape(event.get("title") or "").split())
        if keywords and not any(k in title.casefold() for k in keywords):
            continue
        raw = event.get("start")
        try:
            start = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=offset).astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue                                   # no readable start: not a schedulable calendar entry
        entry = {"href": event.get("url"), "title": title, "timestamp_raw": raw,
                 "timestamp": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "category": None}
        (upcoming if entry["timestamp"] >= now_iso else past).append(entry)
    ordered = sorted(upcoming, key=lambda e: e["timestamp"]) + sorted(past, key=lambda e: e["timestamp"], reverse=True)
    seen, unique = set(), []
    for entry in ordered:                              # recurring entries share one URL: keep its first position
        if entry["href"] not in seen:
            seen.add(entry["href"])
            unique.append(entry)
    return unique
