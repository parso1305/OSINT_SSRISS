"""Regression tests for problems found by the Week 2 audit (assignments/week2_audit/AUDIT_REPORT.md).

Each test names the audit case it reproduces. Real local HTTP (scripts/fixture_site.py), real SQLite, the real
scheduler; no mocks.
"""

import hashlib
import io
import json
import logging
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
