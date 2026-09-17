"""Data schemas and normalization models for scraped items."""

import re
from datetime import datetime
from src.urls import resolve_url


def normalize_event(raw_item: dict, base_url: str = "https://www.iitb.ac.in") -> dict:
    """
    Normalizes raw parsed event dictionary into the standard schema.
    Applies whitespace stripping, URL canonicalization, and ISO date formatting.
    """
    normalized = {}

    # 1. TITLE
    raw_title = raw_item.get("title")
    if raw_title:
        normalized["title"] = re.sub(r'\s+', ' ', raw_title).strip()
    else:
        normalized["title"] = None

    # 2. ITEM URL (Canonical Absolute URL)
    raw_url = raw_item.get("item_url")
    if raw_url:
        normalized["item_url"] = resolve_url(base_url, raw_url)
    else:
        normalized["item_url"] = None

    # 3. DATES
    raw_date = raw_item.get("date_raw")
    normalized["date_raw"] = raw_date.strip() if raw_date else None
    normalized["published_at"] = None

    # Attempt date normalization to ISO YYYY-MM-DD
    candidate_date = raw_item.get("date_datetime") or (raw_date.strip() if raw_date else None)
    if candidate_date:
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(candidate_date, fmt)
                normalized["published_at"] = dt.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    # 4. OPTIONAL VENUE
    raw_venue = raw_item.get("venue")
    if raw_venue:
        normalized["venue"] = re.sub(r'\s+', ' ', raw_venue).strip()
    else:
        normalized["venue"] = None

    # 5. OPTIONAL DESCRIPTION
    raw_desc = raw_item.get("description")
    if raw_desc:
        normalized["description"] = re.sub(r'\s+', ' ', raw_desc).strip()
    else:
        normalized["description"] = None

    # 6. RAW TEXT
    raw_text = raw_item.get("raw_text")
    if raw_text:
        normalized["raw_text"] = raw_text.strip()
    else:
        normalized["raw_text"] = None

    return normalized


def normalize_events(raw_items: list[dict], base_url: str = "https://www.iitb.ac.in") -> list[dict]:
    """Normalizes a batch of raw event items."""
    return [normalize_event(item, base_url=base_url) for item in raw_items]
