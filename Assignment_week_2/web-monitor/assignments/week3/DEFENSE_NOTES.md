# Week 3 defense notes: the 12 Definition-of-Done items

These are the official items from [`WEEK3_SPEC.md`](WEEK3_SPEC.md), "Week 3 Definition of Done" (restructured in
repair R7). Each has a short answer and the file or test that proves it. Paths are relative to
`Assignment_week_2/web-monitor/`.

## 1. How to choose a high-yield central public surface

Compare candidates on evidence, not impressions. I recorded three IITB surfaces with 28 polite requests, saved every
response, and computed every number offline.
- **The institute events calendar won.** One response holds 643 entries; about 6–10 new events a month; several
  departments.
- **News came second.** Its items are reports, not events.
- **The Dean ACR events page came last, for technical reasons.** It lists 4 items, its feed has no events, and its
  sitemap's 500 lastmods are identical.

Repair R1 pointed discovery at the calendar's lecture-type entries. The live yield went from 1 to 16 named speakers
per 20 pages.

Proof: `assignments/week3/00_candidates/iit_bombay_aggregators.md`, `count_samples.py`,
`10_aggregator/live_runs.md` (headline table), DECISIONS D1 and D33.

## 2. How RSS/Atom, sitemaps and HTML listings differ as discovery mechanisms

- **A feed** gives link, title, a publishing timestamp and an id: the publisher's summary.
- **A sitemap** gives URLs and an optional lastmod, often for the whole site. Here all 500 lastmods are identical,
  so lastmod cannot be trusted.
- **An HTML listing** shows what a reader sees, including the event's own date. On IITB that listing is JSON inside
  the page, decoded by an adapter hook.

All four paths produce the same `DiscoveryRecord`, so the downstream pipeline cannot tell which one found a URL.

Proof: `01_discovery/findings.md`, `src/discovery/{feed,sitemap,html,discover}.py`,
`tests/test_discovery_record.py::test_same_item_same_url_across_methods`, `tests/test_calendar_discovery.py`.

## 3. How to prevent a central crawler from expanding into an uncontrolled domain crawl

`src/scope.py::scope_decision` applies to every candidate before anything is fetched:
- exact hosts (`notiitb.ac.in` fails);
- path prefixes with a trailing slash (`/events/` ≠ `/events-archive/`);
- excluded login and search paths;
- excluded calendar and filter query keys (`?month=`, `?view=`, `?page=`).

Caps from config: 1 listing page, 40 in scope, 20 detail fetches. The aggregator never follows next-links, and the
router never fetches PDFs or external links. Live, 122 listed URLs gave exactly 20 detail fetches per run.

Proof: `02_scope/scope_cases.md`, `tests/test_scope.py`,
`tests/test_aggregator_e2e.py::test_requests_made_by_one_run`, `10_aggregator/live_runs.md`.

## 4. How discovery is separated from detail extraction

Discovery returns candidates: URL, title and source timestamp, never a record. Only `run_aggregator` fetches a
candidate's detail page, parses it with the adapter's `parse_event_detail`, assembles and validates a record. The
same detail parser serves a URL found by HTML, RSS, sitemap or the calendar hook. Parsers take text and never fetch.

Proof: `src/discovery/discover.py`, `src/aggregator.py`, `03_discovery_interface/notes.md`,
`01_discovery/findings.md` (1A checkpoint), `tests/test_week3_architecture.py`.

## 5. How repeated runs distinguish new, changed and unchanged items

The key is the canonical URL.
- **new:** a key not stored yet.
- **changed:** a different sha256 over content fields only. Speakers and organizations are sorted before hashing,
  so a reorder is not a change.
- **unchanged:** the same hash. `fetched_at`, HTTP status, raw text and `detail_*` never mark a change.

The write is an upsert inside one transaction per run. Live run 2 gave 40 unchanged, 0 new, 0 changed.

Proof: `04_incremental/run_state_notes.md`, `tests/test_incremental.py`, `10_aggregator/live_runs.md`.

## 6. Why absence from a listing is not proof of deletion

A capped or paged listing, a scope or cap change, a partial fetch, a layout change or a temporary unpublish all look
exactly like a deletion from the listing side. So `not_seen_this_run` is a query (`last_seen_at` older than this run's
start) and nothing is deleted. A returning item is logged `REDISCOVERED` and counted by its hash. Offline run 3: two
events vanished from the listing, `NOT_SEEN_THIS_RUN 2`, and both rows are still stored.

Proof: `tests/test_incremental.py::test_four_states_and_absent_item_is_kept`,
`test_absent_then_back_is_logged_rediscovered_and_counted_by_hash`, `10_aggregator/demo_offline.md`.

## 7. How speakers and organizations are extracted from explicit source metadata

- Labels come from the adapter (`Speaker:`, `Chair:`, `Organized by:`, …), roles only from a label, and an
  affiliation only when written next to the name.
- The honorific goes into its own field, and `source_text` is kept verbatim.
- IITB event pages have no organizer field, and prose is never parsed, so organizations appear only when the body
  labels them.

Live: 16 speakers in 20 pages. Two name shapes found live (a nickname in brackets; post-nominals without a comma)
were fixed and tested.

Proof: `05_extraction/notes.md`, `src/entities.py`,
`tests/test_entities_extraction.py::test_every_entity_has_source_text_that_appears_verbatim_in_its_fixture`, D34.

## 8. How events/items link to people and organizations relationally

People and organizations are tables with UNIQUE `normalized_name`. The many-to-many link tables `item_people` and
`item_organizations` are keyed `(item_url, entity_id, role)`, carry `source_text` and the per-event
`affiliation_raw`, and reference `records(item_url)` with `PRAGMA foreign_keys=ON`. A second run adds zero links, and
a foreign-key violation is rejected. The documented queries were run on real fixture data.

Proof: `06_entities/entity_schema.md`, `tests/test_entity_storage.py`.

## 9. Why uncertain names should not be aggressively merged

A false merge silently gives one person another's events and affiliations, and every later query inherits the error.
A false split is visible and fixable.
- Identity is exact `name_key` equality only: NFKC, casefold, decorative punctuation and honorific removed.
- `A. Rao` / `Ananya Rao` and `Centre` / `Center` go to `entity_alias_candidates` (`needs_review`) and are never
  merged.
- A bare acronym matches only on the page that defines it.

Proof: `07_resolution/entity_matching_policy.md` (16 pairs), `tests/test_matching_policy.py`.

## 10. How mixed content is classified structurally

`src/router.py` applies, in this order: external host → PDF (Content-Type beats the file extension) → the card's
category label → URL pattern from config → unknown. It runs before fetching, so PDFs and external links are never
detail-fetched as HTML, and again with the response's Content-Type. Every candidate is kept in `discovered_items`
with its class and reason. Unknown items are never dropped or forced into `records`.

Proof: `08_router/router_rules.md`, `tests/test_router.py`, `tests/test_aggregator_e2e.py::test_routing_and_detail_fetches`.

## 11. How run metrics distinguish "no new data" from "collection failure"

Every run prints the summary block and a `RUN_SUMMARY` log line, and stores the metrics on its `runs` row, failed
runs included:

| Signature | Meaning |
|---|---|
| discovered N, parsed ~N, new 0 | Nothing new |
| parsed 0 with FAILED = details attempted | Detail parser broke |
| discovered 0 with HTTP 200 | Listing broke |
| HTTP non-200 | Fetch failed |

Warnings catch the quiet cases:
- `COVERAGE_DROP` (≥ 30 points) when a field silently empties;
- `DISCOVER_EMPTY` and `DISCOVERY_DROP` (to half or less) when a second method hides a broken listing.

Proof: `09_metrics/failure_signatures.md` (real output), `tests/test_metrics.py`.

## 12. How the aggregator uses the same reusable infrastructure created in Week 2

The scheduler picks the pipeline from config (`"pipeline": "aggregator"`) and runs it under the same lock, run rows,
retry/interval logic and `RUN_START` / `RUN_END` as Week 2. The aggregator reuses the Week 2 `Fetcher` (robots.txt,
delay, timeout, TLS, FETCH logs), `storage.py`, `schema.py` and `logging_config.py`.

The site-specific part is one short adapter (selectors, labels, the calendar hook, the detail parser) plus a config
entry. Every generic-layer change (G1–G10) is listed with its commit and the requirement that needed it. Existing
tests were edited only for the Section 4 rename.

Proof: `src/scheduler.py` (`PIPELINES`), `src/aggregator.py`, `sources/iit_bombay_events.py`,
README "Changes to the generic layer", `tests/test_aggregator_e2e.py::test_adapter_stays_short_and_has_no_generic_code`.
