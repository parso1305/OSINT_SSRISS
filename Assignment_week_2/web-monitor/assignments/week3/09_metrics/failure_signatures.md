# Section 9: run metrics and failure signatures

Code:
- `src/metrics.py`: `build_summary`, `format_block`, `format_log_line`, `coverage_warnings`, `emit`, and the CLI.
- `src/aggregator.py` builds the summary at the end of every run, failed or not.
- The `runs` table gains the metric columns (generic change G8).
- `src/scheduler.py` stores them on the run row (G9).

Tests: `tests/test_metrics.py`, run against healthy and deliberately broken fixtures through the real scheduler.

## The summary

It is printed as a block, one value per line, in the brief's order, with `STATUS` added as line 2:

```
SOURCE / STATUS / PAGES_FETCHED / ITEMS_DISCOVERED / ITEMS_PARSED / NEW / CHANGED / UNCHANGED /
NOT_SEEN_THIS_RUN / FAILED / PEOPLE_EXTRACTED / ORGANIZATIONS_EXTRACTED
```

The same values go to one Week 2 style log line:
`RUN_SUMMARY run_id=… source=… status=… http_status=… pages_fetched=… items_discovered=… items_parsed=… new=…
changed=… unchanged=… not_seen_this_run=… failed=… parse_failures=… detail_failures=… people_extracted=…
organizations_extracted=… pct_with_date=… pct_with_speaker=… pct_with_org=… error="…"`.

They are also stored on the run's own `runs` row (`http_status`, `pages_fetched`, `items_discovered`,
`items_parsed`, `not_seen_count`, `parse_failures`, `detail_failures`, `people_extracted`,
`organizations_extracted`, `pct_with_date`, `pct_with_speaker`, `pct_with_org`, plus the existing `new_count`,
`changed_count`, `unchanged_count`, `failed_count`).

**A failed run still writes its summary**, with `status=failed`. The aggregator raises `AggregatorRunError`
carrying the summary, and the scheduler stores it on the failed run row
(`test_failed_run_still_writes_its_summary_to_the_runs_row`).

| Metric | Definition |
|---|---|
| `http_status` | Status of the **first** discovery page (the listing), even when it failed |
| `pages_fetched` | Discovery pages fetched successfully (listing pages, feeds, sitemaps) |
| `items_discovered` | Unique canonical URLs found, in and out of scope (`discovered_items` rows) |
| `items_parsed` | Detail pages fetched **and parsed** into a valid record this run |
| `FAILED` | `parse_failures` (page fetched, parser raised) + `detail_failures` (detail fetch failed) + records that failed validation |
| `pct_with_date / _speaker / _org` | Share of the `items_parsed` records with `event_start` / speakers / organizations; `none` when nothing was parsed |

`CLI: python -m src.metrics --last --db <path> [--source <name>]` prints the last finished run's summary
(`test_cli_prints_the_last_summary`).

## Coverage-drop warning (threshold chosen: 30 percentage points)

A coverage percentage that falls by **30 or more percentage points** against the **previous successful run of the
same source** is logged as `WARNING COVERAGE_DROP`, even when the counts look normal. Only runs that parsed at least
one item are compared.

**Why 30 points.**
- Real coverage moves a little from run to run as the listing rotates: the 18 real pages have a labelled speaker on
  12/18 (67 %).
- A renamed label or field moves it to near zero in one step.
- 30 points is far above the run-to-run noise of a 20-item sample (one item = 5 points) and far below the
  collapse a broken field causes.

Example: with-speaker 65 % → 5 % fires; 80 % → 51 % does not
(`test_coverage_threshold`).

## Signatures

| Signature | What it means | Scenario below |
|---|---|---|
| discovered N / parsed ~N / **new 0**, unchanged ~N, failed 0 | **Nothing new.** Healthy. | 2 |
| discovered N / **parsed 0** / failed = details attempted (`parse_failures`) | **The detail parser broke** (or the layout changed). Listing data is still stored, carry-forward keeps the stored detail values, and every page logs `DETAIL_FAILURE`. | 4 |
| **discovered 0 with HTTP 200**, status failed | **The listing selector broke, or the page really is empty.** The run fails (`EmptyListingError`, as in Week 2) and nothing is written. `DISCOVER_EMPTY` names the page. `allow_empty_listing: true` would accept a really empty page. | 5 |
| **HTTP non-200** (or none), discovered 0, status failed | **The fetch failed.** `DISCOVER_FAILURE status=503`, then `FAILURE stage=fetch`. | 7 |
| counts normal, but `COVERAGE_DROP` | **A field silently emptied.** Here a renamed `Speaker:` label means speakers vanish while pages still parse. Shows as `changed` too. | 3 |
| a 2nd discovery method masks a broken listing | The feed still finds items, so the totals look plausible, but `DISCOVER_EMPTY method=html … status=200 found=0` is logged for the broken page. | 6 |

## Real output from the scenario runs

Produced by `venv\Scripts\python -m assignments.week3.09_metrics.failure_signatures_run` (offline, against
`scripts/aggregator_fixture_site.py`; run 2026-10-17). Ports are shown as `PORT` and the per-test logger name as
`web_monitor`. The same scenarios are asserted in `tests/test_metrics.py`.

```
===== 1. healthy run 1 (first run: everything new)
2026-10-17 06:40:38 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=25
2026-10-17 06:40:38 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:PORT/events.rss status=200 found=3
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
2026-10-17 06:40:39 [INFO] logger=web_monitor RUN_SUMMARY run_id=ea3463749eef4f6096409966bed01ac0 source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=25 items_parsed=20 new=22 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=19 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=65.0 pct_with_org=5.0 error=""
2026-10-17 06:40:39 [INFO] logger=web_monitor RUN_END run_id=ea3463749eef4f6096409966bed01ac0 source=local_aggregator_fixture status=success duration_ms=1192 new=22 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error=""

===== 2. healthy run 2 (nothing new)
2026-10-17 06:40:40 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=25
2026-10-17 06:40:40 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:PORT/events.rss status=200 found=3
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
2026-10-17 06:40:40 [INFO] logger=web_monitor RUN_SUMMARY run_id=b447faf94efc4f9bb93185b49817f9ba source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=25 items_parsed=20 new=0 changed=0 unchanged=22 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=19 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=65.0 pct_with_org=5.0 error=""
2026-10-17 06:40:40 [INFO] logger=web_monitor RUN_END run_id=b447faf94efc4f9bb93185b49817f9ba source=local_aggregator_fixture status=success duration_ms=1149 new=0 unchanged=22 changed=0 not_seen_this_run=0 failed=0 error=""

===== 3. detail labels renamed: 'Speaker:' -> 'Presenter:' (pages still parse)
2026-10-17 06:40:41 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=25
2026-10-17 06:40:41 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:PORT/events.rss status=200 found=3
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 25
ITEMS_PARSED: 20
NEW: 0
CHANGED: 12
UNCHANGED: 10
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 6
ORGANIZATIONS_EXTRACTED: 3
2026-10-17 06:40:42 [INFO] logger=web_monitor RUN_SUMMARY run_id=1fddab70bc1e4f1e867fb7929c9136d6 source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=25 items_parsed=20 new=0 changed=12 unchanged=10 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=6 organizations_extracted=3 pct_with_date=100.0 pct_with_speaker=5.0 pct_with_org=5.0 error=""
2026-10-17 06:40:42 [WARNING] logger=web_monitor COVERAGE_DROP source=local_aggregator_fixture run_id=1fddab70bc1e4f1e867fb7929c9136d6 metric=pct_with_speaker previous=65.0 now=5.0 threshold_points=30 previous_run_id=b447faf94efc4f9bb93185b49817f9ba
2026-10-17 06:40:42 [INFO] logger=web_monitor RUN_END run_id=1fddab70bc1e4f1e867fb7929c9136d6 source=local_aggregator_fixture status=success duration_ms=1143 new=0 unchanged=10 changed=12 not_seen_this_run=0 failed=0 error=""

===== 4. detail parser broke (article class renamed)
(20 DETAIL_FAILURE warning lines, one per detail page, omitted here)
2026-10-17 06:40:43 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=25
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 25
ITEMS_PARSED: 0
NEW: 22
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 20
PEOPLE_EXTRACTED: 0
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:40:44 [INFO] logger=web_monitor RUN_SUMMARY run_id=a9740378e2b6416e85225bb8ef82675d source=local_aggregator_fixture status=success http_status=200 pages_fetched=1 items_discovered=25 items_parsed=0 new=22 changed=0 unchanged=0 not_seen_this_run=0 failed=20 parse_failures=20 detail_failures=0 people_extracted=0 organizations_extracted=0 pct_with_date=none pct_with_speaker=none pct_with_org=none error=""
2026-10-17 06:40:44 [INFO] logger=web_monitor RUN_END run_id=a9740378e2b6416e85225bb8ef82675d source=local_aggregator_fixture status=success duration_ms=1122 new=22 unchanged=0 changed=0 not_seen_this_run=0 failed=20 error=""

===== 5. listing selector broke (events block class renamed), html discovery
2026-10-17 06:40:44 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=0
2026-10-17 06:40:44 [WARNING] logger=web_monitor DISCOVER_EMPTY source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=0 hint="selector miss or really empty page"
2026-10-17 06:40:44 [ERROR] logger=web_monitor FAILURE source_id=local_aggregator_fixture url=http://127.0.0.1:PORT/ stage=parse error_type=EmptyListingError message="discovery returned HTTP 200 but found 0 items: possible silent layout change (set allow_empty_listing to accept this)"
SOURCE: local_aggregator_fixture
STATUS: failed
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 0
ITEMS_PARSED: 0
NEW: 0
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 0
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:40:44 [ERROR] logger=web_monitor RUN_SUMMARY run_id=217dc061c5e442e1bbcd4f409a3b5e4a source=local_aggregator_fixture status=failed http_status=200 pages_fetched=1 items_discovered=0 items_parsed=0 new=0 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=0 organizations_extracted=0 pct_with_date=none pct_with_speaker=none pct_with_org=none error="EmptyListingError: discovery returned HTTP 200 but found 0 items: possible silent layout change (set allow_empty_listing to accept this)"
2026-10-17 06:40:44 [ERROR] logger=web_monitor RUN_END run_id=217dc061c5e442e1bbcd4f409a3b5e4a source=local_aggregator_fixture status=failed duration_ms=159 new=0 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error="AggregatorRunError: discovery returned HTTP 200 but found 0 items: possible silent layout change (set allow_empty_listing to accept this)"

===== 6. same broken listing, html + rss discovery (the feed hides it in the totals)
2026-10-17 06:40:45 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=0
2026-10-17 06:40:45 [WARNING] logger=web_monitor DISCOVER_EMPTY source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=200 found=0 hint="selector miss or really empty page"
2026-10-17 06:40:45 [INFO] logger=web_monitor DISCOVER source_id=local_aggregator_fixture method=rss url=http://127.0.0.1:PORT/events.rss status=200 found=3
SOURCE: local_aggregator_fixture
STATUS: success
PAGES_FETCHED: 2
ITEMS_DISCOVERED: 3
ITEMS_PARSED: 3
NEW: 3
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 2
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:40:45 [INFO] logger=web_monitor RUN_SUMMARY run_id=8ebc47554cdf48cea5b6a3fdfb3fd22c source=local_aggregator_fixture status=success http_status=200 pages_fetched=2 items_discovered=3 items_parsed=3 new=3 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=2 organizations_extracted=0 pct_with_date=100.0 pct_with_speaker=66.7 pct_with_org=0.0 error=""
2026-10-17 06:40:45 [INFO] logger=web_monitor RUN_END run_id=8ebc47554cdf48cea5b6a3fdfb3fd22c source=local_aggregator_fixture status=success duration_ms=358 new=3 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error=""

===== 7. HTTP failure (listing answers 503)
2026-10-17 06:40:46 [WARNING] logger=web_monitor DISCOVER_FAILURE source_id=local_aggregator_fixture method=html url=http://127.0.0.1:PORT/ status=503 error="HTTP 503 Service Unavailable"
2026-10-17 06:40:46 [ERROR] logger=web_monitor FAILURE source_id=local_aggregator_fixture url=http://127.0.0.1:PORT/ stage=fetch error_type=FetchError message="HTTP 503 Service Unavailable for url: http://127.0.0.1:PORT/"
SOURCE: local_aggregator_fixture
STATUS: failed
PAGES_FETCHED: 0
ITEMS_DISCOVERED: 0
ITEMS_PARSED: 0
NEW: 0
CHANGED: 0
UNCHANGED: 0
NOT_SEEN_THIS_RUN: 0
FAILED: 0
PEOPLE_EXTRACTED: 0
ORGANIZATIONS_EXTRACTED: 0
2026-10-17 06:40:46 [ERROR] logger=web_monitor RUN_SUMMARY run_id=fc4777ed0a184225b7911a081505d883 source=local_aggregator_fixture status=failed http_status=503 pages_fetched=0 items_discovered=0 items_parsed=0 new=0 changed=0 unchanged=0 not_seen_this_run=0 failed=0 parse_failures=0 detail_failures=0 people_extracted=0 organizations_extracted=0 pct_with_date=none pct_with_speaker=none pct_with_org=none error="FetchError: HTTP 503 Service Unavailable for url: http://127.0.0.1:PORT/"
2026-10-17 06:40:46 [ERROR] logger=web_monitor RUN_END run_id=fc4777ed0a184225b7911a081505d883 source=local_aggregator_fixture status=failed duration_ms=48 new=0 unchanged=0 changed=0 not_seen_this_run=0 failed=0 error="AggregatorRunError: every discovery page failed: HTTP 503 Service Unavailable for url: http://127.0.0.1:PORT/"
```
