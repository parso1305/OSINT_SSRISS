"""Regression tests for problems found by the Week 2 audit (assignments/week2_audit/AUDIT_REPORT.md).

Each test names the audit case it reproduces. Real local HTTP (scripts/fixture_site.py), real SQLite, the real
scheduler; no mocks.
"""

import hashlib
import io
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.fixture_site import FixtureSite, FIXTURES, LISTING_PATH
from src.config import DEFAULT_CONFIG_PATH
from src.logging_config import KeyValueFormatter
from src.scheduler import main, run_once
from src.storage import list_runs

SOURCE_ID = "iit_bombay_hss_seminars"
LOG = logging.getLogger("web_monitor")


@pytest.fixture
def log_stream():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    LOG.addHandler(handler)
    LOG.setLevel(logging.DEBUG)
    yield stream
    LOG.removeHandler(handler)


def write_config(tmp_path: Path, site: FixtureSite, **overrides) -> Path:
    """The real iit_bombay_hss_seminars entry, pointed at this test's local server."""
    entries = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))["sources"]
    entry = dict(next(e for e in entries if e["source_id"] == SOURCE_ID),
                 listing_url=site.listing_url, request_delay_s=0, **overrides)
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [entry]}), encoding="utf-8")
    return path


def records_checksum(db: str) -> tuple[str, int]:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT * FROM records ORDER BY item_url").fetchall()
    finally:
        conn.close()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest(), len(rows)


def listing_html() -> str:
    return (FIXTURES / "listing_2026-09-26.html").read_text(encoding="utf-8")


# -- audit case 8: HTML structure changed ------------------------------------------------------------

@pytest.mark.parametrize("change, error_type", [
    ("card_class_renamed", "EmptyListingError"),   # 200 + 0 items: was recorded 'success' with exit code 0
    ("container_renamed", "StructuralError"),      # already loud before the fix; kept as a guard
])
def test_case08_listing_structure_change_fails_run_and_leaves_data_untouched(tmp_path, log_stream, change, error_type):
    db, locks = str(tmp_path / "t08.db"), tmp_path / "locks"
    old, new = {"card_class_renamed": ("event-card-wrapper", "event-card-box"),
                "container_renamed": ("view-seminars-and-talks", "view-talks-list")}[change]
    with FixtureSite() as site:
        config = write_config(tmp_path, site)
        assert run_once(config, db, locks, source_ids=[SOURCE_ID], force=True, logger=LOG)[0]["status"] == "success"
        before = records_checksum(db)

        site.overrides[LISTING_PATH] = listing_html().replace(old, new)
        exit_code = main(["--once", "--force", "--config", str(config), "--db", db, "--locks-dir", str(locks),
                          "--source", SOURCE_ID])

    runs = list_runs(db)
    assert exit_code == 1
    assert [r["status"] for r in runs] == ["success", "failed"]
    assert runs[-1]["error"].startswith(error_type)
    assert records_checksum(db) == before == (before[0], 20)       # nothing removed, nothing changed
    log = log_stream.getvalue()
    assert f"FAILURE source_id={SOURCE_ID} url={site.listing_url} stage=parse error_type={error_type}" in log
    assert "status=failed" in log


def test_case08_allow_empty_listing_accepts_an_empty_page_with_a_warning(tmp_path, log_stream):
    db, locks = str(tmp_path / "t08b.db"), tmp_path / "locks"
    with FixtureSite(overrides={LISTING_PATH: listing_html().replace("event-card-wrapper", "event-card-box")}) as site:
        config = write_config(tmp_path, site, allow_empty_listing=True)
        result = run_once(config, db, locks, source_ids=[SOURCE_ID], force=True, logger=LOG)[0]
    assert result["status"] == "success" and result["counts"] == {"new": 0, "existing": 0, "changed": 0}
    assert f"[WARNING] logger=web_monitor WARNING source_id={SOURCE_ID}" in log_stream.getvalue()


# -- audit case 9: detail date format changed ----------------------------------------------------------

def textual_dates(slug: str) -> str:
    html = (FIXTURES / "detail" / f"{slug}.html").read_text(encoding="utf-8")
    return re.sub(r'datetime="[^"]+"', 'datetime="25 September 2025"', html)


DETAIL_SLUGS = [m["item_url"].rsplit("/", 1)[-1]
                for m in json.loads((FIXTURES / "detail" / "manifest.json").read_text(encoding="utf-8"))]


def hss_config(site: FixtureSite, **overrides):
    import dataclasses
    from src.config import load_source_configs
    return dataclasses.replace(load_source_configs()[SOURCE_ID], listing_url=site.listing_url, request_delay_s=0,
                               supports_pagination=False, **overrides)


def test_case09_unparseable_detail_dates_never_erase_stored_values(tmp_path, log_stream):
    from src.runner import run_source
    from src.storage import get_record
    db = str(tmp_path / "t09.db")
    with FixtureSite() as site:
        first = run_source(hss_config(site), db_path=db)                      # 10 items, all enriched
        urls = [r["item_url"] for r in first["records"]]
        before = {u: get_record(db, u) for u in urls}
        for slug in DETAIL_SLUGS:
            site.overrides["/events/seminar-talk/" + slug] = textual_dates(slug)
        mark = len(log_stream.getvalue())
        second = run_source(hss_config(site), db_path=db)
        after = {u: get_record(db, u) for u in urls}
    log = log_stream.getvalue()[mark:]

    assert second["detail_status"]["ok"] == 10
    assert second["counts"] == {"new": 0, "existing": 10, "changed": 0}   # was changed=10
    erased = [u for u in urls if before[u]["ends_at"] and not after[u]["ends_at"]]
    assert erased == []                                                    # was 10/10
    assert sum(before[u]["ends_at"] is not None for u in urls) == 10
    for u in urls:
        assert (after[u]["starts_at"], after[u]["ends_at"], after[u]["content_hash"]) == \
               (before[u]["starts_at"], before[u]["ends_at"], before[u]["content_hash"])
        assert after[u]["detail_fetch_status"] == "ok"
    assert log.count('field=ends_at raw="25 September 2025"') == 10
    assert log.count('field=starts_at raw="25 September 2025"') == 10     # listing fallback used, still loud
    assert log.count("[WARNING] logger=web_monitor PARSE_WARNING source_id=iit_bombay_hss_seminars") == 20


def test_case09_fresh_db_keeps_listing_start_and_warns(tmp_path, log_stream):
    from src.runner import run_source
    with FixtureSite() as site:
        for slug in DETAIL_SLUGS:
            site.overrides["/events/seminar-talk/" + slug] = textual_dates(slug)
        result = run_source(hss_config(site), db_path=str(tmp_path / "t09b.db"))
    assert result["invalid"] == [] and result["counts"]["new"] == 10
    assert all(r["starts_at"] and r["ends_at"] is None for r in result["records"])   # nothing stored to keep
    assert log_stream.getvalue().count("PARSE_WARNING") == 20


def test_case09_listing_and_detail_dates_unparseable_rejects_new_and_keeps_stored(tmp_path, log_stream):
    from src.runner import run_source
    from src.storage import get_record
    db = str(tmp_path / "t09c.db")
    with FixtureSite() as site:
        first = run_source(hss_config(site), db_path=db)
        before = records_checksum(db)
        for slug in DETAIL_SLUGS:
            site.overrides["/events/seminar-talk/" + slug] = textual_dates(slug)
        site.overrides[LISTING_PATH] = re.sub(r'(icon-calendar"></i>)[^<]+', r"\g<1>2025/09/25 ", listing_html())
        second = run_source(hss_config(site), db_path=db)
    assert len(second["invalid"]) == 10 and all("starts_at: required" in i["errors"] for i in second["invalid"])
    assert records_checksum(db) == before
    assert get_record(db, first["records"][0]["item_url"])["starts_at"] == first["records"][0]["starts_at"]
    assert "PARSE_WARNING" in log_stream.getvalue() and "VALIDATION_FAILURE" in log_stream.getvalue()


# -- audit X1: a failed run was not retried until a full interval (24 h) had passed ------------------------

def test_caseX1_failed_run_is_retried_on_the_next_hourly_trigger(tmp_path, log_stream):
    db, locks = str(tmp_path / "x1.db"), tmp_path / "locks"
    with FixtureSite(drop_paths=[LISTING_PATH]) as site:                  # listing connection dropped mid-response
        config = write_config(tmp_path, site)                              # real entry: interval_minutes 1440
        first = run_once(config, db, locks, source_ids=[SOURCE_ID], logger=LOG)
        site.drop_paths.clear()                                            # site recovers
        conn = sqlite3.connect(db)                                         # the next hourly trigger, 60 min later
        with conn:
            conn.execute("UPDATE runs SET started_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-60 minutes')")
        conn.close()
        second = run_once(config, db, locks, source_ids=[SOURCE_ID], logger=LOG)
    assert [r["status"] for r in first] == ["failed"]
    assert [r["status"] for r in second] == ["success"]                    # was: not due until +24 h
    schedule = [line for line in log_stream.getvalue().splitlines() if "SCHEDULE" in line]
    assert "wait_minutes=60 " in schedule[-1] and "next_due_reason=retry_after_failure due=true" in schedule[-1]
