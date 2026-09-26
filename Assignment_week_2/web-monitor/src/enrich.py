"""Detail-page enrichment: fetch each item's own page, parse it, and merge it into the listing record.

Generic: the adapter supplies parse_detail; fetching (timeout, delay, robots) is the Fetcher's job.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from src.fetcher import FetchError
from src.logging_config import log_detail_failure, log_enrich

# Keys set here rather than by a parser; never overwritten by detail data.
PROVENANCE_KEYS = ("detail_fetch_status", "detail_http_status", "detail_fetched_at", "detail_error")


def merge_listing_and_detail(listing_item: dict, detail_item: dict) -> dict:
    """
    Merges a listing record with the fields parsed from that item's detail page.

    Conflict rule:
      - Detail wins for every field it has a non-empty value for (None, "" and [] do not
        overwrite a listing value; the listing fills gaps the detail page leaves).
      - EXCEPT item_url: always the listing item's canonical URL (resolve_item_url, Section 4).
        It is never re-derived from the detail page, even if the detail page declares a
        different <link rel="canonical"> (kept separately as detail_canonical_url).
      - Provenance keys (detail_fetch_status, ...) are set by enrich_items, never by detail data.
      - Which detail element feeds which key is the adapter's decision (documented in its
        parse_detail). Because "detail wins", an adapter must not map an unreliable detail element
        onto a key the listing already gets right; e.g. the title source rule in sources/*.py.
    """
    merged = dict(listing_item)
    for key, value in detail_item.items():
        if key == "item_url" or key in PROVENANCE_KEYS:
            continue
        if value is None or value == "" or value == []:
            continue
        merged[key] = value
    merged["item_url"] = listing_item.get("item_url")
    return merged


def enrich_items(
    listing_items: list[dict],
    parse_detail_fn: Callable[[str, str], dict],
    fetch_fn: Callable[[str], Any],
    source_id: str,
    max_items: int,
    logger: Optional[logging.Logger] = None,
) -> list[dict]:
    """
    Fetches and merges detail pages for the first max_items listing items.

    fetch_fn(url) returns a FetchResult (status, text, fetched_at) and raises FetchError on failure.
    Every returned record carries detail_fetch_status:
      "ok"            detail fetched, parsed and merged
      "failed"        fetch or parse failed; the listing record is kept unchanged otherwise
      "not_attempted" beyond max_items (or no item_url to fetch)
    A failure on one item is logged as DETAIL_FAILURE (logger web_monitor.detail) and processing continues.
    """
    active_logger = logger or logging.getLogger("web_monitor")
    detail_logger = active_logger.getChild("detail")

    results: list[dict] = []
    attempted = 0
    for listing_item in listing_items:
        item_url = listing_item.get("item_url")
        if attempted >= max_items or not item_url:
            results.append(dict(listing_item, detail_fetch_status="not_attempted"))
            continue
        attempted += 1

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        status: Optional[int] = None
        try:
            response = fetch_fn(item_url)
            status = response.status
            fetched_at = getattr(response, "fetched_at", fetched_at)
            detail_item = parse_detail_fn(response.text, item_url)
        except Exception as e:
            if isinstance(e, FetchError):
                status = e.status
            log_detail_failure(detail_logger, source_id=source_id, item_url=item_url, status=status, error=e)
            results.append(dict(
                listing_item,
                detail_fetch_status="failed",
                detail_http_status=status,
                detail_fetched_at=fetched_at,
                detail_error=f"{type(e).__name__}: {e}",
            ))
            continue

        merged = merge_listing_and_detail(listing_item, detail_item)
        merged.update(detail_fetch_status="ok", detail_http_status=status, detail_fetched_at=fetched_at)
        results.append(merged)

    counts = {s: sum(r["detail_fetch_status"] == s for r in results) for s in ("ok", "failed", "not_attempted")}
    log_enrich(active_logger, **counts)
    return results
