# Section 10: offline end-to-end demo

`local_aggregator_fixture` is the target's adapter (`sources/iit_bombay_events.py`, unchanged) and config,
pointed at `scripts/aggregator_fixture_site.py` on `127.0.0.1:8766`. The site serves:
- the real homepage with its events block rebuilt to list the 22 saved detail pages, plus an external
  registration link, a PDF and a news item;
- an RSS feed with three of the same events, linked with `utm_*` and `#fragment`;
- the real saved detail pages.

Everything runs through the **Week 2 scheduler CLI**, which chooses the aggregator pipeline from
`"pipeline": "aggregator"` in the config. Recorded 2026-10-17, no network.

```
venv\Scripts\python -m scripts.aggregator_fixture_site --port 8766                 # terminal 1
venv\Scripts\python -m src.scheduler --once --source local_aggregator_fixture --force --db data\week3_demo.db   # x2
venv\Scripts\python -m assignments.week3.10_aggregator.inspect_db --db data\week3_demo.db
venv\Scripts\python -m scripts.aggregator_fixture_site --port 8766 --variant changed   # terminal 1, restarted
venv\Scripts\python -m src.scheduler --once --source local_aggregator_fixture --force --db data\week3_demo.db   # run 3
venv\Scripts\python -m src.metrics --last --db data\week3_demo.db --source local_aggregator_fixture
```

The same sequence is asserted in `tests/test_aggregator_e2e.py::test_two_runs_then_changed_site`.

## Run 1 (fresh `data/week3_demo.db`)

```
2026-10-17 06:45:05 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/ status=200 duration_ms=28
2026-10-17 06:45:06 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/events.rss status=200 duration_ms=21
2026-10-17 06:45:06 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/event/international-conference-quantum-dynamics status=200 duration_ms=3
... (19 more FETCH lines: one per detail page, all status=200)
2026-10-17 06:45:05 [INFO] logger=web_monitor SCHEDULE source=local_aggregator_fixture interval_minutes=3 last_started_at=never last_status=none consecutive_failures=0 wait_minutes=3 next_due_at=now next_due_reason=forced due=true
2026-10-17 06:45:05 [INFO] logger=web_monitor RUN_START run_id=a8ec04ac485648338a9404a0877a16c8 source=local_aggregator_fixture
2026-10-17 06:45:06 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:8766/ status=200 found=25
2026-10-17 06:45:06 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:8766/events.rss status=200 found=3
2026-10-17 06:45:06 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=local_aggregator_fixture pages_fetched=2 raw=28 unique=25 in_scope=24 out_of_scope=1
2026-10-17 06:45:10 [INFO] logger=web_monitor VALIDATE valid=22 invalid=0
2026-10-17 06:45:10 [INFO] logger=web_monitor STORE new=22 unchanged=0 changed=0 not_seen_this_run=0 run_id=a8ec04ac485648338a9404a0877a16c8
2026-10-17 06:45:10 [INFO] logger=web_monitor ENTITIES run_id=a8ec04ac485648338a9404a0877a16c8 source_id=local_aggregator_fixture people_extracted=19 organizations_extracted=3 people_links_added=19 organization_links_added=3 review_candidates_added=2 discovered_items_written=25
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 25
ITEMS_PARSED: 20
NEW: 22
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 19
ORGANIZATIONS_EXTRACTED: 3
2026-10-17 06:45:10 [INFO] logger=web_monitor RUN_SUMMARY run_id=a8ec04ac485648338a9404a0877a16c8 source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=25 items_parsed=20 new=22 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=19 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=65.0 pct_with_org=5.0 error=""
2026-10-17 06:45:10 [INFO] logger=web_monitor RUN_END run_id=a8ec04ac485648338a9404a0877a16c8 source=local_aggregator_fixture status=success duration_ms=4560 new=22 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error=""
exit=0
```

## Run 2: mostly UNCHANGED (here, all 22)

```
2026-10-17 06:45:11 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/ status=200 duration_ms=20
2026-10-17 06:45:11 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/events.rss status=200 duration_ms=23
2026-10-17 06:45:11 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/event/international-conference-quantum-dynamics status=200 duration_ms=25
... (19 more FETCH lines: one per detail page, all status=200)
2026-10-17 06:45:10 [INFO] logger=web_monitor SCHEDULE source=local_aggregator_fixture interval_minutes=3 last_started_at=2026-10-17T01:15:05Z last_status=success consecutive_failures=0 wait_minutes=3 next_due_at=2026-10-17T01:18:05Z next_due_reason=forced due=true
2026-10-17 06:45:10 [INFO] logger=web_monitor RUN_START run_id=06cf2bea982340d7b3c43570b642d421 source=local_aggregator_fixture
2026-10-17 06:45:11 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:8766/ status=200 found=25
2026-10-17 06:45:11 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:8766/events.rss status=200 found=3
2026-10-17 06:45:11 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=local_aggregator_fixture pages_fetched=2 raw=28 unique=25 in_scope=24 out_of_scope=1
2026-10-17 06:45:15 [INFO] logger=web_monitor VALIDATE valid=22 invalid=0
2026-10-17 06:45:15 [INFO] logger=web_monitor STORE new=0 unchanged=22 changed=0 not_seen_this_run=0 run_id=06cf2bea982340d7b3c43570b642d421
2026-10-17 06:45:15 [INFO] logger=web_monitor ENTITIES run_id=06cf2bea982340d7b3c43570b642d421 source_id=local_aggregator_fixture people_extracted=19 organizations_extracted=3 people_links_added=0 organization_links_added=0 review_candidates_added=0 discovered_items_written=25
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 25
ITEMS_PARSED: 20
NEW: 0
CHANGED: 0
UNCHANGED: 22
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 19
ORGANIZATIONS_EXTRACTED: 3
2026-10-17 06:45:15 [INFO] logger=web_monitor RUN_SUMMARY run_id=06cf2bea982340d7b3c43570b642d421 source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=25 items_parsed=20 new=0 changed=0 unchanged=22 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=19 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=65.0 pct_with_org=5.0 error=""
2026-10-17 06:45:15 [INFO] logger=web_monitor RUN_END run_id=06cf2bea982340d7b3c43570b642d421 source=local_aggregator_fixture status=success duration_ms=4495 new=0 unchanged=22 changed=0 not_seen_this_run=0 failed=0 error=""
exit=0
```

## Duplicate checks after run 2

The records check is the brief's own query. The same check is applied to the link tables,
`discovered_items` and `people.normalized_name`.

```
SELECT item_url, COUNT(*) FROM records GROUP BY item_url HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT item_url, person_id, role, COUNT(*) FROM item_people GROUP BY item_url, person_id, role HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT item_url, organization_id, role, COUNT(*) FROM item_organizations GROUP BY item_url, organization_id, role HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT discovered_url, COUNT(*) FROM discovered_items GROUP BY discovered_url HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT normalized_name, COUNT(*) FROM people GROUP BY normalized_name HAVING COUNT(*) > 1;
  -> 0 row(s)

records: 22 | by detail_fetch_status: [('not_attempted', 2), ('ok', 20)]
discovered_items by content_class / in_scope: [('announcement', 1, 1), ('event', 1, 22), ('external_link', 0, 1), ('pdf_document', 1, 1)]
entities: {'people': 18, 'organizations': 3, 'item_people': 19, 'item_organizations': 3, 'entity_alias_candidates': 2}
runs: [('success', 22, 0, 0, 0, 0, 25, 20), ('success', 0, 0, 22, 0, 0, 25, 20)]
```

## Run 3: the "next day" site (`--variant changed`)

Changes on the site:
- 2 events are no longer listed (`van-mahotsav-2026`, `birth-anniversary-gandhi-ji-and-shastri-ji-1`);
- 1 new event (`synthetic-new-workshop`);
- the Taming Turbulence detail page has a new venue.

```
2026-10-17 06:45:50 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/ status=200 duration_ms=9
2026-10-17 06:45:50 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/events.rss status=200 duration_ms=5
2026-10-17 06:45:51 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:8766/event/synthetic-new-workshop status=200 duration_ms=24
... (19 more FETCH lines: one per detail page, all status=200)
2026-10-17 06:45:50 [INFO] logger=web_monitor SCHEDULE source=local_aggregator_fixture interval_minutes=3 last_started_at=2026-10-17T01:15:10Z last_status=success consecutive_failures=0 wait_minutes=3 next_due_at=2026-10-17T01:18:10Z next_due_reason=forced due=true
2026-10-17 06:45:50 [INFO] logger=web_monitor RUN_START run_id=5d113835c8654bfea88350e0324c013a source=local_aggregator_fixture
2026-10-17 06:45:50 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:8766/ status=200 found=24
2026-10-17 06:45:50 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:8766/events.rss status=200 found=3
2026-10-17 06:45:50 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=local_aggregator_fixture pages_fetched=2 raw=27 unique=24 in_scope=23 out_of_scope=1
2026-10-17 06:45:55 [INFO] logger=web_monitor VALIDATE valid=21 invalid=0
2026-10-17 06:45:55 [INFO] logger=web_monitor STORE new=1 unchanged=18 changed=2 not_seen_this_run=2 run_id=5d113835c8654bfea88350e0324c013a
2026-10-17 06:45:55 [INFO] logger=web_monitor ENTITIES run_id=5d113835c8654bfea88350e0324c013a source_id=local_aggregator_fixture people_extracted=21 organizations_extracted=3 people_links_added=2 organization_links_added=0 review_candidates_added=0 discovered_items_written=24
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 24
ITEMS_PARSED: 20
NEW: 1
CHANGED: 2
UNCHANGED: 18
NOT_SEEN_THIS_RUN: 2
FAILED: 0
PEOPLE_EXTRACTED: 21
ORGANIZATIONS_EXTRACTED: 3
2026-10-17 06:45:55 [INFO] logger=web_monitor RUN_SUMMARY run_id=5d113835c8654bfea88350e0324c013a source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=24 items_parsed=20 new=1 changed=2 unchanged=18 not_seen_this_run=2 failed=0 parse_failures=0 detail_failures=0 people_extracted=21 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=75.0 pct_with_org=5.0 error=""
2026-10-17 06:45:55 [INFO] logger=web_monitor RUN_END run_id=5d113835c8654bfea88350e0324c013a source=local_aggregator_fixture status=success duration_ms=4532 new=1 unchanged=18 changed=2 not_seen_this_run=2 failed=0 error=""
exit=0
```

```
SELECT item_url, COUNT(*) FROM records GROUP BY item_url HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT item_url, person_id, role, COUNT(*) FROM item_people GROUP BY item_url, person_id, role HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT item_url, organization_id, role, COUNT(*) FROM item_organizations GROUP BY item_url, organization_id, role HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT discovered_url, COUNT(*) FROM discovered_items GROUP BY discovered_url HAVING COUNT(*) > 1;
  -> 0 row(s)
SELECT normalized_name, COUNT(*) FROM people GROUP BY normalized_name HAVING COUNT(*) > 1;
  -> 0 row(s)

records: 23 | by detail_fetch_status: [('not_attempted', 1), ('ok', 22)]
discovered_items by content_class / in_scope: [('announcement', 1, 1), ('event', 1, 23), ('external_link', 0, 1), ('pdf_document', 1, 1)]
entities: {'people': 19, 'organizations': 3, 'item_people': 21, 'item_organizations': 3, 'entity_alias_candidates': 2}
runs: [('success', 22, 0, 0, 0, 0, 25, 20), ('success', 0, 0, 22, 0, 0, 25, 20), ('success', 1, 2, 18, 2, 0, 24, 20)]
```

```
-- the changed, new and no-longer-listed rows (item_url, location, last_seen_at)
('http://127.0.0.1:8766/event/birth-anniversary-gandhi-ji-and-shastri-ji-1', 'P.C. Saxena Auditorium, IIT Bombay', '2026-10-17T01:15:10Z')
('http://127.0.0.1:8766/event/institute-lecture-taming-turbulence', 'Victor Menezes Convention Centre, IIT Bombay', '2026-10-17T01:15:50Z')
('http://127.0.0.1:8766/event/synthetic-new-workshop', 'Seminar Room, Department of Economics, IIT Bombay', '2026-10-17T01:15:50Z')
('http://127.0.0.1:8766/event/van-mahotsav-2026', 'Hostel 15 playground, IIT Bombay', '2026-10-17T01:15:10Z')
```

**Reading run 3:**
- **NEW 1**: the new workshop.
- **NOT_SEEN_THIS_RUN 2**: the two events no longer listed. They are still in `records` with their old
  `last_seen_at = 2026-10-17T01:15:10Z` (run 2's start); nothing is deleted.
- **CHANGED 2**:
  1. Taming Turbulence's location is now `Victor Menezes Convention Centre, IIT Bombay`.
  2. `institute-lecture-nu-frontier-…`: in runs 1–2 it was 21st in listing order, beyond the 20-detail cap, so it
     was stored from listing data only (`detail_fetch_status = not_attempted`). With two events gone it moved inside
     the cap, its detail page was parsed for the first time, and its description, speaker and venue were added.

  That second change is a real content change to the stored record, not noise. It is the cost of capping detail
  fetches per run (DECISIONS.md D28).

## `python -m src.metrics --last`

```
RUN 5d113835c8654bfea88350e0324c013a started 2026-10-17T01:15:50Z finished 2026-10-17T01:15:55Z
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 24
ITEMS_PARSED: 20
NEW: 1
CHANGED: 2
UNCHANGED: 18
NOT_SEEN_THIS_RUN: 2
FAILED: 0
PEOPLE_EXTRACTED: 21
ORGANIZATIONS_EXTRACTED: 3
RUN_SUMMARY run_id=5d113835c8654bfea88350e0324c013a source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=24 items_parsed=20 new=1 changed=2 unchanged=18 not_seen_this_run=2 failed=0 parse_failures=0 detail_failures=0 people_extracted=21 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=75.0 pct_with_org=5.0 error=""
```
