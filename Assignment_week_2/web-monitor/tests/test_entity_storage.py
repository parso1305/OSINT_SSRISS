"""Week 3 Section 6: entity storage (people / organizations / item links, FKs to records(item_url), D4/D5)."""

import importlib
import sqlite3

import pytest

from src.storage import _open, entity_counts, init_entity_tables, query, store_records_detailed, write_entity_links

# The documented builder (assignments/week3/06_entities/build_fixture_db.py): 20 extraction fixtures + 2 more real
# pages, each parsed by the adapter and stored with its links in one transaction.
build_entity_db = importlib.import_module("assignments.week3.06_entities.build_fixture_db").build
SYNTH_TWO = "https://www.iitb.ac.in/event/synthetic-two-speakers-and-organizers"
SYNTH_CHAIR = "https://www.iitb.ac.in/event/synthetic-chair-moderator-host"


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "entities.db")
    build_entity_db(path)
    return path


def test_one_event_links_to_many_people_and_organizations(db):
    people = query(db, "SELECT p.display_name, ip.role FROM item_people ip JOIN people p ON p.id = ip.person_id "
                       "WHERE ip.item_url = ? ORDER BY p.display_name", (SYNTH_TWO,))
    orgs = query(db, "SELECT o.display_name, io.role FROM item_organizations io JOIN organizations o "
                     "ON o.id = io.organization_id WHERE io.item_url = ? ORDER BY o.display_name", (SYNTH_TWO,))
    assert people == [("Ananya Rao", "speaker"), ("Ravi Sen", "speaker")]
    assert orgs == [("Centre for Policy Research", "organizer"), ("Department of Economics", "organizer"),
                    ("Department of Science and Technology", "co-organizer")]


def test_one_person_appears_across_many_events(db):
    rows = query(db, "SELECT ip.item_url, ip.role, ip.affiliation_raw, ip.source_text FROM item_people ip "
                     "JOIN people p ON p.id = ip.person_id WHERE p.normalized_name = 'ananya rao' ORDER BY ip.role")
    assert rows == [(SYNTH_CHAIR, "chair", None, "Chair: Prof Ananya Rao"),
                    (SYNTH_TWO, "speaker", "Centre for Policy Research",
                     "Speakers: Prof. Ananya Rao, Centre for Policy Research and Dr. Ravi Sen, Department of "
                     "Economics, IIT Bombay")]
    assert query(db, "SELECT COUNT(*) FROM people WHERE normalized_name = 'ananya rao'") == [(1,)]
    # D5: the affiliation lives on the link, so each event keeps its own (here: one stated, one not)


def test_second_run_adds_zero_link_rows(db):
    before = entity_counts(db)
    result = build_entity_db(db)
    assert result["links_added"] == {"people_links": 0, "organization_links": 0}
    assert entity_counts(db) == before
    assert result["records"] == {"new": 0, "unchanged": 22, "changed": 0}


def test_foreign_key_violation_is_rejected(db):
    conn = _open(db)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            write_entity_links(conn, "https://www.iitb.ac.in/event/not-in-records", [
                {"normalized_name": "x", "display_name": "X", "role": "speaker", "source_text": "Speaker: X"}], [])
            conn.commit()
    finally:
        conn.rollback()
        conn.close()
    assert query(db, "SELECT COUNT(*) FROM item_people WHERE item_url LIKE '%not-in-records'") == [(0,)]


def test_links_and_records_commit_or_roll_back_together(tmp_path):
    db = str(tmp_path / "atomic.db")
    init_entity_tables(db)
    record = {"item_url": "https://events.example.org/event/a", "source_name": "s", "source_url": "https://events.example.org/",
              "institution": "X", "item_type": "event", "title": "A", "event_start": "2026-11-01T10:00:00Z",
              "fetched_at": "2026-10-17T00:00:00Z", "http_status": 200}

    def bad_links(conn):     # a link to an item that is not stored -> FK error inside the run transaction
        write_entity_links(conn, "https://events.example.org/event/missing",
                           [{"normalized_name": "x", "display_name": "X", "role": "speaker", "source_text": "s"}], [])

    with pytest.raises(sqlite3.IntegrityError):
        store_records_detailed(db, [record], extra_writes=bad_links)
    assert query(db, "SELECT COUNT(*) FROM records") == [(0,)]          # the record rolled back too


def test_replaced_links_drop_a_removed_speaker_but_failed_detail_keeps_them(db):
    conn = _open(db, isolation_level=None)
    try:
        conn.execute("BEGIN")
        added = write_entity_links(conn, SYNTH_TWO, [{"normalized_name": "ravi sen", "display_name": "Ravi Sen",
                                                      "role": "speaker", "source_text": "Speaker: Dr. Ravi Sen"}], [])
        assert added == {"people_links": -1, "organization_links": -3}    # page now names only Ravi Sen
        kept = write_entity_links(conn, SYNTH_CHAIR, [], [], replace=False)
        assert kept == {"people_links": 0, "organization_links": 0}
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def test_entity_ddl_matches_the_spec(db):
    def cols(table):
        return [(r[1], r[2], r[3], r[5]) for r in query(db, f"PRAGMA table_info({table})")]
    assert [c[0] for c in cols("people")] == ["id", "normalized_name", "display_name", "honorific", "profile_url"]
    assert [c[0] for c in cols("organizations")] == ["id", "normalized_name", "display_name", "org_type", "url"]
    assert [c[0] for c in cols("item_people")] == ["item_url", "person_id", "role", "affiliation_raw", "source_text"]
    assert [c[0] for c in cols("item_organizations")] == ["item_url", "organization_id", "role", "source_text"]
    assert [c[0] for c in cols("item_people") if c[3]] == ["item_url", "person_id", "role"]          # composite PK
    fks = query(db, "PRAGMA foreign_key_list(item_people)")
    assert sorted((f[2], f[3], f[4]) for f in fks) == [("people", "person_id", "id"), ("records", "item_url", "item_url")]
    uniques = [r for r in query(db, "PRAGMA index_list(people)") if r[2]]
    assert any(query(db, f"PRAGMA index_info({r[1]})")[0][2] == "normalized_name" for r in uniques)
