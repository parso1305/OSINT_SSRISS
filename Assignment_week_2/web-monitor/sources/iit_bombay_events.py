"""Adapter: IIT Bombay institute events calendar (Week 3 central aggregator target, D1).

Site-specific values only: listing selectors, label patterns, router patterns and the detail-page parser.
Everything generic (discovery, scope, routing, fetching, storage, entity helpers, metrics) lives in src/.

Discovery (HTML, D11): the homepage's events block, a server-rendered view of the same Drupal "events" view that
/events draws client-side with FullCalendar (its items are only JSON in drupal-settings-json; see
assignments/week3/00_candidates/iit_bombay_aggregators.md, C1 JS check).

Detail pages (/event/<slug>): Drupal field classes for title, event type, date range and venue; people only in the
body as labelled lines ("Speaker: Prof. X, Affiliation", "Organizer: Prof. Y — ...").
Timestamp trap: the detail <time datetime="2026-09-03T17:15:00Z"> is IST wall-clock time mislabelled as UTC (the
homepage block gives 11:45Z for the same 17:15 IST lecture). The trailing Z is dropped and the value is read as
IST (+05:30, no DST) before converting to UTC.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

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
