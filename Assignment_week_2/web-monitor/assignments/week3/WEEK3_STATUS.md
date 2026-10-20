# Week 3 status

Branch `week3-auto`, **pushed to GitHub** (`origin/week3-auto`); not merged into `master`. First unattended run:
2026-10-17. Repair pass R1–R8: 2026-10-20 (the commits are listed below). The official spec is
[`WEEK3_SPEC.md`](WEEK3_SPEC.md); the spec index is [`README.md`](README.md). Status values are **Done**,
**Partial** and **Needs Parth**.

**Test totals,** with outbound HTTP blocked (`scripts/offline_pytest.py`):

| Suite | Before Week 3 | After the first run (2026-10-17) | **After the repair pass (2026-10-20)** |
|---|---|---|---|
| Main (`tests/`) | 136 passed, 1 skipped | 341 passed, 1 skipped, 1 xfailed | **361 passed, 1 skipped** |
| Audit (`assignments/week2_audit/tests`) | 43 passed, 3 xfailed | 43 passed, 3 xfailed | **43 passed, 3 xfailed** |

- The skip is the `LIVE_TESTS`-gated HSS test.
- The D2 xfail is gone: R2 replaced it with a sorted-form test.
- The 3 audit xfails are the Week 2 known limitations M5, m11 and m2.

**Live requests:**
- **First run:** 61 of 80.
- **Repair pass:** 44 of 60 (two live runs on the `/events` calendar).

Ledger: [`live_requests.md`](live_requests.md).

## Repair pass R1–R8 (2026-10-20)

| Item | Result | Commit(s) | Evidence |
|---|---|---|---|
| R1 · discovery yield (Q2) | **Done.** Discovery reads the `/events` calendar JSON through the adapter hook `calendar_entries`, filtered by config to lecture-type titles, upcoming first, then the most recent past. Generic change G10. D11 superseded by D33. Offline calendar fixture plus 6 tests. Live, two runs on a fresh DB: 122 lecture-type URLs listed, 40 in scope, 20 parsed; run 1 has 40 new, run 2 has 40 unchanged; **16 speakers, `pct_with_speaker` 80.0** (was 5.0); 0 duplicates. Two name-parsing defects found live were fixed (D34). Evidence added that IITB event pages have no organizer field. | `ff5b225` (generic), `b1b6262`, `40187ef` | `10_aggregator/live_runs.md`, `tests/test_calendar_discovery.py`, `05_extraction/notes.md` |
| R2 · query order (Q1) | **Done.** Sorted order kept; the xfail was replaced by `test_remaining_params_are_sorted_into_one_canonical_order`; D2 updated; Q1 closed. | `ed7ea3b` | `tests/test_week3_canonical.py` |
| R3 · enable the source (Q3) | **Done.** `iit_bombay_events` has `"enabled": true` (daily via `--once`, 22 requests a run). | `a2b942b` | `config/sources.json`, D35 |
| R4 · official review questions (Q4) | **Done.** `self_review.md` and `review_template.md` use the 10 questions in WEEK3_SPEC.md Section 11; the template has the comments table and the "at least 3 substantive comments" rule. | `1a38c6b` | `11_review/` |
| R5 · repo front page | **Done.** Week 3 row and a "Headline results (Week 3)" table with evidence links in the root README. | `83cf3a0` | root `README.md` |
| R6 · spec index | **Done.** Every spec path and the 16 Section 12 deliverables mapped to files. | `dace5bf` | [`README.md`](README.md) (this folder) |
| R7 · defense notes and status | **Done.** DEFENSE_NOTES.md is organized around the 12 official DoD items; this file is updated. | `week3: R7 …` | [`DEFENSE_NOTES.md`](DEFENSE_NOTES.md) |
| R8 · discovery-drop warning | **Done.** `WARNING DISCOVERY_DROP` when items_discovered falls to ≤ 50 % of the previous successful run (which found ≥ 10). | `4ed8de7` | `09_metrics/failure_signatures.md`, `tests/test_metrics.py` |

**Open question from the repair pass:** Q5. Should the summary's ITEMS_DISCOVERED be capped at 40 too? Live it
reports 122 lecture-type URLs, of which 40 are in scope. A one-line `max_entries` option would do it
([`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md)).

## Still needs Parth

1. **Cross-review with Soumyadipta** (TISS aggregator): fill in `11_review/review_template.md` with at least 3
   substantive comments.
2. **Week 2 Assignment 9** (the template swap with a teammate's framework): not started; no template or instructions
   were provided to these runs.
3. **A test run with Wi-Fi actually off.** The runs here blocked HTTP through proxy environment variables
   (`scripts/offline_pytest.py`), not at the network layer.
4. **Merge `week3-auto` into `master`.** The branch is on GitHub. Local `master` is 4 ahead and 1 behind
   `origin/master`, so reconcile that first.
5. Review `DECISIONS.md` (D1–D36) and answer Q5.

## Checklist (first run, updated by the repair pass)

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
| D2 | Param order | Done: sorted, decided in R2 | `tests/test_week3_canonical.py::test_remaining_params_are_sorted_into_one_canonical_order` |
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
| 10 | Target registered with discovery, scope, router and caps | Done (calendar hook since R1; enabled since R3) | `config/sources.json` (`iit_bombay_events`) |
| 10 | Offline e2e: 2 runs, duplicate checks, changed site; `demo_offline.md` | Done | `10_aggregator/demo_offline.md`, `tests/test_aggregator_e2e.py` |
| 10 | Live: 2 runs back to back via the scheduler, summaries + duplicate checks + adapter unchanged | Done (redone on the calendar in R1, 44 requests) | `10_aggregator/live_runs.md` |
| 11 | `self_review.md` (official 10 questions, canonical URLs in depth) and `review_template.md` (≥ 3 comments) | Done (R4) | `11_review/` |
| 12 | README (architecture, tree, scope, hash fields, matching, discovery record, generic changes, commands, out of scope) | Done | `README.md` |
| 12 | DEFENSE_NOTES.md (12 official DoD items), WEEK3_STATUS.md, spec index README.md | Done (R6, R7) | this folder |
| — | Q5: cap ITEMS_DISCOVERED itself at 40? | Needs Parth | OPEN_QUESTIONS Q5 |
| — | Review DECISIONS.md (D1–D36); Q1–Q4 are closed | Needs Parth | `DECISIONS.md`, `OPEN_QUESTIONS.md` |
| — | Week 2 Assignment 9 template swap | Needs Parth | not done in this run (no instructions or template were provided) |
| — | Cross-review with Soumyadipta (TISS aggregator) | Needs Parth | `11_review/review_template.md` |
| — | A pytest run with Wi-Fi actually off (this run only blocked HTTP via proxy env vars) | Needs Parth | `scripts/offline_pytest.py` |
| — | Merge `week3-auto` into `master` (already on GitHub; local master 4 ahead / 1 behind origin/master) | Needs Parth | `git log 3471522..week3-auto` |

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
d64efcb week3: 12 integration (README, defense notes, status)
ce6e1c3 docs: add the mentor's official Week 3 spec (WEEK3_SPEC.md)
ff5b225 generic: html discovery can call an adapter listing hook
b1b6262 week3: R1 calendar discovery for iit_bombay_events (lecture-type, upcoming first; offline fixture + tests)
40187ef week3: R1 live runs on the /events calendar + two name-parsing fixes found live
ed7ea3b week3: R2 canonical query order is sorted (xfail replaced by a sorted-form test; Q1 closed)
a2b942b week3: R3 enable iit_bombay_events (Q3 closed)
1a38c6b week3: R4 self-review and review template on the official Section 11 questions (Q4 closed)
4ed8de7 week3: R8 DISCOVERY_DROP warning when items_discovered falls sharply
dace5bf week3: R6 spec index (every WEEK3_SPEC path and the 16 deliverables mapped to files)
83cf3a0 week3: R5 repo front page: Week 3 row and headline results with evidence links
(+ week3: R7 defense notes and status)
```
