"""Checkpoint 4B: URL resolution rules and canonical-URL deduplication.

The "real" hrefs below were copied verbatim from live HTML fetched on 2026-09-25:
  - HSS listing:  https://www.hss.iitb.ac.in/events/seminars-and-talks
                  (saved as fixtures/iit_bombay_hss/live_page_1.html)
  - HSS detail:   https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability
  - EE listing:   https://www.ee.iitb.ac.in/info/news/
  - EE detail:    https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/
Hrefs marked SYNTHETIC cover formats that did not occur on any fetched page.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from bs4 import BeautifulSoup

from src.urls import resolve_item_url
from src.storage import init_db, store_all, count_items, get_item_by_url
from src.config import load_source_configs
from src.schema import assemble_record
from src.storage import store_records, get_record, count_records
from sources import iit_bombay

HSS_LISTING = "https://www.hss.iitb.ac.in/events/seminars-and-talks"
HSS_ITEM_DETAIL = "https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
EE_LISTING = "https://www.ee.iitb.ac.in/info/news/"
EE_ITEM_DETAIL = "https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/"

# Real markup, copied verbatim from the live pages above.
HSS_LISTING_CARD_LINK = (
    '<a href="/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability" hreflang="en">'
    'The A&amp;N Islands – At the tri-junction of fragility and vulnerability</a>'
)
# Re-fetched live 2026-09-26 05:38 UTC: unchanged (line 7 of the detail page response).
HSS_DETAIL_CANONICAL = (
    '<link rel="canonical" href="https://www.hss.iitb.ac.in/events/seminar-talk/'
    'islands-tri-junction-fragility-and-vulnerability" />'
)
EE_LISTING_MAIN_ACTION = '<a href="/info/news/clip_seminar_satish/" class="ann-action ann-action--main">'
EE_DETAIL_CANONICAL = '<link href="https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/" rel="canonical">'
HSS_HEADER_CAREERS = '<a href="https://www.hss.iitb.ac.in/careers" class="nav-link">Careers</a>'
HSS_FOOTER_CAREERS = '<a href="/careers" class="nav-link" data-drupal-link-system-path="careers">Careers</a>'

HSS_ITEM_CANONICAL = "https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
EE_ITEM_CANONICAL = "https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/"   # path kept as served


def href_of(snippet: str) -> str:
    return BeautifulSoup(snippet, "html.parser").find(["a", "link"])["href"]


# ---------------------------------------------------------------------------
# 1. The four href forms
# ---------------------------------------------------------------------------

def test_root_relative_href():
    """REAL: HSS listing card uses a root-relative path."""
    assert resolve_item_url(href_of(HSS_LISTING_CARD_LINK), HSS_LISTING) == HSS_ITEM_CANONICAL


def test_already_absolute_href():
    """REAL: HSS detail page declares an absolute canonical."""
    assert resolve_item_url(href_of(HSS_DETAIL_CANONICAL), HSS_ITEM_DETAIL) == HSS_ITEM_CANONICAL


def test_query_relative_href_from_real_pager():
    """REAL: Drupal pager next link is href="?page=1" (resolved against the listing path)."""
    assert resolve_item_url("?page=1", HSS_LISTING) == HSS_LISTING + "?page=1"


def test_pure_relative_href():
    """SYNTHETIC: pure-relative paths resolve against the page's directory, including '..'."""
    assert resolve_item_url("clip_seminar_satish/", EE_LISTING) == EE_ITEM_CANONICAL
    assert resolve_item_url("../people/", EE_LISTING) == "https://www.ee.iitb.ac.in/info/people/"
    # Page without trailing slash: last segment is a file, so siblings replace it
    assert resolve_item_url("seminar-talk/x", HSS_LISTING) == "https://www.hss.iitb.ac.in/events/seminar-talk/x"


def test_protocol_relative_href():
    """SYNTHETIC: '//host/path' borrows the page's scheme; https when there is no page."""
    assert resolve_item_url("//www.ee.iitb.ac.in/info/news/clip_seminar_satish/", EE_LISTING) == EE_ITEM_CANONICAL
    assert resolve_item_url("//www.ee.iitb.ac.in/a", "http://www.ee.iitb.ac.in/") == "http://www.ee.iitb.ac.in/a"
    assert resolve_item_url("//www.ee.iitb.ac.in/a", "") == "https://www.ee.iitb.ac.in/a"


# ---------------------------------------------------------------------------
# 2. Canonicalization rules
# ---------------------------------------------------------------------------

def test_lowercases_scheme_and_host_but_not_path():
    assert resolve_item_url("HTTPS://WWW.HSS.IITB.AC.IN/Events/X", "") == "https://www.hss.iitb.ac.in/Events/X"


def test_strips_default_ports_only():
    assert resolve_item_url("https://www.ee.iitb.ac.in:443/a", "") == "https://www.ee.iitb.ac.in/a"
    assert resolve_item_url("http://www.ee.iitb.ac.in:80/a", "") == "http://www.ee.iitb.ac.in/a"
    assert resolve_item_url("https://www.ee.iitb.ac.in:8443/a", "") == "https://www.ee.iitb.ac.in:8443/a"


def test_path_is_kept_as_given():
    """A trailing slash or '//' can be significant, so the path is never rewritten; an empty path is '/'."""
    assert resolve_item_url("/info/news/clip_seminar_satish/", EE_LISTING) == EE_ITEM_CANONICAL
    assert resolve_item_url("/info/news/clip_seminar_satish", EE_LISTING) == EE_ITEM_CANONICAL.rstrip("/")
    assert resolve_item_url("https://www.ee.iitb.ac.in", "") == "https://www.ee.iitb.ac.in/"
    assert resolve_item_url("https://www.ee.iitb.ac.in/", "") == "https://www.ee.iitb.ac.in/"
    assert resolve_item_url("/a//b///", "https://x.org/") == "https://x.org/a//b///"
    # REAL (audit, 2026-09-26): CMI serves /activities/; /activities only works via a 301 redirect
    assert resolve_item_url("https://www.cmi.ac.in/activities/", "") == "https://www.cmi.ac.in/activities/"


def test_whitespace_is_stripped_like_a_browser():
    # REAL (audit, ME department listing): hrefs end with a space, e.g. "/event/slug "
    assert resolve_item_url("/event/seminar-x ", "https://www.me.iitb.ac.in/events") == "https://www.me.iitb.ac.in/event/seminar-x"
    assert resolve_item_url("  /event/\n  seminar-x\t", "https://x.org/") == "https://x.org/event/  seminar-x"


def test_strips_tracking_and_session_params_keeps_semantic_ones():
    raw = HSS_LISTING + "?page=2&utm_source=x&utm_campaign=y&fbclid=abc&gclid=1&PHPSESSID=s1&sid=s2&jsessionid=s3"
    assert resolve_item_url(raw, "") == HSS_LISTING + "?page=2"
    assert resolve_item_url("/a;jsessionid=0A1B2C?b=2&a=1", "https://x.org/") == "https://x.org/a?a=1&b=2"


def test_fragments_stripped_unless_they_identify_content():
    # REAL fragment on HSS pages: skip-link "#main-content" -> same page, fragment dropped
    assert resolve_item_url("#main-content", HSS_LISTING) == HSS_LISTING
    assert resolve_item_url(HSS_ITEM_CANONICAL + "#abstract", "") == HSS_ITEM_CANONICAL
    # SYNTHETIC: client-side routes select the item, so they are kept
    assert resolve_item_url("/app#!/event/42", "https://x.org/") == "https://x.org/app#!/event/42"
    assert resolve_item_url("/app#/event/42", "https://x.org/") == "https://x.org/app#/event/42"


@pytest.mark.parametrize("href", ["mailto:eeoffice@ee.iitb.ac.in", "tel:+912225767401", "javascript:void(0)", "", "   "])
def test_non_http_or_empty_hrefs_resolve_to_empty(href):
    """REAL mailto:/tel: hrefs from the EE page are not item URLs."""
    assert resolve_item_url(href, EE_LISTING) == ""


def test_idempotent():
    for url in (HSS_ITEM_CANONICAL, EE_ITEM_CANONICAL, HSS_LISTING + "?page=1", "https://x.org/"):
        assert resolve_item_url(resolve_item_url(url, ""), "") == resolve_item_url(url, "")


# ---------------------------------------------------------------------------
# 3. Real differently-formatted hrefs for the same item -> one canonical URL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw_a, page_a, raw_b, page_b, expected", [
    # HSS seminar: root-relative listing link vs absolute canonical on the detail page
    (href_of(HSS_LISTING_CARD_LINK), HSS_LISTING, href_of(HSS_DETAIL_CANONICAL), HSS_ITEM_DETAIL, HSS_ITEM_CANONICAL),
    # EE news item: root-relative listing link vs absolute canonical on the detail page
    (href_of(EE_LISTING_MAIN_ACTION), EE_LISTING, href_of(EE_DETAIL_CANONICAL), EE_ITEM_DETAIL, EE_ITEM_CANONICAL),
    # HSS Careers page: absolute header link vs root-relative footer link on the same page
    (href_of(HSS_HEADER_CAREERS), HSS_LISTING, href_of(HSS_FOOTER_CAREERS), HSS_LISTING,
     "https://www.hss.iitb.ac.in/careers"),
])
def test_real_href_pairs_resolve_to_same_canonical(raw_a, page_a, raw_b, page_b, expected):
    assert raw_a != raw_b
    assert resolve_item_url(raw_a, page_a) == resolve_item_url(raw_b, page_b) == expected


# ---------------------------------------------------------------------------
# 4. The canonical URL, not the raw href, is the storage dedup key
# ---------------------------------------------------------------------------

def test_storage_dedups_on_canonical_url_not_raw_href(tmp_path):
    """
    Item seen once via the real listing card (root-relative href) and once via the real
    detail-page canonical (absolute href) must produce exactly one row keyed by the canonical URL.
    """
    db = str(tmp_path / "dedup.db")
    config = load_source_configs()["iit_bombay_hss_seminars"]

    listing_html = (PROJECT_ROOT / "fixtures" / "iit_bombay_hss" / "live_page_1.html").read_text(encoding="utf-8")
    from_listing = next(
        it for it in iit_bombay.parse_listing(listing_html, base_url=HSS_LISTING)
        if it["raw_href"] == href_of(HSS_LISTING_CARD_LINK)
    )
    detail_href = href_of(HSS_DETAIL_CANONICAL)
    from_detail = dict(from_listing, raw_href=detail_href, item_url=resolve_item_url(detail_href, HSS_ITEM_DETAIL))
    assert from_listing["raw_href"] != from_detail["raw_href"]

    records = [
        assemble_record(config, dict(m, detail_fetch_status="not_attempted"), iit_bombay.normalize(m))
        for m in (from_listing, from_detail)
    ]
    assert records[0]["item_url"] == records[1]["item_url"] == HSS_ITEM_CANONICAL

    assert store_records(db, records) == {"new": 1, "existing": 1, "changed": 0}
    assert count_records(db) == 1
    assert get_record(db, HSS_ITEM_CANONICAL)["item_url"] == HSS_ITEM_CANONICAL
    assert get_record(db, href_of(HSS_LISTING_CARD_LINK)) is None


def test_storage_ee_slash_and_no_slash_are_distinct_keys(tmp_path):
    """
    The two REAL EE hrefs (listing link, detail canonical) both carry the slash and dedupe to one row.
    The no-slash form is a different URL: EE happens to 301-redirect it to the slash form (verified live),
    but that is server behaviour the canonicalizer must not assume, so it is its own key.
    """
    from src.schema import NormalizedItem

    db = str(tmp_path / "dedup_ee.db")
    init_db(db)
    raw_hrefs = [
        (href_of(EE_LISTING_MAIN_ACTION), EE_LISTING),                    # /info/news/clip_seminar_satish/
        (href_of(EE_DETAIL_CANONICAL), EE_ITEM_DETAIL),                   # https://.../clip_seminar_satish/
        ("https://www.ee.iitb.ac.in/info/news/clip_seminar_satish", ""),  # 301 -> slash form (verified live)
    ]
    items = [
        NormalizedItem(source_name="ee", source_url=page, item_url=resolve_item_url(href, page), title="CLIP seminar")
        for href, page in raw_hrefs
    ]
    assert store_all(db, items) == {"new": 2, "existing": 1, "changed": 0}
    assert count_items(db) == 2
    assert get_item_by_url(db, EE_ITEM_CANONICAL) is not None
    assert get_item_by_url(db, EE_ITEM_CANONICAL.rstrip("/")) is not None
