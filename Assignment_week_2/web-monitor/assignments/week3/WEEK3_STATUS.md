# Week 3 status

Branch `week3-auto` (not pushed). Unattended run on 2026-10-17. Status values are **Done**, **Partial** and
**Needs Parth**.

**Final test totals,** with outbound HTTP blocked (`scripts/offline_pytest.py`):

| Suite | Before Week 3 | After Week 3 |
|---|---|---|
| Main (`tests/`) | 136 passed, 1 skipped | **341 passed, 1 skipped, 1 xfailed** |
| Audit (`assignments/week2_audit/tests`) | 43 passed, 3 xfailed | **43 passed, 3 xfailed** |

- The skip is the `LIVE_TESTS`-gated HSS test.
- The xfail is the D2 query-order test (Q1).
- The 3 audit xfails are the Week 2 known limitations M5, m11 and m2.

**Live requests:** 61 of 80 (`live_requests.md`).

| # | Item | Status | Evidence |
|---|---|---|---|
| 1A | Formats found and where (RSS/Atom/sitemap/index) | Done | `01_discovery/findings.md` |
| 1A | `feed.py` (RSS + Atom from bytes, UTC Z + raw, URL input rejected) | Done | `src/discovery/feed.py`, `tests/test_discovery_feed_sitemap.py` |
| 1A | `sitemap.py` (defusedxml, namespaces, index children separate, cap 2) | Done | `src/discovery/sitemap.py`, same tests |
| 1A | `inspect_feed.py` / `inspect_sitemap.py`, run once live, output pasted | Done | `01_discovery/`, findings.md (4 requests) |
| 1A | Fixtures (target has no event feed/sitemap: synthetic + real samples), stated plainly | Done | `fixtures/week3/discovery/README.md`, findings.md |
| 1A | lastmod trust with evidence, sitemap = whole-site map, why defusedxml, 1A checkpoint | Done | findings.md |
| 1A | feedparser + defusedxml pinned | Done | `requirements.txt` |
| 1B | `DiscoveryRecord` (6 spec fields + raw; `to_spec_dict`; validation) | Done | `src/discovery/record.py`, `tests/test_discovery_record.py` |
| 1B | `html.py` selector-driven; only item containers; selectors in the adapter | Done | `src/discovery/html.py`, `sources/iit_bombay_events.py::LISTING_SELECTORS` |
| 1B | `test_same_item_same_url_across_methods` | Done | `tests/test_discovery_record.py` |
| D2 | Canonical URLs: fragment, tracking params, case, ports | Done | `tests/test_week3_canonical.py` |
| D2 | Original param order | Partial (xfail: Week 2 tests require sorted order) | DECISIONS D2, OPEN_QUESTIONS Q1 |
| 2 | `scope.py` (`is_allowed_item_url`, `scope_decision`), exact hosts, prefix boundaries, query keys | Done | `src/scope.py` |
| 2 | Target scope config + caps in `config/sources.json` | Done | `iit_bombay_events.scope` |
| 2 | One test per case (13) + `scope_cases.md` with the calendar-explosion rule | Done | `tests/test_scope.py`, `02_scope/scope_cases.md` |
| 3 | `discover_items(source_config, client)`, methods from the registry, dedup on the canonical URL, merge rule documented | Done | `src/discovery/discover.py`, `03_discovery_interface/notes.md` |
| 3 | `test_html_discovery`, `test_feed_discovery`, `test_sitemap_discovery`, `test_scope_filter`, `test_duplicate_discovery_url` | Done | `tests/test_discovery_interface.py` |
| 4 | `existing` → `unchanged` everywhere (incl. `runs.unchanged_count`, log keys); tests edited for the rename only | Done | commit `b68ef39` |
| 4 | Sorted list fields in the hash; `not_seen_this_run` (D6); rediscovered; ON CONFLICT upsert in one transaction; run_id on log lines | Done | `src/storage.py`, `tests/test_incremental.py` |
| 4 | `run_state_notes.md` | Done | `04_incremental/run_state_notes.md` |
| 5 | `entities.py` (dataclasses, splitting, honorifics, source_text); labels in the adapter; roles only from labels | Done | `src/entities.py`, `sources/iit_bombay_events.py::LABELS` |
| 5 | 10–20 fixtures incl. all required cases; controlled live sample (13 requests) | Done | `fixtures/week3/iitb_events/detail/`, `05_extraction/notes.md` |
| 5 | `records.speakers` / `organizations` from the same extraction; source_text verbatim test | Done | `tests/test_entities_extraction.py` |
| 6 | 4 tables, FKs per D4, indexes, `PRAGMA foreign_keys=ON`, no duplicate links | Done | `src/storage.py`, `tests/test_entity_storage.py` |
| 6 | `entity_schema.md` with DDL, D4/D5 trade-offs, 2 queries with real output | Done | `06_entities/entity_schema.md` |
| 7 | `name_key` rules; 10 person + 6 org pairs decided and tested; review table; acronym rule; false-merge sentence | Done | `07_resolution/entity_matching_policy.md`, `tests/test_matching_policy.py` |
| 8 | `router.py` with the documented order; Content-Type beats the extension; classify before fetching | Done | `src/router.py`, `08_router/router_rules.md` |
| 8 | `discovered_items` persistence (unknown kept with reason) | Done | `tests/test_router.py` |
| 8 | ITEM_TYPES widened only where a parser exists | Done (stays `("event",)`, D25) | DECISIONS D25 |
| 9 | Runs table extended (12 columns); summary block + key=value line; failed run still summarised | Done | `src/metrics.py`, `tests/test_metrics.py` |
| 9 | Coverage-drop WARNING (threshold 30 points, documented) | Done | `09_metrics/failure_signatures.md` |
| 9 | CLI `python -m src.metrics --last` | Done | `tests/test_metrics.py::test_cli_prints_the_last_summary` |
| 9 | `failure_signatures.md` with real output from the broken-fixture tests | Done | `09_metrics/failure_signatures.md` |
| 10 | Short target adapter; generic pipeline in `src/`; scheduler picks the aggregator from config | Done | `sources/iit_bombay_events.py`, `src/aggregator.py`, `src/scheduler.py` |
| 10 | Target registered with discovery, scope, router and caps | Done | `config/sources.json` (`iit_bombay_events`, `enabled: false` → Q3) |
| 10 | Offline e2e: 2 runs, duplicate checks, changed site; `demo_offline.md` | Done | `10_aggregator/demo_offline.md`, `tests/test_aggregator_e2e.py` |
| 10 | Live: 2 runs back to back via the scheduler, summaries + duplicate checks + adapter unchanged | Done (44 requests) | `10_aggregator/live_runs.md` |
| 11 | `self_review.md` (10 questions, canonical URLs in depth) and `review_template.md` | Done (questions derived from the requirements → Q4) | `11_review/` |
| 12 | README (architecture, tree, scope, hash fields, matching, discovery record, generic changes, commands, out of scope) | Done | `README.md` |
| 12 | DEFENSE_NOTES.md, WEEK3_STATUS.md | Done | this folder |
| — | Confirm the D1 target (and Q2: the people yield of the homepage block) | Needs Parth | DECISIONS D1, D11; OPEN_QUESTIONS Q2, Q3 |
| — | Review DECISIONS.md (D1–D30) and OPEN_QUESTIONS.md (Q1–Q4) | Needs Parth | `DECISIONS.md`, `OPEN_QUESTIONS.md` |
| — | Week 2 Assignment 9 template swap | Needs Parth | not done in this run (no instructions or template were provided) |
| — | Cross-review with Soumyadipta (TISS aggregator) | Needs Parth | `11_review/review_template.md` |
| — | A pytest run with Wi-Fi actually off (this run only blocked HTTP via proxy env vars) | Needs Parth | `scripts/offline_pytest.py` |
| — | Merge `week3-auto` and push | Needs Parth | `git log 3471522..week3-auto` |

## Commits on `week3-auto`

```
0b185af week3: 1A feed and sitemap inspectors
5ae11e9 week3: 1B unified discovery record
6528057 generic: config accepts Week 3 aggregator keys
ac95879 week3: 2 scope filter
8fe8ed0 week3: 3 discovery interface
b68ef39 generic: record states new/changed/unchanged/not_seen_this_run
e6afaad week3: 4 incremental collection
97e5a67 week3: 5 entity extraction
a01c7d6 generic: entity tables and PRAGMA foreign_keys=ON
8e56933 week3: 6 entity storage
d1bbdb0 generic: entity_alias_candidates review table
6504fb5 week3: 7 entity matching policy
a414ee4 generic: discovered_items table
d0ed193 week3: 8 content router
f3fb696 generic: run metrics columns on the runs table
9fa9870 generic: scheduler dispatches the aggregator pipeline from config
56a27b1 week3: 9 run metrics
2f6bdbf week3: 10 central aggregator
aa76a3b week3: 11 cross-review prep
(+ week3: 12 integration)
```
