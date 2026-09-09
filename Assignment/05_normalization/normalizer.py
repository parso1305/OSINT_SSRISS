import re
import urllib.parse
from datetime import datetime

def normalize_item(raw_item: dict, base_url: str) -> dict:
    """
    Normalizes a single raw scraped item into a consistent schema.
    """
    normalized = {}

    # 1. TITLE
    # Preserve meaning, but clean whitespace.
    raw_title = raw_item.get("title")
    if raw_title:
        # Collapse repeated internal whitespace to a single space and strip
        normalized["title"] = re.sub(r'\s+', ' ', raw_title).strip()
    else:
        normalized["title"] = None

    # 2. URL
    # Convert to canonical absolute URL
    raw_url = raw_item.get("item_url")
    if raw_url:
        normalized["item_url"] = urllib.parse.urljoin(base_url, raw_url.strip())
    else:
        normalized["item_url"] = None

    # 3. DATE
    # Convert DD Mon YYYY to ISO format (YYYY-MM-DD), keep raw date for provenance.
    raw_date = raw_item.get("date_raw")
    normalized["date_raw"] = raw_date
    normalized["published_at"] = None
    
    if raw_date:
        clean_date = raw_date.strip()
        try:
            # Expected format: "03 Sep 2026"
            dt = datetime.strptime(clean_date, "%d %b %Y")
            normalized["published_at"] = dt.strftime("%Y-%m-%d")
        except ValueError:
            # If parsing fails, we safely ignore it (published_at stays None)
            pass

    # 4. IMAGE URL
    raw_img = raw_item.get("image_url")
    if raw_img:
        normalized["image_url"] = urllib.parse.urljoin(base_url, raw_img.strip())
    else:
        normalized["image_url"] = None

    # 5. IMAGE ALT
    raw_alt = raw_item.get("image_alt")
    if raw_alt:
        normalized["image_alt"] = re.sub(r'\s+', ' ', raw_alt).strip()
    else:
        normalized["image_alt"] = None

    # 6. RAW TEXT
    # Preserve raw_text, clean surrounding whitespace safely.
    raw_text = raw_item.get("raw_text")
    if raw_text:
        normalized["raw_text"] = raw_text.strip()
    else:
        normalized["raw_text"] = None

    return normalized


def normalize_all(raw_items: list, base_url: str) -> list:
    """
    Normalizes a list of raw scraped items.
    """
    normalized_items = []
    for item in raw_items:
        normalized_items.append(normalize_item(item, base_url))
    return normalized_items
