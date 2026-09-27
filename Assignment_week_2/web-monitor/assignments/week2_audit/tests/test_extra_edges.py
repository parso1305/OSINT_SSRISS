"""Extra edge found while reading the code (not in the 21-case list): cross-source keys (X2).

X1 (retry after a failed run) was fixed and its test now lives in tests/test_audit_regressions.py::test_caseX1_...
"""

import logging

from audit_server import AuditSite
from conftest import SOURCE_ID, write_sandbox_config, real_entry, open_problem

from src.scheduler import run_once
from src.storage import count_records, get_record

LOG = logging.getLogger("web_monitor")


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
