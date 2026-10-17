"""Week 3 Section 7: entity matching policy. One test per row of assignments/week3/07_resolution/entity_matching_policy.md."""

import re
from pathlib import Path

import pytest

from src.aggregator import write_entities
from src.entities import (NO_MATCH, REVIEW, SAFE, OrgMention, extract_mentions, mention_rows, name_key, org_match,
                          person_match, resolve_page_acronyms)
from src.storage import _open, init_entity_tables, query, store_records_detailed

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "assignments" / "week3" / "07_resolution" / "entity_matching_policy.md"

PERSON_ROWS = [
    ("P1", "Prof. Ananya Rao", "Ananya Rao", SAFE),
    ("P2", "Prof. Ananya Rao", "Prof Ananya Rao", SAFE),
    ("P3", "Prof. Ananya Rao", "A. Rao", REVIEW),
    ("P4", "Prof. Ananya Rao", "Ananya R.", REVIEW),
    ("P5", "Ananya Rao", "Prof Ananya Rao", SAFE),
    ("P6", "Ananya Rao", "A. Rao", REVIEW),
    ("P7", "Ananya Rao", "Ananya R.", REVIEW),
    ("P8", "Prof Ananya Rao", "A. Rao", REVIEW),
    ("P9", "Prof Ananya Rao", "Ananya R.", REVIEW),
    ("P10", "A. Rao", "Ananya R.", NO_MATCH),
]
ORG_ROWS = [
    ("O1", "Centre for Policy Research", "Centre for Policy Research (CPR)", SAFE),
    ("O2", "Centre for Policy Research", "CPR", NO_MATCH),
    ("O3", "Centre for Policy Research", "Center for Policy Research", REVIEW),
    ("O4", "Centre for Policy Research (CPR)", "CPR", NO_MATCH),
    ("O5", "Centre for Policy Research (CPR)", "Center for Policy Research", REVIEW),
    ("O6", "CPR", "Center for Policy Research", NO_MATCH),
]


@pytest.mark.parametrize("row, a, b, decision", PERSON_ROWS, ids=[r[0] for r in PERSON_ROWS])
def test_person_pair(row, a, b, decision):
    assert person_match(a, b)[0] == decision
    assert person_match(b, a)[0] == decision                  # symmetric


@pytest.mark.parametrize("row, a, b, decision", ORG_ROWS, ids=[r[0] for r in ORG_ROWS])
def test_org_pair(row, a, b, decision):
    assert org_match(a, b)[0] == decision
    assert org_match(b, a)[0] == decision


def test_every_policy_row_has_a_test():
    doc = POLICY.read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([PO]\d+) \| (.+?) \| (.+?) \| (.+?) \|", doc, re.M)
    assert [(r, a, b, d) for r, a, b, d in rows] == [(r, a, b, d) for r, a, b, d in PERSON_ROWS + ORG_ROWS]
    assert len([r for r in rows if r[0].startswith("P")]) == 10 and len([r for r in rows if r[0].startswith("O")]) == 6


def test_name_key_never_gives_an_initial_and_a_full_name_the_same_key():
    assert name_key("A. Rao") == "a rao" and name_key("Ananya Rao") == "ananya rao"
    assert name_key("A. Rao") != name_key("Ananya Rao")
    assert name_key("Ananya R.") != name_key("Ananya Rao")


@pytest.mark.parametrize("a, b", [("Ananya  Rao ", "ananya rao"), ("ＡＮＡＮＹＡ Rao", "ananya rao"),   # NFKC + casefold
                                  ("“Ananya Rao”", "ananya rao"), ("Rao, Ananya", "rao ananya")])
def test_name_key_steps(a, b):
    assert name_key(a) == b


def test_name_key_never_reorders_or_drops_parts():
    assert name_key("Rao Ananya") != name_key("Ananya Rao")
    assert name_key("Ananya K. Rao") == "ananya k rao" and name_key("Ananya K. Rao") != name_key("Ananya Rao")
    assert name_key("Center for Policy Research") != name_key("Centre for Policy Research")


def test_acronym_is_an_alias_only_on_the_page_that_defines_it():
    same_page = ["Organized by: Centre for Policy Research (CPR)", "Co-organized by: CPR"]
    _, orgs = extract_mentions(same_page, {"organizer": ["Organized by"], "co-organizer": ["Co-organized by"]})
    assert [(o.name, o.role) for o in orgs] == [("Centre for Policy Research", "organizer"),
                                                 ("Centre for Policy Research", "co-organizer")]
    _, other_page = extract_mentions(["Co-organized by: CPR"], {"co-organizer": ["Co-organized by"]})
    assert [o.name for o in other_page] == ["CPR"]                       # stays CPR elsewhere
    assert resolve_page_acronyms([OrgMention("CPR", "organizer", None, None, None, "s")])[0].name == "CPR"


def test_review_pairs_are_queued_never_merged(tmp_path):
    db = str(tmp_path / "policy.db")
    init_entity_tables(db)
    base = {"source_name": "s", "source_url": "https://events.example.org/", "institution": "X", "item_type": "event",
            "event_start": "2026-11-01T10:00:00Z", "fetched_at": "2026-10-17T00:00:00Z", "http_status": 200}
    records, links = [], {}
    for i, (label, name) in enumerate([("Speaker", "Prof. Ananya Rao"), ("Speaker", "Ananya Rao"),
                                       ("Chair", "Prof Ananya Rao"), ("Speaker", "A. Rao"), ("Speaker", "Ananya R.")]):
        url = f"https://events.example.org/event/{i}"
        records.append({**base, "item_url": url, "title": f"Event {i}"})
        people, orgs = extract_mentions([f"{label}: {name}"], {"speaker": ["Speaker"], "chair": ["Chair"]})
        links[url] = mention_rows(people, orgs)
    for i, name in enumerate(["Centre for Policy Research", "Centre for Policy Research (CPR)", "CPR",
                              "Center for Policy Research"], start=10):
        url = f"https://events.example.org/event/{i}"
        records.append({**base, "item_url": url, "title": f"Event {i}"})
        people, orgs = extract_mentions([f"Organized by: {name}"], {"organizer": ["Organized by"]})
        links[url] = mention_rows(people, orgs)

    added = {}
    store_records_detailed(db, records, extra_writes=lambda conn: added.update(write_entities(conn, links, links)))
    people = [r[0] for r in query(db, "SELECT display_name FROM people ORDER BY id")]
    assert people == ["Ananya Rao", "A. Rao", "Ananya R."]                                     # P1/P2/P5 safe: one row
    orgs = [r[0] for r in query(db, "SELECT display_name FROM organizations ORDER BY id")]
    assert orgs == ["Centre for Policy Research", "CPR", "Center for Policy Research"]        # O1 safe: one row
    queue = query(db, "SELECT c.kind, a.display_name, b.display_name, c.status FROM entity_alias_candidates c "
                      "JOIN people a ON a.id = c.a_id JOIN people b ON b.id = c.b_id WHERE c.kind = 'person' "
                      "UNION ALL SELECT c.kind, a.display_name, b.display_name, c.status FROM entity_alias_candidates c "
                      "JOIN organizations a ON a.id = c.a_id JOIN organizations b ON b.id = c.b_id "
                      "WHERE c.kind = 'organization' ORDER BY 1, 2, 3")
    assert queue == [("organization", "Centre for Policy Research", "Center for Policy Research", "needs_review"),
                     ("person", "Ananya Rao", "A. Rao", "needs_review"),
                     ("person", "Ananya Rao", "Ananya R.", "needs_review")]
    assert added["review_candidates"] == 3
    # A reviewer's decision survives a re-run; nothing is ever merged by code.
    conn = _open(db)
    with conn:
        conn.execute("UPDATE entity_alias_candidates SET status = 'rejected' WHERE kind = 'organization'")
    conn.close()
    again = {}
    store_records_detailed(db, records, extra_writes=lambda conn: again.update(write_entities(conn, links, links)))
    assert again["review_candidates"] == 0
    assert query(db, "SELECT status FROM entity_alias_candidates WHERE kind = 'organization'") == [("rejected",)]
    assert query(db, "SELECT COUNT(*) FROM people") == [(3,)]
