"""Week 3 Sections 6-7: build the entity fixture DB from the saved detail fixtures and run the documented queries.

Offline (no network). Each fixture page is parsed by the real adapter, assembled into a shared-schema record,
validated, and stored with its entity links and review candidates in ONE transaction
(storage.store_records_detailed + extra_writes=aggregator.write_entities), exactly the aggregator's write path.
Run it twice: the second run adds zero link rows and zero review candidates.

    venv\\Scripts\\python -m assignments.week3.06_entities.build_fixture_db [--db data/week3_entities_fixture.db]
"""

import argparse
import sys
from pathlib import Path

from sources.iit_bombay_events import parse_event_detail
from src.aggregator import write_entities
from src.config import load_source_configs
from src.entities import mention_rows, name_key
from src.schema import assemble_record, validate_record
from src.storage import entity_counts, init_entity_tables, query, store_records_detailed

ROOT = Path(__file__).resolve().parents[3]
DETAIL = ROOT / "fixtures" / "week3" / "iitb_events" / "detail"
FETCHED_AT = "2026-10-17T00:00:00Z"

QUERY_PERSON = """
SELECT r.title, r.event_start, ip.role, ip.affiliation_raw
FROM item_people ip
JOIN people p ON p.id = ip.person_id
JOIN records r ON r.item_url = ip.item_url
WHERE p.normalized_name = ?
ORDER BY r.event_start, ip.role"""

QUERY_ORGANIZERS = """
SELECT o.display_name, o.org_type, io.role, COUNT(DISTINCT io.item_url) AS events
FROM item_organizations io
JOIN organizations o ON o.id = io.organization_id
WHERE io.role IN ('organizer', 'co-organizer')
GROUP BY o.id, io.role
ORDER BY events DESC, o.display_name"""

QUERY_REVIEW = """
SELECT c.kind, a.display_name, b.display_name, c.status, c.reason
FROM entity_alias_candidates c
JOIN people a ON a.id = c.a_id
JOIN people b ON b.id = c.b_id
WHERE c.kind = 'person'
UNION ALL
SELECT c.kind, a.display_name, b.display_name, c.status, c.reason
FROM entity_alias_candidates c
JOIN organizations a ON a.id = c.a_id
JOIN organizations b ON b.id = c.b_id
WHERE c.kind = 'organization'
ORDER BY 1, 2, 3"""


def build(db: str) -> dict:
    config = load_source_configs()["iit_bombay_events"]
    init_entity_tables(db)
    records, links = [], {}
    for path in sorted(DETAIL.glob("*.html")):
        url = f"https://www.iitb.ac.in/event/{path.stem}"
        parsed = parse_event_detail(path.read_text(encoding="utf-8"), url)
        merged = {"item_url": url, "fetched_at": FETCHED_AT, "http_status": 200, "detail_fetch_status": "ok",
                  "detail_http_status": 200, "detail_fetched_at": FETCHED_AT}
        record = assemble_record(config, merged, parsed["fields"])
        errors = validate_record(record)
        if errors:
            raise SystemExit(f"{path.name}: {errors}")
        records.append(record)
        links[url] = mention_rows(parsed["people"], parsed["orgs"])

    added: dict = {}

    def write_links(conn):
        added.update(write_entities(conn, links, replace=links))   # every page was parsed: replace its links

    stored = store_records_detailed(db, records, extra_writes=write_links)
    return {"records": stored.counts,
            "links_added": {k: added[k] for k in ("people_links", "organization_links")},
            "review_candidates_added": added["review_candidates"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "week3_entities_fixture.db"))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    result = build(args.db)
    print(f"stored: {result['records']} links added this run: {result['links_added']} "
          f"review candidates added: {result['review_candidates_added']} totals: {entity_counts(args.db)}")
    key = name_key("Ananya Rao")
    print(f"\n-- Query 1: events that mention the exact normalized person name {key!r}{QUERY_PERSON};")
    for row in query(args.db, QUERY_PERSON, (key,)):
        print(row)
    print(f"\n-- Query 2: organizations that appeared as organizers{QUERY_ORGANIZERS};")
    for row in query(args.db, QUERY_ORGANIZERS):
        print(row)
    print(f"\n-- Section 7 review queue (never merged){QUERY_REVIEW};")
    for row in query(args.db, QUERY_REVIEW):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
