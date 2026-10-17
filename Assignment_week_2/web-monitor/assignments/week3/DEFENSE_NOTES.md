# Week 3 defense notes

One short answer per Definition-of-Done item, each pointing at the file or test that demonstrates it. The brief for
the unattended run did not list the DoD items verbatim, so they follow the Week 3 sections (OPEN_QUESTIONS.md Q4
covers the same gap for Section 11).

**0. A central aggregator was chosen on evidence, not guesswork.**
Three IITB surfaces were recorded with 28 polite requests, every raw response saved with a manifest. All numbers in
the matrix come from an offline script.
- The events calendar ranked first: 643 entries in one response, about 6–10 new events a month, at least 5 units in
  an 8-page sample.
- The ACR office ranked last, for technical reasons: a 4-item listing, a feed with no events, and a sitemap whose 500
  lastmods are all identical.

The choice is D1, auto-selected and pending review.
Evidence: `00_candidates/iit_bombay_aggregators.md`, `00_candidates/count_samples.py`.

**1A. Feeds and sitemaps are inspected safely and honestly.**
- `src/discovery/feed.py` parses RSS/Atom from bytes only and refuses a URL, so feedparser can never fetch on its own
  (`tests/test_discovery_feed_sitemap.py::test_feed_parser_rejects_url_or_path_input`).
- `src/discovery/sitemap.py` uses defusedxml and refuses a billion-laughs document with a clear error.
- The target has no event feed and no sitemap (live 404). That is stated plainly, and the exercises run on fixtures.
- The only IITB-family sitemap has all 500 lastmods identical, so lastmod is flagged as untrustworthy.

Evidence: `01_discovery/findings.md`.

**1B. One discovery record for every method, with one URL per item.**
`DiscoveryRecord` has exactly the six spec fields plus `source_timestamp_raw`, and validates itself. It rejects a
`discovered_url` that is not already canonical. One event found as a relative href, an RSS link with `utm_*` and a
fragment, and a sitemap `<loc>` gets the identical URL.
Evidence: `tests/test_discovery_record.py::test_same_item_same_url_across_methods`.

**2. The crawl cannot wander or explode.**
`src/scope.py::scope_decision`:
- matches hosts exactly (`notiitb.ac.in` fails);
- keeps prefix boundaries (`/events/` ≠ `/events-archive/`);
- excludes login and search;
- rejects calendar-explosion query keys;
- returns a reason for every decision.

The 13 brief cases are one test each, and the doc table is checked against the tests.
Evidence: `02_scope/scope_cases.md`, `tests/test_scope.py`.

**3. Discovery is config-driven and deduplicates on the canonical URL.**
`discover_items(source_config, client)` reads its methods and URLs from the registry entry. Same-URL hits from
several methods collapse into one candidate, with a documented merge rule: html > rss > atom > sitemap, field by
field.
Evidence: `tests/test_discovery_interface.py` (`test_duplicate_discovery_url`, `test_scope_filter`, …),
`03_discovery_interface/notes.md`.

**4. Re-runs report new / changed / unchanged / not_seen_this_run correctly, and never delete.**
- The hash covers content fields only, with list fields sorted.
- Volatile fields such as `fetched_at`, `http_status` and raw text never mark a change.
- An absent item is kept and counted. A returning item is logged `REDISCOVERED` and counted by its hash.

Evidence: `tests/test_incremental.py`, `04_incremental/run_state_notes.md`.

**5. Entities are only what the page states.**
- Labels come from the adapter, roles only from labels, and an affiliation only when written next to the name.
- Every mention's `source_text` appears verbatim in its fixture (20 fixtures, 18 of them real).
- Unlabelled speaker-like text yields nothing.

Evidence: `tests/test_entities_extraction.py`, `05_extraction/notes.md`.

**6. Entities are stored relationally, without duplicates.**
- Four tables with FKs to `records(item_url)` (D4), enforced by `PRAGMA foreign_keys=ON`.
- Composite keys, so a second run adds zero link rows.
- The per-event affiliation lives on the link (D5).
- The two documented queries were run on the fixture DB.

Evidence: `06_entities/entity_schema.md`, `tests/test_entity_storage.py`.

**7. Matching never merges two people or organizations by guesswork.**
- Identity is `name_key` only. The 16 fixture pairs are each decided in a table and each tested.
- Initial-versus-full-name pairs and Centre/Center go to `entity_alias_candidates`, where they are never merged and a
  reviewer's status survives re-runs.
- A bare acronym is an alias only on the page that defines it.

Evidence: `07_resolution/entity_matching_policy.md`, `tests/test_matching_policy.py`.

**8. Every candidate is routed by structure and kept.**
- Rule order: external host → PDF (Content-Type beats the extension) → card label → URL pattern → unknown.
- PDFs and external links are never detail-fetched as HTML.
- Every candidate is persisted in `discovered_items` with its reasons.
- `ITEM_TYPES` widens only for classes with a parser (D25).

Evidence: `tests/test_router.py`, `08_router/router_rules.md`.

**9. A broken listing, a broken parser and a dead site each look different from "nothing new".**
- The summary block, a `RUN_SUMMARY` log line, and metric columns on the existing `runs` row, including for failed
  runs.
- `COVERAGE_DROP` fires on a ≥ 30-point drop even when counts look normal.
- `DISCOVER_EMPTY` stops a second method from hiding a broken listing.

Evidence: `09_metrics/failure_signatures.md` (real output), `tests/test_metrics.py`.

**10. The aggregator runs end to end on the Week 2 scheduler, offline and live.**
- **Offline:** run 2 is all unchanged; the duplicate checks return 0 rows; the changed site shows NEW 1, CHANGED 2,
  NOT_SEEN 2.
- **Live:** two back-to-back runs give 40 new, then 40 unchanged; 0 duplicates; the adapter hash is identical before,
  between and after the runs; 44 requests.

The adapter is short and holds no generic code.
Evidence: `10_aggregator/demo_offline.md`, `10_aggregator/live_runs.md`, `tests/test_aggregator_e2e.py`.

**11. Ready for cross-review.**
- A self-review answers 10 questions with file, function and test evidence, with extra depth on canonical URLs.
- A blank template for the TISS aggregator is ready.

Evidence: `11_review/self_review.md`, `11_review/review_template.md`.

**12. Integrated and documented, with every generic change justified.**
The README covers:
- the Week 3 architecture and folder tree;
- URL scope rules, content-hash fields, the entity matching policy and the discovery record;
- "Changes to the generic layer" (G1–G9, each with its commit and requirement);
- exact commands;
- "Out of scope".

Existing tests were edited only for the Section 4 rename. Both suites pass with outbound HTTP blocked
(`scripts/offline_pytest.py`).
Evidence: `README.md`, `WEEK3_STATUS.md`, `DECISIONS.md`.
