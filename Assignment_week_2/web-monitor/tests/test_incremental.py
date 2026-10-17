"""Week 3 Section 4: incremental collection. States new / changed / unchanged / not_seen_this_run (D6).

Storage-level tests pass explicit run timestamps (now_iso = the run's started_at), exactly what the scheduler
does, so the D6 comparisons do not depend on the wall clock. The rediscovery test runs the full scheduler path.
"""

import io
import logging
import sqlite3
import types

from bs4 import BeautifulSoup

from scripts.fixture_site import FixtureSite
from src.config import SourceConfig
from src.logging_config import KeyValueFormatter
from src.scheduler import run_scheduled
from src.storage import content_hash, count_not_seen, get_record, list_runs, store_records_detailed
from src.urls import resolve_item_url

SOURCE = "incremental_fixture"
T1, T2, T3 = "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "2026-10-03T00:00:00Z"


def rec(slug: str, title: str = None, **extra) -> dict:
    record = {"item_url": f"https://events.example.org/event/{slug}", "source_name": SOURCE,
              "source_url": "https://events.example.org/", "institution": "Example University", "item_type": "event",
              "title": title or slug.upper(), "event_start": "2026-11-01T10:00:00Z", "speakers": [],
              "organizations": [], "fetched_at": T1, "http_status": 200, "detail_fetch_status": "ok", "extras": {}}
    record.update(extra)
    return record


def test_four_states_and_absent_item_is_kept(tmp_path):
    db = str(tmp_path / "inc.db")
    first = store_records_detailed(db, [rec("a"), rec("b"), rec("c")], now_iso=T1)
    assert first.counts == {"new": 3, "unchanged": 0, "changed": 0}

    second = store_records_detailed(db, [rec("a"), rec("b", title="B (venue moved)"), rec("d")], now_iso=T2,
                                    rediscovery_cutoff=T1)
    not_seen = count_not_seen(db, SOURCE, T2)
    assert (second.counts["new"], second.counts["changed"], second.counts["unchanged"], not_seen) == (1, 1, 1, 1)
    assert second.states == {rec("a")["item_url"]: "unchanged", rec("b")["item_url"]: "changed",
                             rec("d")["item_url"]: "new"}
    c = get_record(db, rec("c")["item_url"])
    assert c is not None and c["last_seen_at"] == T1 and c["title"] == "C"        # never deleted, untouched
    assert get_record(db, rec("a")["item_url"])["first_seen_at"] == T1           # first_seen_at kept on update


def test_only_fetched_at_changed_is_unchanged(tmp_path):
    db = str(tmp_path / "inc.db")
    store_records_detailed(db, [rec("a", fetched_at=T1, http_status=200, raw_text="posted 3 days ago")], now_iso=T1)
    again = store_records_detailed(db, [rec("a", fetched_at=T2, http_status=304, raw_text="posted 4 days ago",
                                            detail_fetched_at=T2, detail_http_status=200)], now_iso=T2)
    assert again.counts == {"new": 0, "unchanged": 1, "changed": 0}
    assert get_record(db, rec("a")["item_url"])["fetched_at"] == T2                # provenance still refreshed


def test_reordered_speakers_and_organizations_are_unchanged(tmp_path):
    db = str(tmp_path / "inc.db")
    rao = {"name": "Ananya Rao", "affiliation": "IIT Bombay"}
    sen = {"name": "Ravi Sen", "affiliation": None}
    store_records_detailed(db, [rec("a", speakers=[rao, sen], organizations=["Dept of Physics", "CPR"])], now_iso=T1)
    again = store_records_detailed(db, [rec("a", speakers=[sen, rao], organizations=["CPR", "Dept of Physics"])],
                                   now_iso=T2)
    assert again.counts["unchanged"] == 1
    assert get_record(db, rec("a")["item_url"])["speakers"] == [sen, rao]           # stored in page order
    assert content_hash(rec("a", speakers=[rao])) != content_hash(rec("a", speakers=[sen]))   # a real change is seen


def test_hash_inputs_are_content_fields_only():
    base = rec("a")
    for volatile in ({"fetched_at": T3}, {"http_status": 500}, {"raw_text": "posted 3 days ago"},
                     {"detail_fetched_at": T3}, {"detail_http_status": 404}, {"detail_error": "x"},
                     {"extras": {"views": 1234, "token": "abc"}}, {"source_url": "https://other/"}):
        assert content_hash({**base, **volatile}) == content_hash(base), volatile
    for content in ({"title": "Other"}, {"event_start": "2026-11-02T10:00:00Z"}, {"location": "Hall B"},
                    {"description": "new abstract"}, {"speakers": [{"name": "X", "affiliation": None}]}):
        assert content_hash({**base, **content}) != content_hash(base), content


# -- rediscovery through the real scheduler path ----------------------------------------------------------------

def listing(*slugs) -> str:
    return "<ul class='talks'>" + "".join(f"<li><a href='/event/{s}'>{s.title()}</a></li>" for s in slugs) + "</ul>"


def adapter() -> types.ModuleType:
    module = types.ModuleType("incremental_fixture_adapter")
    module.parse_listing = lambda html, base_url: [
        {"title": a.get_text(), "item_url": resolve_item_url(a["href"], base_url)}
        for a in BeautifulSoup(html, "html.parser").select("ul.talks a")]
    module.normalize = lambda r: {"title": r["title"], "event_start": "2026-11-01T10:00:00Z"}
    return module


def test_absent_then_back_is_logged_rediscovered_and_counted_by_hash(tmp_path):
    db, locks = str(tmp_path / "re.db"), tmp_path / "locks"
    stream = io.StringIO()
    logger = logging.getLogger("test_incremental_rediscovery")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with FixtureSite(overrides={"/talks": listing("alpha", "beta")}) as site:
            config = SourceConfig(source_id=SOURCE, institution="Example University", adapter=adapter(),
                                  listing_url=site.url + "/talks", request_delay_s=0)
            run_scheduled(config, db, locks, logger)
            shift_runs(db)                                   # make run 1 clearly earlier than run 2
            site.overrides["/talks"] = listing("alpha")      # beta absent
            r2 = run_scheduled(config, db, locks, logger)
            shift_runs(db)
            site.overrides["/talks"] = listing("alpha", "beta")   # beta back, same content
            r3 = run_scheduled(config, db, locks, logger)
    finally:
        logger.removeHandler(handler)
    log = stream.getvalue()
    beta = site.url + "/event/beta"
    assert r2["counts"] == {"new": 0, "unchanged": 1, "changed": 0}
    assert r3["counts"] == {"new": 0, "unchanged": 2, "changed": 0}                 # counted by its hash, not new
    assert f"REDISCOVERED run_id={r3['run_id']} source_id={SOURCE} item_url={beta} rediscovered=true state=unchanged" in log
    assert log.count("REDISCOVERED") == 1
    run2_end = next(line for line in log.splitlines() if f"RUN_END run_id={r2['run_id']}" in line)
    assert "new=0 unchanged=1 changed=0 not_seen_this_run=1" in run2_end
    run2_store = next(line for line in log.splitlines() if f"STORE " in line and f"run_id={r2['run_id']}" in line)
    assert "unchanged=1 changed=0 not_seen_this_run=1" in run2_store
    assert [r["unchanged_count"] for r in list_runs(db)] == [0, 1, 2]


def shift_runs(db: str) -> None:
    """Moves every stored run start and last_seen_at one hour back (runs in a test start within one second)."""
    conn = sqlite3.connect(db)
    try:
        with conn:
            conn.execute("UPDATE runs SET started_at = strftime('%Y-%m-%dT%H:%M:%SZ', started_at, '-1 hour')")
            conn.execute("UPDATE records SET last_seen_at = strftime('%Y-%m-%dT%H:%M:%SZ', last_seen_at, '-1 hour'), "
                         "first_seen_at = strftime('%Y-%m-%dT%H:%M:%SZ', first_seen_at, '-1 hour')")
    finally:
        conn.close()
