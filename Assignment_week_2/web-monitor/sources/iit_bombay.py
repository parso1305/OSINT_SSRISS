"""IIT Bombay source adapter and HTML parser."""

import logging
from bs4 import BeautifulSoup
from src.urls import resolve_url

logger = logging.getLogger("web_monitor")


class StructuralError(ValueError):
    """Raised when expected HTML listing container or card selectors are missing or redesigned."""
    pass


def parse_events(html: str, base_url: str = "https://www.iitb.ac.in") -> list[dict]:
    """
    Parses IIT Bombay event listing HTML.

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
    listing_container = soup.select_one(".view-events-listing")
    if not listing_container:
        msg = "Structural layout mismatch: Target container '.view-events-listing' not found in HTML. Site structure may have changed."
        logger.error(msg)
        raise StructuralError(msg)

    cards = listing_container.select(".view-content .views-row")
    if not cards:
        logger.warning("Empty listing encountered: container exists but contains zero event cards.")
        return []

    events = []
    for card in cards:
        # Title
        title_el = card.select_one(".event-title")
        title = title_el.get_text(" ", strip=True) if title_el else None

        # Link
        link_el = card.select_one("a.event-link")
        raw_href = link_el["href"].strip() if (link_el and link_el.has_attr("href")) else None
        item_url = resolve_url(base_url, raw_href) if raw_href else None

        # Date
        time_el = card.select_one(".event-date time")
        date_raw = time_el.get_text(" ", strip=True) if time_el else None
        date_datetime = time_el.get("datetime") if time_el else None

        # Optional Venue
        venue_el = card.select_one(".event-venue")
        venue = venue_el.get_text(" ", strip=True) if venue_el else None
        if not venue:
            logger.warning("Missing optional field 'venue' for event: %s", title)

        # Optional Description
        desc_el = card.select_one(".event-description")
        description = desc_el.get_text(" ", strip=True) if desc_el else None
        if not description:
            logger.warning("Missing optional field 'description' for event: %s", title)

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
