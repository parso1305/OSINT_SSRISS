# Week 3 decisions

Every judgment call made during the unattended run. Format: ID · section · decision · alternatives · why · how to reverse.
D1–D6 were made by Parth before the run and are logged as given.

## D1 · 1A–10 · Target = rank-1 PROPOSED surface: IIT Bombay institute events calendar
- **Decision:** auto-selected, pending Parth's review. Target = `https://www.iitb.ac.in/events` (listing) + `/event/<slug>` (details), rank 1 in `00_candidates/iit_bombay_aggregators.md`.
- **Check against the fallback rule:** rank 1 has item detail links (643 calendar entries, each with a `url`) and robots.txt allows `/events` and `/event/`, so no fallback to rank 2.
- **Alternatives:** rank 2 (IITB news) — items are news reports, not events.
- **Reverse:** change `listing_url`/`adapter` of the `iit_bombay_events` entry in `config/sources.json`.

## D2 · 1B, 2 · Canonical URLs (resolve_item_url)
- **Update (repair R2, 2026-10-20): RESOLVED — sorted order kept.** Parth chose sorted query parameters. The xfail test was replaced by `tests/test_week3_canonical.py::test_remaining_params_are_sorted_into_one_canonical_order`, which asserts the sorted canonical form (`?view=list&page=2` and `?page=2&view=list` both become `?page=2&view=list`). Q1 closed.
- **Decision (as given):** drop fragment, drop utm_*/fbclid/gclid/mc_cid/mc_eid, keep other params in original order, lowercase scheme and host, drop :80/:443 — only where existing tests stay green unchanged.
- **Finding:** `src/urls.py` already does all of it except two points that existing tests encode:
  1. Remaining query params are **sorted** by key, not kept in original order (`tests/test_canonicalization.py::test_resolve_url_strip_tracking_params` expects `?category=talks&page=2` from `?page=2&...&category=talks`; `tests/test_url_resolution.py::test_strips_tracking_and_session_params_keeps_semantic_ones` expects `?a=1&b=2` from `?b=2&a=1`).
  2. Client-side route fragments (`#!/…`, `#/…`) are **kept** (`test_fragments_stripped_unless_they_identify_content`), and `synthetic_item_url` depends on `#/item/<hash>` surviving.
- **Action:** `src/urls.py` unchanged. The Week 3 test for original param order is `xfail(strict=False)` with this reason (`tests/test_week3_canonical.py`). Logged in OPEN_QUESTIONS.md (Q1).
- **Reverse:** if Parth prefers original order, change the `query_params.sort(...)` line in `src/urls.py` and update the two tests above (that is a Week 2 behaviour change, so it needs his call).

## D3 · all · Layout (as given)
Week 3 written work under `assignments/week3/<NN_name>/`; reusable code in `src/` (`src/discovery/`, `src/scope.py`, `src/router.py`, `src/entities.py`, `src/metrics.py`, `src/aggregator.py`); assignment scripts are thin CLIs run with `python -m` (no sys.path hacks).

## D4 · 6 · Entity link tables reference records(item_url) (as given)
No integer items.id. Trade-off documented in `06_entities/entity_schema.md`.

## D5 · 6, 7 · people.normalized_name UNIQUE via name_key() after honorific removal (as given)
Two different people with an identical full name collapse into one row; accepted and documented. affiliation_raw lives on item_people.

## D6 · 4 · not_seen_this_run and rediscovered (as given)
not_seen_this_run = rows of this source with last_seen_at older than this run's started_at (no new column). Rediscovered = stored last_seen_at older than the previous run's started_at for this source; logged rediscovered=true, counted in the four buckets by its hash.

## D7 · 0 · offline_pytest.py also redirects the audit suite's evidence output
- **Decision:** `scripts/offline_pytest.py` sets `AUDIT_EVIDENCE_DIR` to a temp dir unless already set.
- **Why:** without it, running the audit suite rewrites the frozen Week 2 files in `assignments/week2_audit/logs/after_fixes/evidence/` (rule: don't touch frozen evidence).
- **Alternatives:** leave it and `git checkout` the evidence after each run (noisy, risky).
- **Reverse:** set `AUDIT_EVIDENCE_DIR` explicitly, or delete the `setdefault` line.

## D8 · 1A · `pythonpath = .` in pytest.ini
- **Decision:** added `pythonpath = .` so new test files import `src.*` without a `sys.path` hack (Week 3 rule: no sys.path hacks) and a single new test file can run on its own.
- **Alternatives:** copy the existing `sys.path.insert` boilerplate into every new test (forbidden for new code by the brief).
- **Reverse:** delete the line; new test files then only pass when run together with an older file that inserts the path.

## D9 · 1A · Feeds: RSS `updated` is not invented from `pubDate`
- **Decision:** `feed.py` reads entry dates with `dict.get`, bypassing feedparser's deprecated published↔updated aliasing, so an RSS item reports only its pubDate and an Atom entry with only `<updated>` has `published=None`. `timestamp` = published, else updated.
- **Why:** the alias would fabricate a second timestamp; the spec asks for the source's own values with the raw string kept.
- **Reverse:** use `entry.get(...)`.

## D10 · 1A · Event-shaped feed and sitemap fixtures are synthetic
- **Decision:** the target has no event feed, no Atom feed and no sitemap (Section 0 evidence, live 404 on 2026-10-17), so RSS/Atom/urlset/index exercises use synthetic fixtures modelled on real `/event/<slug>` URLs; the real `/rss.xml` (trimmed) and the real ACR sitemap (trimmed) are also fixtures. Stated in `01_discovery/findings.md` and `fixtures/week3/discovery/README.md`.
- **Reverse:** n/a (replace fixtures if the site adds a feed).

## D11 · 1B, 10 · HTML discovery reads the homepage events block, not the FullCalendar JSON — **SUPERSEDED by D33 (repair R1) for the live source**; still used by the offline source `local_aggregator_fixture`
- **Decision:** the target's HTML discovery page is `https://www.iitb.ac.in/` with `LISTING_SELECTORS` for its events block (`.homepage-events .views-row`: 40 server-rendered event cards, `<time datetime>` in correct UTC). It is a block of the same Drupal `events` view that `/events` draws client-side.
- **Why:** `/events` has 0 item links in its markup; all 643 entries are JSON inside `drupal-settings-json`, which a selector-driven HTML parser cannot read without site-specific JSON decoding. The homepage block is plain HTML for the same view, already capped at 40 items (inside the 20–40 discovered-items ceiling), and its timestamps are correct UTC, unlike the detail pages' `<time datetime="…Z">` which mislabels IST as UTC (17:15 IST shown as `17:15:00Z` on the detail page, `11:45:00Z` on the homepage).
- **Alternatives:** an adapter hook that turns the calendar JSON into items (full archive, 643 entries: better for a one-off backfill, too many for a capped monitoring run).
- **Reverse:** add a calendar-JSON listing function to the adapter and point `discovery_urls.html` at `/events`.

## D12 · 1B · DiscoveryRecord rejects a non-canonical discovered_url
- **Decision:** besides "absolute http(s)", `__post_init__` checks `resolve_item_url(url, "") == url`, so no code path can build a record with an un-canonicalized URL.
- **Why:** the focus area: one item, one key, regardless of discovery method.
- **Reverse:** drop that check in `src/discovery/record.py`.

## D13 · 2, 3, 10 · Generic change G2: SourceConfig gains optional Week 3 keys
- **Decision:** `pipeline` ("listing" default | "aggregator"), `discovery` (method or list), `discovery_urls` ({method: [urls]}), `scope` (dict), `router` (dict). Validated in `__post_init__`; unknown keys are still rejected by the loader.
- **Why:** Section 3 requires the discovery method to come from the source's registry entry; Section 2 requires scope config and caps in the entry; Section 10 requires the scheduler to choose the aggregator path from config.
- **Alternatives:** a separate config file for aggregators (two registries to keep in sync).
- **Reverse:** remove the five fields and the validation block; Week 2 sources never set them.

## D14 · 2 · Target scope: no department subdomains; listing pages and pager URLs are not items
- **Decision:** `allowed_hosts=["www.iitb.ac.in"]`, `allowed_subdomains_of=[]`; allowed prefixes `/event/`, `/events/`, `/breaking-news/`, `/sites/default/files/`; the allowed-prefix match is strict (`/events` itself is a listing, not an item); `page` and `search_api_fulltext` are excluded query keys (observed on the target), plus the standard calendar keys.
- **Why:** department sites are separate sources with their own adapters; a central-calendar link to one must not pull a whole department site in.
- **Alternatives:** `allowed_subdomains_of=["iitb.ac.in"]` (would admit every department site, unbounded).
- **Reverse:** edit the `scope` block in `config/sources.json`.

## D15 · 3 · Dedup merge rule: html > rss > atom > sitemap, field by field
- **Decision:** when several methods find one canonical URL, the title and the (timestamp, raw timestamp) pair come from the first method in that priority that has a value; `discovery_methods` keeps all of them.
- **Why:** the HTML listing shows what the reader sees and the event's own date; a sitemap has no title and its lastmod is unreliable (findings.md).
- **Alternatives:** newest timestamp wins (would let a 2024 sitemap lastmod or a pubDate stand in for the event date).
- **Reverse:** change `METHOD_PRIORITY` / `merge_records` in `src/discovery/discover.py`.

## D16 · 3 · Out-of-scope candidates are returned, not dropped
- **Decision:** `discover_items` returns every unique candidate with `in_scope`/`scope_reason`; the over-cap remainder is marked out of scope with "over max_discovered_items cap (N)".
- **Why:** Section 8 requires every candidate to be persisted with its reason; dropping them would make scope decisions invisible.
- **Reverse:** filter `result.candidates` on `in_scope` in `discover_items`.

## D17 · 4 · Generic changes G3/G4: four record states, sorted list fields in the hash
- **Decision:** `existing` → `unchanged` in storage return values, `runs.unchanged_count` (migrated in place with `ALTER TABLE runs RENAME COLUMN`), and log keys (`STORE … unchanged=`, `RUN_END … unchanged=`). `not_seen_this_run` is a query, `count_not_seen(db, source, run_started_at)`, per D6; every stored row gets `last_seen_at = run started_at` (the scheduler passes the run row's `started_at`), so the D6 comparison is exact. `REDISCOVERED … rediscovered=true state=<hash state>` is logged when a row's last_seen_at predates the previous run's start. `content_hash` sorts `speakers` by (name, affiliation) and `organizations` alphabetically before hashing. The upsert became one `INSERT … ON CONFLICT(item_url) DO UPDATE` (first_seen_at only on insert) inside the existing one-transaction-per-run.
- **Kept as is:** the legacy `items` path (`store_item`/`store_all`) still returns `existing` (legacy is out of bounds); `store_records()` still returns a 3-key dict (`not_seen_this_run` is reported separately, so the only test edits are the renames).
- **Hash reset note:** sorting only changes the hash of rows whose list fields were stored out of order; single-speaker/single-organization rows hash the same as before.
- **Reverse:** revert the `generic: record states …` commit (the column rename is reversible with `RENAME COLUMN unchanged_count TO existing_count`).

## D18 · 5 · Controlled live entity sample + two synthetic variants
- **Decision:** the Section 0 evidence had 8 detail pages (< 10), so 12 more lecture/colloquium/seminar pages were fetched once (13 requests, budget ≤ 20). No real page has two people in one field or an `Organized by:` organization line, so two synthetic variants of a real page (only the Speaker paragraph replaced, fictional Section 7 names) cover those cases. Extraction fixture set: 18 real + 2 synthetic = 20.
- **Alternatives:** hand-written pages (unrealistic markup); more live fetches hoping to find those cases (budget, and unbounded).
- **Reverse:** delete `synthetic-*.html` and the two cases in `tests/test_entities_extraction.py`.

## D19 · 5, 10 · Event times: detail `<time datetime>` read as IST with a fixed +05:30 offset
- **Decision:** the adapter drops the mislabelled `Z` and converts IST→UTC with a fixed +05:30 (`timezone = Asia/Kolkata` stored next to it).
- **Why:** proven mislabel (homepage `11:45:00Z` vs detail `17:15:00Z` for one lecture; body says 5:15 p.m.); India has no DST; the venv has no tz database (`ZoneInfoNotFoundError: Asia/Kolkata`) and `tzdata` would be a new dependency for one constant.
- **Reverse:** `pip install tzdata` and use `ZoneInfo("Asia/Kolkata")` in `_ist_to_utc`.

## D20 · 5 · People-splitting rule: a new person starts only at an explicit honorific (unless no comma at all)
- **Decision:** see `05_extraction/notes.md`. Real affiliations contain `;`, `&`, ` and ` and line breaks, so splitting on every separator would invent people ("Padma Shri Awardee", "Professor, Computer Science…"). Plain comma never splits.
- **Cost:** an unlabelled-honorific list with affiliations ("Ananya Rao, IITB; Ravi Sen, TISS") stays one person (under-split, never a false person). Logged as the conservative failure mode.
- **Reverse:** change `split_people` in `src/entities.py`.

## D21 · 6 · Generic change G5: entity tables + PRAGMA foreign_keys=ON on every connection
- **Decision:** DDL as specified (people / organizations with UNIQUE normalized_name; item_people / item_organizations keyed (item_url, entity_id, role), REFERENCES records(item_url) per D4). All storage connections go through `_open()`, which sets `PRAGMA foreign_keys = ON`. Indexes: the UNIQUE constraints already index normalized_name (sqlite_autoindex), plus indexes on person_id / organization_id for reverse lookups.
- **Re-run semantics:** an item whose detail page was parsed this run gets its links REPLACED by what the page says now (a removed speaker does not linger); if the detail fetch failed, links are kept (same rule as `_carry_forward` for content). Either way the composite key means a re-run never duplicates a link.
- **display_name:** first form seen wins (`ON CONFLICT DO NOTHING`); per-event spellings stay in item_people.source_text.
- **Reverse:** revert the `generic: entity tables …` commit; the PRAGMA is one line in `_open()`.

## D22 · 7 · Generic change G6: entity_alias_candidates review table
- **Decision:** `entity_alias_candidates(kind, a_id, b_id, reason, status DEFAULT 'needs_review', PK(kind, a_id, b_id), CHECK a_id < b_id)`; `add_alias_candidates` uses INSERT OR IGNORE so re-runs never duplicate a pair or reset a reviewer's status. No code path merges entities.
- **Reverse:** drop the table and the two helpers.

## D23 · 7 · Matching outcomes per pair
- **Decision:** people: identical name_key after honorific removal = safe (one row, D5); same number of name parts, every part equal or initial-compatible, and at least one full part identical = review; otherwise (incl. two abbreviated forms like "A. Rao" vs "Ananya R.") = do not match. Organizations: identical key (a parenthesised acronym is only a same-page definition) = safe; Centre/Center = review; any bare acronym = do not match across pages (same-page definition resolves it inside one item only).
- **Why:** a false merge is invisible and contaminates every later query; a false split is visible and fixable.
- **Reverse:** `person_match` / `org_match` in `src/entities.py`.

## D24 · 8 · Generic change G7: discovered_items table
- **Decision:** columns exactly as specified; `discovery_methods` stored as JSON; written inside the run's single transaction; `first_discovered_at` kept on update. Out-of-scope candidates are stored too (in_scope=0 with scope_reason), so every scope and routing decision is auditable.
- **Reverse:** drop the table and the three helpers.

## D25 · 8 · ITEM_TYPES stays ("event",); announcements stay in discovered_items
- **Decision:** no announcement parser was built this week, so `announcement` is not added to ITEM_TYPES. `/breaking-news/` items are discovered, scoped and routed (`content_class = announcement`) and kept in discovered_items.
- **Why:** the brief allows widening only for classes with a parser that writes to records; building a news parser and its schema rules would be new scope.
- **Reverse:** add an announcement parser to the adapter, widen ITEM_TYPES, route `announcement` to it.

## D26 · 8 · Router order and target patterns
- **Decision:** external host → PDF (Content-Type, else extension) → category label (config map) → URL pattern (config) → unknown. Target patterns from the real URLs seen: event `/event/`, `/events/`; announcement `/breaking-news/`, `/announcement-staff/`, `/announcements/`; faculty `/employee/`, `/faculty/`. `/node/N`, `/tenders/`, `/award/`, `/research-highlight/` deliberately unmapped (unknown).
- **Reverse:** edit `router` in config/sources.json.

## D27 · 9 · Generic change G8: metrics columns on the existing runs table
- **Decision:** 12 nullable columns added to `runs` (created for new DBs, `ALTER TABLE ADD COLUMN` for existing ones); `finish_run` takes an optional `metrics` dict; `last_runs()` reads the latest finished runs. new/changed/failed counts stay; unchanged_count comes from Section 4.
- **Reverse:** the columns are nullable and unused by Week 2 code; revert the commit (SQLite ≥ 3.35 can DROP COLUMN if needed).

## D28 · 9, 10 · Generic change G9: config-driven pipeline dispatch; aggregator code lands before the Section 9 commit
- **Decision:** `run_scheduled` picks `PIPELINES[config.pipeline]` (listing → `run_source`, aggregator → `run_aggregator`); both take the same arguments (run_id, run_started_at, rediscovery_cutoff) and return the same result shape, so lock, run row, RUN_START/RUN_END and exit codes are shared. A failed aggregator run raises `AggregatorRunError` carrying its summary; the scheduler stores those metrics on the failed run row.
- **Ordering note:** `src/aggregator.py` and `src/metrics.py` are committed here (before "week3: 9 run metrics") because the Section 9 broken-fixture tests need a pipeline to break. Section 9's commit adds the metric tests, the CLI check and failure_signatures.md; Section 10's adds the fixture site demo and live runs.
- **Detail order:** detail pages are fetched in listing order up to the cap (page order is stable, so run 2 re-fetches the same pages and is "unchanged"). Alternative considered: prioritising never-enriched items, which converges coverage but makes every second run report the previously listing-only items as "changed". Documented in 10_aggregator.
- **Reverse:** set `"pipeline": "listing"` on a source, or revert the commit.

## D29 · 9 · Metric definitions, coverage threshold, DISCOVER_EMPTY
- **Decision:** items_parsed = detail pages parsed into a valid record; FAILED = parse failures + detail-fetch failures + invalid records; coverage % over items_parsed; http_status = the first discovery page's status even when it failed. COVERAGE_DROP when a % falls ≥ 30 points vs the previous successful run (only runs with items_parsed > 0 compared). A discovery page answering 200 with 0 items logs `DISCOVER_EMPTY` (WARNING) even if another method found items, so a second method cannot hide a broken listing.
- **Found while testing:** the first version reported the first *successful* page's status (a 503 listing showed http_status=200 when the feed worked); fixed in `discover()`.
- **Reverse:** `src/metrics.py` (COVERAGE_DROP_POINTS) and `src/discovery/discover.py`.

## D30 · 11 · Review questions derived from the Week 3 requirements
- **Decision:** the 10 Section 11 questions were not in the brief; used 10 derived from Sections 1–10, logged as Q4. The TISS review template is left blank (the brief says not to review his code).
- **Reverse:** replace the headings with the official list.

## D31 · 12 · Definition-of-Done items derived from the sections; Assignment 9 swap not attempted
- **Decision:** DEFENSE_NOTES.md answers one DoD item per Week 3 section (0–12) because the brief did not list the DoD items verbatim (same gap as Q4). The "Week 2 Assignment 9 template swap" is listed as Needs Parth: the run had no instructions or template for it.
- **Reverse:** re-key DEFENSE_NOTES.md to the official DoD list.

## D32 · R1 · Generic change G10: html discovery can call an adapter listing hook (config `listing_options`)
- **Decision:** a source may set `listing_options = {"hook": "<adapter function>", ...}`; html discovery then calls `adapter.<hook>(text, page_url, options, now_iso)` instead of the CSS selectors. The hook returns plain entries (href, title, raw/UTC timestamp, category); `discover.py` builds the DiscoveryRecords itself (`make_record` → `resolve_item_url`), so scope, dedup, merge rule and caps are untouched. Filter values live in `listing_options`, never in code.
- **Why:** R1: the target's calendar items exist only as JSON inside `drupal-settings-json`; decoding that is site-specific (adapter), calling it is generic (discovery).
- **Reverse:** remove `listing_options` from the config entry (the selector path is unchanged) or revert the commit.

## D33 · R1 · iit_bombay_events discovers from the /events calendar JSON, lecture-type entries only (supersedes D11)
- **Decision:** `listing_url` / `discovery_urls.html` = `https://www.iitb.ac.in/events`; `listing_options = {"hook": "calendar_entries", "include_title_keywords": ["Institute Lecture", "Lecture", "Colloquium", "Seminar", "Talk"], "utc_offset": "+05:30"}`. The adapter hook decodes `drupal-settings-json → fullCalendarView[0].calendar_options.events`, keeps entries whose title contains a keyword (case-insensitive), one per URL, ordered upcoming first (soonest first) then past (most recent first). Caps unchanged: 40 discovered (`max_discovered_items`), 20 detail fetches.
- **Seminar/Talk:** the calendar JSON has only title, url, start and node id: no event type. "Seminar/Talk" is a detail-page field, so the title keywords `Seminar` and `Talk` stand in for it at discovery time; the detail page's `event_type` is stored on the record.
- **Why:** Q2: the homepage block (40 nearest events, mostly observances) gave 1 labelled speaker in 20 parsed pages live; the lecture-type calendar entries are where IITB labels speakers (offline: 12 of 13 parsed fixtures).
- **Offline check:** the real saved calendar (2026-10-16) yields 122 lecture-type entries of 643; first is the one upcoming lecture (Saral AI), then Taming Turbulence (2026-09-03), … (`tests/test_calendar_discovery.py`).
- **Reverse:** remove `listing_options` and point `discovery_urls.html` back at `https://www.iitb.ac.in/` (D11 selectors are still in the adapter).

## D34 · R1 · Two name-parsing fixes found by the live calendar run
- **Decision:** `parse_person` keeps a bracketed nickname followed by more name inside the name ("Matthew (Mat) Collins"), and ends the name before post-nominal letters (FRS, FREng, FRSC, FNA, FASc, FNAE, FNASc, FAAAS, PhD) with the rest kept verbatim as affiliation_raw ("Michael L. Klein" + "FRS Laura H. Carnell Professor of Science, …"). Tests use the live source text verbatim.
- **Not re-run live:** the fix came after both runs; a third run (22 requests) would exceed the 60 budget (44 used). The fixed code was re-applied offline to the 16 stored source_text lines (2 differ, 14 identical; `10_aggregator/live_runs.md`). The next live run corrects the stored links.
- **Reverse:** remove `_NICKNAME_RE` / `_POSTNOMINAL_RE` from `src/entities.py`.

## D35 · R3 · iit_bombay_events enabled
- **Decision:** `"enabled": true` after R1 passed (both live runs succeeded, run 2 all unchanged, 0 duplicates). A plain `python -m src.scheduler --once` (Task Scheduler) now runs it when due: `interval_minutes 1440`, so at most one run a day, 22 requests each (robots.txt, /events, 20 details), 3 s apart.
- **Reverse:** set `"enabled": false`.
