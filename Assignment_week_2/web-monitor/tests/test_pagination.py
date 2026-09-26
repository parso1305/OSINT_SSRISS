"""Tests for Assignment 4A: Local Pagination Fixtures, Link Extraction,
Traversal Stopping Conditions, and Full Pipeline Deduplication (Checkpoint 4A).
"""

import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pagination import get_next_page_url, collect_listing
from sources.iit_bombay_legacy import parse_events, normalize_item
from src.schema import normalize_events
from src.storage import init_db, store_all, count_items, get_item_by_url

FIXTURES_DIR = PROJECT_ROOT / "fixtures" / "iit_bombay"


def load_fixture(filename: str) -> str:
    """Reads fixture HTML from fixtures/iit_bombay/."""
    file_path = FIXTURES_DIR / filename
    return file_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Tests for get_next_page_url
# ---------------------------------------------------------------------------

def test_get_next_page_url_relative_resolution():
    """Verify get_next_page_url finds rel='next' and resolves relative URL against base."""
    html_p1 = load_fixture("page_1.html")
    next_url = get_next_page_url(html_p1, current_url="https://www.iitb.ac.in/events")
    assert next_url == "https://www.iitb.ac.in/events?page=2"


def test_get_next_page_url_page_2():
    """Verify get_next_page_url extracts page 3 from page 2."""
    html_p2 = load_fixture("page_2.html")
    next_url = get_next_page_url(html_p2, current_url="https://www.iitb.ac.in/events?page=2")
    assert next_url == "https://www.iitb.ac.in/events?page=3"


def test_get_next_page_url_last_page_returns_none():
    """Verify get_next_page_url returns None on the terminal page (no next link)."""
    html_p3 = load_fixture("page_3.html")
    next_url = get_next_page_url(html_p3, current_url="https://www.iitb.ac.in/events?page=3")
    assert next_url is None


def test_get_next_page_url_empty_or_fragment():
    """Verify handling of empty HTML or fragment-only links."""
    assert get_next_page_url("", "https://www.iitb.ac.in/events") is None
    dummy_html = '<div class="pager"><a href="#" rel="next">Next</a></div>'
    assert get_next_page_url(dummy_html, "https://www.iitb.ac.in/events") is None


# ---------------------------------------------------------------------------
# 2. Tests for collect_listing Traversal & Stopping Conditions
# ---------------------------------------------------------------------------

def test_collect_listing_traversal_all_pages():
    """Verify collect_listing walks page 1 -> 2 -> 3 and stops when no next page exists."""
    pages = {
        "https://www.iitb.ac.in/events": load_fixture("page_1.html"),
        "https://www.iitb.ac.in/events?page=2": load_fixture("page_2.html"),
        "https://www.iitb.ac.in/events?page=3": load_fixture("page_3.html"),
    }

    result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=10,
        fetch_fn=lambda url: pages[url],
        parse_fn=parse_events
    )

    assert result["pages_crawled"] == 3
    assert result["stop_reason"] == "no_next_page"
    assert len(result["visited_urls"]) == 3
    assert len(result["items"]) == 15  # 5 items per page * 3 pages
    # Verify discovered_on_url is accurately tracked per item
    assert result["items"][0]["discovered_on_url"] == "https://www.iitb.ac.in/events"
    assert result["items"][5]["discovered_on_url"] == "https://www.iitb.ac.in/events?page=2"
    assert result["items"][10]["discovered_on_url"] == "https://www.iitb.ac.in/events?page=3"


def test_collect_listing_stop_condition_max_pages():
    """Verify traversal halts strictly when max_pages limit is reached."""
    pages = {
        "https://www.iitb.ac.in/events": load_fixture("page_1.html"),
        "https://www.iitb.ac.in/events?page=2": load_fixture("page_2.html"),
        "https://www.iitb.ac.in/events?page=3": load_fixture("page_3.html"),
    }

    result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=2,
        fetch_fn=lambda url: pages[url],
        parse_fn=parse_events
    )

    assert result["pages_crawled"] == 2
    assert result["stop_reason"] == "max_pages_reached"
    assert len(result["visited_urls"]) == 2
    assert len(result["items"]) == 10


def test_collect_listing_stop_condition_cycle_detection():
    """Verify traversal halts when a circular next-page loop is encountered."""
    # Page 2 maliciously points back to Page 1
    page_2_loop = load_fixture("page_2.html").replace(
        '/events?page=3', '/events'
    )
    pages = {
        "https://www.iitb.ac.in/events": load_fixture("page_1.html"),
        "https://www.iitb.ac.in/events?page=2": page_2_loop,
    }

    result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=10,
        fetch_fn=lambda url: pages[url],
        parse_fn=parse_events
    )

    assert result["pages_crawled"] == 2
    assert result["stop_reason"] == "cycle_detected"


def test_collect_listing_stop_condition_domain_mismatch_safety():
    """Verify explicit safety condition: halts if next page diverges to external domain."""
    # Page 1 next link points to an external untrusted domain
    page_1_external = load_fixture("page_1.html").replace(
        '/events?page=2', 'https://external-phishing-site.com/events?page=2'
    )
    pages = {
        "https://www.iitb.ac.in/events": page_1_external,
    }

    result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=10,
        fetch_fn=lambda url: pages[url],
        parse_fn=parse_events
    )

    assert result["pages_crawled"] == 1
    assert result["stop_reason"] == "domain_mismatch"


def test_collect_listing_stop_condition_empty_listing_safety():
    """Verify explicit safety condition: halts immediately if a listing returns 0 items."""
    empty_html = load_fixture("empty_listing.html")
    result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=10,
        fetch_fn=lambda url: empty_html,
        parse_fn=parse_events
    )

    assert result["pages_crawled"] == 1
    assert result["stop_reason"] == "empty_listing"
    assert len(result["items"]) == 0


# ---------------------------------------------------------------------------
# 3. Checkpoint 4A: End-to-End Duplicate Item Deduplication in Storage
# ---------------------------------------------------------------------------

def test_checkpoint_4a_duplicate_item_deduplication(tmp_path):
    """
    Checkpoint 4A:
    Proves that the duplicate item appearing across page_1 and page_2 does NOT
    create a duplicate row when passing through the full normalize -> store pipeline.
    """
    # 1. Offline fixture setup for all 3 pages
    pages = {
        "https://www.iitb.ac.in/events": load_fixture("page_1.html"),
        "https://www.iitb.ac.in/events?page=2": load_fixture("page_2.html"),
        "https://www.iitb.ac.in/events?page=3": load_fixture("page_3.html"),
    }

    # 2. Walk all 3 pages using collect_listing
    crawl_result = collect_listing(
        start_url="https://www.iitb.ac.in/events",
        max_pages=10,
        fetch_fn=lambda url: pages[url],
        parse_fn=parse_events
    )

    raw_items = crawl_result["items"]
    # Total cards parsed: 5 on Page 1 + 5 on Page 2 + 5 on Page 3 = 15
    assert len(raw_items) == 15

    # 3. Run through the full normalization pipeline
    base_url = "https://www.iitb.ac.in/events"
    normalized_items = [normalize_item(raw, base_url=base_url) for raw in raw_items]
    assert len(normalized_items) == 15

    # Identify the duplicate item URL:
    duplicate_canonical_url = "https://www.iitb.ac.in/event/ai-ethics-workshop"
    duplicate_items = [it for it in normalized_items if it.item_url == duplicate_canonical_url]
    # In normalized items, the duplicate appears twice (once from page 1, once from page 2)
    assert len(duplicate_items) == 2
    assert duplicate_items[0].title == "National Workshop on Ethical AI in Healthcare"
    assert duplicate_items[1].title == "National Workshop on Ethical AI in Healthcare"

    # 4. Store in an isolated temporary SQLite database
    test_db = str(tmp_path / "test_events.db")
    init_db(test_db)
    counts = store_all(test_db, normalized_items)

    # 5. Verify deduplication stats:
    # 14 distinct records are new; exactly 1 duplicate item is identified as existing
    assert counts["new"] == 14
    assert counts["existing"] == 1
    assert counts["changed"] == 0

    # 6. Verify SQLite database row count
    total_db_rows = count_items(test_db)
    assert total_db_rows == 14

    # 7. Verify the duplicate item row exists exactly once in the database
    stored_row = get_item_by_url(test_db, duplicate_canonical_url)
    assert stored_row is not None
    assert stored_row["title"] == "National Workshop on Ethical AI in Healthcare"
    assert stored_row["venue"] == "VMCC Seminar Hall 1"
