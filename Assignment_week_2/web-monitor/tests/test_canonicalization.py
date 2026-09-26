"""Tests for URL resolution, comprehensive canonicalization, and SQLite deduplication."""

import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.urls import resolve_item_url
from src.schema import NormalizedItem
from src.storage import init_db, store_all, count_items, get_item_by_url


# ---------------------------------------------------------------------------
# 1. Tests for Canonicalization Rules
# ---------------------------------------------------------------------------

def test_resolve_url_relative_to_absolute():
    """Resolves relative path against base URL."""
    base = "https://www.hss.iitb.ac.in/events/seminars-and-talks"
    relative = "/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
    expected = "https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
    assert resolve_item_url(relative, base) == expected


def test_resolve_url_query_relative_pagination():
    """Resolves relative pagination query against base URL."""
    base = "https://www.hss.iitb.ac.in/events/seminars-and-talks"
    query_rel = "?page=1"
    expected = "https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1"
    assert resolve_item_url(query_rel, base) == expected


def test_resolve_url_lowercase_scheme_and_host():
    """Lowercases uppercase scheme and hostname while preserving path casing."""
    raw = "HTTPS://WWW.IITB.AC.IN/Events/Seminar-1"
    expected = "https://www.iitb.ac.in/Events/Seminar-1"
    assert resolve_item_url(raw, "https://www.iitb.ac.in") == expected


def test_resolve_url_strip_default_ports():
    """Strips default port 443 for HTTPS and port 80 for HTTP."""
    raw_https = "https://www.iitb.ac.in:443/event/1"
    raw_http = "http://www.iitb.ac.in:80/event/1"
    raw_custom = "https://www.iitb.ac.in:8443/event/1"

    assert resolve_item_url(raw_https, "https://www.iitb.ac.in") == "https://www.iitb.ac.in/event/1"
    assert resolve_item_url(raw_http, "http://www.iitb.ac.in") == "http://www.iitb.ac.in/event/1"
    assert resolve_item_url(raw_custom, "https://www.iitb.ac.in") == "https://www.iitb.ac.in:8443/event/1"


def test_resolve_url_strip_fragment_anchors():
    """Strips internal page fragment anchors."""
    raw = "https://www.ee.iitb.ac.in/info/news/seminar-prof-deb/index.html#abstract"
    expected = "https://www.ee.iitb.ac.in/info/news/seminar-prof-deb/index.html"
    assert resolve_item_url(raw, "https://www.ee.iitb.ac.in") == expected


def test_resolve_url_strip_tracking_params():
    """Strips tracking query parameters (utm_*, ref, fbclid) while preserving semantic parameters."""
    raw = "https://www.hss.iitb.ac.in/events?page=2&utm_source=twitter&utm_medium=social&ref=newsletter&category=talks"
    # Preserves page=2 and category=talks (sorted deterministically), strips utm_* and ref
    expected = "https://www.hss.iitb.ac.in/events?category=talks&page=2"
    assert resolve_item_url(raw, "https://www.hss.iitb.ac.in") == expected


def test_resolve_url_protocol_relative():
    """Handles protocol-relative URLs correctly."""
    base = "https://www.iitb.ac.in/events"
    raw = "//www.iitb.ac.in/events/talk-2"
    expected = "https://www.iitb.ac.in/events/talk-2"
    assert resolve_item_url(raw, base) == expected


def test_resolve_url_keeps_path_as_given():
    """Duplicate and trailing slashes can be significant to a server, so the path is not rewritten."""
    base = "https://www.ee.iitb.ac.in"
    assert resolve_item_url("/info//news///2026/notice.html", base) == "https://www.ee.iitb.ac.in/info//news///2026/notice.html"
    assert resolve_item_url("/info/news/", base) == "https://www.ee.iitb.ac.in/info/news/"


# ---------------------------------------------------------------------------
# 2. End-to-End SQLite Deduplication Proof with Canonical URLs
# ---------------------------------------------------------------------------

def test_canonical_url_deduplication_in_storage(tmp_path):
    """
    Proves that three different raw representations of the same item URL
    resolve to the same canonical key and result in exactly 1 SQLite record (2 deduped).
    """
    base_url = "https://www.ee.iitb.ac.in/info/news/"

    raw_variant_1 = "/info/news/seminar-prof-deb/index.html"
    raw_variant_2 = "HTTPS://WWW.EE.IITB.AC.IN:443/info/news/seminar-prof-deb/index.html#abstract"
    raw_variant_3 = "https://www.ee.iitb.ac.in/info/news/seminar-prof-deb/index.html?utm_source=feed&ref=email"

    canon_1 = resolve_item_url(raw_variant_1, base_url)
    canon_2 = resolve_item_url(raw_variant_2, base_url)
    canon_3 = resolve_item_url(raw_variant_3, base_url)

    # All three must resolve to the identical canonical key
    expected_canonical = "https://www.ee.iitb.ac.in/info/news/seminar-prof-deb/index.html"
    assert canon_1 == expected_canonical
    assert canon_2 == expected_canonical
    assert canon_3 == expected_canonical

    # Build 3 normalized items representing successive scrapes of the same item
    item1 = NormalizedItem(
        source_name="ee_dept",
        source_url=base_url,
        item_url=canon_1,
        title="Distinguished Lecture by Prof. Deb",
        venue="EEG-301",
        date_raw="Sep 25, 2026"
    )
    item2 = NormalizedItem(
        source_name="ee_dept",
        source_url=base_url,
        item_url=canon_2,
        title="Distinguished Lecture by Prof. Deb",
        venue="EEG-301",
        date_raw="Sep 25, 2026"
    )
    item3 = NormalizedItem(
        source_name="ee_dept",
        source_url=base_url,
        item_url=canon_3,
        title="Distinguished Lecture by Prof. Deb",
        venue="EEG-301",
        date_raw="Sep 25, 2026"
    )

    db_file = str(tmp_path / "test_dedup.db")
    init_db(db_file)

    # Ingest batch of 3 items
    stats = store_all(db_file, [item1, item2, item3])

    # Exactly 1 new record inserted, 2 identified as duplicates (existing)
    assert stats["new"] == 1
    assert stats["existing"] == 2
    assert stats["changed"] == 0
    assert count_items(db_file) == 1

    # Verify stored record
    stored = get_item_by_url(db_file, expected_canonical)
    assert stored is not None
    assert stored["title"] == "Distinguished Lecture by Prof. Deb"
