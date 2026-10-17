# Section 10: central aggregator

| File | What |
|---|---|
| [`demo_offline.md`](demo_offline.md) | Offline end-to-end. Two scheduler runs on a fresh DB, with duplicate checks on records and link tables; then the changed site, showing NEW, CHANGED and NOT_SEEN_THIS_RUN; then the metrics CLI. |
| [`live_runs.md`](live_runs.md) | Two back-to-back live scheduler runs against www.iitb.ac.in, with summaries, duplicate checks and adapter hashes. |
| `inspect_db.py` | Duplicate checks and an inventory of an aggregator DB (`python -m assignments.week3.10_aggregator.inspect_db --db …`). |

## Pipeline (`src/aggregator.py::run_aggregator`, chosen by the scheduler from `"pipeline": "aggregator"`)

```
config/sources.json entry
 -> discovery (src/discovery/discover.py; methods + URLs from the entry; client = src.fetcher.Fetcher)
 -> scope (src/scope.py) -> dedup on the canonical URL (resolve_item_url)
 -> router before fetching (src/router.py: PDFs and external links never detail-fetched as HTML)
 -> capped detail fetch (min(scope.max_detail_items, detail_limit) = 20, listing order)
 -> router again with the response Content-Type
 -> adapter.parse_event_detail -> assemble_record + validate_record (src/schema.py)
 -> entity mentions (src/entities.py) -> mention_rows (name_key)
 -> ONE transaction: records (upsert) + item_people / item_organizations + entity_alias_candidates + discovered_items
 -> not_seen_this_run -> run metrics (src/metrics.py: block, RUN_SUMMARY line, runs-table columns, COVERAGE_DROP)
```

It reuses the Week 2 pieces:
- the HTTP client (robots.txt, delay, timeout, TLS, FETCH logs);
- `src/storage.py`;
- `src/logging_config.py` helpers;
- `src/schema.py`;
- the scheduler's lock, run rows, retry/interval logic and `RUN_START` / `RUN_END`.

There is no duplicated DB code: every SQL statement is in `src/storage.py`.

## The adapter stays short

`sources/iit_bombay_events.py` holds:
- `LISTING_SELECTORS`
- `LABELS` (the label patterns)
- `TIMEZONE` and `UTC_OFFSET`
- `_ist_to_utc`
- `parse_event_detail(html, item_url) -> {fields, people, orgs, parse_warnings}`

It contains no fetching, storage, logging setup, scope, routing or dedup.
`tests/test_aggregator_e2e.py::test_adapter_stays_short_and_has_no_generic_code` checks it. The same adapter
serves the live source (`iit_bombay_events`) and the offline one (`local_aggregator_fixture`). Only the config
differs: hosts, URLs and the discovery methods (html, or html + rss).

## Registered sources (`config/sources.json`)

- `iit_bombay_events`: live; `pipeline: aggregator`, `discovery: "html"` (the homepage events block), the scope block
  (Section 2), the router block (Section 8), `max_discovered_items 40`, `max_detail_items 20`,
  `request_delay_s 3.0`. `enabled: false` until Parth confirms the target (OPEN_QUESTIONS.md Q3).
- `local_aggregator_fixture`: the same adapter, `discovery: ["html", "rss"]`, served by
  `scripts/aggregator_fixture_site.py` on `127.0.0.1:8766`.
