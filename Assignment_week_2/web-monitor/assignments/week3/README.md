# Week 3: index of the spec's paths and deliverables

The official spec is [`WEEK3_SPEC.md`](WEEK3_SPEC.md). Week 2 already uses `assignments/01_…`–`08_…`, so Week 3 work
lives under `assignments/week3/<NN_name>/` (D3). Reusable code is in `src/`, the target adapter in `sources/`, tests in
`tests/` and fixtures in `fixtures/week3/`. Paths below are relative to `Assignment_week_2/web-monitor/`.

Status and evidence: [`WEEK3_STATUS.md`](WEEK3_STATUS.md). Definition of Done: [`DEFENSE_NOTES.md`](DEFENSE_NOTES.md).
Judgment calls: [`DECISIONS.md`](DECISIONS.md). Questions for Parth: [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md). Run
log: [`PROGRESS.md`](PROGRESS.md). Live requests: [`live_requests.md`](live_requests.md).

## Paths named in the spec → files in this repo

| Spec section | Path in the spec | File(s) in this repo |
|---|---|---|
| 0 · Assignment 0 | `assignments/00_candidates/<institution>_aggregators.md` | [`00_candidates/iit_bombay_aggregators.md`](00_candidates/iit_bombay_aggregators.md) (+ `evidence/`, `recon.py`, `count_samples.py`) |
| 1A | `assignments/01_discovery/inspect_feed.py` | [`01_discovery/inspect_feed.py`](01_discovery/inspect_feed.py) (parser: `src/discovery/feed.py`) |
| 1A | `assignments/01_discovery/inspect_sitemap.py` | [`01_discovery/inspect_sitemap.py`](01_discovery/inspect_sitemap.py) (parser: `src/discovery/sitemap.py`) |
| 1A | `assignments/01_discovery/findings.md` | [`01_discovery/findings.md`](01_discovery/findings.md) |
| 1B | common discovery shape | `src/discovery/record.py::DiscoveryRecord`; produced by `src/discovery/html.py`, `feed.py`, `sitemap.py` and the calendar hook (`sources/iit_bombay_events.py::calendar_entries` via `src/discovery/discover.py::_hook_items`); `tests/test_discovery_record.py` |
| 2 | `is_allowed_item_url(url, source_config)` | `src/scope.py::is_allowed_item_url`, `scope_decision`; `tests/test_scope.py` |
| 2 | `assignments/02_scope/scope_cases.md` | [`02_scope/scope_cases.md`](02_scope/scope_cases.md) |
| 3 | `discover_items(source_config)` | `src/discovery/discover.py::discover_items` (+ [`03_discovery_interface/notes.md`](03_discovery_interface/notes.md)) |
| 3 | `test_html_discovery`, `test_feed_discovery`, `test_sitemap_discovery`, `test_scope_filter`, `test_duplicate_discovery_url` | `tests/test_discovery_interface.py` (all five, by those names) |
| 4 | `assignments/04_incremental/run_state_notes.md` | [`04_incremental/run_state_notes.md`](04_incremental/run_state_notes.md); `tests/test_incremental.py` |
| 5 | 10–20 event records → people / organizations | `src/entities.py`, `sources/iit_bombay_events.py::LABELS`, `parse_event_detail`; fixtures `fixtures/week3/iitb_events/detail/`; [`05_extraction/notes.md`](05_extraction/notes.md); `tests/test_entities_extraction.py` |
| 6 | `assignments/06_entities/entity_schema.md` | [`06_entities/entity_schema.md`](06_entities/entity_schema.md) (+ `build_fixture_db.py`); `src/storage.py` (entity tables); `tests/test_entity_storage.py` |
| 7 | `assignments/07_resolution/entity_matching_policy.md` | [`07_resolution/entity_matching_policy.md`](07_resolution/entity_matching_policy.md); `src/entities.py::name_key`, `person_match`, `org_match`; `tests/test_matching_policy.py` |
| 8 | `classify_discovered_item(discovery_record)` | `src/router.py::classify_discovered_item` (+ `classify_with_reason`); [`08_router/router_rules.md`](08_router/router_rules.md); `tests/test_router.py` |
| 9 | run summary + deliberately broken fixture | `src/metrics.py`; [`09_metrics/failure_signatures.md`](09_metrics/failure_signatures.md) (+ `failure_signatures_run.py`); `tests/test_metrics.py` |
| 10 | central aggregator implementation | `src/aggregator.py::run_aggregator`, `sources/iit_bombay_events.py`, `config/sources.json` (`iit_bombay_events`, `local_aggregator_fixture`); [`10_aggregator/README.md`](10_aggregator/README.md), [`demo_offline.md`](10_aggregator/demo_offline.md), [`live_runs.md`](10_aggregator/live_runs.md); `tests/test_aggregator_e2e.py`, `tests/test_calendar_discovery.py` |
| 11 | cross-review (10 questions, ≥ 3 comments) | [`11_review/self_review.md`](11_review/self_review.md), [`11_review/review_template.md`](11_review/review_template.md) |

## Section 12: the 16 required deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Aggregator candidate matrix | [`00_candidates/iit_bombay_aggregators.md`](00_candidates/iit_bombay_aggregators.md) |
| 2 | Chosen central source rationale | Ranking and checkpoint in [`00_candidates/iit_bombay_aggregators.md`](00_candidates/iit_bombay_aggregators.md); D1 and D33 in [`DECISIONS.md`](DECISIONS.md); live yield in [`10_aggregator/live_runs.md`](10_aggregator/live_runs.md) |
| 3 | Feed/sitemap/listing discovery exercise | [`01_discovery/findings.md`](01_discovery/findings.md), `src/discovery/`, `tests/test_discovery_feed_sitemap.py`, `tests/test_discovery_record.py` |
| 4 | URL scope rules | [`02_scope/scope_cases.md`](02_scope/scope_cases.md), `src/scope.py`, README "URL scope rules" |
| 5 | Discovery adapter | `src/discovery/discover.py`, [`03_discovery_interface/notes.md`](03_discovery_interface/notes.md), `tests/test_discovery_interface.py`, `tests/test_calendar_discovery.py` |
| 6 | Incremental run/change detection | [`04_incremental/run_state_notes.md`](04_incremental/run_state_notes.md), `src/storage.py::store_records_detailed`, `count_not_seen`, `tests/test_incremental.py` |
| 7 | Content router | [`08_router/router_rules.md`](08_router/router_rules.md), `src/router.py`, `tests/test_router.py` |
| 8 | Detail parser where relevant | `sources/iit_bombay_events.py::parse_event_detail`, `tests/test_entities_extraction.py` |
| 9 | Person entity extraction | [`05_extraction/notes.md`](05_extraction/notes.md), `src/entities.py::extract_mentions`, `parse_person` |
| 10 | Organization entity extraction | [`05_extraction/notes.md`](05_extraction/notes.md) (incl. the "no organizer field" evidence), `src/entities.py::parse_org`, `resolve_page_acronyms` |
| 11 | Entity relationship schema | [`06_entities/entity_schema.md`](06_entities/entity_schema.md), [`07_resolution/entity_matching_policy.md`](07_resolution/entity_matching_policy.md) |
| 12 | Tests and fixtures | `tests/` (Week 3 files: `test_discovery_*`, `test_listing_hook`, `test_calendar_discovery`, `test_week3_*`, `test_scope`, `test_incremental`, `test_entities_extraction`, `test_entity_storage`, `test_matching_policy`, `test_router`, `test_metrics`, `test_aggregator_e2e`, `test_fetcher_content_type`); `fixtures/week3/` ([`discovery/README.md`](../../fixtures/week3/discovery/README.md)) |
| 13 | Logs | Real log output in [`10_aggregator/demo_offline.md`](10_aggregator/demo_offline.md), [`10_aggregator/live_runs.md`](10_aggregator/live_runs.md), [`09_metrics/failure_signatures.md`](09_metrics/failure_signatures.md); log helpers in `src/logging_config.py` |
| 14 | Run metrics | `src/metrics.py`, metric columns on `runs`, `python -m src.metrics --last`, [`09_metrics/failure_signatures.md`](09_metrics/failure_signatures.md) |
| 15 | README | [`../../README.md`](../../README.md) (architecture, scope rules, hash fields, matching policy, discovery record, changes to the generic layer, commands, out of scope); this index |
| 16 | Peer-review notes | [`11_review/self_review.md`](11_review/self_review.md); [`11_review/review_template.md`](11_review/review_template.md) for the TISS review (Needs Parth) |

## Final architecture (spec Section 12) → code

| Stage | Code |
|---|---|
| SOURCE CONFIG | `config/sources.json` → `src/config.py::SourceConfig` |
| SCHEDULED RUN | `src/scheduler.py` (`PIPELINES[config.pipeline]`) |
| DISCOVERY ADAPTER | `src/discovery/discover.py` (+ `html.py`, `feed.py`, `sitemap.py`, adapter hook) |
| SCOPE CONTROL | `src/scope.py` (applied inside discovery) |
| NEW / CHANGED ITEM CANDIDATES | `DiscoveryCandidate` + `src/router.py` |
| FETCH + PARSE | `src/fetcher.py` + `sources/iit_bombay_events.py::parse_event_detail` |
| NORMALIZE | `src/schema.py::assemble_record`, `validate_record` |
| EXPLICIT ENTITY EXTRACTION | `src/entities.py` |
| ITEM + ENTITY RELATIONSHIPS | `src/storage.py::write_entity_links` (`item_people`, `item_organizations`) |
| DATABASE | `src/storage.py` (one transaction per run) |
| HEALTH / COVERAGE SUMMARY | `src/metrics.py` (block, `RUN_SUMMARY`, runs columns, `COVERAGE_DROP`, `DISCOVERY_DROP`) |
