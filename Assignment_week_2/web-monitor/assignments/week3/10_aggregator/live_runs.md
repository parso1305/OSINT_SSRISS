# Section 10: live runs against the real target

Target: `iit_bombay_events` (D1, auto-selected, pending Parth's review).
- **Discovery:** the homepage events block at `https://www.iitb.ac.in/` (D11).
- **Details:** `/event/<slug>`, capped at 20 per run.

Both runs went **through the Week 2 scheduler**, back to back, on a fresh `data/week3_live.db`, on 2026-10-17:

```
venv\Scripts\python -m src.scheduler --once --source iit_bombay_events --force --db data\week3_live.db
```

The source is `enabled: false` in the config, so a plain `--once` (Task Scheduler) does not run it until Parth confirms
the target. Naming it with `--source` runs it, as in Week 2. The scheduler picked the aggregator pipeline from the
source's `"pipeline": "aggregator"`, under the usual lock, `runs` row and `RUN_START` / `RUN_END` lines.

**Requests:**
- 22 per run: robots.txt, the homepage, and 20 detail pages. All returned 200, with ≥ 3 s per request
  (`request_delay_s: 3.0`) and a 15 s timeout.
- 44 for both runs.
- The whole Week 3 run used 61 of 80 (ledger: `../live_requests.md`).
- There were no 403, 429 or robots.txt refusals.

## The adapter was not edited between runs

```
## before run 1: 2026-10-17T01:17:31Z
f4b6bbb69c98977c7fddc1db19a56fdccb9a3517c915ae5e847585ab5687d7d3 *sources/iit_bombay_events.py
last commit touching adapter: 97e5a67 week3: 5 entity extraction
## before run 2: 2026-10-17T01:18:44Z
f4b6bbb69c98977c7fddc1db19a56fdccb9a3517c915ae5e847585ab5687d7d3 *sources/iit_bombay_events.py
## after run 2: 2026-10-17T01:19:48Z
f4b6bbb69c98977c7fddc1db19a56fdccb9a3517c915ae5e847585ab5687d7d3 *sources/iit_bombay_events.py
```

The hash is identical before run 1, between the runs and after run 2. `git status --short sources/` was empty, and the
adapter's last commit is `97e5a67`, made before both runs.

## Run 1 (fresh DB)

The 21 FETCH lines are shown once below; robots.txt is fetched inside the client and is not logged.

```
2026-10-17 06:47:31 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_events interval_minutes=1440 last_started_at=never last_status=none consecutive_failures=0 wait_minutes=1440 next_due_at=now next_due_reason=forced due=true
2026-10-17 06:47:31 [INFO] logger=web_monitor RUN_START run_id=b4faa679a63847d6ae5c70caa9132cbd source=iit_bombay_events
2026-10-17 06:47:35 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/ status=200 duration_ms=55
2026-10-17 06:47:35 [INFO] logger=web_monitor DISCOVER source_id=iit_bombay_events method=html url=https://www.iitb.ac.in/ status=200 found=40
2026-10-17 06:47:35 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=iit_bombay_events pages_fetched=1 raw=40 unique=40 in_scope=40 out_of_scope=0
2026-10-17 06:47:38 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/20th-world-sanskrit-conference status=200 duration_ms=34
2026-10-17 06:47:41 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/4th-international-conference-construction-materials-and-structures-iccms-2027 status=200 duration_ms=38
2026-10-17 06:47:44 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/alumni-day-celebrations-2026 status=200 duration_ms=32
2026-10-17 06:47:47 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/veer-bal-diwas-2026 status=200 duration_ms=34
2026-10-17 06:47:50 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-energy-conservation-day-1 status=200 duration_ms=38
2026-10-17 06:47:53 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/conference-currents-war-tides-change-second-world-war-indian-ocean status=200 duration_ms=31
2026-10-17 06:47:56 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/armed-forces-flag-day-2026 status=200 duration_ms=37
2026-10-17 06:47:59 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/international-conference-quantum-dynamics status=200 duration_ms=35
2026-10-17 06:48:02 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-pollution-control-day-2026 status=200 duration_ms=37
2026-10-17 06:48:05 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/5th-japan-india-forum status=200 duration_ms=40
2026-10-17 06:48:08 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-constitution-day-5 status=200 duration_ms=33
2026-10-17 06:48:11 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/communal-harmony-campaign-week-1 status=200 duration_ms=33
2026-10-17 06:48:14 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/janajatiya-gaurav-diwas-1 status=200 duration_ms=36
2026-10-17 06:48:17 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-education-day-2026 status=200 duration_ms=32
2026-10-17 06:48:20 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-entrepreneurship-day-2026 status=200 duration_ms=36
2026-10-17 06:48:23 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/rashtriya-ekta-diwas-1 status=200 duration_ms=34
2026-10-17 06:48:26 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/vigilance-awareness-week-4 status=200 duration_ms=33
2026-10-17 06:48:29 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual status=200 duration_ms=35
2026-10-17 06:48:32 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institutions-innovation-day-1 status=200 duration_ms=36
2026-10-17 06:48:35 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/world-mental-health-day-0 status=200 duration_ms=38
2026-10-17 06:48:35 [INFO] logger=web_monitor VALIDATE valid=40 invalid=0
2026-10-17 06:48:35 [INFO] logger=web_monitor STORE new=40 unchanged=0 changed=0 not_seen_this_run=0 run_id=b4faa679a63847d6ae5c70caa9132cbd
2026-10-17 06:48:35 [INFO] logger=web_monitor ENTITIES run_id=b4faa679a63847d6ae5c70caa9132cbd source_id=iit_bombay_events people_extracted=1 organizations_extracted=0 people_links_added=1 organization_links_added=0 review_candidates_added=0 discovered_items_written=40
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 40
ITEMS_PARSED: 20
NEW: 40
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 1
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:48:35 [INFO] logger=web_monitor RUN_SUMMARY run_id=b4faa679a63847d6ae5c70caa9132cbd source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=40 items_parsed=20 new=40 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=1 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=5.0 pct_with_org=0.0 error=""
2026-10-17 06:48:35 [INFO] logger=web_monitor RUN_END run_id=b4faa679a63847d6ae5c70caa9132cbd source=iit_bombay_events status=success duration_ms=63435 new=40 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error=""
exit=0
```

## Run 2 (back to back)

```
2026-10-17 06:48:45 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_events interval_minutes=1440 last_started_at=2026-10-17T01:17:31Z last_status=success consecutive_failures=0 wait_minutes=1440 next_due_at=2026-10-18T01:17:31Z next_due_reason=forced due=true
2026-10-17 06:48:45 [INFO] logger=web_monitor RUN_START run_id=e85257d9789f4b498e029a6645b72a8c source=iit_bombay_events
2026-10-17 06:48:48 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/ status=200 duration_ms=51
2026-10-17 06:48:48 [INFO] logger=web_monitor DISCOVER source_id=iit_bombay_events method=html url=https://www.iitb.ac.in/ status=200 found=40
2026-10-17 06:48:48 [INFO] logger=web_monitor DISCOVER_SUMMARY source_id=iit_bombay_events pages_fetched=1 raw=40 unique=40 in_scope=40 out_of_scope=0
2026-10-17 06:48:51 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/20th-world-sanskrit-conference status=200 duration_ms=30
2026-10-17 06:48:54 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/4th-international-conference-construction-materials-and-structures-iccms-2027 status=200 duration_ms=29
2026-10-17 06:48:57 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/alumni-day-celebrations-2026 status=200 duration_ms=30
2026-10-17 06:49:00 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/veer-bal-diwas-2026 status=200 duration_ms=31
2026-10-17 06:49:03 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-energy-conservation-day-1 status=200 duration_ms=30
2026-10-17 06:49:06 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/conference-currents-war-tides-change-second-world-war-indian-ocean status=200 duration_ms=31
2026-10-17 06:49:09 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/armed-forces-flag-day-2026 status=200 duration_ms=31
2026-10-17 06:49:12 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/international-conference-quantum-dynamics status=200 duration_ms=33
2026-10-17 06:49:15 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-pollution-control-day-2026 status=200 duration_ms=33
2026-10-17 06:49:18 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/5th-japan-india-forum status=200 duration_ms=31
2026-10-17 06:49:21 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-constitution-day-5 status=200 duration_ms=29
2026-10-17 06:49:24 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/communal-harmony-campaign-week-1 status=200 duration_ms=34
2026-10-17 06:49:27 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/janajatiya-gaurav-diwas-1 status=200 duration_ms=29
2026-10-17 06:49:30 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-education-day-2026 status=200 duration_ms=34
2026-10-17 06:49:33 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/national-entrepreneurship-day-2026 status=200 duration_ms=33
2026-10-17 06:49:36 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/rashtriya-ekta-diwas-1 status=200 duration_ms=29
2026-10-17 06:49:39 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/vigilance-awareness-week-4 status=200 duration_ms=30
2026-10-17 06:49:42 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual status=200 duration_ms=34
2026-10-17 06:49:45 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/institutions-innovation-day-1 status=200 duration_ms=31
2026-10-17 06:49:48 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/event/world-mental-health-day-0 status=200 duration_ms=30
2026-10-17 06:49:48 [INFO] logger=web_monitor VALIDATE valid=40 invalid=0
2026-10-17 06:49:48 [INFO] logger=web_monitor STORE new=0 unchanged=40 changed=0 not_seen_this_run=0 run_id=e85257d9789f4b498e029a6645b72a8c
2026-10-17 06:49:48 [INFO] logger=web_monitor ENTITIES run_id=e85257d9789f4b498e029a6645b72a8c source_id=iit_bombay_events people_extracted=1 organizations_extracted=0 people_links_added=0 organization_links_added=0 review_candidates_added=0 discovered_items_written=40
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 40
ITEMS_PARSED: 20
NEW: 0
CHANGED: 0
UNCHANGED: 40
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 1
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:49:48 [INFO] logger=web_monitor RUN_SUMMARY run_id=e85257d9789f4b498e029a6645b72a8c source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=40 items_parsed=20 new=0 changed=0 unchanged=40 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=1 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=5.0 pct_with_org=0.0 error=""
2026-10-17 06:49:48 [INFO] logger=web_monitor RUN_END run_id=e85257d9789f4b498e029a6645b72a8c source=iit_bombay_events status=success duration_ms=63377 new=0 unchanged=40 changed=0 not_seen_this_run=0 failed=0 error=""
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
discovered_items by content_class / in_scope: [('event', 1, 40)]
entities: {'people': 1, 'organizations': 0, 'item_people': 1, 'item_organizations': 0, 'entity_alias_candidates': 0}
runs: [('success', 40, 0, 0, 0, 0, 40, 20), ('success', 0, 0, 40, 0, 0, 40, 20)]
```

## Last-run summary (`python -m src.metrics --last`)

```
RUN e85257d9789f4b498e029a6645b72a8c started 2026-10-17T01:18:45Z finished 2026-10-17T01:19:48Z
SOURCE: iit_bombay_events
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 40
ITEMS_PARSED: 20
NEW: 0
CHANGED: 0
UNCHANGED: 40
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 1
ORGANIZATIONS_EXTRACTED: 0
RUN_SUMMARY run_id=e85257d9789f4b498e029a6645b72a8c source=iit_bombay_events status=success http_status=200 pages_fetched=1 items_discovered=40 items_parsed=20 new=0 changed=0 unchanged=40 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=1 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=5.0 pct_with_org=0.0 error=""
```

## What the live data shows

The 20 detail-parsed records, from `data/week3_live.db`: slug, `event_type`, `event_start`, `detail_fetch_status`,
number of speakers.

```
('20th-world-sanskrit-conference', 'Conference/Symposium', '2027-12-10T03:30:00Z', 'ok', 0)
('4th-international-conference-construction-materials-and-stru', 'Conference/Symposium', '2027-12-01T03:30:00Z', 'ok', 0)
('alumni-day-celebrations-2026', 'Academic Event', '2026-12-27T04:30:00Z', 'ok', 0)
('veer-bal-diwas-2026', 'Social/Cultural', '2026-12-26T03:45:00Z', 'ok', 0)
('national-energy-conservation-day-1', 'Academic Event', '2026-12-14T03:45:00Z', 'ok', 0)
('conference-currents-war-tides-change-second-world-war-indian', 'Conference/Symposium', '2026-12-11T03:30:00Z', 'ok', 0)
('armed-forces-flag-day-2026', 'Social/Cultural', '2026-12-07T03:45:00Z', 'ok', 0)
('international-conference-quantum-dynamics', 'Conference/Symposium', '2026-12-07T03:30:00Z', 'ok', 0)
('national-pollution-control-day-2026', 'Academic Event', '2026-12-02T03:45:00Z', 'ok', 0)
('5th-japan-india-forum', 'Conference/Symposium', '2026-11-28T05:30:00Z', 'ok', 0)
('national-constitution-day-5', 'Academic Event', '2026-11-26T03:45:00Z', 'ok', 0)
('communal-harmony-campaign-week-1', 'Academic Event', '2026-11-19T03:30:00Z', 'ok', 0)
('janajatiya-gaurav-diwas-1', 'Social/Cultural', '2026-11-15T03:45:00Z', 'ok', 0)
('national-education-day-2026', 'Academic Event', '2026-11-11T09:30:00Z', 'ok', 0)
('national-entrepreneurship-day-2026', 'Academic Event', '2026-11-09T03:45:00Z', 'ok', 0)
('rashtriya-ekta-diwas-1', 'Academic Event', '2026-10-31T03:45:00Z', 'ok', 0)
('vigilance-awareness-week-4', 'Academic Event', '2026-10-26T03:45:00Z', 'ok', 0)
('institute-lecture-saral-ai-democratising-scholarly-work-tran', 'Seminar/Talk', '2026-10-21T11:45:00Z', 'ok', 1)
('institutions-innovation-day-1', 'Academic Event', '2026-10-15T03:45:00Z', 'ok', 0)
('world-mental-health-day-0', 'Academic Event', '2026-10-10T03:30:00Z', 'ok', 0)
[('Ponnurangam Kumaraguru', 'Prof.', 'speaker', 'Visiting Scientist, Anusandhan National Research Foundation (ANRF), Government of India; Professor, Computer Science, International Institute of Information Technology (IIIT) Hyderabad; and President of ACM India.', 'https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual')]
[('Academic Event', 11), ('Conference/Symposium', 5), ('Seminar/Talk', 1), ('Social/Cultural', 3)]
[('https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual', 'Institute Lecture on "Saral AI: Democratising Scholarly Work by Transforming into Accessible, Multilingual Content"', '2026-10-21T11:45:00Z', 'F.C. Kohli Auditorium, (KReSIT) Building, Department of Computer Science and Engineering, IIT Bombay', '[{"affiliation": "Visiting Scientist, Anusandhan National Research Foundation (ANRF), Government of India; Professor, Computer Science, International Institute of Information Technology (IIIT) Hyderabad; and President of ACM India.", "name": "Ponnurangam Kumaraguru"}]')]
```

- **Run 2 is all UNCHANGED** (40 of 40): 0 new, 0 changed, 0 failed. It discovered the same 40 URLs, re-fetched the
  same 20 detail pages in listing order, and every content hash matched.
- **Times are correct UTC.** The homepage gives the Saral AI lecture as `2026-10-21T11:45:00Z`. The detail page's
  `17:15:00Z` is IST mislabelled as UTC; the adapter reads it as IST, giving the same `11:45:00Z` (D19). The two
  sources agree on all 20 parsed items, so no record changed between the runs.
- **People are scarce on this surface right now.** Only 1 of the 20 parsed events labels a speaker:
  `Prof. Ponnurangam Kumaraguru`, with his whole semicolon-separated affiliation kept as one person (D20). The
  homepage block lists the next 40 events by date, and in October 2026 these are mostly observances. By
  `event_type`, they are 11 Academic Event, 5 Conference/Symposium, 3 Social/Cultural and 1 Seminar/Talk.
  `pct_with_speaker = 5.0` is therefore true coverage, not a parser failure. The 18 real fixture pages (more
  lectures, sampled from the calendar) give 12/18.
  This is the main open question about the target's yield for Sections 5–7 (OPEN_QUESTIONS.md Q2).
- **20 records are listing-only** (`not_attempted`): the 21st–40th events beyond the 20-detail cap, stored with title,
  date and timezone from the homepage block. The cap is the brief's live ceiling. A later run that finds them inside
  the cap will report them `changed` once, when their detail content is added (shown offline in
  `demo_offline.md`, run 3).
