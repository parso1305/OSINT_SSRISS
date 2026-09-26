"""Generic paginated listing traversal. The adapter only supplies how to find the next page (a CSS selector)."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from src.fetcher import FetchError
from src.logging_config import log_failure
from src.urls import resolve_item_url

# HTML-standard rel="next" link: not tied to any CMS.
DEFAULT_NEXT_PAGE_SELECTOR = "a[rel~='next'], link[rel~='next']"


class ListingParser(Protocol):
    """A source parser: resolves item hrefs against base_url via resolve_item_url."""

    def __call__(self, html: str, base_url: str) -> list[dict]: ...


def get_next_page_url(html: str, current_url: str, selector: str = DEFAULT_NEXT_PAGE_SELECTOR) -> Optional[str]:
    """Returns the canonical absolute URL of the first element matching selector, or None."""
    if not html or not current_url:
        return None
    link = BeautifulSoup(html, "html.parser").select_one(selector)
    if not link or not link.has_attr("href"):
        return None
    raw_href = link["href"].strip()
    if not raw_href or raw_href == "#" or raw_href.lower().startswith("javascript:"):
        return None
    return resolve_item_url(raw_href, current_url) or None


def _unpack(fetched: Any, requested_url: str) -> tuple[str, str, str]:
    """Accepts a FetchResult, an (html, final_url) tuple or a bare html string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if hasattr(fetched, "text") and hasattr(fetched, "final_url"):
        return fetched.text, fetched.final_url, getattr(fetched, "fetched_at", now)
    if isinstance(fetched, tuple):
        return fetched[0], fetched[1], now
    return fetched, requested_url, now


def collect_listing(
    start_url: str,
    max_pages: int,
    fetch_fn: Callable[[str], Any],
    parse_fn: ListingParser,
    next_page_selector: Optional[str] = None,
    source_id: str = "",
    logger: Optional[logging.Logger] = None,
) -> dict:
    """
    Walks listing pages from start_url, following next_page_selector (default: rel="next").

    Stops on: no next link, max_pages reached, a URL already visited (cycle), a next link to another
    host, a page with zero items (empty_listing), a page whose items were all seen already
    (repeated_items), or a fetch failure on page 2+ (fetch_failed: logged as listing FAILURE; items
    from earlier pages are kept). A failure on page 1 raises.

    Each item gets discovered_on_url, discovered_on_page and listing_fetched_at.
    """
    active_logger = logger or logging.getLogger("web_monitor")
    selector = next_page_selector or DEFAULT_NEXT_PAGE_SELECTOR

    visited_urls: list[str] = []
    seen_item_urls: set[str] = set()
    all_items: list[dict] = []
    current_url: Optional[str] = resolve_item_url(start_url, start_url)
    start_domain = urlparse(current_url).netloc.lower()
    stop_reason = "no_next_page"

    while current_url:
        if current_url in visited_urls:
            stop_reason = "cycle_detected"
            active_logger.warning("Pagination loop detected for URL: %s", current_url)
            break
        if len(visited_urls) >= max_pages:
            stop_reason = "max_pages_reached"
            break
        if urlparse(current_url).netloc.lower() != start_domain:
            stop_reason = "domain_mismatch"
            active_logger.warning("Next page URL '%s' leaves domain '%s'. Halting.", current_url, start_domain)
            break

        page_number = len(visited_urls) + 1
        try:
            html, base_url, fetched_at = _unpack(fetch_fn(current_url), current_url)
        except FetchError as e:
            if page_number == 1:
                raise
            log_failure(active_logger, source_id=source_id, url=current_url, stage="fetch", error=e)
            stop_reason = "fetch_failed"
            break
        visited_urls.append(current_url)

        # Relative hrefs resolve against the URL actually served (post-redirect).
        page_items = parse_fn(html, base_url=base_url)
        for item in page_items:
            item["discovered_on_url"] = current_url
            item["discovered_on_page"] = page_number
            item["listing_fetched_at"] = fetched_at
        page_urls = {item.get("item_url") for item in page_items}
        all_items.extend(page_items)
        active_logger.info("Page %d yielded %d items", page_number, len(page_items))

        if not page_items:
            stop_reason = "empty_listing"
            break
        if page_number > 1 and page_urls <= seen_item_urls:
            stop_reason = "repeated_items"
            active_logger.warning("Page %d repeats only already-seen items. Halting.", page_number)
            break
        seen_item_urls |= page_urls
        if len(visited_urls) >= max_pages:
            stop_reason = "max_pages_reached"
            break

        next_url = get_next_page_url(html, base_url, selector)
        if not next_url:
            stop_reason = "no_next_page"
            break
        current_url = next_url

    return {
        "items": all_items,
        "visited_urls": visited_urls,
        "pages_crawled": len(visited_urls),
        "stop_reason": stop_reason,
    }
