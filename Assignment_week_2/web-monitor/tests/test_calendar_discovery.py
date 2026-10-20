"""Repair R1: iit_bombay_events discovers from the /events calendar JSON, filtered to lecture-type entries (config),
upcoming first, then the most recent past ones; at most 40 discovered and 20 detail fetches."""

import dataclasses
import socket
from pathlib import Path

import pytest

from scripts.aggregator_fixture_site import AggregatorFixtureSite
from sources.iit_bombay_events import calendar_entries
from src.config import load_source_configs
from src.discovery.discover import discover
from src.fetcher import FetchResult
from src.storage import query

ROOT = Path(__file__).resolve().parent.parent
REAL_CALENDAR = ROOT / "fixtures" / "week3" / "iitb_events" / "events_calendar_2026-10-16.html"
CONFIG = load_source_configs()["iit_bombay_events"]
FETCHED_AT = "2026-10-16T13:56:34Z"           # when the real calendar page was saved


def entries(options=None, now=FETCHED_AT):
    return calendar_entries(REAL_CALENDAR.read_text(encoding="utf-8"), "https://www.iitb.ac.in/events",
                            options or CONFIG.listing_options, now)


def test_filter_values_come_from_config():
    assert CONFIG.listing_options == {"hook": "calendar_entries", "utc_offset": "+05:30",
                                      "include_title_keywords": ["Institute Lecture", "Lecture", "Colloquium",
                                                                 "Seminar", "Talk"]}
    assert CONFIG.discovery_urls == {"html": ["https://www.iitb.ac.in/events"]}


def test_real_calendar_is_filtered_to_lecture_type_entries():
    found = entries()
    keywords = [k.casefold() for k in CONFIG.listing_options["include_title_keywords"]]
    assert len(found) == 122                                       # of 643 entries (614 distinct URLs)
    assert all(any(k in e["title"].casefold() for k in keywords) for e in found)
    assert len({e["href"] for e in found}) == len(found)           # one entry per URL
    assert not any("Van Mahotsav" in e["title"] or "Diwas" in e["title"] for e in found)
    only_colloquia = entries(dict(CONFIG.listing_options, include_title_keywords=["Colloquium"]))
    assert 0 < len(only_colloquia) < len(found) and all("colloquium" in e["title"].casefold() for e in only_colloquia)


def test_upcoming_first_then_most_recent_past():
    found = entries()
    upcoming = [e for e in found if e["timestamp"] >= FETCHED_AT]
    past = found[len(upcoming):]
    assert [e["title"][:30] for e in upcoming] == ['Institute Lecture on "Saral AI']
    assert [e["timestamp"] for e in upcoming] == sorted(e["timestamp"] for e in upcoming)
    assert [e["timestamp"] for e in past] == sorted((e["timestamp"] for e in past), reverse=True)
    assert past[0]["title"] == 'Institute Lecture on "Taming Turbulence"' and past[0]["timestamp"] == "2026-09-03T11:45:00Z"
    assert past[0]["timestamp_raw"] == "2026-09-03T17:15:00"      # local IST in the JSON, converted to UTC


def test_discovery_caps_at_40_in_scope():
    class Page:
        def get(self, url):
            return FetchResult(url, url, 200, REAL_CALENDAR.read_text(encoding="utf-8"), 1, FETCHED_AT, "text/html")
    result = discover(CONFIG, Page(), discovered_at=FETCHED_AT)
    in_scope = [c for c in result.candidates if c.in_scope]
    assert len(result.candidates) == 122 and len(in_scope) == 40
    assert in_scope[0].url.endswith("/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual")
    assert {c.scope_reason for c in result.candidates if not c.in_scope} == {"over max_discovered_items cap (40)"}
    assert all(c.record.discovery_method == "html" for c in result.candidates)


def test_broken_calendar_is_a_clear_error():
    with pytest.raises(ValueError, match="fullCalendarView events not found"):
        calendar_entries(REAL_CALENDAR.read_text(encoding="utf-8").replace("fullCalendarView", "x"), "u",
                         CONFIG.listing_options, FETCHED_AT)
    with pytest.raises(ValueError, match="no drupal-settings-json"):
        calendar_entries("<html></html>", "u", CONFIG.listing_options, FETCHED_AT)


@pytest.fixture
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def calendar_config(site_url: str):
    """The live source's own config (calendar hook, filter, caps), pointed at the offline site."""
    scope = dict(CONFIG.scope, allowed_hosts=["127.0.0.1"])
    router = dict(CONFIG.router, hosts=["127.0.0.1"])
    return dataclasses.replace(CONFIG, listing_url=site_url + "/events", request_delay_s=0, ca_bundle=None,
                               discovery_urls={"html": [site_url + "/events"]}, scope=scope, router=router)


def test_calendar_pipeline_end_to_end_offline(tmp_path, port):
    from src.logging_config import setup_logger
    from src.scheduler import run_scheduled
    db, locks = str(tmp_path / "cal.db"), tmp_path / "locks"
    with AggregatorFixtureSite(port=port) as site:
        first = run_scheduled(calendar_config(site.url), db, locks, setup_logger("calendar_e2e"))
        second = run_scheduled(calendar_config(site.url), db, locks, setup_logger("calendar_e2e"))
        requests = list(site.requests)
    s = first["summary"]
    # lecture-type detail fixtures in the calendar (synthetic panels, observances and the dateless entry filtered out)
    assert (s["items_discovered"], s["items_parsed"], s["failed"]) == (13, 13, 0)
    assert first["counts"]["new"] == 13 and second["counts"] == {"new": 0, "unchanged": 13, "changed": 0}
    assert s["pct_with_speaker"] == 92.3                            # 12 of 13 label a speaker
    assert "/" not in requests and requests.count("/events") == 2  # the homepage is never fetched
    assert query(db, "SELECT COUNT(*) FROM records WHERE item_url LIKE '%van-mahotsav%'") == [(0,)]
