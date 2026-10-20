# Section 11: self-review of the IIT Bombay events aggregator

The 10 questions are the official ones from `assignments/week3/WEEK3_SPEC.md`, Section 11 (repair R4). Evidence is
given as `file::function`, a test name, or output already pasted in the section folders. Question 5 (canonical item
URLs) is Parth's focus area and gets the most depth.

---

## 1. Is the target genuinely high-yield?

**Yes.**
- **The surface.** It is the institute-wide `/events` calendar: 643 entries, 614 distinct URLs, back to 2014, about
  6–10 new events a month. One response carries the whole list (`00_candidates/iit_bombay_aggregators.md`, C1).
- **What discovery keeps.** Since repair R1 it keeps the 122 lecture-type entries (Institute Lectures, Colloquia,
  Seminar/Talk), upcoming first (D33).
- **Live yield, 2026-10-20.** One listing request gave 40 in-scope events; 20 detail pages gave **16 named speakers**
  (`pct_with_speaker 80.0`) from several institutions and departments (`10_aggregator/live_runs.md`).
- **The comparison.** The homepage block used before R1 gave 1 speaker in 20 pages. The department page from Week 2
  (HSS) covers one department.
- **Weak point.** Organizations: IITB event pages have no organizer field, and 0 of 20 live bodies label one
  (`05_extraction/notes.md`, R1 evidence). The yield is in people, not organizations.

## 2. Is scope clearly bounded?

**Yes.**

The rules (`src/scope.py::scope_decision`):
- exact host `www.iitb.ac.in`, with no subdomains;
- allowed prefixes kept with a trailing slash (`/events/` ≠ `/events-archive/`);
- login and search prefixes excluded;
- calendar, search and pager query keys excluded (`month`, `view`, `page`, `search_api_fulltext`, …).

The caps:
- `max_listing_pages 1`;
- `max_discovered_items 40` (the over-cap URLs are kept as out of scope with their reason);
- `max_detail_items 20`.

Evidence:
- **The 13 brief cases:** one test each in `tests/test_scope.py`, and `test_every_scope_cases_md_row_has_a_test`
  ties them to `02_scope/scope_cases.md`.
- **Live:** 122 URLs listed, 40 in scope, exactly 20 detail fetches per run (`live_runs.md`).
- **Router:** PDFs and external links are never fetched (`tests/test_aggregator_e2e.py::test_requests_made_by_one_run`).

## 3. Could pagination loop indefinitely?

**No.**
- **The aggregator does not paginate.** `discover()` fetches exactly the URLs listed in the config's `discovery_urls`
  (one page for this source) and never follows next-links.
- **Sitemap indexes:** at most 2 children are followed (`DEFAULT_MAX_CHILD_SITEMAPS`,
  `tests/test_discovery_interface.py::test_sitemap_discovery`).
- **Calendar navigation:** URLs like `?month=…` and `?view=…` are rejected by the excluded query keys, even under an
  allowed prefix (`tests/test_scope.py`, case "calendar ?month= variant").
- **Week 2 listing pipeline** (`src/pagination.py::collect_listing`, still used by HSS) stops on any of:
  - `max_pages`;
  - a visited URL (`cycle_detected`);
  - another host (`domain_mismatch`);
  - an empty page;
  - repeated items;
  - a failed fetch.

  Tests: `tests/test_pagination.py::test_collect_listing_stop_condition_*`.

## 4. Are feeds/sitemaps treated as discovery rather than complete truth?

**Yes.**
- **Shape.** A feed entry or sitemap `<loc>` becomes a `DiscoveryRecord`: URL, title, timestamp. It never becomes a
  record.
- **Path to a record.** A record exists only after the detail page is fetched, parsed and validated
  (`src/aggregator.py::run_aggregator`). This is the 1A checkpoint in `01_discovery/findings.md`.
- **lastmod is never trusted for change detection.** The one IITB-family sitemap has all 500 lastmods identical
  (`2024-02-14T06:57:38`). Lastmod is kept only as a source timestamp, the lowest priority in the merge rule (D15).
  Change detection uses the content hash.
- **Feeds.** The target's real `/rss.xml` holds 0 events. It is not used for discovery, only as a parsing fixture.
- **Raw values are kept.** Feed parsing keeps the raw timestamp string, and a date-only lastmod becomes `None` rather
  than a guessed instant (`tests/test_discovery_feed_sitemap.py`).

## 5. Are item URLs canonicalized consistently? *(focus area: in depth)*

**Yes.**

**One function.** `src/urls.py::resolve_item_url` is the only `urljoin` call in the code base
(`tests/test_week3_architecture.py::test_urljoin_is_called_only_in_resolve_item_url`).

**Every discovery path uses it**, including the R1 calendar hook:
- the adapter returns raw hrefs;
- `src/discovery/discover.py::_hook_items` builds every record with `make_record`, which calls `resolve_item_url`.

**A non-canonical record cannot exist.** `DiscoveryRecord.__post_init__` rejects any `discovered_url` that is not
already canonical (`tests/test_discovery_record.py::test_post_init_validation`).

**What it normalizes, and why each rule is safe:**

| Rule | Example (from tests) | Why it never merges two different items |
|---|---|---|
| Resolve relative, protocol-relative and root-relative hrefs against the page | `/event/institute-lecture-taming-turbulence` and `event/international-conference-quantum-dynamics#main-content` | Standard RFC 3986 resolution, as a browser does |
| Lowercase scheme and host; drop `:80` / `:443` | `HTTPS://WWW.IITB.AC.IN:443/event/...` | Host names and default ports are case- and port-insensitive by definition |
| Keep path case and trailing slashes | `/Event/X` stays `/Event/X` | Only the server knows whether `/a/` and `/a` are one resource (Week 2: `test_storage_ee_slash_and_no_slash_are_distinct_keys`) |
| Drop the fragment (except `#!/…`, `#/…` route fragments) | `#main-content`, `#register` | A fragment is never sent to the server |
| Drop tracking and session params | `utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref`, `sid`, `PHPSESSID`, `;jsessionid=` | They identify the click or the visitor, not the content (`tests/test_week3_canonical.py::test_tracking_fragment_case_and_port_variants_collapse`) |
| **Sort** the remaining params by key | `?view=list&page=2` → `?page=2&view=list` | Two spellings of one query become one key. Decided in R2; tested in `test_remaining_params_are_sorted_into_one_canonical_order` |

**The same item across methods** (the 1B checkpoint).
- `tests/test_discovery_record.py::test_same_item_same_url_across_methods`: a relative HTML href, an RSS link with
  `utm_source=rss&utm_medium=feed#main-content`, and a sitemap `<loc>` all give the identical `discovered_url`.
- `tests/test_discovery_interface.py::test_duplicate_discovery_url`: they collapse into **one** candidate with
  `discovery_methods == ("html", "rss", "sitemap")`.
- Offline e2e: one `discovered_items` row with `["html", "rss"]` and one record.

**The same key in every table.** `records.item_url` (PK), `discovered_items.discovered_url` (PK) and the link tables'
`item_url` (FK, D4). After two live runs, after two offline runs, and after the changed run, every duplicate check
returns 0 rows (`live_runs.md`, `demo_offline.md`).

**Known limit.** Two different URLs for one event (a renamed slug, a redirect) stay two keys. The redirect shows in
FETCH `final_url=`, but deciding that two URLs are one event is a matching problem, deliberately not guessed.

## 6. Is a missing field handled without crashing?

**Yes, at every level:**
- **A missing optional field on a detail page** (no venue, no speaker, no end time) becomes `None` / `[]`.
  `tests/test_entities_extraction.py::test_event_with_no_speaker` covers real pages; 4 of the 20 live pages have no
  labelled speaker.
- **A missing structure** (no `<article class="node--type-event">`) raises a clear `ValueError` inside the adapter.
  The aggregator logs `DETAIL_FAILURE`, counts a parse failure and keeps going. The record is stored from listing
  data, and stored values are kept by carry-forward (`09_metrics/failure_signatures.md`, scenario 4: 20 parse
  failures, run still `success`).
- **A calendar entry with no start** is skipped, never crashes. The offline calendar fixture contains one
  (`tests/test_calendar_discovery.py::test_calendar_pipeline_end_to_end_offline` discovers 13, not 14).
- **A missing calendar block** raises `fullCalendarView events not found` (`test_broken_calendar_is_a_clear_error`),
  which fails the run with a summary instead of storing nothing silently.
- **Missing feed and sitemap fields** (no date, no lastmod, no title) become `None` with the raw value kept
  (`tests/test_discovery_feed_sitemap.py`).
- **A required field that is really missing** (no `event_start` at all) fails validation: logged as
  `VALIDATION_FAILURE`, counted in `FAILED`, not stored.

## 7. Are speakers/organizations supported by source text?

**Yes.**
- Labels come from the adapter, roles only from labels, and an affiliation only when written next to the name.
  Prose such as "About the Speaker: Dr. …" or "the Department of Chemistry is organizing" is **not** extracted.
- Every mention keeps `source_text`, the labelled line verbatim.
  `tests/test_entities_extraction.py::test_every_entity_has_source_text_that_appears_verbatim_in_its_fixture` checks
  all 20 fixtures, and `item_people.source_text` stores it, so every stored link points back to its line.
- **Defects found live (R1).** The live run turned up two name shapes the parser got wrong: a bracketed nickname and
  post-nominals without a comma. Because the source text was stored, both were found and the fixed code was checked
  against the stored lines (D34).

## 8. Are uncertain identities merged too aggressively?

**No.**
- Identity is exact `name_key` equality only (`src/entities.py::name_key`): NFKC, casefold, decorative punctuation
  removed, honorific removed first. Initials are never expanded, and nothing is fuzzy-matched.
- **Pairs that might be one person or organization go to `entity_alias_candidates` with `status = 'needs_review'`,
  never merged:**
  - `A. Rao` / `Ananya Rao`;
  - `Ananya R.` / `Ananya Rao`;
  - `Centre` / `Center for Policy Research`.
- A bare acronym matches only on the page that defines it.
- All 16 fixture pairs are decided and tested (`07_resolution/entity_matching_policy.md`,
  `tests/test_matching_policy.py`).
- **The one accepted collapse** is two different people with an identical full name (D5). Per-event affiliations stay
  on the link rows, so it remains visible.

## 9. Can you tell from logs whether zero new items means "nothing new" or "parser broken"?

**Yes.** Every run prints a summary block and a `RUN_SUMMARY` log line, and stores the metrics on its `runs` row,
failed runs included (`09_metrics/failure_signatures.md`, real output; `tests/test_metrics.py`):

| Signature | Meaning |
|---|---|
| discovered N, parsed ~N, new 0, unchanged ~N, failed 0 | Nothing new. Live run 2: discovered 122, parsed 20, unchanged 40. |
| parsed 0 with failed = details attempted | The detail parser broke |
| discovered 0, HTTP 200, status failed | The listing broke |
| HTTP non-200, status failed | The fetch failed |

Warnings for the quiet failures:
- **`COVERAGE_DROP`:** a ≥ 30-point drop in speaker/date/org coverage, when the counts look normal.
- **`DISCOVER_EMPTY`:** a page that answered 200 with 0 items, when another method still found some.
- **`DISCOVERY_DROP`:** a sharp fall in items discovered against the previous successful run (R8).

## 10. Could this adapter run repeatedly without duplicating records?

**Yes.**
- **Keys:** records are keyed and upserted on the canonical URL (`INSERT … ON CONFLICT(item_url)`). Entity links
  have composite keys plus `INSERT OR IGNORE`, and parsed items have their links replaced, not appended. Review pairs
  are keyed on `(kind, a_id, b_id)`, and `discovered_items` on its URL.
- **Live:** two back-to-back runs on 2026-10-20 gave 40 new, then **40 unchanged**, 0 changed, 0 duplicate rows in any
  table, and 0 new links in run 2.
- **Offline:** after three runs, including a changed site, every duplicate check returns 0 rows
  (`demo_offline.md`; `tests/test_entity_storage.py::test_second_run_adds_zero_link_rows`;
  `tests/test_aggregator_e2e.py`).
- **Change detection:** only content changes mark `changed`. `fetched_at` and other volatile fields never do
  (`tests/test_incremental.py`).
