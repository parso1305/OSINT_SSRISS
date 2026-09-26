"""AUDIT SANDBOX adapter: IIT Bombay Mechanical Engineering "Events" (Drupal 9, different theme from HSS).

Developed only against fixtures fetched once on 2026-09-26 (audit_week2/fixtures/me_iitb/).
Same adapter contract as sources/iit_bombay.py: parse_listing, parse_detail, normalize (+ selectors).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.urls import resolve_item_url

CONTAINER_SELECTOR = ".region-content"
CARD_SELECTOR = "div.card.my-4"
NEXT_PAGE_SELECTOR = "a[rel~='next']"
DETAIL_ARTICLE_SELECTOR = "article.node--type-events"   # same Drupal content-type class as HSS
SITE_TITLE_SUFFIX = " | The Department of Mechanical Engineering"
DISPLAY_TIMEZONE = "Asia/Kolkata"
IST = timezone(timedelta(hours=5, minutes=30))
ONLINE_RE = re.compile(r"\b(online|zoom|teams|webex|google meet)\b", re.IGNORECASE)


class StructuralError(ValueError):
    """Expected container is missing."""


def _clean(text: Optional[str]) -> Optional[str]:
    return re.sub(r"\s+", " ", text).strip() or None if text else None


def parse_listing(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(CONTAINER_SELECTOR)
    if not container:
        raise StructuralError(f"container '{CONTAINER_SELECTOR}' not found")
    items = []
    for card in container.select(CARD_SELECTOR):
        link = card.select_one("a.marooncolor[href]")
        time_el = card.select_one("time[datetime]")
        title_el = card.select_one("h5")
        items.append({
            "title": title_el.get_text(" ", strip=True) if title_el else None,
            "raw_href": link["href"] if link else None,          # live hrefs carry a trailing space
            "item_url": resolve_item_url(link["href"], base_url) if link else None,
            "listing_datetime": time_el["datetime"] if time_el else None,
            "date_text": time_el.get_text(" ", strip=True) if time_el else None,
        })
    return items


def parse_detail(html: str, item_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(DETAIL_ARTICLE_SELECTOR)
    if not article:
        raise StructuralError(f"detail container '{DETAIL_ARTICLE_SELECTOR}' not found on {item_url}")
    venue = None
    label = article.find(lambda t: t.name == "strong" and "Venue" in t.get_text())
    if label:
        box = label.find_parent("div")
        venue_div = box.find("div") if box else None
        venue = venue_div.get_text(" ", strip=True) if venue_div else None
    body = article.select_one(".col-12.pl-0.pb-4")
    canonical = soup.select_one("link[rel='canonical']")
    title_el = soup.select_one("title")
    return {
        "title": title_el.get_text(strip=True) if title_el else None,
        "venue": venue,
        "description": body.get_text(" ", strip=True) if body else None,
        "detail_canonical_url": resolve_item_url(canonical["href"], item_url) if canonical else None,
        "node_id": article.get("data-history-node-id"),
    }


def _listing_start_utc(value: Optional[str]) -> Optional[str]:
    """ME's <time datetime> ends in 'Z' but holds IST wall-clock time (seminar at '4:00 PM' ->
    '...T16:00:00Z'; 9/10 listing items with a stated time agree). Treat it as naive IST."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return naive.replace(tzinfo=IST).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(record: dict) -> dict:
    title = _clean(record.get("title"))
    venue = _clean(record.get("venue"))
    return {
        "title": title.removesuffix(SITE_TITLE_SUFFIX) if title else None,
        "starts_at": _listing_start_utc(record.get("listing_datetime")),
        "ends_at": None,                     # not published as data (only inside free text)
        "timezone": DISPLAY_TIMEZONE,
        "speakers": [],                      # not structured on this site
        "venue": venue,
        "is_online": True if venue and ONLINE_RE.search(venue) else None,
        "event_type": None,
        "description": _clean(record.get("description")),
        "extras": {k: record.get(k) for k in ("node_id", "detail_canonical_url", "listing_datetime", "date_text",
                                              "raw_href", "discovered_on_url") if record.get(k) is not None},
    }
