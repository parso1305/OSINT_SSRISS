"""Generic runner / fetcher / storage end to end on the saved HSS fixtures, over real local HTTP.

scripts/fixture_site.FixtureSite replays the live HTML under the site's real paths on 127.0.0.1.
No mocks: the real Fetcher, robots.txt handling, pagination, enrichment, validation and SQLite run.
"""

import dataclasses
import io
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import pytest
from bs4 import BeautifulSoup

from scripts.fixture_site import FixtureSite, FIXTURES, LISTING_PATH
from src.config import load_source_configs, SourceConfig
from src.fetcher import Fetcher, FetchError
from src.logging_config import KeyValueFormatter
from src.runner import EmptyListingError, run_source
from src.schema import validate_record, CONTENT_FIELDS
from src.storage import content_hash, count_records, get_record

SOURCE_ID = "iit_bombay_hss_seminars"
ISLANDS = "/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
TRACING = "/events/seminar-talk/tracing-success-indian-democracy-success-nation-building"


def site_config(site: FixtureSite, **overrides) -> SourceConfig:
    return dataclasses.replace(load_source_configs()[SOURCE_ID], listing_url=site.listing_url,
                               request_delay_s=0, **overrides)


@pytest.fixture
def log_stream():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield stream
    logger.removeHandler(handler)


# -- config ---------------------------------------------------------------------

def test_config_entry_has_every_required_key():
    config = load_source_configs()[SOURCE_ID]
    assert (config.institution, config.adapter, config.enabled) == ("IIT Bombay", "sources.iit_bombay", True)
    assert (config.supports_pagination, config.max_pages, config.supports_detail, config.detail_limit) == (True, 2, True, 10)
    assert config.request_delay_s > 0 and config.timeout_s > 0
    assert (config.interval_minutes, config.lock_max_age_minutes) == (1440, 60)


def test_config_rejects_unknown_keys(tmp_path):
    bad = tmp_path / "sources.json"
    bad.write_text(json.dumps({"sources": [{"source_id": "x", "institution": "X", "adapter": "a", "listing_url": "https://x.org", "colour": "red"}]}))
    with pytest.raises(ValueError, match="Unknown config keys"):
        load_source_configs(bad)


# -- end to end ---------------------------------------------------------------------

def test_end_to_end_on_fixtures_all_records_valid(tmp_path, log_stream):
    db = str(tmp_path / "e2e.db")
    with FixtureSite() as site:
        result = run_source(site_config(site), db_path=db)

    assert (result["pages_crawled"], result["stop_reason"]) == (2, "max_pages_reached")
    assert result["detail_status"] == {"ok": 10, "failed": 0, "not_attempted": 10}
    assert result["counts"] == {"new": 20, "existing": 0, "changed": 0}
    assert result["invalid"] == []
    assert all(validate_record(r) == [] for r in result["records"])
    assert count_records(db, source_id=SOURCE_ID) == 20

    stored = get_record(db, site.url + TRACING)
    assert stored["speakers"] == [{"name": "Salvatore Babones", "affiliation": "University of Sydney"}]
    assert (stored["starts_at"], stored["ends_at"], stored["is_online"]) == ("2025-09-17T09:30:00Z", "2025-09-17T11:30:00Z", True)
    assert stored["description"].startswith("Why did democracy take root")
    assert (stored["institution"], stored["organizer"]) == ("IIT Bombay", "Department of Humanities and Social Sciences")

    log = log_stream.getvalue()
    assert f"logger=web_monitor START source_id={SOURCE_ID}" in log
    assert f"logger=web_monitor END source_id={SOURCE_ID}" in log
    assert "logger=web_monitor.fetcher FETCH url=" in log
    assert "logger=web_monitor ENRICH ok=10 failed=0 not_attempted=10" in log
    assert "logger=web_monitor STORE new=20 existing=0 changed=0" in log


def test_second_run_is_idempotent(tmp_path):
    db = str(tmp_path / "dedup.db")
    with FixtureSite() as site:
        run_source(site_config(site), db_path=db)
        second = run_source(site_config(site), db_path=db)
    assert second["counts"] == {"new": 0, "existing": 20, "changed": 0}
    assert count_records(db) == 20


def test_failed_detail_fetch_keeps_listing_record(tmp_path, log_stream):
    """Real 404 from the local server for one detail page; that item is stored from its listing data."""
    db = str(tmp_path / "failed.db")
    with FixtureSite(fail_paths=[TRACING]) as site:
        result = run_source(site_config(site), db_path=db)
        stored = get_record(db, site.url + TRACING)

    assert result["detail_status"] == {"ok": 9, "failed": 1, "not_attempted": 10}
    assert result["counts"]["new"] == 20
    assert (stored["detail_fetch_status"], stored["detail_http_status"]) == ("failed", 404)
    assert stored["title"] == "Tracing the Success of Indian Democracy to Success in Nation-Building"
    assert stored["starts_at"] == "2025-09-17T09:30:00Z"   # from listing date + time
    assert stored["speakers"] == [] and stored["description"] is None
    log = log_stream.getvalue()
    assert "[WARNING] logger=web_monitor.detail DETAIL_FAILURE" in log and "status=404" in log
    assert "FAILURE source_id" not in log.replace("DETAIL_FAILURE", "")


# -- Step 3: change detection ------------------------------------------------------------

def test_failed_refetch_of_enriched_item_is_not_a_change_and_keeps_content(tmp_path):
    """Run 1: detail 200. Run 2: same detail answers a real 404. Run 3: 200 again. No run is a change."""
    db = str(tmp_path / "change.db")
    with FixtureSite() as site:
        run_source(site_config(site), db_path=db)
        before = get_record(db, site.url + ISLANDS)
        site.fail_paths.add(ISLANDS)
        second = run_source(site_config(site), db_path=db)
        after_fail = get_record(db, site.url + ISLANDS)
        site.fail_paths.clear()
        third = run_source(site_config(site), db_path=db)
        after_recover = get_record(db, site.url + ISLANDS)

    assert second["detail_status"]["failed"] == 1
    assert second["counts"] == {"new": 0, "existing": 20, "changed": 0}
    assert after_fail["detail_fetch_status"] == "failed" and after_fail["detail_http_status"] == 404
    for field in CONTENT_FIELDS:
        assert after_fail[field] == before[field], field
    assert after_fail["description"].startswith("The Andaman and Nicobar Islands")
    assert after_fail["content_hash"] == before["content_hash"]
    assert third["counts"] == {"new": 0, "existing": 20, "changed": 0}
    assert after_recover["detail_fetch_status"] == "ok"


def test_real_content_change_is_detected(tmp_path):
    db = str(tmp_path / "edit.db")
    edited = (FIXTURES / "detail" / (ISLANDS.rsplit("/", 1)[-1] + ".html")).read_text(encoding="utf-8").replace("LT 101", "LT 102")
    with FixtureSite() as site:
        run_source(site_config(site), db_path=db)
        site.overrides[ISLANDS] = edited
        second = run_source(site_config(site), db_path=db)
        stored = get_record(db, site.url + ISLANDS)
    assert second["counts"] == {"new": 0, "existing": 19, "changed": 1}
    assert stored["venue"] == "LT 102"


def test_content_hash_ignores_provenance():
    record = {"title": "T", "starts_at": "2025-01-01T00:00:00Z", "detail_fetch_status": "ok",
              "detail_fetched_at": "2026-01-01T00:00:00Z", "listing_fetched_at": "2026-01-01T00:00:00Z", "extras": {"raw_text": "a"}}
    changed_provenance = dict(record, detail_fetch_status="failed", detail_fetched_at="2027-01-01T00:00:00Z",
                              listing_fetched_at="2027-01-01T00:00:00Z", detail_http_status=404, extras={"raw_text": "b"})
    assert content_hash(record) == content_hash(changed_provenance)
    assert content_hash(record) != content_hash(dict(record, title="T2"))


# -- Step 4: pagination --------------------------------------------------------------------

def test_pagination_disabled_fetches_one_page(tmp_path):
    with FixtureSite() as site:
        result = run_source(site_config(site, supports_pagination=False), db_path=str(tmp_path / "p.db"))
        listing_requests = [p for p in site.requests if p.startswith(LISTING_PATH)]
    assert result["pages_crawled"] == 1 and listing_requests == [LISTING_PATH]


def test_pagination_respects_max_pages(tmp_path):
    with FixtureSite() as site:
        result = run_source(site_config(site, max_pages=3, detail_limit=0), db_path=str(tmp_path / "p.db"))
    assert (result["pages_crawled"], result["stop_reason"]) == (3, "max_pages_reached")
    assert result["counts"]["new"] == 30


def test_pagination_stops_on_repeated_items(tmp_path):
    page1 = (FIXTURES / "listing_2026-09-26.html").read_text(encoding="utf-8")
    with FixtureSite(overrides={LISTING_PATH + "?page=1": page1}) as site:
        result = run_source(site_config(site, max_pages=5, detail_limit=0), db_path=str(tmp_path / "p.db"))
    assert (result["pages_crawled"], result["stop_reason"]) == (2, "repeated_items")
    assert result["counts"]["new"] == 10


def test_page2_failure_is_listing_failure_and_keeps_page1(tmp_path, log_stream):
    with FixtureSite(fail_paths=[LISTING_PATH + "?page=1"]) as site:
        result = run_source(site_config(site, detail_limit=0), db_path=str(tmp_path / "p.db"))
    assert (result["pages_crawled"], result["stop_reason"]) == (1, "fetch_failed")
    assert result["counts"]["new"] == 10
    assert "[ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars" in log_stream.getvalue()


def test_page1_failure_aborts_run(tmp_path, log_stream):
    with FixtureSite(fail_paths=[LISTING_PATH]) as site:
        with pytest.raises(FetchError):
            run_source(site_config(site), db_path=str(tmp_path / "p.db"))
    assert "stage=fetch error_type=FetchError" in log_stream.getvalue()


def test_zero_items_fails_the_run_unless_allowed(tmp_path, log_stream):
    soup = BeautifulSoup((FIXTURES / "listing_2026-09-26.html").read_text(encoding="utf-8"), "html.parser")
    for card in soup.select(".event-card-wrapper"):
        card.decompose()
    with FixtureSite(overrides={LISTING_PATH: str(soup)}) as site:
        with pytest.raises(EmptyListingError):
            run_source(site_config(site), db_path=str(tmp_path / "p.db"))
        failed_log = log_stream.getvalue()
        allowed = run_source(site_config(site, allow_empty_listing=True), db_path=str(tmp_path / "p.db"))
    assert f"[ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url={site.listing_url} stage=parse " \
           "error_type=EmptyListingError" in failed_log
    assert allowed["counts"] == {"new": 0, "existing": 0, "changed": 0}
    assert "[WARNING] logger=web_monitor WARNING source_id=iit_bombay_hss_seminars" in log_stream.getvalue()


# -- fetcher politeness -------------------------------------------------------------------------

def test_robots_disallow_is_respected(tmp_path, log_stream):
    with FixtureSite(robots_txt="User-agent: *\nDisallow: /events/\n") as site:
        with pytest.raises(FetchError, match="robots.txt"):
            run_source(site_config(site), db_path=str(tmp_path / "p.db"))
        assert site.requests == ["/robots.txt"]
    assert "FETCH_ERROR" in log_stream.getvalue()


def test_fetcher_waits_for_robots_crawl_delay():
    with FixtureSite(robots_txt="User-agent: *\nCrawl-delay: 1\n") as site:
        fetcher = Fetcher(delay_s=0)
        fetcher.get(site.listing_url)
        start = time.monotonic()
        fetcher.get(site.listing_url + "?page=1")
        assert time.monotonic() - start >= 0.9
