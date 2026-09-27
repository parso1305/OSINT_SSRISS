# Week 2 audit: what was fixed, where, and what proves it

The audit ([`AUDIT_REPORT.md`](AUDIT_REPORT.md), 2026-09-26) is kept unchanged as evidence of the code before any fix.
Fixes were applied on 2026-09-27, one commit per fix, and the full test suite was run after each one. Problem ids
(C1, M1…M6, m1…m17, case N, X1/X2, §8.3 #N) are the report's own.

| Audit problem | Fixed in | Proof (test or evidence) |
|---|---|---|
| **C1** Week 2 work not under version control; no `.gitignore`; tracked `.pyc`; half-staged rename | `ad51647` pre-audit-fix snapshot (+ `.gitignore`, `.gitattributes` so raw evidence bytes survive checkout) | fresh clone → fresh venv → `pip install -r requirements.txt` → `pytest`: 97 passed, 1 skipped (same as the working copy) |
| **M6** no `requirements.txt` | `ad51647` (pinned from the audit venv); `c37a213` drops `urllib3` (no longer imported), pins `certifi` | the same fresh-clone run; step 10 repeats it on the final tree |
| **M4** TLS verification silently disabled on any SSL error (`fetcher.py:107-110`) | `c37a213` fallback removed; HSS diagnosed (server omits the *GlobalSign RSA OV SSL CA 2018* intermediate); per-source `ca_bundle` = certifi + that intermediate | `tests/test_tls.py` (local HTTPS: self-signed fails loudly with `error_type=SSLError` and no request reaches the server; succeeds only via `ca_bundle`; leaf-without-intermediate reproduces HSS); `tests/test_architecture.py::test_tls_verification_is_never_disabled`; live: `LIVE_TESTS=1 pytest tests/test_enrichment.py::test_live_mistyped_url_is_a_real_404` passed 2026-09-27 |
| **M3 / case 8** HTTP 200 with 0 items recorded `success`, exit code 0 | `261ac13` → `FAILURE … error_type=EmptyListingError`, run `failed`, exit 1, nothing stored (`allow_empty_listing` to opt out) | `tests/test_audit_regressions.py::test_case08_listing_structure_change_fails_run_and_leaves_data_untouched`, `::test_case08_allow_empty_listing_accepts_an_empty_page_with_a_warning`; `tests/test_runner.py::test_zero_items_fails_the_run_unless_allowed`; audit `test_08[card_class_renamed]` now passes |
| **M1 / case 9** changed detail date format silently erased `ends_at` (10/10 rows, `changed=10`, no warning) | `748c9ea` parse failure = unknown: `PARSE_WARNING field=… raw="…"`, listing fallback, stored value kept | `tests/test_audit_regressions.py::test_case09_unparseable_detail_dates_never_erase_stored_values` (0 erased, `changed=0`, 20 warnings), `::test_case09_fresh_db_keeps_listing_start_and_warns`, `::test_case09_listing_and_detail_dates_unparseable_rejects_new_and_keeps_stored`; audit `test_09[*]` (3) now pass |
| **M2 / X1** failed run not retried for a full interval (24 h) | `707a0a1` retry after `retry_minutes` (60), doubling, capped at the interval; `SCHEDULE … next_due_reason=retry_after_failure` | `tests/test_scheduler.py::test_failed_run_is_retried_after_retry_minutes_then_success_uses_the_interval`, `::test_repeated_failures_back_off`, `::test_wait_after_failures_backs_off_and_is_capped_at_the_interval`, `::test_retry_still_respects_the_overlap_lock`; `tests/test_audit_regressions.py::test_caseX1_failed_run_is_retried_on_the_next_hourly_trigger`. Audit `test_x1` is marked *superseded*: it fires the "next trigger" 0 min after the failure |
| **m4 / §8.3 #1** canonical form (slash stripped) used as the fetch URL; CMI `/activities/` only worked via a 301 | `6714df9` path kept as given | `tests/test_audit_regressions.py::test_listing_url_with_trailing_slash_is_fetched_as_given_and_redirects_are_logged`; `tests/test_url_resolution.py::test_path_is_kept_as_given`, `::test_storage_ee_slash_and_no_slash_are_distinct_keys`; after-fix CMI run fetches `/activities/` directly (`logs/after_fixes/generalization_run.log`) |
| **m10 / §8.3 #7** `FETCH` logged the requested URL, not where a redirect ended | `6714df9` `FETCH … final_url=… redirect_status=301` | same redirect test as above |
| **case 11** (6 href forms → 1 row) | `6714df9` changes it **by design**: 4 forms still → 1 key; `…/islands…/` and `…/events//…/` now distinct (they only matched by rewriting the path; both were hand-made, no real HSS href has either) | `tests/test_audit_regressions.py::test_case11_href_forms_that_differ_only_in_host_query_or_fragment_are_one_item`; audit `test_11` marked *superseded* |
| **§8.3 #2** every item needs its own GET-able URL | `1f9eb46` generic `src.urls.synthetic_item_url` (listing + `#/item/<hash>` of a site id, else title + date); rule documented in `src/schema.py` and `assignments/06_schema/schema_review.md` §(h); CMI sandbox adapter uses it instead of its inline key | `tests/test_url_resolution.py::test_synthetic_item_url_is_stable_canonical_and_page_independent`; `tests/test_generic_source.py::test_source_without_item_links_and_with_a_date_only_event` |
| **m5 / §8.3 #3** no date-only `starts_at` | `1f9eb46` convention: `starts_at` may be `YYYY-MM-DD` (local date in `timezone`); validator rules | `tests/test_audit_regressions.py::test_date_only_events_validate_with_their_rules`; `tests/test_generic_source.py::test_source_without_item_links_and_with_a_date_only_event`. CMI re-run: the 8 rejected items were not date-only (times on following lines / other layouts); all 8 now validate, and 1 other item (`absref=66`, no title in the listing) is correctly rejected: **134 stored / 1 rejected**, was 127 / 8 (`logs/after_fixes/generalization_run.log`) |
| **m14, m16 / §9** documentation drift (failure_examples format, recon selectors, pagination fallbacks, adapter-notes errors, stale schema review, README run history) | `be26dc4` | `assignments/01_logging/failure_examples.md` is regenerated by `scripts/failure_examples_run.py` from real runs; recon selectors checked against `fixtures/iit_bombay_hss/recon_events_2026-09-27.html` (one live fetch) |
| S3.1 recon future-dated item "unverified" | `be26dc4` | verified on live `/events` 2026-09-26 20:12Z: `11th Nov 2026`, `JALVIHAR CONFERENCE HALL` (`recon_events_2026-09-27.html:372-395`) |
| *found during the fixes*: an invalid `listing_url` (e.g. `http://`) was never fetched yet failed with a misleading "HTTP 200 … parsed 0 items" message | config validation: `SourceConfig` rejects a `listing_url` that is not an absolute http(s) URL, naming the `source_id` | `tests/test_runner.py::test_config_rejects_listing_url_that_is_not_absolute_http`; `assignments/01_logging/failure_examples.md` Case 1 |
| **m8** `with sqlite3.connect()` never closes: 157 `ResourceWarning`s in the audit (257 in the grown suite) | `storage._connect()`: commit/rollback **and** close on every call; tests close their own connections | `pytest -W always::ResourceWarning`: main suite 257 → **0**, audit suite → **0** |
| **A8.3** optional live demo DEFERRED (HSS unreachable during the audit) | live demo 2026-09-27 (HSS reachable again) | `assignments/08_schedule/live_demo.log`: run 1 `new=20`, run 2 `new=0 existing=20 changed=0`, both `success`; runs table in `assignments/08_schedule/schedule_notes.md` → **PASS** |
| ME fake-UTC `<time>` (§8.2) and talks.cam.ac.uk robots.txt (§8.1) | `be26dc4` documented as findings (adapter-level; no generic change is correct) | `assignments/07_template/iit_bombay_adapter_notes.md` §6 |

## Still open (not in the fix list)

These audit tests are marked `xfail(strict=True)` with the reason. If one starts passing, pytest reports `XPASS` as a failure,
so a fix cannot go unnoticed.

| Audit problem | Audit test |
|---|---|
| **M5 / X2** `item_url` alone is the `records` key: two sources listing one URL overwrite each other (`changed=10` every cycle) | `test_extra_edges.py::test_x2_two_sources_listing_the_same_item` |
| **m1 / case 17** a lock with a non-`Z` `started_at` raises out of `run_once` (whole cycle aborts) | `test_scheduler_behaviour.py::test_17_stale_lock[unparseable_started_at]` |
| **m2 / case 12** failed detail fetch + listing value differing from the stored detail value → overwritten, `changed=1` | `test_pipeline_behaviour.py::test_12_failed_refetch_is_not_a_change[listing_disagrees_with_detail]` |
| **m11 / case 8** a renamed detail field silently yields `None` (no warning) | `test_pipeline_behaviour.py::test_08_html_structure_changed[detail_speaker_field_renamed]` |
| m3, m6, m7, m9, m12, m13, m15, m17 | not covered by a failing test; see the report §10 |

## Running the audit

From the project root (`Assignment_week_2/web-monitor`):

```
python -m pytest assignments/week2_audit/tests -v              # 42 passed, 6 xfailed (2026-09-27)
python assignments/week2_audit/scripts/run_generalization.py   # ME + CMI sandbox on fixtures, real scheduler
```

Re-runs write their evidence to `logs/after_fixes/` (override with `AUDIT_EVIDENCE_DIR`). `logs/evidence/` and the
other files directly under `logs/` are the original audit output and are never overwritten. The sandbox config names
the adapters `assignments.week2_audit.sources.*`; the ME and CMI adapters are sandbox code, not registered sources.
