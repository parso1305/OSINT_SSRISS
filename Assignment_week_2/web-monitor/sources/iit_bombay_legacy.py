"""IIT Bombay source adapter and HTML parser."""

import re
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup

from src.urls import resolve_item_url
from src.schema import NormalizedItem

# Source Metadata & Selectors
LISTING_URL: str = "https://www.iitb.ac.in/events"
CONTAINER_SELECTOR: str = ".view-events-listing"
CARD_SELECTOR: str = ".view-content .views-row"
TITLE_SELECTOR: str = ".event-title"
LINK_SELECTOR: str = "a.event-link"
DATE_SELECTOR: str = ".event-date time"
VENUE_SELECTOR: str = ".event-venue"
DESC_SELECTOR: str = ".event-description"


class StructuralError(ValueError):
    """Raised when expected HTML listing container or card selectors are missing or redesigned."""
    pass


def parse_events(html: str, base_url: str = LISTING_URL) -> list[dict]:
    """
    Parses IIT Bombay event listing HTML into raw dictionaries.

    Args:
        html: Raw HTML string.
        base_url: Base URL used for resolving relative URLs to absolute.

    Returns:
        List of raw event dicts before normalization.

    Raises:
        StructuralError: If the expected container structure is absent, indicating a site redesign.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Verify structural layout presence
    listing_container = soup.select_one(CONTAINER_SELECTOR)
    if not listing_container:
        msg = f"Structural layout mismatch: Target container '{CONTAINER_SELECTOR}' not found in HTML. Site structure may have changed."
        raise StructuralError(msg)

    cards = listing_container.select(CARD_SELECTOR)
    if not cards:
        return []

    events = []
    for card in cards:
        # Title
        title_el = card.select_one(TITLE_SELECTOR)
        title = title_el.get_text(" ", strip=True) if title_el else None

        # Link
        link_el = card.select_one(LINK_SELECTOR)
        raw_href = link_el["href"].strip() if (link_el and link_el.has_attr("href")) else None
        item_url = resolve_item_url(raw_href, base_url) if raw_href else None

        # Date
        time_el = card.select_one(DATE_SELECTOR)
        date_raw = time_el.get_text(" ", strip=True) if time_el else None
        date_datetime = time_el.get("datetime") if time_el else None

        # Optional Venue
        venue_el = card.select_one(VENUE_SELECTOR)
        venue = venue_el.get_text(" ", strip=True) if venue_el else None

        # Optional Description
        desc_el = card.select_one(DESC_SELECTOR)
        description = desc_el.get_text(" ", strip=True) if desc_el else None

        # Raw Text
        raw_text = card.get_text(" ", strip=True)

        events.append({
            "title": title,
            "item_url": item_url,
            "date_raw": date_raw,
            "date_datetime": date_datetime,
            "venue": venue,
            "description": description,
            "raw_text": raw_text
        })

    return events


# Section 2 standard naming alias
parse_listing = parse_events


def normalize_item(raw_item: dict, base_url: str = LISTING_URL) -> NormalizedItem:
    """
    Normalizes raw parsed IIT Bombay event dictionary into NormalizedItem.
    Applies whitespace stripping, URL canonicalization, and ISO date formatting.
    """
    raw_title = raw_item.get("title")
    title = re.sub(r'\s+', ' ', raw_title).strip() if raw_title else None

    raw_url = raw_item.get("item_url")
    item_url = resolve_item_url(raw_url, base_url) if raw_url else ""

    raw_date = raw_item.get("date_raw")
    date_raw = raw_date.strip() if raw_date else None

    published_at = None
    candidate_date = raw_item.get("date_datetime") or date_raw
    if candidate_date:
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(candidate_date, fmt)
                published_at = dt.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    raw_venue = raw_item.get("venue")
    venue = re.sub(r'\s+', ' ', raw_venue).strip() if raw_venue else None

    raw_desc = raw_item.get("description")
    description = re.sub(r'\s+', ' ', raw_desc).strip() if raw_desc else None

    raw_text = raw_item.get("raw_text")
    clean_raw_text = raw_text.strip() if raw_text else None

    return NormalizedItem(
        source_name="iit_bombay",
        source_url=base_url,
        item_url=item_url,
        item_type="event",
        title=title,
        raw_text=clean_raw_text,
        first_seen_at=None,
        last_seen_at=None,
        fetched_at=None,
        http_status=200,
        date_raw=date_raw,
        published_at=published_at,
        venue=venue,
        description=description
    )
