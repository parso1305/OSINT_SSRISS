"""Extra edges found while reading the code (not in the 21-case list): retry-after-failure and cross-source keys."""

import logging

from audit_server import AuditSite, Fault, LISTING_PATH
from conftest import SOURCE_ID, write_sandbox_config, real_entry, open_problem, superseded

from src.scheduler import run_once
from src.storage import list_runs, count_records, get_record

LOG = logging.getLogger("web_monitor")


@superseded("a failed run is now retried after retry_minutes (60, backing off), i.e. at the next hourly trigger; "
            "this test fires the 'next trigger' 0 minutes later. Clock-shifted version: "
            "tests/test_audit_regressions.py::test_caseX1_failed_run_is_retried_on_the_next_hourly_trigger")
def test_x1_failed_run_is_not_retried_until_next_interval(tmp_path, log_stream, evidence):
    db, locks = str(tmp_path / "x1.db"), tmp_path / "locks"
    with AuditSite() as site:
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0)])
        site.faults[LISTING_PATH] = Fault(status=503)
        first = run_once(cfg, db, locks, source_ids=[SOURCE_ID], logger=LOG)        # due (never run) -> fails
        del site.faults[LISTING_PATH]                                                 # site recovers
        second = run_once(cfg, db, locks, source_ids=[SOURCE_ID], logger=LOG)       # next hourly trigger
    evidence(f"cycle 1: {[(r['status']) for r in first]}", f"cycle 2 (site healthy again): ran={len(second)}",
             f"runs: {[(r['status'], r['error']) for r in list_runs(db)]}",
             [l for l in log_stream.getvalue().splitlines() if "SCHEDULE" in l])
    assert len(second) == 1, "a failed run should be retried on the next trigger, not after a full interval"


@open_problem("M5", "item_url alone is the records key, so two sources listing one URL overwrite each other")
def test_x2_two_sources_listing_the_same_item(tmp_path, evidence):
    """item_url is the table's only key: two sources that list the same URL share one row."""
    db, locks = str(tmp_path / "x2.db"), tmp_path / "locks"
    with AuditSite() as site:
        cfg = write_sandbox_config(tmp_path / "sources.json", [
            real_entry(listing_url=site.listing_url, request_delay_s=0, supports_pagination=False),
            real_entry(source_id="audit_parent_site", institution="IIT Bombay", organizer="Institute events office",
                       listing_url=site.listing_url, request_delay_s=0, supports_pagination=False)])
        r1 = run_once(cfg, db, locks, logger=LOG)
        url = site.url + "/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
        after_cycle1 = get_record(db, url)
        r2 = run_once(cfg, db, locks, force=True, logger=LOG)
    evidence(f"cycle1: {[(r['source_id'], r['counts']) for r in r1]}",
             f"cycle2: {[(r['source_id'], r['counts']) for r in r2]}",
             f"rows total={count_records(db)}; rows per source: {SOURCE_ID}={count_records(db, SOURCE_ID)} "
             f"audit_parent_site={count_records(db, 'audit_parent_site')}",
             f"shared row after cycle 1: source_id={after_cycle1['source_id']} organizer={after_cycle1['organizer']}")
    changed = sum(r["counts"]["changed"] for r in r2)
    assert changed == 0 and count_records(db, SOURCE_ID) == 10, "sources overwrite each other's rows"
