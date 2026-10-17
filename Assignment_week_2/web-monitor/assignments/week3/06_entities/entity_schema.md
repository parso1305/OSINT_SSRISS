# Section 6: entity storage

Code:
- `src/storage.py`: `ENTITY_DDL`, `init_entity_tables`, `write_entity_links`, `entity_counts`, `query`, and
  `_open()` with `PRAGMA foreign_keys = ON`.
- `src/entities.py::mention_rows`: mentions to rows, keyed by `name_key`.

Fixture DB builder: `assignments/week3/06_entities/build_fixture_db.py`. Tests: `tests/test_entity_storage.py`.

## DDL (as created; copied from `sqlite_master` of the fixture DB)

```sql
CREATE TABLE people (
        id INTEGER PRIMARY KEY,
        normalized_name TEXT NOT NULL UNIQUE,      -- name_key(name without honorific): the identity claim (D5)
        display_name TEXT NOT NULL,                -- as first seen
        honorific TEXT,
        profile_url TEXT
    );
CREATE TABLE organizations (
        id INTEGER PRIMARY KEY,
        normalized_name TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        org_type TEXT,
        url TEXT
    );
CREATE TABLE item_people (
        item_url TEXT NOT NULL REFERENCES records(item_url),
        person_id INTEGER NOT NULL REFERENCES people(id),
        role TEXT NOT NULL,
        affiliation_raw TEXT,                      -- per event, as written next to the name (D5)
        source_text TEXT NOT NULL,
        PRIMARY KEY (item_url, person_id, role)
    );
CREATE TABLE item_organizations (
        item_url TEXT NOT NULL REFERENCES records(item_url),
        organization_id INTEGER NOT NULL REFERENCES organizations(id),
        role TEXT NOT NULL,
        source_text TEXT NOT NULL,
        PRIMARY KEY (item_url, organization_id, role)
    );
CREATE INDEX idx_item_people_person ON item_people(person_id);
CREATE INDEX idx_item_organizations_org ON item_organizations(organization_id);
```

Indexes on `normalized_name`: the `UNIQUE` constraints create `sqlite_autoindex_people_1` and
`sqlite_autoindex_organizations_1` on `normalized_name`, so a second explicit index would duplicate them. The two
extra indexes serve the reverse lookups ("every event of this person").
`test_entity_ddl_matches_the_spec` checks the columns, the composite keys, the FKs and the unique index.

**PRAGMA foreign_keys = ON on every connection.** SQLite ignores `REFERENCES` unless that pragma is set on the
connection, and it is off by default. All storage connections are opened in `storage._open()`, which sets it.
`test_foreign_key_violation_is_rejected` shows a link to an `item_url` that is not in `records` raising
`sqlite3.IntegrityError: FOREIGN KEY constraint failed`. `test_links_and_records_commit_or_roll_back_together`
shows that error rolling back the whole run, record included, because links are written inside the run's single
transaction (`store_records_detailed(extra_writes=…)`).

**Re-runs never duplicate links.**
- The keys are `(item_url, person_id, role)` and `(item_url, organization_id, role)`.
- People and organizations are inserted `ON CONFLICT(normalized_name) DO NOTHING`.
- Links are inserted with `INSERT OR IGNORE`.
- When an item's detail page was parsed this run, its links are replaced by what the page says now, so a removed
  speaker does not linger. When the detail fetch failed, they are kept.

Running the builder twice gives:

```
stored: {'new': 22, 'unchanged': 0, 'changed': 0} links added this run: {'people_links': 20, 'organization_links': 3} review candidates added: 2 totals: {'people': 19, 'organizations': 3, 'item_people': 20, 'item_organizations': 3}
stored: {'new': 0, 'unchanged': 22, 'changed': 0} links added this run: {'people_links': 0, 'organization_links': 0} review candidates added: 0 totals: {'people': 19, 'organizations': 3, 'item_people': 20, 'item_organizations': 3}
```

(22 records = the 20 real pages, including the 2 no-speaker pages left out of the extraction set, plus the 2
synthetic pages.)

## D4: link tables reference `records(item_url)`, no integer `items.id`

`item_url` is already the canonical primary key of `records`. It is the output of `resolve_item_url()`, the
dedup key since Week 2, and the value every discovery method produces. So the links point at it directly.

- **For:**
  - one identity for an item everywhere (records, discovered_items, links, logs);
  - no second key to keep in sync;
  - a link row is readable on its own: you can see which event it is without a join;
  - the shared schema stays the Week 2 one, with no surrogate-key migration.
- **Against:**
  - a URL is longer than an integer, so link rows and indexes are bigger. Irrelevant at thousands of rows.
  - If a site **moves** an item to a new URL, it becomes a new record, and its links are a new set. The old URL's
    links stay with the old row (not_seen_this_run), and nothing re-keys them. An integer id would not solve this
    either: deciding that two URLs are one event is a matching problem (Section 7's review queue), not a key
    problem.
  - `ON UPDATE CASCADE` is not used. A canonical URL never changes in place, because canonicalization is
    deterministic, so there is nothing to cascade.

## D5: `people.normalized_name` is UNIQUE

`normalized_name = name_key(name without honorific)`. Making it UNIQUE is an **identity claim**: two different
people with an identical full name collapse into one `people` row. For example, two different "Ravi Sen"s, one at
IIT Bombay and one at TISS, would share one person row.

This is accepted, for three reasons:
- the alternative, no unique key, would create a new person for every mention and make "every event of this
  person" impossible without fuzzy matching, which is out of scope;
- the collision is visible: each link keeps its own `affiliation_raw` and `source_text`, so the two "Ravi Sen"s
  still show different affiliations event by event;
- a reviewer can split them later.

**`affiliation_raw` lives on `item_people`, not on `people`.** It is what that page wrote next to the name at that
event. People move between institutions, and one event may give a short form ("IIT Bombay") and another a long one.
Storing it per link keeps every stated affiliation visible and infers nothing. The fixture DB shows it: the same
person `ananya rao` has `affiliation_raw = 'Centre for Policy Research'` on one event and `None` on the other (query
1 below).

What is never collapsed: `A. Rao` (`a rao`), `Ananya R.` (`ananya r`) and `Ananya Rao` (`ananya rao`) are three
`people` rows. Initials are never expanded; Section 7 sends those pairs to review.

## Two queries with real output from the fixture DB

`venv\Scripts\python -m assignments.week3.06_entities.build_fixture_db` (DB: `data/week3_entities_fixture.db`):

```
-- Query 1: events that mention the exact normalized person name 'ananya rao'
SELECT r.title, r.event_start, ip.role, ip.affiliation_raw
FROM item_people ip
JOIN people p ON p.id = ip.person_id
JOIN records r ON r.item_url = ip.item_url
WHERE p.normalized_name = ?
ORDER BY r.event_start, ip.role;
('SYNTHETIC Round Table: Chair, Moderator and Hosts', '2026-03-11T08:30:00Z', 'chair', None)
('SYNTHETIC Panel: Two Speakers and Organizers', '2026-03-11T08:30:00Z', 'speaker', 'Centre for Policy Research')

-- Query 2: organizations that appeared as organizers
SELECT o.display_name, o.org_type, io.role, COUNT(DISTINCT io.item_url) AS events
FROM item_organizations io
JOIN organizations o ON o.id = io.organization_id
WHERE io.role IN ('organizer', 'co-organizer')
GROUP BY o.id, io.role
ORDER BY events DESC, o.display_name;
('Centre for Policy Research', 'centre', 'organizer', 1)
('Department of Economics', 'department', 'organizer', 1)
('Department of Science and Technology', 'department', 'co-organizer', 1)
```

Query 1 matches `Prof. Ananya Rao` (speaker) and `Prof Ananya Rao` (chair) on two events: the same key after the
honorific is removed. It does **not** return `A. Rao` (moderator) or `Ananya R.` (speaker), which are separate
people pending review (Section 7). Query 2 has only synthetic organizations, because no real page in the sample
has an organization line. The one real `Organizer:` line names a person: `Prof. Azizuddin Khan` (role organizer
in `item_people`).

All 19 people in the fixture DB:
`A. Rao`, `Abhay Deshpande`, `Ananya R.`, `Ananya Rao`, `Azizuddin Khan`, `Beverley J. McKeon`, `Chaitram Pawar`,
`Chandrashekhar Khare`, `Eric Laenen`, `Jainendra K. Jain`, `Joachim Kopp`, `Karan Shah`, `Meera Iyer`,
`Nitash P. Balsara`, `Partha Deb`, `Ponnurangam Kumaraguru`, `Ravi Sen`, `Vinod G. Mengle`, `Vivek Shenoy`.
