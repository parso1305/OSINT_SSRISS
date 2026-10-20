# Section 10: live runs against the real target (redone in repair R1, 2026-10-20)

Target: `iit_bombay_events` (D1).
- **Discovery (R1, D33):** the **`/events` calendar**. Its items exist only as FullCalendar JSON inside
  `drupal-settings-json`, which the adapter hook `calendar_entries` decodes. The entries are filtered by the config's
  `listing_options.include_title_keywords` to lecture-type entries (Institute Lecture, Lecture, Colloquium, Seminar,
  Talk) and ordered upcoming first, then the most recent past ones.
- **Caps:** 40 in scope (`max_discovered_items`), 20 detail fetches (`max_detail_items` / `detail_limit`).
- **Details:** `/event/<slug>`.

This replaces the homepage-events-block runs of 2026-10-17 (D11, superseded). Those gave **1 labelled speaker in 20
parsed pages**; these give **16 in 20**.

Both runs went **through the Week 2 scheduler**, back to back, on a fresh `data/week3_live.db`:

```
venv\Scripts\python -m src.scheduler --once --source iit_bombay_events --force --db data\week3_live.db
```

**Requests:**
- 22 per run: robots.txt, `/events` and 20 detail pages. All returned 200, with ≥ 3 s per request and a 15 s
  timeout.
- **44 in total** for the repair pass, of its 60 budget (`../live_requests.md`).
- There were no 403, 429 or robots.txt refusals.

## Adapter and config not edited between runs

```
## before run 1: 2026-10-20T13:27:30Z
15c5ea2aad579a07c04a4f1ebc52c8fc228e9a5a2a22a753b0286ee46c2034c9 *sources/iit_bombay_events.py
8d788543538901621a0808f5853cba6456a3b7d0cc4591327879c7c854733a89 *config/sources.json
last commit touching adapter/config: b1b6262 week3: R1 calendar discovery for iit_bombay_events (lecture-type, upcoming first; offline fixture + tests)
## before run 2: 2026-10-20T13:28:55Z
15c5ea2aad579a07c04a4f1ebc52c8fc228e9a5a2a22a753b0286ee46c2034c9 *sources/iit_bombay_events.py
8d788543538901621a0808f5853cba6456a3b7d0cc4591327879c7c854733a89 *config/sources.json
## after run 2: 2026-10-20T13:29:59Z
15c5ea2aad579a07c04a4f1ebc52c8fc228e9a5a2a22a753b0286ee46c2034c9 *sources/iit_bombay_events.py
8d788543538901621a0808f5853cba6456a3b7d0cc4591327879c7c854733a89 *config/sources.json
```

## Run 1 (fresh DB)

```
2026-10-20 18:57:31 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_events interval_minutes=1440 last_started_at=never last_status=none consecutive_failures=0 wait_minutes=1440 next_due_at=now next_due_reason=forced due=true
2026-10-20 18:57:31 [INFO] logger=web_monitor RUN_START run_id=e95724198fa5448fa9d2c6c1f9ae6963 source=iit_bombay_events
2026-10-20 18:57:34 [INFO] logger=web_monitor DISCOVER source_id=iit_bombay_events method=html url=https://www.iitb.ac.in/events status=200 found=122
2026-10-20 18:57:34 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/events status=200 duration_ms=66
2026-10-20 18:57:37 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual status=200 duration_ms=44
2026-10-20 18:57:40 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-taming-turbulence status=200 duration_ms=38
... (18 more FETCH lines: detail pages, all status=200)
2026-10-20 18:57:34 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=iit_bombay_events pages_fetched=1 raw=122 unique=122 in_scope=40 out_of_scope=82
2026-10-20 18:58:35 [INFO] logger=web_monitor VALIDATE valid=40 invalid=0
2026-10-20 18:58:35 [INFO] logger=web_monitor STORE new=40 unchanged=0 changed=0 not_seen_this_run=0 run_id=e95724198fa5448fa9d2c6c1f9ae6963
2026-10-20 18:58:35 [INFO] logger=web_monitor ENTITIES run_id=e95724198fa5448fa9d2c6c1f9ae6963 source_id=iit_bombay_events people_extracted=16 organizations_extracted=0 people_links_added=16 organization_links_added=0 review_candidates_added=0 discovered_items_written=122
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 122
ITEMS_PARSED: 20
NEW: 40
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 16
ORGANIZATIONS_EXTRACTED: 0
2026-10-20 18:58:35 [INFO] logger=web_monitor RUN_SUMMARY run_id=e95724198fa5448fa9d2c6c1f9ae6963 source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=122 items_parsed=20 new=40 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=16 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=80.0 pct_with_org=0.0 error=""
2026-10-20 18:58:35 [INFO] logger=web_monitor RUN_END run_id=e95724198fa5448fa9d2c6c1f9ae6963 source=iit_bombay_events status=success duration_ms=63841 new=40 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error=""
exit=0
```

## Run 2 (back to back)

```
2026-10-20 18:58:55 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_events interval_minutes=1440 last_started_at=2026-10-20T13:27:31Z last_status=success consecutive_failures=0 wait_minutes=1440 next_due_at=2026-10-21T13:27:31Z next_due_reason=forced due=true
2026-10-20 18:58:55 [INFO] logger=web_monitor RUN_START run_id=0aef8870ed22416ba17551ffadcf6c31 source=iit_bombay_events
2026-10-20 18:58:59 [INFO] logger=web_monitor DISCOVER source_id=iit_bombay_events method=html url=https://www.iitb.ac.in/events status=200 found=122
2026-10-20 18:58:58 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/events status=200 duration_ms=47
2026-10-20 18:59:01 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual status=200 duration_ms=29
2026-10-20 18:59:04 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-taming-turbulence status=200 duration_ms=32
... (18 more FETCH lines: detail pages, all status=200)
2026-10-20 18:58:59 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=iit_bombay_events pages_fetched=1 raw=122 unique=122 in_scope=40 out_of_scope=82
2026-10-20 18:59:59 [INFO] logger=web_monitor VALIDATE valid=40 invalid=0
2026-10-20 18:59:59 [INFO] logger=web_monitor STORE new=0 unchanged=40 changed=0 not_seen_this_run=0 run_id=0aef8870ed22416ba17551ffadcf6c31
2026-10-20 18:59:59 [INFO] logger=web_monitor ENTITIES run_id=0aef8870ed22416ba17551ffadcf6c31 source_id=iit_bombay_events people_extracted=16 organizations_extracted=0 people_links_added=0 organization_links_added=0 review_candidates_added=0 discovered_items_written=122
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 122
ITEMS_PARSED: 20
NEW: 0
CHANGED: 0
UNCHANGED: 40
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 16
ORGANIZATIONS_EXTRACTED: 0
2026-10-20 18:59:59 [INFO] logger=web_monitor RUN_SUMMARY run_id=0aef8870ed22416ba17551ffadcf6c31 source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=122 items_parsed=20 new=0 changed=0 unchanged=40 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=16 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=80.0 pct_with_org=0.0 error=""
2026-10-20 18:59:59 [INFO] logger=web_monitor RUN_END run_id=0aef8870ed22416ba17551ffadcf6c31 source=iit_bombay_events status=success duration_ms=63371 new=0 unchanged=40 changed=0 not_seen_this_run=0 failed=0 error=""
exit=0
```

## Duplicate checks and inventory after run 2

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

records: 40 | by detail_fetch_status: [('not_attempted', 20), ('ok', 20)]
discovered_items by content_class / in_scope: [('event', 0, 82), ('event', 1, 40)]
entities: {'people': 16, 'organizations': 0, 'item_people': 16, 'item_organizations': 0, 'entity_alias_candidates': 0}
runs: [('success', 40, 0, 0, 0, 0, 122, 20), ('success', 0, 0, 40, 0, 0, 122, 20)]
```

## Last-run summary (`python -m src.metrics --last`)

```
RUN 0aef8870ed22416ba17551ffadcf6c31 started 2026-10-20T13:28:55Z finished 2026-10-20T13:29:59Z
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 122
ITEMS_PARSED: 20
NEW: 0
CHANGED: 0
UNCHANGED: 40
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 16
ORGANIZATIONS_EXTRACTED: 0
RUN_SUMMARY run_id=0aef8870ed22416ba17551ffadcf6c31 source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=122 items_parsed=20 new=0 changed=0 unchanged=40 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=16 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=80.0 pct_with_org=0.0 error=""
```

## Headline numbers

| | Old discovery (homepage block, 2026-10-17) | **Calendar, lecture-type (2026-10-20)** |
|---|---|---|
| items discovered (unique URLs on the listing) | 40 | 122 lecture-type, of which 40 in scope (82 marked `over max_discovered_items cap (40)`) |
| items parsed (detail pages) | 20 | 20 |
| people extracted | 1 | **16** |
| `pct_with_speaker` | 5.0 | **80.0** |
| `pct_with_org` | 0.0 | 0.0 (IITB event pages have no organizer field; see `05_extraction/notes.md`) |
| run 2 | 40 unchanged | **40 unchanged**, 0 new, 0 changed, 0 failed |

**About ITEMS_DISCOVERED = 122.** The metric counts every unique URL the discovery page listed after the keyword
filter, so a shrinking listing stays visible. The cap is applied as before (D16): only 40 enter scope, and the other
82 are stored in `discovered_items` with `in_scope = 0` and the reason `over max_discovered_items cap (40)`. They are
never fetched. Both runs fetched exactly 20 detail pages. If "at most 40 discovered" must also hold for this metric, a
`max_entries` option on the hook would truncate before discovery; that is logged as OPEN_QUESTIONS Q5 rather than
changed after the runs.

## The 20 parsed events (from `data/week3_live.db`)

Columns: slug, `event_type`, `event_start` (UTC), labelled speaker as stored.

```
('institute-lecture-saral-ai-democratising-scholarly-work-tr', 'Seminar/Talk', '2026-10-21T11:45:00Z', 'Prof. Ponnurangam Kumaraguru')
('institute-lecture-taming-turbulence', 'Seminar/Talk', '2026-09-03T11:45:00Z', 'Prof. Beverley J. McKeon')
('lecture-strong-interactions-exotic-emergent-particles-and-', 'Seminar/Talk', '2026-08-12T11:45:00Z', 'Prof. Jainendra K. Jain')
('seminar-cum-workshop-staggered-difference-differences-desi', 'Seminar/Talk', '2026-03-11T08:30:00Z', 'Prof. Partha Deb')
('institute-colloquium-understanding-glue-binds-us-all', 'Seminar/Talk', '2026-02-12T11:45:00Z', 'Prof. Abhay Deshpande')
('institute-lecture-living-genome-active-material', 'Seminar/Talk', '2026-01-22T11:45:00Z', 'Prof. Vivek Shenoy')
('institute-lecture-movement-polymer-molecules-under-electri', 'Seminar/Talk', '2026-01-21T11:45:00Z', 'Prof. Nitash P. Balsara')
('institute-colloquium-tale-two-symmetries', 'Seminar/Talk', '2026-01-19T11:45:00Z', 'Prof. Chandrashekhar Khare')
('institute-lecture-innovations-jet-noise-reduction-technolo', 'Seminar/Talk', '2025-12-02T11:45:00Z', 'Dr. Vinod G. Mengle')
('institute-lecture-nu-frontier-current-challenges-and-oppor', 'Seminar/Talk', '2025-11-19T11:45:00Z', 'Prof. Dr. Joachim Kopp')
('lecture-future-cern-and-outstanding-questions-particle-phy', 'Seminar/Talk', '2025-10-17T11:45:00Z', 'Prof. Eric Laenen')
('institute-lecture-beyond-solar-cells-unlocking-potential-h', 'Seminar/Talk', '2025-10-13T11:30:00Z', 'Prof. Prashant V. Kamat')
('lecture-village-development-through-public-participation-w', 'Seminar/Talk', '2025-10-01T10:30:00Z', 'Shri Chaitram Pawar')
('institute-lecture-joy-discovery-modern-era-some-reflection', 'Seminar/Talk', '2025-08-13T11:45:00Z', 'Prof. B. Ananthanarayan')
('institute-colloquium-global-health-research-india-world', 'Seminar/Talk', '2025-07-10T09:30:00Z', None)
('institute-lecture-anrf-overview', 'Seminar/Talk', '2025-05-26T11:00:00Z', None)
('institute-colloquium-evolution-weather-forecasting-service', 'Seminar/Talk', '2025-03-26T11:45:00Z', None)
('institute-colloquium-indian-cultural-values-inclusive-deve', 'Seminar/Talk', '2025-02-27T11:45:00Z', None)
('institute-lecture-new-insights-climate-change-signals-equa', 'Seminar/Talk', '2025-02-12T10:30:00Z', 'Prof. Matthew')
('institute-colloquium-prof-michael-l-klein-frs', 'Seminar/Talk', '2025-02-06T08:30:00Z', 'Prof. Michael L. Klein FRS Laura H. Carnell Professor of Science')
[('Seminar/Talk', 20)]
[(0,)]
```

- All 20 are `Seminar/Talk` on their detail pages. That fits the filter: the calendar JSON has no event type, so the
  title keywords select them (D33).
- 16 of 20 have a labelled speaker. The 4 without one (`global-health-research`, `anrf-overview`,
  `evolution-weather-forecasting`, `indian-cultural-values`) describe the speaker only in prose, which is not
  extracted.
- **Two extraction defects found by this run, fixed after it** (`src/entities.py::parse_person`, tests
  `test_live_name_shapes_nickname_and_post_nominals`):
  1. `Speaker: Prof. Matthew (Mat) Collins, …` was stored as **`Matthew`**: the name stopped at ` (`. A bracketed
     nickname followed by more name now stays in the name.
  2. `Speaker: Prof. Michael L. Klein FRS Laura H. Carnell Professor of Science, …` was stored with the title inside
     the name. Post-nominal letters (FRS, PhD, …) now end the name, and the rest goes verbatim to `affiliation_raw`.

  The fixed code was re-run offline on the 16 stored `source_text` lines (no new requests):

```
stored='Michael L. Klein FRS Laura H. Carnell Professor of Science' -> fixed code='Michael L. Klein'
stored='Matthew' -> fixed code='Matthew (Mat) Collins'
16 stored speaker links re-extracted from their source_text; 2 differ, 14 identical
```

The two people rows stored by these runs keep the old names until the next live run re-parses those pages. A parsed
item's links are replaced (D21), and the old rows are left unlinked; `people` rows are never deleted.

- No organization was extracted. As the evidence shows, IITB event pages have no organizer field, and none of these
  20 bodies has an `Organized by:` label.
