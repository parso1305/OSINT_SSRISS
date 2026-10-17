"""Week 3 Section 10: the central aggregator end to end, offline, through the Week 2 scheduler.

local_aggregator_fixture (config/sources.json) against scripts/aggregator_fixture_site.py: two runs on a fresh DB
(run 2 mostly unchanged, no duplicate rows anywhere), then the "next day" site (one new event, one venue change,
two events gone).
"""

import importlib
import socket

import pytest

from src.config import load_source_configs
from src.storage import get_discovered_item, get_record, query

scenarios = importlib.import_module("assignments.week3.09_metrics.failure_signatures_run")
inspect_db = importlib.import_module("assignments.week3.10_aggregator.inspect_db")


@pytest.fixture
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def no_duplicates(db: str) -> None:
    for name, sql in inspect_db.DUPLICATE_CHECKS.items():
        assert query(db, sql) == [], name


def test_two_runs_then_changed_site(tmp_path, port):
    db, locks = str(tmp_path / "agg.db"), tmp_path / "locks"
    first, _ = scenarios.scenario(db, locks, port=port)
    second, text2 = scenarios.scenario(db, locks, port=port)
    assert first["counts"] == {"new": 22, "unchanged": 0, "changed": 0}
    assert second["counts"] == {"new": 0, "unchanged": 22, "changed": 0} and second["not_seen_this_run"] == 0
    no_duplicates(db)
    assert query(db, "SELECT COUNT(*) FROM item_people") == [(19,)]                # unchanged by run 2

    third, _ = scenarios.scenario(db, locks, port=port, variant="changed")
    assert third["counts"] == {"new": 1, "unchanged": 18, "changed": 2} and third["not_seen_this_run"] == 2
    no_duplicates(db)
    base = f"http://127.0.0.1:{port}/event/"
    assert get_record(db, base + "institute-lecture-taming-turbulence")["location"].startswith("Victor Menezes")
    gone = get_record(db, base + "van-mahotsav-2026")
    assert gone is not None and gone["last_seen_at"] < get_record(db, base + "synthetic-new-workshop")["last_seen_at"]


def test_routing_and_detail_fetches(tmp_path, port):
    db, locks = str(tmp_path / "agg.db"), tmp_path / "locks"
    result, _ = scenarios.scenario(db, locks, port=port)
    site = f"http://127.0.0.1:{port}"
    pdf = get_discovered_item(db, site + "/events/brochure-iccms-2027.pdf")
    external = get_discovered_item(db, "https://www.iitbombay.org/e/ieor-alumni-meet-2026")
    news = get_discovered_item(db, site + "/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug")
    assert (pdf["content_class"], pdf["in_scope"]) == ("pdf_document", True)
    assert (external["content_class"], external["in_scope"]) == ("external_link", False)
    assert news["content_class"] == "announcement"
    assert get_record(db, pdf["discovered_url"]) is None and get_record(db, news["discovered_url"]) is None
    taming = get_discovered_item(db, site + "/event/institute-lecture-taming-turbulence")
    assert taming["discovery_methods"] == ["html", "rss"]                  # found by both, one row, one record
    # 22 in-scope events, details capped at 20 (scope.max_detail_items); the other 2 are stored from the listing
    assert result["summary"]["items_parsed"] == 20
    assert query(db, "SELECT detail_fetch_status, COUNT(*) FROM records GROUP BY 1 ORDER BY 1") == \
        [("not_attempted", 2), ("ok", 20)]


def test_requests_made_by_one_run(tmp_path):
    from scripts.aggregator_fixture_site import AggregatorFixtureSite
    import dataclasses
    from src.logging_config import setup_logger
    from src.scheduler import run_scheduled
    config = load_source_configs()["local_aggregator_fixture"]
    with AggregatorFixtureSite() as site:
        c = dataclasses.replace(config, listing_url=site.url + "/", request_delay_s=0,
                                discovery_urls={"html": [site.url + "/"], "rss": [site.url + "/events.rss"]})
        run_scheduled(c, str(tmp_path / "r.db"), tmp_path / "locks", setup_logger("test_requests_quiet"))
        requests = list(site.requests)
    assert requests[:3] == ["/robots.txt", "/", "/events.rss"]
    assert len([r for r in requests if r.startswith("/event/")]) == 20
    assert not any(r.endswith(".pdf") or r.startswith("/breaking-news/") for r in requests)


def test_adapter_stays_short_and_has_no_generic_code():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "sources" / "iit_bombay_events.py").read_text(encoding="utf-8")
    code = [line for line in source.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert len(code) < 120
    for forbidden in ("import requests", "sqlite3", "Fetcher(", "urljoin", "logging.basicConfig", "addHandler"):
        assert forbidden not in source
