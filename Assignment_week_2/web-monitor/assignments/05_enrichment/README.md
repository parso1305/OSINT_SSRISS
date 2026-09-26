# Assignment 5: detail enrichment evidence

| File | What |
|---|---|
| `enrichment_run.log` | live run, 2026-09-26 05:53 UTC: 10 detail pages fetched and merged |
| `checkpoint_404_run.log` | Checkpoint 5: live run with one mistyped item URL, a real HTTP 404 from the server |
| `merged_records.json`, `checkpoint_404_merged.json` | the merged records of those two runs |

The merge rule is documented in `src/enrich.py` (`merge_listing_and_detail`); the test is `tests/test_enrichment.py`.

**Read the two logs as historical evidence, not as the current format** (Week 2 audit, §9). They were produced by
the pre-Assignment 7 code: no `logger=` field, `source=` instead of `source_id=`, a `STORE_ENRICHMENT` event and
`error_type=HTTPError`. They also show the old Fetcher's warning `SSL verification failed … Retrying with
verify=False` on every HSS request, i.e. those runs did **not** verify the server's certificate. That fallback has
been removed. HSS omits an intermediate certificate, and the source now uses a `ca_bundle` that adds it, with
verification always on (README, TLS section). For current log lines see `assignments/01_logging/failure_examples.md`,
which is regenerated from real runs of the current code.
