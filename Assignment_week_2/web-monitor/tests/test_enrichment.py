"""Assignment 5 (kept through the Assignment 7 refactor): detail parsing, merge rule, failure isolation.

Detail fixtures were fetched live on 2026-09-26 (fixtures/iit_bombay_hss/detail/manifest.json).
"""

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.fixture_site import FixtureSite, FIXTURES
from src.enrich import enrich_items, merge_listing_and_detail
from src.fetcher import Fetcher, FetchError
from sources import iit_bombay

DETAIL_DIR = FIXTURES / "detail"
ISLANDS_URL = "https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
ECHOES_SLUG = "echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup"
# Real item URL with its last two letters swapped; the live server answers 404 (checked 2026-09-26).
MISTYPED_LIVE_URL = "https://www.hss.iitb.ac.in/events/seminar-talk/tracing-success-indian-democracy-success-nation-buildign"


def detail_html(slug: str) -> str:
    return (DETAIL_DIR / f"{slug}.html").read_text(encoding="utf-8")


def listing_items(base_url: str = "https://www.hss.iitb.ac.in/events/seminars-and-talks") -> list[dict]:
    return iit_bombay.parse_listing((FIXTURES / "listing_2026-09-26.html").read_text(encoding="utf-8"), base_url=base_url)


# ---------------------------------------------------------------------------
# merge_listing_and_detail conflict rule
# ---------------------------------------------------------------------------

def test_merge_detail_wins_except_item_url():
    listing = {"item_url": "https://a.org/x", "title": "Listing title", "venue": "Room 1", "category": "Talk"}
    detail = {"item_url": "https://evil.org/y", "title": "Detail title", "venue": "Room 2", "speaker": "Dr X"}
    merged = merge_listing_and_detail(listing, detail)
    assert merged["item_url"] == "https://a.org/x"
    assert merged["title"] == "Detail title"
    assert merged["venue"] == "Room 2"
    assert merged["speaker"] == "Dr X"
    assert merged["category"] == "Talk"


def test_merge_empty_detail_values_do_not_erase_listing_values():
    listing = {"item_url": "https://a.org/x", "venue": "Room 1", "title": "T"}
    merged = merge_listing_and_detail(listing, {"venue": None, "title": "", "speaker": None})
    assert merged["venue"] == "Room 1" and merged["title"] == "T"
    assert "speaker" not in merged


def test_merge_item_url_not_rederived_from_detail_canonical():
    listing = listing_items()[0]
    detail = dict(iit_bombay.parse_detail(detail_html("islands-tri-junction-fragility-and-vulnerability"), listing["item_url"]),
                  detail_canonical_url="https://www.hss.iitb.ac.in/node/2809")
    merged = merge_listing_and_detail(listing, detail)
    assert merged["item_url"] == listing["item_url"] == ISLANDS_URL
    assert merged["detail_canonical_url"] == "https://www.hss.iitb.ac.in/node/2809"


def test_merge_then_normalize_keeps_correct_title_despite_bad_event_title_field():
    """field-event-title on the real Echoes page repeats 'Echoes of Translation:'; the stored title must not."""
    listing = next(it for it in listing_items() if ECHOES_SLUG in it["item_url"])
    merged = merge_listing_and_detail(listing, iit_bombay.parse_detail(detail_html(ECHOES_SLUG), listing["item_url"]))
    title = iit_bombay.normalize(merged)["title"]
    assert title == listing["title"]
    assert title.count("Echoes of Translation") == 1


# ---------------------------------------------------------------------------
# enrich_items: one detail 404 does not stop the others (real HTTP, local server, no mocks)
# ---------------------------------------------------------------------------

def test_detail_404_is_isolated(caplog):
    mistyped_slug = "tracing-success-indian-democracy-success-nation-buildign"
    with FixtureSite() as site:
        items = listing_items(base_url=site.listing_url)
        items[1]["item_url"] = f"{site.url}/events/seminar-talk/{mistyped_slug}"
        fetcher = Fetcher(delay_s=0, logger=logging.getLogger("web_monitor.fetcher"))
        with caplog.at_level(logging.INFO, logger="web_monitor"):
            merged = enrich_items(items, iit_bombay.parse_detail, fetch_fn=fetcher.get, source_id="hss",
                                  max_items=4, logger=logging.getLogger("web_monitor"))

    assert [r["detail_fetch_status"] for r in merged] == ["ok", "failed", "ok", "ok"] + ["not_attempted"] * 6
    failed = merged[1]
    assert failed["detail_http_status"] == 404
    assert failed["title"] == items[1]["title"]  # listing record kept
    assert "speaker" not in failed
    assert all(merged[i]["speaker"] for i in (0, 2, 3))

    detail_failures = [r for r in caplog.records if "DETAIL_FAILURE" in r.getMessage()]
    assert len(detail_failures) == 1
    assert detail_failures[0].name == "web_monitor.detail"
    assert "status=404" in detail_failures[0].getMessage()
    assert not any(r.getMessage().startswith("FAILURE ") for r in caplog.records)


@pytest.mark.skipif(os.environ.get("LIVE_TESTS") != "1", reason="hits the real HSS server; set LIVE_TESTS=1")
def test_live_mistyped_url_is_a_real_404():
    from src.config import load_source_configs
    ca_bundle = load_source_configs()["iit_bombay_hss_seminars"].ca_bundle   # HSS omits its intermediate cert
    with pytest.raises(FetchError) as exc:
        Fetcher(timeout_s=10, delay_s=0, ca_bundle=ca_bundle).get(MISTYPED_LIVE_URL)
    assert exc.value.status == 404
