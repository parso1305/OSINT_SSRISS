# web-monitor: academic event monitor (Weeks 2–3)

Monitors institutional event sources on a schedule. A **generic pipeline** (`src/`) fetches politely, validates
against a shared schema and stores changes in SQLite. Each site contributes only an **adapter**
(`sources/<name>.py`: selectors, label patterns and cleaning rules) and a **config entry** (`config/sources.json`).
The config's `pipeline` key picks one of two pipelines. Both run under the same scheduler, lock, run records and
logs.

**Week 2, `"pipeline": "listing"`** (`src/runner.py`): one department listing, e.g. IIT Bombay HSS
"Seminars and Talks".

```
fetch listing (robots.txt, delay, timeout, TLS verified) -> adapter.parse_listing -> [pagination]
  -> [detail pages: adapter.parse_detail, merged into the listing record] -> adapter.normalize
  -> assemble shared-schema record -> validate -> store (one transaction; new / changed / unchanged,
     then not_seen_this_run)
```

**Week 3, `"pipeline": "aggregator"`** (`src/aggregator.py`): a central aggregator. The target is the IIT Bombay
institute events calendar (`sources/iit_bombay_events.py`; target choice D1, pending review).

```
config entry -> discovery (html / rss / atom / sitemap -> DiscoveryRecord, canonical URLs)
  -> scope filter -> dedup on the canonical URL -> content router (event / announcement / faculty / pdf_document /
     external_link / unknown) -> capped detail fetch -> router again (Content-Type) -> adapter.parse_event_detail
  -> assemble + validate -> entity mentions (people, organizations; labelled roles only)
  -> ONE transaction: records + entity links + review queue + discovered_items -> not_seen_this_run
  -> run metrics (summary block, RUN_SUMMARY log line, runs-table columns, coverage-drop warning)
```

## Setup

Python 3.13 on Windows (the code is plain Python and also runs elsewhere).

```powershell
cd C:\Project\OSINT_SSRISS\Assignment_week_2\web-monitor
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

`requirements.txt` pins the direct dependencies (`requests`, `beautifulsoup4`, `certifi`, `feedparser`,
`defusedxml`, `pytest`, `pytest-cov`).

Keep the checkout path short on Windows. Some saved fixture names are long, and a clone under a deep folder
(roughly 100+ characters) exceeds the 260-character path limit; git then fails with `Filename too long`.
Alternatively, enable long paths (`git config --global core.longpaths true` plus the Windows `LongPathsEnabled`
policy).

## Running

| Command | What it does |
|---|---|
| `python -m src.scheduler --once` | Runs every **due** enabled source once, then exits. This is what Task Scheduler runs. Exit code 1 if any run failed. |
| `python -m src.scheduler --once --source <id> --force` | One source now, even if disabled or not yet due. |
| `python -m src.scheduler` | Loop mode: checks every 60 s (`--tick-s`). For demos. |
| `python scripts/fixture_site.py --port 8765` | Serves the saved HSS HTML on 127.0.0.1. The disabled `local_fixture` source points here, so `python -m src.scheduler --once --source local_fixture --db data/demo.db` runs the full pipeline with no network. |
| `python scripts/run_fixtures.py --show-records 2` | Runs the HSS config against the fixture site directly (no scheduler) into a temp DB. |
| `python -m scripts.aggregator_fixture_site --port 8766` | **Week 3 offline aggregator**: serves the saved IIT Bombay events pages on 127.0.0.1:8766 (`--variant changed` for the next-day site; `--broken listing\|detail\|http\|speaker_label` for failure demos). |
| `python -m src.scheduler --once --source local_aggregator_fixture --force --db data/week3_demo.db` | Runs the aggregator **once, offline**, against that site (`assignments/week3/10_aggregator/demo_offline.md`). |
| `python -m src.scheduler --once --source iit_bombay_events --force --db data/week3_live.db` | Runs the aggregator **once, live**, against www.iitb.ac.in: about 22 requests, 3 s apart (`assignments/week3/10_aggregator/live_runs.md`). |
| `python -m src.metrics --last --db <path> [--source <id>]` | Prints the last run's summary (Week 3 Section 9). |
| `python -m assignments.week3.10_aggregator.inspect_db --db <path>` | Duplicate checks and an inventory of an aggregator DB. |

Other flags: `--db <path>` (default `data/events.db`), `--locks-dir <dir>`, `--config <path>`.

**When a source is due** (`src/scheduler.py`): it is due if it never ran; otherwise `interval_minutes` after its
last successful run, or `retry_minutes` after a failed one (default 60, doubling per consecutive failure: 60, 120,
240, …, capped at `interval_minutes`). Every cycle logs one `SCHEDULE` line per source with `last_status`,
`consecutive_failures`, `wait_minutes` and `next_due_reason` (`never_run`, `interval_after_success`,
`retry_after_failure`, `retry_after_unfinished_run`, `forced`). A per-source lock file (`locks/<source_id>.lock`)
prevents overlapping runs; a held lock is logged as `RUN_SKIPPED` and recorded as a `skipped` run.

**What counts as a failed run** (`runs.status = failed`, exit code 1, nothing stored): the listing's first page
cannot be fetched (HTTP error, network, TLS, robots.txt), the listing structure is gone (`StructuralError`), the
listing parses to 0 items (`EmptyListingError`, unless the source sets `allow_empty_listing: true`), or storage
fails (the whole run's writes roll back). Per-item problems do not fail the run: a detail page that fails
(`DETAIL_FAILURE`), a value the adapter cannot parse (`PARSE_WARNING`), and a record that fails validation
(`VALIDATION_FAILURE`, not stored). Neither a failed detail fetch nor an unparseable value ever erases stored data.

**Output**: table `records` (one row per canonical `item_url`, shared schema in `src/schema.py`) and table `runs`
(one row per run: status, counts, error, and the Week 3 run metrics), both in the `--db` file. Aggregator sources
also write `discovered_items`, `people`, `organizations`, `item_people`, `item_organizations` and
`entity_alias_candidates`. `data/events.db` is created on the first run
(the local databases were reset for the shared-schema rename below, so no row predates it).
Logs go to stdout as `YYYY-MM-DD HH:MM:SS [LEVEL] logger=<name> EVENT key=value …` (examples:
[`assignments/01_logging/failure_examples.md`](assignments/01_logging/failure_examples.md)).

## Shared record schema

Every row in `records` uses the team's Week 2 event-schema field names, so another intern's records of the same
item type can be written into the same table without renaming anything (Week 2 Section 6 checkpoint;
`tests/test_runner.py::test_records_table_has_shared_schema_fields` checks the table). Field groups and validation
rules: `src/schema.py`.

**16 shared fields**

| Field | Value |
|---|---|
| `item_url` | `TEXT PRIMARY KEY`; canonical URL from `src.urls.resolve_item_url()` |
| `source_name` | config `source_id`, e.g. `iit_bombay_hss_seminars` |
| `source_url` | config `listing_url` (the listing the item came from) |
| `item_type` | config `content_type`; today always `event` |
| `title` | text |
| `event_start`, `event_end` | UTC `YYYY-MM-DDTHH:MM:SSZ`, or date-only `YYYY-MM-DD` plus `timezone` |
| `location` | text |
| `speakers` | JSON list of `{"name", "affiliation"}` |
| `organizations` | JSON list of strings: from the page when it names an organiser, else `[config organizer]` |
| `description` | text |
| `raw_text` | listing card text, as scraped (not part of `content_hash`) |
| `first_seen_at`, `last_seen_at` | `TEXT NOT NULL`, UTC; set by storage |
| `fetched_at` | listing fetch time, UTC with `Z` |
| `http_status` | `INTEGER`; HTTP status of the listing response |

**Kept extras** (columns beyond the shared 16)

| Column | Why it stays |
|---|---|
| `institution` | Groups sources by institution; `source_name` names a feed, not an institution. |
| `timezone` | Needed to read a date-only `event_start` (a local calendar date has no UTC instant). |
| `is_online` | Online/in-person filter without re-parsing `location`. |
| `event_type` | The site's own category (Seminar / Talk / Workshop), finer than `item_type`. |
| `detail_fetched_at` | When the detail page was fetched (separate from the listing's `fetched_at`). |
| `detail_fetch_status` | `ok` / `failed` / `not_attempted`: tells "the field is empty" apart from "the detail page was not read". |
| `detail_http_status` | `INTEGER`; detail response status, separate from the listing's `http_status`. |
| `detail_error` | Error type and message of a failed detail fetch. |
| `extras` | JSON dict of source-specific values only (node id, raw date text, pagination provenance `discovered_on_url` / `discovered_on_page`). |
| `content_hash` | `TEXT NOT NULL`; sha256 over the content fields only, so `raw_text`, `fetched_at`, `http_status` and `detail_*` never make a re-fetch look changed. |

**Rename map (Week 3 Part 0)**: `source_id` → `source_name`; new `source_url`; `content_type` → `item_type`;
`starts_at` → `event_start`; `ends_at` → `event_end`; `venue` → `location`; `organizer` (text) → `organizations`
(JSON list of strings); `extras.raw_text` → `raw_text` column; `listing_fetched_at` → `fetched_at`; new
`http_status`. Unchanged: `item_url`, `title`, `speakers`, `description`, `first_seen_at`, `last_seen_at`.
Config keys (`source_id`, `content_type`, `organizer`), the `runs` table and the `source_id=` log keys keep their
names: they describe a source or a run, not a record. Every stored `content_hash` changed with the rename (the hash
covers field names as well as values), so local databases were reset rather than migrated.

`speakers` keeps its `{name, affiliation}` object shape, although some teammates store plain strings. It is not
changed now because Week 3 Section 6 moves speakers into a people table.

## Discovery record

Week 3 discovery turns every way of finding an item (HTML listing, RSS, Atom, sitemap) into one shape,
`src/discovery/record.py::DiscoveryRecord` (frozen; validated in `__post_init__`):

| Field | Value |
|---|---|
| `source_name` | config `source_id` of the source that found it |
| `discovered_url` | canonical URL, always the output of `src.urls.resolve_item_url()` (validated: absolute http(s), already canonical) |
| `discovery_method` | `html` · `rss` · `atom` · `sitemap` |
| `discovered_title` | listing link text / feed `<title>`; `None` for sitemaps |
| `source_timestamp` | the source's own timestamp (listing date, pubDate/updated, lastmod) as UTC `...Z`, or `None` |
| `discovered_at` | when this run found it, UTC `...Z` |

`to_spec_dict()` returns exactly these six. One extra provenance field, `source_timestamp_raw`, stays on the object
(the timestamp as the source wrote it, kept even when it cannot be normalized). Because every method goes through
`resolve_item_url()`, one event found as a relative HTML href, an RSS link with `utm_*` and a `#fragment`, and a
sitemap `<loc>` gets the same `discovered_url` (`tests/test_discovery_record.py::test_same_item_same_url_across_methods`).
A discovery record is a candidate, not an event record (`assignments/week3/01_discovery/findings.md`).

## URL scope rules

`src/scope.py::scope_decision(url, cfg) -> (allowed, reason)` runs on canonical URLs. Its rules apply in this order:
1. **Scheme:** http/https only. `mailto:`, `javascript:`, `tel:` and `data:` are never items.
2. **Host:** an exact match against `allowed_hosts`. A subdomain is allowed only when its parent is listed in
   `allowed_subdomains_of`, checked on a dot boundary (`notiitb.ac.in` never matches). Other hosts are rejected
   unless `allow_external`.
3. **Excluded path prefixes:** login, search, admin and user pages.
4. **Excluded query keys:** the calendar, search and filter explosion (`?month=`, `?view=`, `?page=`,
   `?search_api_fulltext=`, …), rejected even under an allowed prefix.
5. **Allowed path prefixes**, stored with a trailing slash, so `/events/` never matches `/events-archive/`.

A PDF inside an allowed prefix is in scope, but it is routed as `pdf_document` and never detail-fetched as HTML. The
per-run caps (`max_listing_pages`, `max_discovered_items`, `max_detail_items`) live in the same `scope` config block.
Out-of-scope candidates are kept in `discovered_items` with their reason.
Cases: `assignments/week3/02_scope/scope_cases.md` (one test per row in `tests/test_scope.py`).

## Content-hash fields

`content_hash` = sha256 over `schema.CONTENT_FIELDS` only:
- `item_type`, `title`
- `event_start`, `event_end`, `timezone`
- `speakers`, `location`, `is_online`
- `event_type`, `organizations`, `description`

List fields are sorted before hashing (speakers by (name, affiliation), organizations alphabetically), so a reorder
on the page is not a change. Stored values keep the page order.

Never hashed:
- `fetched_at`, `discovered_at`
- `http_status`
- `detail_*`
- `raw_text`
- `extras` (where relative "posted 3 days ago" text, view counts and tokens would go)
- identity and provenance (`item_url`, `source_name`, `source_url`, `institution`)

Record states:
- **new:** an unseen canonical URL;
- **changed:** a different hash;
- **unchanged:** the same hash (was `existing` in Week 2);
- **not_seen_this_run:** a query, not a write (`last_seen_at` older than the run's start). Nothing is ever deleted.

Details: `assignments/week3/04_incremental/run_state_notes.md`.

## Entity matching policy

People and organizations come only from **labelled** lines (`Speaker:`, `Chair:`, `Organized by:`, …; the patterns
are the adapter's), with `source_text` kept verbatim. An affiliation is recorded only when it is written next to the
name.

Identity is `name_key()` and nothing else: NFKC, casefold, decorative punctuation removed, whitespace collapsed, with
the honorific removed first and stored separately. It never expands initials, reorders names, drops parts or
fuzzy-matches.

Decisions:
- **Equal keys** are one row (`people.normalized_name` UNIQUE; an accepted identity claim, D5).
- **Review, never merged:** an initial compatible with a full name plus an identical other part (`A. Rao` /
  `Ananya Rao`), and Centre/Center spelling variants. These go to `entity_alias_candidates` with
  `status = 'needs_review'`.
- **A bare acronym** is an alias only on the page that defines it (`Centre for Policy Research (CPR)`).

A false merge is worse than a false split: a merge silently gives one person another's events, while a split is
visible and fixable. Table of every decided pair: `assignments/week3/07_resolution/entity_matching_policy.md`.

## Changes to the generic layer

Week 3 changed the generic layer only where a Week 3 requirement needed it. Existing tests stayed green without
edits, except the Section 4 state/column rename. Every change also has an entry in
`assignments/week3/DECISIONS.md`.

| # | Commit | What | Why (Week 3 requirement) |
|---|---|---|---|
| G1 | `7d83a56` | `src/fetcher.py`: `FetchResult.content_type` (optional, default `None`), filled from the response header | Recon evidence needs content-type; the router (Section 8) prefers Content-Type over the file extension |
| G2 | `generic: config accepts Week 3 aggregator keys` | `src/config.py`: optional `pipeline`, `discovery`, `discovery_urls`, `scope`, `router` keys, validated | Section 3 (discovery method from the registry entry, never hardcoded), Section 2 (scope config and caps in the source entry), Section 10 (scheduler picks the pipeline from config) |
| G3 | `generic: record states new/changed/unchanged/not_seen_this_run` | `src/storage.py`, `src/runner.py`, `src/scheduler.py`, `src/logging_config.py`: state `existing` renamed `unchanged` everywhere (counts, `runs.existing_count` → `unchanged_count` with an in-place `ALTER TABLE … RENAME COLUMN` migration, log keys `existing=` → `unchanged=`); `not_seen_this_run` = `count_not_seen()` query (D6); `REDISCOVERED` log line; `run_id=` on the STORE line; rows get `last_seen_at = run started_at`; upsert is one `INSERT … ON CONFLICT(item_url) DO UPDATE` | Section 4 (four states, D6, upsert in one transaction with run_id on log lines) |
| G4 | same commit | `content_hash`: list fields sorted before hashing (speakers by (name, affiliation), organizations alphabetically); stored order unchanged | Section 4 (a reorder on the page is not a change) |
| G5 | `generic: entity tables and PRAGMA foreign_keys=ON` | `src/storage.py`: tables `people`, `organizations`, `item_people`, `item_organizations` (FKs to `records(item_url)`, composite primary keys), `write_entity_links` (runs inside the run's single transaction), and `PRAGMA foreign_keys = ON` on every connection (one `_open()` helper) | Section 6 (entity storage, FK enforcement, re-runs never duplicate links) |
| G6 | `generic: entity_alias_candidates review table` | `src/storage.py`: table `entity_alias_candidates(kind, a_id, b_id, reason, status='needs_review')`, `add_alias_candidates` (INSERT OR IGNORE, keeps a reviewer's status), `list_entities` | Section 7 (review pairs are written to entity_alias_candidates and never merged) |
| G7 | `generic: discovered_items table` | `src/storage.py`: table `discovered_items` (every candidate with scope and routing decision), `upsert_discovered_items` (inside the run transaction; `first_discovered_at` kept), `get_discovered_item` | Section 8 (persist every candidate; unknown/unsupported items stay with their reason, never dropped, never forced into records) |
| G8 | `generic: run metrics columns on the runs table` | `src/storage.py`: `runs` gains `http_status`, `pages_fetched`, `items_discovered`, `items_parsed`, `not_seen_count`, `parse_failures`, `detail_failures`, `people_extracted`, `organizations_extracted`, `pct_with_date`, `pct_with_speaker`, `pct_with_org` (added in place with `ALTER TABLE ADD COLUMN`; NULL for older rows); `finish_run(..., metrics=)`; `last_runs()` | Section 9 (extend the existing runs table, no second run table) |
| G9 | `generic: scheduler dispatches the aggregator pipeline from config` | `src/scheduler.py`: `PIPELINES = {"listing": run_source, "aggregator": run_aggregator}` chosen by `config.pipeline`; the run row stores the run's metrics (`finish_run(metrics=…)`), also for a failed aggregator run (`AggregatorRunError.summary`). New generic modules `src/aggregator.py` (the pipeline) and `src/metrics.py` (summary). `src/runner.py` is unchanged apart from G3. | Section 10 (the scheduler chooses the aggregator path from the source's config; reuse the Week 2 scheduler, lock and run records), Section 9 (a failed run still writes a summary) |
| G10 | `generic: html discovery can call an adapter listing hook` | `src/config.py`: optional `listing_options` (`{"hook": <adapter function>, …filter values}`); `src/discovery/discover.py::_hook_items`: html discovery calls the named adapter hook instead of CSS selectors and builds the records itself (`make_record` → `resolve_item_url`), so scope, dedup and caps are unchanged | Repair R1 (the target's calendar items are JSON inside the page; decoding it is site-specific, the filter values belong in config) |

## Adding a source (adapter + config only)

1. **Adapter** `sources/<name>.py` (no network, database or logging setup; `tests/test_architecture.py` enforces this):
   * `parse_listing(html, base_url) -> list[dict]`: one raw dict per item. `item_url` must come from
     `src.urls.resolve_item_url(href, base_url)`. If items have no URL of their own, use
     `src.urls.synthetic_item_url(base_url, <site id, or title + date>)` (rules in `src/schema.py`).
     Raise an error when the listing container is missing, so a redesign fails loudly.
   * `normalize(record) -> dict`: shared-schema content fields (`title`, `event_start` as UTC
     `YYYY-MM-DDTHH:MM:SSZ` or date-only `YYYY-MM-DD`, `event_end`, `timezone`, `speakers`, `location`,
     `is_online`, `event_type`, `description`, and `organizations` only when the page names an organiser),
     `extras` for site-only fields, and optionally
     `parse_warnings: {field: raw}` for values present but unparseable (logged; stored values are kept).
   * `parse_detail(html, item_url) -> dict`: only if the source has detail pages (`supports_detail`).
   * Optional `NEXT_PAGE_SELECTOR` (default: `rel="next"` links).
2. **Config entry** in `config/sources.json` (unknown keys are rejected):

| Key | Meaning |
|---|---|
| `source_id`, `institution`, `adapter`, `listing_url` | required; `adapter` is a module path, e.g. `sources.iit_bombay` |
| `content_type`, `organizer` | copied into every record as `item_type` and `organizations: [organizer]` (the latter only when the adapter gives none) |
| `enabled` | picked up by `--once` without `--source` |
| `supports_pagination`, `max_pages` | follow next-page links, at most `max_pages` pages |
| `supports_detail`, `detail_limit` | fetch the detail page of the first `detail_limit` items |
| `request_delay_s`, `timeout_s` | politeness gap per host (robots.txt `Crawl-delay` wins if larger); per-request timeout |
| `interval_minutes`, `retry_minutes` | schedule after a success / first retry after a failure (default 60) |
| `lock_max_age_minutes` | a lock older than this is stale and removed |
| `allow_empty_listing` | default `false`: 0 parsed items fails the run |
| `ca_bundle` | PEM file for TLS verification, relative to the project root (see below) |
| `pipeline` | `listing` (default, Week 2 runner) or `aggregator` (Week 3) |
| `discovery`, `discovery_urls` | aggregator: method(s) `html` / `rss` / `atom` / `sitemap`, and `{method: [urls]}` (`html` defaults to `[listing_url]`) |
| `scope` | aggregator: `src.scope.ScopeConfig` keys (hosts, prefixes, excluded query keys, caps) |
| `router` | aggregator: `hosts`, `category_map` (card label → class), `url_patterns` (class → path prefixes) |
| `listing_options` | aggregator html discovery through an adapter hook: `{"hook": "calendar_entries", …filter values}` (G10) |

An **aggregator adapter** provides `LISTING_SELECTORS` (for `src/discovery/html.py`), the label patterns, and
`parse_event_detail(html, item_url) -> {fields, people, orgs, parse_warnings}`. See `sources/iit_bombay_events.py`.

3. **Tests**: save real pages under `fixtures/<site>/`, test the adapter on them (see
   `tests/test_adapter_iit_bombay.py`), and serve them through `scripts/fixture_site.py` for an end-to-end run.
   `tests/test_generic_source.py` shows that a new source needs nothing else.

## Scheduled runs on Windows (Task Scheduler)

`scripts\run_scheduler_once.bat` changes into the project directory, runs `python -m src.scheduler --once` and
appends the output to `logs\scheduler.log`. Register it to fire **hourly**. The scheduler decides what is due
(HSS: daily after a success, 60 min after a failure), so an hourly trigger catches up within an hour after the PC
was off or asleep, and retries a failed run at the next trigger.

```bat
schtasks /Create /TN "WebMonitor\ScheduledRun" /SC HOURLY /MO 1 /F ^
  /TR "\"C:\Project\OSINT_SSRISS\Assignment_week_2\web-monitor\scripts\run_scheduler_once.bat\""
schtasks /Run   /TN "WebMonitor\ScheduledRun"           & rem run now to test
schtasks /Query /TN "WebMonitor\ScheduledRun" /V /FO LIST
```

Then, in Task Scheduler → the task → Properties (settings `schtasks /Create` cannot set):

* **Settings → If the task is already running: "Do not start a new instance"**: a second guard next to the
  per-source lock file.
* **Settings → "Run task as soon as possible after a scheduled start is missed"**.
* **Settings → "Stop the task if it runs longer than" 1 hour**: far longer than a normal run (seconds), and no
  longer than `lock_max_age_minutes` (60).
* **Conditions → optionally "Wake the computer to run this task"**.
* If `python` isn't on the task account's PATH, set a user environment variable `WEB_MONITOR_PYTHON` to the full
  path of `venv\Scripts\python.exe`.

Change a schedule by editing `interval_minutes` / `retry_minutes` in `config/sources.json`. The config is re-read
every cycle, so no restart and no code change is needed.

## Tests

```powershell
venv\Scripts\python scripts\offline_pytest.py                          # main suite, outbound HTTP blocked
venv\Scripts\python scripts\offline_pytest.py assignments\week2_audit\tests   # audit suite, HTTP blocked
venv\Scripts\python -m pytest --cov=src --cov=sources          # with coverage
$env:LIVE_TESTS = "1"; venv\Scripts\python -m pytest tests\test_enrichment.py   # + the live HSS test
```

`scripts/offline_pytest.py` sets `HTTP_PROXY` / `HTTPS_PROXY` to a dead local port (`NO_PROXY=localhost,127.0.0.1`)
before pytest starts, so any test that tries the real network fails instead of passing online. It also sends the
audit suite's evidence files to a temp dir, so the frozen Week 2 evidence is never overwritten.

By default the suite never touches the network: every end-to-end test runs the real Fetcher, robots.txt handling,
pagination, enrichment, validation, SQLite and scheduler against a local HTTP(S) server (`scripts/fixture_site.py`)
that serves real saved HTML. Nothing is mocked. `LIVE_TESTS=1` enables the one live test, which requests a
mistyped HSS URL and expects a real 404; it is skipped otherwise.

## TLS certificates (`ca_bundle`)

Certificate verification is always on. The fetcher never retries with `verify=False`: a TLS failure is logged as
`FETCH_ERROR … error_type=SSLError` and fails the run.

`www.hss.iitb.ac.in` sends only its leaf certificate (`CN=iitb.ac.in`) and omits the intermediate
*GlobalSign RSA OV SSL CA 2018* (diagnosed 2026-09-26 with `openssl s_client -showcerts`: one certificate in the
chain, `verify error:num=21: unable to verify the first certificate`). Browsers and Windows schannel fetch the
missing intermediate from the leaf's AIA URL. OpenSSL, and therefore Python/requests, does not, so every request
fails with `CERTIFICATE_VERIFY_FAILED`.

The fix is the server's to make. Until then, the source's config entry sets
`"ca_bundle": "certs/iitb_ca_bundle.pem"`, which the fetcher passes to requests as `verify=<path>`. That file is
certifi's CA bundle plus `certs/globalsign_rsa_ov_ssl_ca_2018.pem` (fetched from the leaf's AIA URL; SHA-256 and
provenance in the file header; it chains to *GlobalSign Root CA - R3*, which certifi already trusts).
It adds only the one missing intermediate and trusts nothing beyond that.

* Rebuild after upgrading certifi: `python scripts/build_ca_bundle.py`.
* The intermediate expires 2028-11-21. Re-check the chain before then, or when HSS renews its certificate.
* Any source can use `ca_bundle` (a path relative to the project root; the config is rejected if the file is missing).

## Project structure

```
web-monitor/
├── config/sources.json        source registry: HSS live + local_fixture (Week 2); iit_bombay_events (live aggregator)
│                              + local_aggregator_fixture (offline aggregator) (Week 3)
├── src/                       GENERIC layer: no institution-specific code (enforced by tests/test_architecture.py)
│   ├── config.py              SourceConfig, JSON loader, adapter contract check
│   ├── fetcher.py             the only `requests` user: session, robots.txt, per-host delay, timeout, TLS, FETCH logs
│   ├── pagination.py          collect_listing: next-page walk + stop conditions
│   ├── enrich.py              detail-page fetch loop + listing/detail merge rule
│   ├── schema.py              shared record schema, assemble_record, validate_record (+ legacy Section 1-4A types)
│   ├── storage.py             the only `sqlite3` user: records (one transaction per run), content_hash, runs table
│   ├── runner.py              run_source(config): the Week 2 listing pipeline
│   ├── aggregator.py          run_aggregator(config): the Week 3 central-aggregator pipeline + entity/route helpers
│   ├── scope.py               URL scope filter (scope_decision, ScopeConfig)
│   ├── router.py              content router (classify_with_reason)
│   ├── entities.py            PersonMention / OrgMention, labelled-line extraction, name_key, matching policy
│   ├── metrics.py             run summary, coverage-drop warning, `python -m src.metrics --last`
│   ├── scheduler.py           due/retry logic, per-source lock, run records, pipeline dispatch, --once / loop CLI
│   ├── urls.py                resolve_item_url (the one canonicalizer) + synthetic_item_url
│   ├── logging_config.py      the only log-handler setup + one helper per log event
│   └── discovery/             Week 3: content -> DiscoveryRecord (never fetches)
│       ├── record.py          DiscoveryRecord (the unified discovery record)
│       ├── html.py            selector-driven listing parser (selectors come from the adapter)
│       ├── feed.py            RSS 2.0 / Atom via feedparser (bytes only, never a URL)
│       ├── sitemap.py         urlset / sitemapindex via defusedxml (+ capped child walk)
│       ├── timestamps.py      to_utc_z: RFC 822 / ISO 8601 -> "...Z"
│       └── discover.py        discover_items(source_config, client): methods from config, scope, dedup
├── sources/
│   ├── iit_bombay.py          HSS "Seminars and Talks" adapter (live source)
│   ├── iit_bombay_events.py   Week 3 aggregator adapter: IIT Bombay events calendar (selectors, labels, detail parser)
│   └── iit_bombay_legacy.py   Section 1-4A adapter for the hand-written fixtures (tests only, not in config)
├── scripts/                   fixture_site.py (local HTTP(S) server), run_fixtures.py, run_scheduler_once.bat,
│                              build_ca_bundle.py, failure_examples_run.py, live_pagination_run.py, detail_enrichment_run.py,
│                              offline_pytest.py, aggregator_fixture_site.py, make_week3_site_fixtures.py,
│                              make_week3_synthetic_fixtures.py
├── certs/                     CA bundle for HSS (see TLS above)
├── fixtures/                  iit_bombay_hss/ (real saved HTML + manifest), iit_bombay/ (legacy hand-written), tls/ (test-only certs),
│                              week3/discovery/ (feed/sitemap/listing fixtures), week3/iitb_events/ (real homepage + detail
│                              pages, offline site files)
├── tests/                     main suite (see Tests)
├── assignments/               write-ups and evidence per assignment (below); Week 3 work in assignments/week3/<NN_name>/
├── data/  locks/  logs/       runtime state (git-ignored)
├── requirements.txt  pytest.ini
```

## Assignment documents

| Assignment | Documents |
|---|---|
| 1: logging | [`01_logging/failure_examples.md`](assignments/01_logging/failure_examples.md): real log output of every failure type, regenerated by `scripts/failure_examples_run.py` |
| 3: recon / patterns | [`03_patterns/iit_bombay_structure.md`](assignments/03_patterns/iit_bombay_structure.md) |
| 4: pagination + URLs | [`04_pagination/iit_bombay_pagination_notes.md`](assignments/04_pagination/iit_bombay_pagination_notes.md), [`04_pagination/url_canonicalization_notes.md`](assignments/04_pagination/url_canonicalization_notes.md), [`04_pagination/live_run.json`](assignments/04_pagination/live_run.json) |
| 5: detail enrichment | [`05_enrichment/README.md`](assignments/05_enrichment/README.md) (live run logs + merged records) |
| 6: schema | [`06_schema/schema_review.md`](assignments/06_schema/schema_review.md), [`06_schema/records_inspected.json`](assignments/06_schema/records_inspected.json) |
| 7: shared template | [`07_template/iit_bombay_adapter_notes.md`](assignments/07_template/iit_bombay_adapter_notes.md) (+ `step5_fixture_run.log`, `step7_logging_run.log`) |
| 8: scheduling | [`08_schedule/schedule_notes.md`](assignments/08_schedule/schedule_notes.md) (+ `demo1_2_loop.log`, `demo3_overlap.log`) |
| Week 2 audit | [`week2_audit/AUDIT_REPORT.md`](assignments/week2_audit/AUDIT_REPORT.md) (audit of 2026-09-26, kept as evidence) and [`week2_audit/FIXES.md`](assignments/week2_audit/FIXES.md) (each problem → fixing commit → proving test; open items) |
| Week 3 status | [`week3/WEEK3_STATUS.md`](assignments/week3/WEEK3_STATUS.md), [`week3/DEFENSE_NOTES.md`](assignments/week3/DEFENSE_NOTES.md), [`week3/DECISIONS.md`](assignments/week3/DECISIONS.md), [`week3/OPEN_QUESTIONS.md`](assignments/week3/OPEN_QUESTIONS.md), [`week3/PROGRESS.md`](assignments/week3/PROGRESS.md), [`week3/live_requests.md`](assignments/week3/live_requests.md) |
| W3 0: candidates | [`week3/00_candidates/iit_bombay_aggregators.md`](assignments/week3/00_candidates/iit_bombay_aggregators.md) (+ `evidence/`, `recon.py`, `count_samples.py`) |
| W3 1: discovery | [`week3/01_discovery/findings.md`](assignments/week3/01_discovery/findings.md) (+ `inspect_feed.py`, `inspect_sitemap.py`) |
| W3 2: scope | [`week3/02_scope/scope_cases.md`](assignments/week3/02_scope/scope_cases.md) |
| W3 3: discovery interface | [`week3/03_discovery_interface/notes.md`](assignments/week3/03_discovery_interface/notes.md) |
| W3 4: incremental | [`week3/04_incremental/run_state_notes.md`](assignments/week3/04_incremental/run_state_notes.md) |
| W3 5: extraction | [`week3/05_extraction/notes.md`](assignments/week3/05_extraction/notes.md) (+ `fetch_sample.py`) |
| W3 6: entities | [`week3/06_entities/entity_schema.md`](assignments/week3/06_entities/entity_schema.md) (+ `build_fixture_db.py`) |
| W3 7: matching | [`week3/07_resolution/entity_matching_policy.md`](assignments/week3/07_resolution/entity_matching_policy.md) |
| W3 8: router | [`week3/08_router/router_rules.md`](assignments/week3/08_router/router_rules.md) |
| W3 9: metrics | [`week3/09_metrics/failure_signatures.md`](assignments/week3/09_metrics/failure_signatures.md) (+ `failure_signatures_run.py`) |
| W3 10: aggregator | [`week3/10_aggregator/README.md`](assignments/week3/10_aggregator/README.md), [`demo_offline.md`](assignments/week3/10_aggregator/demo_offline.md), [`live_runs.md`](assignments/week3/10_aggregator/live_runs.md) |
| W3 11: review | [`week3/11_review/self_review.md`](assignments/week3/11_review/self_review.md), [`review_template.md`](assignments/week3/11_review/review_template.md) |

## Out of scope

This was deliberately not built (Week 3 brief):
- AI, LLM or NLP extraction: entities come only from labelled lines;
- fuzzy matching: identity is exact `name_key` equality, everything else goes to a review queue;
- sentiment, ideology, political or topic classification: the router uses structure only;
- proxies, CAPTCHA or anti-bot workarounds, login bypass, distributed crawling;
- dashboards and email alerts.

Also not built this week, with the reasons logged in `assignments/week3/DECISIONS.md`:
- an announcement/news parser (announcements stay in `discovered_items`, D25);
- the full calendar-JSON listing (D11, Q2);
- deleting or expiring items that disappear (absence is only counted).