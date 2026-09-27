# Assignment 5: detail enrichment

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

For a controlled sample of listing items, fetch each item's own detail page, merge its fields into the listing
record, and make sure one failing detail page never breaks the run.

## What I built / found

- [`src/enrich.py`](../../src/enrich.py): `enrich_items` fetches the first `detail_limit` items;
  `merge_listing_and_detail` merges them. Each record carries `detail_fetch_status` (`ok` / `failed` /
  `not_attempted`), the HTTP status and the error.
- A failed detail page keeps the listing record and is logged as `DETAIL_FAILURE` on its own logger; the others
  continue.
- Live run on 2026-09-26: 10 detail pages fetched and merged ([`enrichment_run.log`](enrichment_run.log),
  [`merged_records.json`](merged_records.json)).
- Checkpoint 5: one item URL mistyped on purpose, and the real server answered 404
  ([`checkpoint_404_run.log`](checkpoint_404_run.log)). The same check against the live server passes today
  ([`live_test_404.txt`](../../verification/live_test_404.txt)).

## Key decisions and why

- **Detail wins, except `item_url`.** A non-empty detail value overrides the listing value, but the key always
  comes from the listing's canonical URL. The key must be known before the fetch and must not depend on whether
  the fetch succeeds.
- **The title comes from `<title>`, not `field-event-title`.** The editor-typed field is wrong on at least one live
  page ("Echoes of Translation: Echoes of Translation:…"). Because detail wins, reading it would overwrite a
  correct listing title.
- **A failure is not a change.** A failed or unparseable detail value never erases stored content, and doesn't
  count as `changed` (carry-forward in [`src/storage.py`](../../src/storage.py)).

## Evidence

- [`tests/test_enrichment.py`](../../tests/test_enrichment.py) (merge rule, title rule, isolated 404)
- [`tests/test_runner.py`](../../tests/test_runner.py) (`test_failed_detail_fetch_keeps_listing_record`,
  `test_failed_refetch_of_enriched_item_is_not_a_change_and_keeps_content`)
- Logs and merged records in this folder

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_enrichment.py tests\test_runner.py
$env:LIVE_TESTS = "1"; venv\Scripts\python -m pytest tests\test_enrichment.py::test_live_mistyped_url_is_a_real_404
```

## Status

**PASS.** Known limitations:

- **The two logs in this folder predate the Assignment 7 refactor.** They use the old format (no `logger=`,
  `source=` instead of `source_id=`). They also show the old fetcher retrying with `verify=False` on every HSS
  request, so those runs did not verify the server's certificate. That fallback is removed: verification is always
  on, and HSS uses a [`ca_bundle`](../../README.md#tls-certificates-ca_bundle). Current log lines are in
  [`failure_examples.md`](../01_logging/failure_examples.md).
- When a detail fetch fails and the listing shows a different value than the stored detail value, the listing value
  wins once (audit m2, [FIXES.md](../week2_audit/FIXES.md#known-limitations-assessed-2026-09-27-not-fixed)).
