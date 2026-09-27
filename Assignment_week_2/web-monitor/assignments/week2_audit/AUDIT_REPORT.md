# Week 2 Audit: `Assignment_week_2/web-monitor`

> **Moved 2026-09-27.** This audit now lives in `assignments/week2_audit/` (it was `audit_week2/`). Paths below
> that start with `audit_week2/` refer to this folder. The report text and `logs/evidence/` are unchanged (they
> describe the code as audited on 2026-09-26); only local absolute paths were shortened to `<repo>\`, and code blocks got language tags. What was fixed since, by which commit and which test: [`FIXES.md`](FIXES.md).

Audit date: 2026-09-26 (UTC 13:30–14:00). Auditor: Claude Code, working in `audit_week2/` only.
Project root for every relative path below: `Assignment_week_2/web-monitor/` of this repository.
Nothing under `src/`, `sources/`, `config/`, `tests/` or `data/` was modified. The real DBs have the same sha256 before
and after the audit (`audit_week2/tmp/real_db_sha256_{before,after}.txt`). No file in `src/ sources/ config/ tests/ scripts/
data/ fixtures/ assignments/` is newer than the first audit file. The one side effect was 13 `.pyc` bytecode caches that
the audit's early import checks wrote into `tests/__pycache__` and `scripts/__pycache__`; they were deleted at the end
(all later runs used `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`).

**How to reproduce everything in this report** (from the project root):

```bash
python -m venv audit_week2/venv && audit_week2/venv/Scripts/python -m pip install -r audit_week2/requirements_inferred.txt pytest-cov
audit_week2/venv/Scripts/python -m pytest tests -v -p no:cacheprovider                  # Part 5
audit_week2/venv/Scripts/python -m pytest audit_week2/tests -v -p no:cacheprovider      # Part 6 (+2 extra edges)
audit_week2/venv/Scripts/python audit_week2/scripts/run_generalization.py               # Part 7 (fixtures only)
```

---

## 1. Executive summary

**Verdict: strong, genuinely layered Week 2 pipeline (A5–A8 substantively complete and well tested), undermined by repository state and a few silent-failure paths.**
Benchmark table (58 rows): **49 PASS · 4 PARTIAL · 2 FAIL · 2 DEFERRED · 1 NOT STARTED** (A9). Existing suite: **97 passed, 1 skipped** (live test; HSS host unreachable), 88 % line coverage.
Audit behaviour tests (21 required cases): **17 PASS · 3 PARTIAL · 1 FAIL**, plus 2 extra edge cases found in code review, both FAIL. Generalization: a second IIT Bombay source (ME, Drupal) needed only an adapter (79 code lines) + config; a structurally different source (CMI) also ran with zero `src/` changes but exposed 4 built-in "fake generic" assumptions.
Top 5 problems:
1. **CRITICAL: none of the Week 2 code is committed.** `src/{config,enrich,fetcher,pagination,scheduler}.py`, `sources/iit_bombay.py`, 9 test files, `config/`, and assignments 03–08 are untracked. There is also no `requirements.txt`.
2. **MAJOR: silent data loss when the detail date format changes.** `ends_at` is erased on 10/10 rows, the rows are flagged `changed`, and no WARNING is logged (case 9).
3. **MAJOR: a failed run is not retried until a full interval (24 h) has passed**, on a host documented as often unreachable (case X1).
4. **MAJOR: HTTP 200 with 0 parsed items logs a WARNING, but the run is recorded `success` with exit code 0** (case 8).
5. **MAJOR: `Fetcher` silently retries with TLS verification disabled** on any SSL error (`src/fetcher.py:107-110`); it fired on every live HSS request.

---

## 2. Benchmark table

Curriculum source: **no Week 2 curriculum file exists in this repo or anywhere else on the auditor's machine**. I searched for curriculum/README/assignment definitions. `Web_Scraping` (a folder next to this repository on the auditor's machine) holds only two week-1 scripts. The checklist below is therefore the one given in the audit brief, plus what each assignment folder's own docs state. No "Section 2" artefact exists (`assignments/` jumps 01 → 03), so it is not scored.

| # | Section / item | Status | Evidence |
|---|---|---|---|
| **S0** | **Tests + fixtures** | | |
| S0.1 | Adapter/pipeline tests on fixtures pass | PASS | `pytest tests`: 97 passed, 1 skipped (Appendix A) |
| S0.2 | Fixtures are saved real HTML, with provenance | PASS | `fixtures/iit_bombay_hss/` (listing + 10 detail pages + `detail/manifest.json` with fetch times) |
| S0.3 | Tests use real HTTP, no mock of fetch | PASS | `scripts/fixture_site.py` (ThreadingHTTPServer); `tests/test_runner.py` docstring; no `requests_mock` imports |
| **S1** | **Logging** | | |
| S1.1 | Structured, grep-able lines with stage / source / error type | PASS | `src/logging_config.py`; examples in §4.8 |
| S1.2 | One place configures handlers | PASS | `tests/test_architecture.py::test_only_logging_config_configures_handlers`; grep §5 |
| S1.3 | `failure_examples.md` with real captured logs | PARTIAL | Exists, 5 cases + baseline; log format predates the A7 refactor (no `logger=`, `source=` not `source_id=`), see §9 |
| **S3** | **Recon** | | |
| S3.1 | Structural comparison of ≥3 surfaces + template suitability | PARTIAL | `assignments/03_patterns/iit_bombay_structure.md`; HSS selectors in it (`.views-row`, `.views-field-title`) do not match the saved live HSS HTML (`.event-card-wrapper`, `.event-name a`), and its future-dated-item claim is unverified (already flagged by the author in `schedule_notes.md` §1) |
| **S4** | **Canonical URLs / pagination** | | |
| S4.1 | Single `resolve_item_url` used by every parser and the pager | PASS | `src/urls.py:47`; case 11 (6 href forms → 1 key) |
| S4.2 | Canonicalization rules + real before→after examples | PASS | `assignments/04_pagination/url_canonicalization_notes.md` (cites file:line in fetched HTML) |
| S4.3 | Pagination with stop conditions | PASS | `src/pagination.py:46-131`; case 14 (max_pages, empty page, repeated page, disabled, next-page 404) |
| S4.4 | Live pagination evidence | PASS | `assignments/04_pagination/live_run.json` (3 pages, 30 unique items) |
| S4.5 | Pagination notes consistent with code | PARTIAL | Notes lines 52-53 describe fallback selectors / anchor-text matching that do not exist in `src/pagination.py` |
| **A5** | **Detail enrichment** | | |
| 5.1 | `parse_listing(html, base_url)` | PASS | `sources/iit_bombay.py:44` |
| 5.2 | `parse_detail(html, item_url)` | PASS | `sources/iit_bombay.py:86` |
| 5.3 | `merge_listing_and_detail`: detail wins except `item_url` from the listing's canonical URL, rule documented | PASS | `src/enrich.py:17-40`; case 3 (crafted pair: detail title wins, `""`/`None` don't erase, `item_url` kept, provenance key not taken from detail) |
| 5.4 | `detail_fetch_status` ok / failed / not_attempted | PASS | `src/enrich.py:55-58`; case 3 distribution ok=10, not_attempted=10 |
| 5.5 | Controlled sample with timeout + delay | PASS | config `detail_limit 10, timeout_s 10, request_delay_s 1.5`; `enrichment_run.log` shows ~2 s spacing live |
| 5.6 | Failed detail keeps the listing record | PASS | cases 5, 6 (404, 500, timeout, connection reset) |
| 5.7 | Detail failures logged separately | PASS | logger `web_monitor.detail` / `DETAIL_FAILURE` (same stream as other logs, distinct logger and event name) |
| 5.8 | Real 404 checkpoint + test | PASS | `assignments/05_enrichment/checkpoint_404_run.log` (live 404 on mistyped URL, 2026-09-26); `tests/test_enrichment.py::test_detail_404_is_isolated`; live variant skipped (host down) |
| **A6** | **Schema review** | | |
| 6.1 | `schema_review.md` table from 10 real merged records | PASS | §(a), 27 fields with presence counts |
| 6.2 | `item_url` as the identifier, reasoned | PASS | §(b) (why not `detail_canonical_url`, why not `node_id`) |
| 6.3 | Shared vs source-specific | PASS | §(c), §(d) |
| 6.4 | Which fields are lists | PASS | §(d) `speakers` (honestly: justified by cross-source generality, 0/10 multi-speaker) |
| 6.5 | Identifiers / content / provenance | PASS | §(c) table blocks; mirrored in `src/schema.py:21-30` |
| 6.6 | Rejected field with reasoning | PASS | §(e) `image_url` (same placeholder on 10/10), `node_id`, `category` |
| 6.7 | Team alignment checkpoint | DEFERRED | §(f) states "pending peer-review confirmation"; no teammate schema available |
| 6.8 | `records_inspected.json` | PASS | 10 records |
| **A7** | **Shared template** | | |
| 7.1 | Generic fetcher | PASS | `src/fetcher.py` (only `requests` user) |
| 7.2 | Generic runner | PASS | `src/runner.py::run_source`; no institution strings (§5) |
| 7.3 | Shared storage | PASS | `src/storage.py::store_records` (table `records`) |
| 7.4 | IIT Bombay-only adapter | PASS | `sources/iit_bombay.py` (selectors + 3 functions) |
| 7.5 | Config entry | PASS | `config/sources.json` → `iit_bombay_hss_seminars` |
| 7.6 | Schema-validated output | PASS | `validate_record` in runner; case 1: 20/20 stored rows valid |
| 7.7 | Fixture tests | PASS | `tests/test_adapter_iit_bombay.py`, `test_runner.py` |
| 7.8 | Logging | PASS | START/FETCH/PARSE/ENRICH/NORMALIZE/VALIDATE/STORE/END lines, Appendix B |
| 7.9 | Controlled pagination | PASS | `max_pages: 2`; case 14 |
| 7.10 | Detail enrichment | PASS | `detail_limit: 10`; cases 3, 5, 6, 12 |
| 7.11 | `iit_bombay_adapter_notes.md` (generic / source-specific / optional / brittle) | PASS | All 4 sections present; 2 factual mismatches listed in §9 |
| 7.C | **Checkpoint:** adapter has zero DB / logger / requests re-implementation | PASS | grep §5 (no hits); `test_architecture.py` |
| 7.S1 | **Standout:** honest, specific brittle assumptions | PASS | 17-row table; cases 8 and 9 reproduce rows #2, #5, #6 exactly (row #6 is slightly optimistic, see §9) |
| 7.S2 | **Standout:** short adapter | PASS | 203 lines, 146 code lines (excluding docstrings/comments/blank) |
| 7.G | New source = adapter + config only (Part 7) | PARTIAL | ME: yes. CMI: runs with no `src/` change, but only because the server redirects `/activities`→`/activities/`; detail enrichment and date-only events are impossible without generic changes (§8) |
| **A8** | **Scheduled run** | | |
| 8.1 | Scheduling around the common runner | PASS | `src/scheduler.py:174` calls `run_source` |
| 8.2 | Fixture demo first | PASS | `assignments/08_schedule/demo1_2_loop.log` |
| 8.3 | Optional live demo | DEFERRED | HSS unreachable: author's check 2026-09-26, re-confirmed by audit `curl` timeout at 13:35:36Z |
| 8.4 | No institution selectors in scheduler | PASS | `test_scheduler_knows_only_source_ids_and_config`; grep §5 |
| 8.5 | No overlapping runs of one source | PASS | case 16 (two OS processes → `RUN_SKIPPED`) |
| 8.6 | No uncontrolled duplicates | PASS | case 2, case 11, `test_repeat_scheduled_runs_create_no_duplicates` |
| 8.7 | Runs logged | PASS | `runs` table + `RUN_START`/`RUN_END`; cases 7, 16, 18 |
| 8.8 | Failed run doesn't corrupt data | PASS | cases 7 (listing 404/500/timeout) and 18 (mid-UPDATE and mid-INSERT abort): checksums identical |
| 8.C | **Checkpoint:** schedule change without touching the parser | PASS | case 19 (temp config only; `src/`+`sources/` hashes identical) |
| 8.S1 | **Standout:** overlap prevention demonstrated with a log line | PASS | `demo3_overlap.log`; case 16 reproduces `RUN_SKIPPED … holder=pid:23448@…` |
| 8.S2 | **Standout:** crawl frequency justified from real data | PASS | case 21: every number in `schedule_notes.md` §1 recomputed exactly |
| **A9** | **Template swap with Saanvi** | NOT STARTED | `assignments/09_template_swap/` does not exist (not attempted, per brief) |
| **X** | **Cross-cutting (audit-added)** | | |
| X.1 | `requirements.txt` + fresh install | FAIL | No requirements file anywhere; fresh venv works only with an inferred list (§3.3) |
| X.2 | Week 2 work under version control | FAIL | `git status`: all new modules, tests, config and assignment docs untracked (§3.1) |
| X.3 | Existing test suite green in a fresh venv | PASS | 97 passed, 1 skipped |

---

## 3. Repository state (Part 2)

### 3.1 Git

```text
$ git branch --show-current            -> master   (up to date with origin/master)
$ git log --oneline -30
5e5d290 Merge branch 'master' of https://github.com/parso1305/OSINT_SSRISS
369c90f week_2: add web-monitor and logging logic
e0e187c Enhance DOM_map.md with formatted code blocks
566ba9c Initial commit: OSINT SSRISS project
```

`git status` (abridged; full output in `audit_week2/logs/git_status.txt`, which also lists `audit_week2/` as untracked because it was created by this audit):

* **Staged:** `renamed: sources/iit_bombay.py -> sources/iit_bombay_legacy.py`; `deleted: src/fetch.py`.
* **Modified, not staged:** `README.md`, `sources/__init__.py`, `sources/iit_bombay_legacy.py` (staged rename then edited again: half-staged), `src/{__init__,logging_config,runner,schema,storage,urls}.py`, `tests/test_iit_bombay.py`, and **11 tracked `__pycache__/*.pyc` files**.
* **Untracked (the whole Week 2 deliverable):** `src/{config,enrich,fetcher,pagination,scheduler}.py`, the new `sources/iit_bombay.py`, 9 test files, `config/`, `scripts/`, `assignments/03…08/`, `fixtures/iit_bombay_hss/`, `data/*.db`, `logs/`, plus repo-root `assignments/`, `open_db.bat`, `open_db.ps1`.
* **Flags:** no `.gitignore` (so pyc, DBs and pytest caches show up); tracked `.pyc` files; staged rename + unstaged edit on the same file. The modified, tracked `src/runner.py` imports untracked `src/config.py`, `enrich.py`, `fetcher.py` and `pagination.py`, so committing only the tracked changes would produce a tree that does not import. A clone of `origin/master` today has **none** of A5–A8.
* **Leftover locks:** `locks/` exists and is empty. No `*.lock` or `*.stale-*` anywhere.
* **TODO/FIXME/XXX/HACK:** none in `*.py`, `*.md`, `*.json` (grep exit 1).
* **Imports:** every module under `src/`, `sources/`, `scripts/` imports cleanly (`python -c "import X"` → OK for 18 modules). `import tests.test_*` fails, but only because the machine's global `site-packages` contains a stray `tests` package that shadows the repo's non-package `tests/` folder (`<module 'tests' from '...\\Python313\\Lib\\site-packages\\tests\\__init__.py'>`). All 10 test files import fine by path and under pytest. This is an environment issue, not a repo defect.

### 3.2 Directory tree (venv, `__pycache__`, `.git`, caches excluded)

```text
OSINT_SSRISS/
├── Assignment/                        Week 1 (HTTP, recon, DOM, fetch, normalization): not audited
│   └── 02_recon/IITB_recon.md         Week 1 recon, cited by schedule_notes.md
├── assignments/                       STRAY older copies of 03_patterns + 04_pagination (repo root, untracked)
├── open_db.bat / open_db.ps1          helpers: open data/events.db in sqlite3 CLI
└── Assignment_week_2/web-monitor/     ← the Week 2 project (paths below are relative to here)
    ├── README.md                      Only covers A8 (Task Scheduler setup); no overview/install/test section
    ├── config/sources.json            Source registry (2 entries: live HSS + disabled local_fixture)
    ├── src/                           GENERIC layer
    │   ├── __init__.py                re-exports collect_listing, get_next_page_url
    │   ├── config.py                  SourceConfig dataclass, JSON loader, adapter contract check
    │   ├── fetcher.py                 only `requests` user: session, UA, timeout, per-host delay, robots.txt
    │   ├── pagination.py              collect_listing / get_next_page_url (rel="next" default)
    │   ├── enrich.py                  merge_listing_and_detail + enrich_items (detail fetch loop)
    │   ├── schema.py                  shared event schema, assemble_record, validate_record (+ legacy NormalizedItem)
    │   ├── storage.py                 only `sqlite3` user: records table, content_hash, carry-forward, runs table (+ legacy items API)
    │   ├── runner.py                  run_source(config): the pipeline
    │   ├── scheduler.py               due logic, per-source lock file, runs rows, --once / loop CLI
    │   ├── logging_config.py          only handler setup + one helper per log event
    │   └── urls.py                    resolve_item_url (single canonicalizer)
    ├── sources/
    │   ├── __init__.py                docstring only (registry lives in config)
    │   ├── iit_bombay.py              HSS seminars adapter: selectors, parse_listing, parse_detail, normalize
    │   └── iit_bombay_legacy.py       Section 1–4A adapter for hand-written fixtures (not in config)
    ├── tests/                         10 files, 98 tests (see §6)
    ├── scripts/
    │   ├── fixture_site.py            local HTTP server replaying fixtures (used by tests + demos)
    │   ├── run_fixtures.py            run a configured source against fixtures
    │   ├── detail_enrichment_run.py   A5 live run + Checkpoint-5 URL mistype
    │   ├── live_pagination_run.py     A4B live 3-page crawl, saves pages
    │   └── run_scheduler_once.bat     Task Scheduler entry point (appends to logs/scheduler.log)
    ├── fixtures/
    │   ├── iit_bombay/*.html          7 hand-written legacy fixtures (Section 0–4A)
    │   └── iit_bombay_hss/            REAL: listing_2026-09-26.html, live_page_{1,2,3}.html, detail/*.html (10) + manifest.json
    ├── assignments/
    │   ├── 01_logging/failure_examples.md
    │   ├── 03_patterns/iit_bombay_structure.md
    │   ├── 04_pagination/{iit_bombay_pagination_notes.md, url_canonicalization_notes.md, live_run.json}
    │   ├── 05_enrichment/{enrichment_run.log, checkpoint_404_run.log, merged_records.json, checkpoint_404_merged.json}
    │   ├── 06_schema/{schema_review.md, records_inspected.json}
    │   ├── 07_template/{iit_bombay_adapter_notes.md, step5_fixture_run.log, step7_logging_run.log}
    │   └── 08_schedule/{schedule_notes.md, demo1_2_loop.log, demo3_overlap.log}
    ├── data/                          events.db (legacy tables only!), checkpoint5_404.db, local_fixture_demo.db
    ├── logs/scheduler.log             1 line (output of the .bat)
    ├── locks/                         empty
    └── audit_week2/                   THIS AUDIT (report, tests, sandbox adapters/config, fixtures, logs, venv)
```

### 3.3 `requirements.txt` and a fresh install

**There is no `requirements.txt` (or pyproject/setup.cfg) anywhere in the repo.** The author's own notes acknowledge it (`iit_bombay_adapter_notes.md` §0: "no requirements file declares it"). Third-party imports across `src/ sources/ scripts/ tests/` are only `requests`, `urllib3` (a requests dependency), `bs4` and `pytest`. I wrote `audit_week2/requirements_inferred.txt` (requests, beautifulsoup4, pytest; unpinned) and:

```bash
python -m venv audit_week2/venv && pip install -r requirements_inferred.txt   -> OK
pip freeze: beautifulsoup4==4.15.0 requests==2.34.2 urllib3==2.8.0 pytest==9.1.1 soupsieve==2.10 certifi==2026.7.22 ...
pytest tests -v   -> 97 passed, 1 skipped in 21.87s
```

The fresh install works, but only because the dependency set is tiny. The deliverable itself is missing.

---

## 4. Architecture (Part 3)

### 4.1 Modules, layers, sizes

| Module | Lines | Layer | Purpose |
|---|---|---|---|
| `src/urls.py` | 111 | normalize (URL) | `resolve_item_url`: resolve + canonicalize every href; dedup key |
| `src/fetcher.py` | 143 | fetch | `Fetcher.get`: robots.txt (RFC 9309, Crawl-delay), per-host delay, timeout, `FetchError` |
| `src/pagination.py` | 132 | fetch + parse orchestration | `collect_listing`: walk listing pages; stop conditions |
| `src/enrich.py` | 99 | fetch + parse orchestration | `enrich_items`, `merge_listing_and_detail` |
| `src/schema.py` | 196 | normalize/validate | shared schema constants, `assemble_record`, `validate_record` (+ legacy) |
| `src/storage.py` | 389 | persist | `store_records` (1 transaction), `content_hash`, carry-forward, runs table (+ legacy) |
| `src/runner.py` | 137 | orchestration | `run_source(config)` |
| `src/scheduler.py` | 252 | orchestration (scheduling) | due logic, `SourceLock`, `run_scheduled`, `run_once`, CLI |
| `src/config.py` | 74 | config | `SourceConfig`, `load_source_configs`, `load_adapter` |
| `src/logging_config.py` | 148 | logging | formatter, `setup_logger`, one helper per event |
| `src/__init__.py` | 4 | — | re-exports |
| `sources/iit_bombay.py` | 203 | parse + normalize (source-specific) | HSS adapter |
| `sources/iit_bombay_legacy.py` | 146 | parse + normalize (legacy) | Section 1–4A fixture adapter |
| `sources/__init__.py` | 6 | — | docstring |

### 4.2 Public API of every module (signature, docstring summary, imports)

Generated with `ast` from the source (`audit_week2/logs/api_inventory.md`). "(no docstring)" is reported as found: 21 public callables have none, mostly scheduler/storage run helpers and dataclasses.

#### `src/__init__.py` (4 lines)

*Module doc:* (none)  
*Imports:* src.pagination: get_next_page_url, collect_listing


#### `src/config.py` (74 lines)

*Module doc:* Source configuration: loads config/sources.json into SourceConfig objects.  
*Imports:* importlib; json; dataclasses: dataclass, fields; pathlib: Path; types: ModuleType; typing: Any, Optional, Union

- `class SourceConfig` — (no docstring)
- `load_adapter(adapter: Union[str, ModuleType, Any], supports_detail: bool=False) -> Any` — Imports an adapter by module path (or accepts a module-like object) and checks its contract.
- `load_source_configs(path: Union[str, Path]=DEFAULT_CONFIG_PATH) -> dict[str, SourceConfig]` — Reads the JSON config file; returns {source_id: SourceConfig}. Unknown keys are rejected.

#### `src/enrich.py` (99 lines)

*Module doc:* Detail-page enrichment: fetch each item's own page, parse it, and merge it into the listing record.  
*Imports:* logging; datetime: datetime, timezone; typing: Any, Callable, Optional; src.fetcher: FetchError; src.logging_config: log_detail_failure, log_enrich

- `merge_listing_and_detail(listing_item: dict, detail_item: dict) -> dict` — Merges a listing record with the fields parsed from that item's detail page.
- `enrich_items(listing_items: list[dict], parse_detail_fn: Callable[[str, str], dict], fetch_fn: Callable[[str], Any], source_id: str, max_items: int, logger: Optional[logging.Logger]=None) -> list[dict]` — Fetches and merges detail pages for the first max_items listing items.

#### `src/fetcher.py` (143 lines)

*Module doc:* HTTP fetching: the only module that uses requests.  
*Imports:* logging; time; dataclasses: dataclass; datetime: datetime, timezone; typing: Optional; urllib.parse: urlsplit; urllib.robotparser: RobotFileParser; requests; urllib3; src.logging_config: log_fetch, log_fetch_error

- `class FetchResult` — (no docstring)
- `class FetchError` — Any failed fetch: HTTP >= 400, network error, timeout, or disallowed by robots.txt.
  - `__init__(self, url: str, status: Optional[int], reason: str)` — (no docstring)
- `class Fetcher` — (no docstring)
  - `__init__(self, timeout_s: float=DEFAULT_TIMEOUT_SECONDS, delay_s: float=DEFAULT_DELAY_SECONDS, user_agent: str=DEFAULT_USER_AGENT, respect_robots: bool=True, logger: Optional[logging.Logger]=None)` — (no docstring)
  - `get(self, url: str)` — GET url politely. Raises FetchError on robots disallow, network error or HTTP >= 400.

#### `src/logging_config.py` (148 lines)

*Module doc:* Structured logging: the only place log handlers are configured.  
*Imports:* logging; sys; typing: Optional

- `class KeyValueFormatter` — Formats log records into timestamped [LEVEL] logger=<name> message strings.
  - `format(self, record: logging.LogRecord)` — (no docstring)
- `setup_logger(name: str='web_monitor', level: int=logging.INFO, stream: Optional[object]=None) -> logging.Logger` — Configures and returns a structured logger.
- `log_start(logger: logging.Logger, source_id: str) -> None` — Logs run start.
- `log_fetch(logger: logging.Logger, url: str, status: int, duration_ms: int) -> None` — Logs fetch step metrics.
- `log_fetch_error(logger: logging.Logger, url: str, status: Optional[int], error: Exception) -> None` — Logs a request that produced no HTTP response (network error, timeout, robots disallow).
- `log_parse(logger: logging.Logger, records_count: int) -> None` — Logs parse step metrics.
- `log_normalize(logger: logging.Logger, records_count: int) -> None` — Logs normalize step metrics.
- `log_paginate(logger: logging.Logger, pages_crawled: int, stop_reason: str) -> None` — Logs paginated listing traversal outcome.
- `log_detail_failure(logger: logging.Logger, source_id: str, item_url: str, status: Optional[int], error: Exception) -> None` — Logs a non-aborting detail-page failure (distinct from listing-level FAILURE lines).
- `log_enrich(logger: logging.Logger, ok: int, failed: int, not_attempted: int) -> None` — Logs detail enrichment outcome counts.
- `log_validation_failure(logger: logging.Logger, source_id: str, item_url: str, errors: list[str]) -> None` — Logs a record rejected by schema validation (not stored).
- `log_validate(logger: logging.Logger, valid: int, invalid: int) -> None` — Logs schema validation counts.
- `log_store(logger: logging.Logger, new_count: int, existing_count: int, changed_count: int) -> None` — Logs store step counts.
- `log_end(logger: logging.Logger, source_id: str, duration_ms: int) -> None` — Logs run completion.
- `log_warning_item(logger: logging.Logger, source_id: str, url: str, stage: str, message: str) -> None` — Logs non-aborting recoverable oddities (e.g. empty listing, missing optional field).
- `log_failure(logger: logging.Logger, source_id: str, url: str, stage: str, error: Exception) -> None` — Logs listing-level failures with source_id, url, stage, error type, and useful message.
- `log_schedule(logger: logging.Logger, source_id: str, interval_minutes: Optional[float], last_started_at: Optional[str], next_due_at: Optional[str], due: bool) -> None` — Logs the scheduling decision for one source in one cycle.
- `log_run_start(logger: logging.Logger, run_id: str, source_id: str) -> None` — (no docstring)
- `log_run_end(logger: logging.Logger, run_id: str, source_id: str, status: str, duration_ms: int, counts: Optional[dict]=None, failed_count: int=0, error: Optional[str]=None) -> None` — (no docstring)
- `log_run_skipped(logger: logging.Logger, source_id: str, reason: str, holder: str='') -> None` — (no docstring)
- `log_stale_lock(logger: logging.Logger, source_id: str, holder: str, reason: str) -> None` — (no docstring)

#### `src/pagination.py` (132 lines)

*Module doc:* Generic paginated listing traversal. The adapter only supplies how to find the next page (a CSS selector).  
*Imports:* logging; datetime: datetime, timezone; typing: Any, Callable, Optional, Protocol; urllib.parse: urlparse; bs4: BeautifulSoup; src.fetcher: FetchError; src.logging_config: log_failure; src.urls: resolve_item_url

- `class ListingParser` — A source parser: resolves item hrefs against base_url via resolve_item_url.
- `get_next_page_url(html: str, current_url: str, selector: str=DEFAULT_NEXT_PAGE_SELECTOR) -> Optional[str]` — Returns the canonical absolute URL of the first element matching selector, or None.
- `collect_listing(start_url: str, max_pages: int, fetch_fn: Callable[[str], Any], parse_fn: ListingParser, next_page_selector: Optional[str]=None, source_id: str='', logger: Optional[logging.Logger]=None) -> dict` — Walks listing pages from start_url, following next_page_selector (default: rel="next").

#### `src/runner.py` (137 lines)

*Module doc:* Generic pipeline runner: config-driven, with no source-specific code.  
*Imports:* sys; pathlib: Path; logging; time; typing: Optional; src.config: SourceConfig, load_adapter, load_source_configs, DEFAULT_CONFIG_PATH; src.enrich: enrich_items; src.fetcher: Fetcher, FetchError; src.pagination: collect_listing; src.schema: assemble_record, validate_record; src.storage: store_records; src.logging_config: setup_logger, log_start, log_end, log_parse, log_paginate, log_normalize, log_validate, log_validation_failure, log_store, log_warning_item, log_failure

- `run_source(config: SourceConfig, db_path: Optional[str]=None, logger: Optional[logging.Logger]=None, fetcher: Optional[Fetcher]=None) -> dict` — Runs one configured source end to end. A listing-level failure on page 1 raises.

#### `src/scheduler.py` (252 lines)

*Module doc:* Generic scheduler: runs each configured source through runner.run_source on its own interval.  
*Imports:* sys; pathlib: Path; json; logging; os; socket; time; uuid; datetime: datetime, timedelta, timezone; typing: Optional; src.config: SourceConfig, load_source_configs, DEFAULT_CONFIG_PATH; src.logging_config: setup_logger, log_schedule, log_run_start, log_run_end, log_run_skipped, log_stale_lock; src.runner: run_source, DEFAULT_DB_PATH; src.storage: start_run, finish_run, abandon_running_runs, last_run_started_at

- `pid_alive(pid: int) -> bool` — True if a process with this pid exists. Never signals the process.
- `class SourceLock` — Atomic per-source lock file. acquire() -> True if this process now holds it.
  - `__init__(self, source_id: str, lock_dir: Path, max_age_s: float, logger: logging.Logger)` — (no docstring)
  - `acquire(self)` — (no docstring)
  - `release(self)` — (no docstring)
- `due_grace(config: SourceConfig) -> timedelta` — Slack so a run started a few seconds after an hourly trigger is due at the next day's same trigger
- `next_due(config: SourceConfig, last_started_at: Optional[str]) -> Optional[datetime]` — None = due now (never run). Otherwise last start + interval.
- `run_scheduled(config: SourceConfig, db_path: str, lock_dir: Path, logger: logging.Logger) -> dict` — Runs one source under its lock and records the run. Never raises for a failed run.
- `run_once(config_path: Path=DEFAULT_CONFIG_PATH, db_path: str=str(DEFAULT_DB_PATH), lock_dir: Path=DEFAULT_LOCK_DIR, source_ids: Optional[list[str]]=None, force: bool=False, logger: Optional[logging.Logger]=None) -> list[dict]` — One scheduler cycle: re-reads config, runs each selected source that is due (or all, with force).
- `run_loop(tick_s: float=DEFAULT_TICK_S, max_cycles: Optional[int]=None, **kwargs) -> None` — Plain loop: one run_once cycle every tick_s seconds (max_cycles for demos/tests).
- `main(argv: Optional[list[str]]=None) -> int` — (no docstring)

#### `src/schema.py` (196 lines)

*Module doc:* Shared cross-team record schema (Assignment 6, section c) and validation.  
*Imports:* re; dataclasses: dataclass, asdict; datetime: datetime; typing: Optional, Any; src.urls: resolve_item_url

- `assemble_record(config: Any, merged: dict, normalized: dict) -> dict` — Builds a shared-schema record from generic inputs:
- `validate_record(record: dict) -> list[str]` — Returns a list of schema errors (empty list = valid).
- `class NormalizedItem` — Legacy normalized item shape (Sections 1-4A).
  - `to_dict(self)` — (no docstring)
  - `get(self, key: str, default: Any=None)` — (no docstring)
  - `keys(self)` — (no docstring)
- `normalize_event(raw_item: dict, base_url: str) -> dict` — Legacy: normalizes a raw parsed event dict (whitespace, canonical URL, ISO date).
- `normalize_events(raw_items: list[dict], base_url: str) -> list[dict]` — Legacy: normalizes a batch of raw event items.

#### `src/storage.py` (389 lines)

*Module doc:* SQLite storage: the only module that touches sqlite3.  
*Imports:* sqlite3; uuid; hashlib; json; datetime: datetime, timezone; pathlib: Path; typing: Optional, Union, Any, Literal; src.schema: CONTENT_FIELDS, IDENTIFIER_FIELDS, PROVENANCE_FIELDS

- `init_db(db_path: str) -> None` — Initializes the SQLite database with the items schema.
- `compute_content_hash(item: Union[dict, Any]) -> str` — Computes a SHA256 hash across content fields to detect modifications.
- `get_item_by_url(db_path: str, url: str) -> Optional[dict]` — Fetches an existing item by canonical URL.
- `store_item(db_path: str, item: Union[dict, Any]) -> Literal['new', 'existing', 'changed']` — Upserts an item record into the database using canonical URL as dedup key.
- `store_all(db_path: str, items: list[Union[dict, Any]]) -> dict[str, int]` — Stores a batch of items and returns counts: {'new': int, 'existing': int, 'changed': int}.
- `count_items(db_path: str) -> int` — Returns the total number of items stored in the database.
- `content_hash(record: dict) -> str` — sha256 over CONTENT fields only (schema.CONTENT_FIELDS). Provenance never feeds the hash.
- `init_records_table(db_path: str) -> None` — Creates the shared-schema `records` table keyed by canonical item_url.
- `get_record(db_path: str, item_url: str) -> Optional[dict]` — Returns the stored record for a canonical item_url, or None.
- `count_records(db_path: str, source_id: Optional[str]=None) -> int` — (no docstring)
- `store_records(db_path: str, records: list[dict]) -> dict[str, int]` — Stores a run's records in ONE transaction; returns {'new', 'existing', 'changed'} counts.
- `store_record(db_path: str, record: dict) -> Literal['new', 'existing', 'changed']` — Upserts one shared-schema record (its own transaction).
- `init_runs_table(db_path: str) -> None` — (no docstring)
- `start_run(db_path: str, source_id: str, status: str='running', error: Optional[str]=None) -> str` — Inserts a run row and returns its run_id. status='skipped' rows are finished immediately.
- `finish_run(db_path: str, run_id: str, status: str, counts: Optional[dict]=None, failed_count: int=0, error: Optional[str]=None) -> None` — (no docstring)
- `abandon_running_runs(db_path: str, source_id: str, reason: str) -> int` — Marks 'running' rows of a source as failed (their process died without finishing).
- `last_run_started_at(db_path: str, source_id: str) -> Optional[str]` — started_at of the latest non-skipped run (success, failed or running), or None.
- `list_runs(db_path: str, source_id: Optional[str]=None) -> list[dict]` — (no docstring)

#### `src/urls.py` (111 lines)

*Module doc:* URL resolution and canonicalization.  
*Imports:* re; typing: Optional; urllib.parse: urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

- `resolve_item_url(href: Optional[str], page_url: Optional[str]) -> str` — Resolves a raw href found on page_url into a canonical absolute URL.

#### `sources/__init__.py` (6 lines)

*Module doc:* Source adapters. Each module provides parse_listing, parse_detail (optional), normalize and selector  
*Imports:* 


#### `sources/iit_bombay.py` (203 lines)

*Module doc:* IIT Bombay adapter: HSS Department "Seminars and Talks" (Drupal 9 Views listing + event nodes).  
*Imports:* re; datetime: datetime, timedelta, timezone; typing: Optional; bs4: BeautifulSoup; src.urls: resolve_item_url

- `class StructuralError` — Expected container is missing: the site was redesigned or this is not an event page.
- `parse_listing(html: str, base_url: str) -> list[dict]` — Parses one listing page into raw dicts; item_url is canonicalized with resolve_item_url.
- `parse_detail(html: str, item_url: str) -> dict` — Parses one event detail page into the fields present there (raw; cleaning is normalize's job).
- `normalize(record: dict) -> dict` — Source-specific cleaning of a merged listing(+detail) record into shared-schema content fields.

#### `sources/iit_bombay_legacy.py` (146 lines)

*Module doc:* IIT Bombay source adapter and HTML parser.  
*Imports:* re; datetime: datetime; typing: Optional; bs4: BeautifulSoup; src.urls: resolve_item_url; src.schema: NormalizedItem

- `class StructuralError` — Raised when expected HTML listing container or card selectors are missing or redesigned.
- `parse_events(html: str, base_url: str=LISTING_URL) -> list[dict]` — Parses IIT Bombay event listing HTML into raw dictionaries.
- `normalize_item(raw_item: dict, base_url: str=LISTING_URL) -> NormalizedItem` — Normalizes raw parsed IIT Bombay event dictionary into NormalizedItem.

### 4.3 Data flow of one scheduled run (exact functions)

```text
python -m src.scheduler --once
 └ scheduler.main → scheduler.run_once(config_path, db, lock_dir, source_ids, force)
    ├ config.load_source_configs(path)                       JSON → {source_id: SourceConfig}; unknown keys rejected
    ├ storage.last_run_started_at(db, sid)                   latest non-skipped run (running/success/FAILED)
    ├ scheduler.next_due / due_grace → logging_config.log_schedule        "SCHEDULE … due=true|false"
    └ scheduler.run_scheduled(config, db, lock_dir, logger)
       ├ SourceLock.acquire()  (os.open O_CREAT|O_EXCL; stale → log_stale_lock)   else log_run_skipped + storage.start_run(status='skipped')
       ├ storage.abandon_running_runs (only after stale-lock recovery)
       ├ storage.start_run → log_run_start
       ├ runner.run_source(config, db_path, logger)
       │  ├ config.load_adapter(config.adapter, supports_detail)          importlib + contract check
       │  ├ fetcher.Fetcher(timeout_s, delay_s, logger.getChild("fetcher"))
       │  ├ log_start
       │  ├ pagination.collect_listing(start_url, max_pages | 1, fetch_fn=Fetcher.get,
       │  │     parse_fn=adapter.parse_listing, next_page_selector=adapter.NEXT_PAGE_SELECTOR)
       │  │     ├ Fetcher.get → _robots_for (robots.txt once per origin) → _wait_turn (max(delay, Crawl-delay)) → _request → log_fetch
       │  │     ├ adapter.parse_listing(html, base_url=final_url)  → items (+ discovered_on_url/page, listing_fetched_at)
       │  │     └ pagination.get_next_page_url(html, base_url, selector) → urls.resolve_item_url
       │  ├ log_paginate, log_parse; if 0 items → log_warning_item ("parsed 0 items")
       │  ├ enrich.enrich_items(items, adapter.parse_detail, Fetcher.get, sid, detail_limit)   [if supports_detail and detail_limit>0]
       │  │     └ per item: Fetcher.get(item_url) → adapter.parse_detail(html, item_url) → enrich.merge_listing_and_detail
       │  │        failure → log_detail_failure (logger web_monitor.detail), status 'failed'; ENRICH counts
       │  ├ adapter.normalize(merged) → schema.assemble_record(config, merged, normalized)  → log_normalize
       │  ├ schema.validate_record(record) → invalid: log_validation_failure (not stored) → log_validate
       │  ├ storage.store_records(db, valid)  → init_records_table; BEGIN IMMEDIATE;
       │  │     per record: _upsert → _carry_forward (non-ok detail keeps stored content) → content_hash → INSERT | UPDATE
       │  │     COMMIT (or ROLLBACK + re-raise) → log_store
       │  └ log_end → returns {status, counts, detail_status, records, invalid, …}
       ├ storage.finish_run(success|failed, counts, failed_count) → log_run_end
       └ SourceLock.release()
```

A listing-level exception (fetch error on page 1, `StructuralError`, normalize or store failure) is logged as `FAILURE stage=…` by the runner, re-raised, caught in `run_scheduled` (`scheduler.py:175-179`), and recorded as a `failed` run.

### 4.4 Configuration: `config/sources.json` (full contents)

```json
{
  "sources": [
    {
      "source_id": "iit_bombay_hss_seminars", "institution": "IIT Bombay",
      "organizer": "Department of Humanities and Social Sciences", "content_type": "event",
      "adapter": "sources.iit_bombay", "listing_url": "https://www.hss.iitb.ac.in/events/seminars-and-talks",
      "enabled": true, "supports_pagination": true, "max_pages": 2, "supports_detail": true, "detail_limit": 10,
      "request_delay_s": 1.5, "timeout_s": 10, "interval_minutes": 1440, "lock_max_age_minutes": 60
    },
    {
      "source_id": "local_fixture", "institution": "IIT Bombay",
      "organizer": "Department of Humanities and Social Sciences", "content_type": "event",
      "adapter": "sources.iit_bombay", "listing_url": "http://127.0.0.1:8765/events/seminars-and-talks",
      "enabled": false, "supports_pagination": true, "max_pages": 2, "supports_detail": true, "detail_limit": 3,
      "request_delay_s": 0.2, "timeout_s": 10, "interval_minutes": 3, "lock_max_age_minutes": 30
    }
  ]
}
```
(The file is JSON, not YAML. It is reproduced key for key, re-wrapped only for width.)

| Key | Meaning (`src/config.py:20-48`) |
|---|---|
| `source_id` | unique key; stored on every record and run; lock file name |
| `institution`, `organizer`, `content_type` | identity fields copied into every record by `assemble_record` (organizer only if the adapter gives none) |
| `adapter` | module path imported by `load_adapter`; must expose `parse_listing`, `normalize` (+ `parse_detail` if `supports_detail`) |
| `listing_url` | page 1 of the listing |
| `enabled` | picked up by `run_once` without `--source` |
| `supports_pagination`, `max_pages` | follow `NEXT_PAGE_SELECTOR` up to `max_pages` (≥1); otherwise 1 page |
| `supports_detail`, `detail_limit` | fetch detail pages for the first `detail_limit` items |
| `request_delay_s` | minimum gap between requests to one host (robots `Crawl-delay` wins if larger) |
| `timeout_s` | per-request timeout (>0) |
| `interval_minutes` | scheduler: due when this long since the last non-skipped run |
| `lock_max_age_minutes` | lock older than this is stale |

Unknown keys raise `ValueError` (`config.py:67-69`); duplicates raise too.

### 4.5 Shared schema (`src/schema.py:21-121`)

| Field | Type | Required | Role |
|---|---|---|---|
| `item_url` | str, canonical (must equal `resolve_item_url(item_url, "")`) | **yes** | identifier (PRIMARY KEY) |
| `source_id` | str | **yes** | identifier (from config) |
| `institution` | str | **yes** | identifier (from config) |
| `content_type` | str ∈ {`event`} | **yes** | content (from config) |
| `title` | str | **yes** | content |
| `starts_at` | str `YYYY-MM-DDTHH:MM:SSZ` | **yes** | content |
| `ends_at` | same, ≥ `starts_at` | no | content |
| `timezone` | str (IANA name) | no | content (display tz) |
| `speakers` | list of `{name: str (non-empty), affiliation: str\|null}` | no (defaults `[]`) | content |
| `venue` | str | no | content |
| `is_online` | bool \| null | no | content |
| `event_type` | str | no | content |
| `organizer` | str | no | content (adapter or config) |
| `description` | str | no | content |
| `listing_fetched_at`, `detail_fetched_at` | UTC `Z` timestamp | no | provenance |
| `detail_fetch_status` | ∈ {ok, failed, not_attempted} | effectively **yes** (validated) | provenance |
| `detail_http_status` | int \| null | no | provenance |
| `detail_error` | str \| null | no | provenance |
| `extras` | dict | no | source-specific fields |
| `content_hash`, `first_seen_at`, `last_seen_at` | added by storage | — | provenance (storage) |

### 4.6 SQLite schema (from `sqlite_master`, temp copies in `audit_week2/tmp/`)

Current pipeline (`records` + `runs`): found only in `data/local_fixture_demo.db`. **`data/events.db`, the default DB for the live source, has never been written by the A7/A8 code**: it contains only the legacy tables.

```sql
-- copy_local_fixture_demo.db
CREATE TABLE records (
  item_url TEXT PRIMARY KEY, source_id TEXT, institution TEXT, content_type TEXT, title TEXT, starts_at TEXT,
  ends_at TEXT, timezone TEXT, speakers TEXT, venue TEXT, is_online INTEGER, event_type TEXT, organizer TEXT,
  description TEXT, listing_fetched_at TEXT, detail_fetched_at TEXT, detail_fetch_status TEXT,
  detail_http_status INTEGER, detail_error TEXT, extras TEXT,
  content_hash TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'skipped')),
  new_count INTEGER, existing_count INTEGER, changed_count INTEGER, failed_count INTEGER, error TEXT)
-- indexes: sqlite_autoindex_records_1 (item_url, pk), sqlite_autoindex_runs_1 (run_id, pk). No other indexes.
-- rows: records 20, runs 7

-- copy_events.db and copy_checkpoint5_404.db (legacy, Sections 1–5)
CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE NOT NULL, title TEXT, published_at TEXT,
  date_raw TEXT, venue TEXT, description TEXT, raw_text TEXT, content_hash TEXT,
  first_seen DATETIME NOT NULL, last_seen DATETIME NOT NULL)
CREATE TABLE item_enrichment (url TEXT PRIMARY KEY, detail_fetch_status TEXT NOT NULL, detail_http_status INTEGER,
  detail_fetched_at TEXT, detail_error TEXT, merged_record TEXT NOT NULL, updated_at DATETIME NOT NULL)
-- indexes: sqlite_autoindex_items_1 (url, UNIQUE), sqlite_autoindex_item_enrichment_1 (url, pk)
-- rows: events.db items 23 / item_enrichment 10; checkpoint5_404.db items 10 / item_enrichment 10
```

Unique constraints: `records.item_url` (PK), `runs.run_id` (PK). Note that `item_url` alone is the key: there is no `(source_id, item_url)` scoping (see problem M5).

### 4.7 `content_hash`

```python
# src/storage.py:181-185
def content_hash(record: dict) -> str:
    """sha256 over CONTENT fields only (schema.CONTENT_FIELDS). Provenance never feeds the hash."""
    payload = json.dumps({field: record.get(field) for field in CONTENT_FIELDS},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
```
Fields: `content_type, title, starts_at, ends_at, timezone, speakers, venue, is_online, event_type, organizer, description`.
Excluded: identifiers (`item_url, source_id, institution`), all provenance, `extras` (so raw_text/date_raw layout noise is ignored). The hash is computed **after** `_carry_forward` (`storage.py:259-260`). The legacy `compute_content_hash` (`title|published_at|venue|description|raw_text`, `storage.py:47-58`) serves only the legacy `items` table.

### 4.8 Lock / overlap and transaction / rollback

```python
# src/scheduler.py:112-124 — SourceLock.acquire
fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)     # atomic create
except FileExistsError:
    info = self._read()                                           # {pid, host, started_at, source_id}
    reason = self._stale_reason(info)                             # max_age_exceeded | process_dead (same host)
    if not reason: return False                                   # -> RUN_SKIPPED
    log_stale_lock(...); os.replace(self.path, <name>.stale-xxxx); continue   # retry create
```
Windows liveness uses `OpenProcess` + `GetExitCodeProcess == STILL_ACTIVE` (`scheduler.py:56-68`), which deliberately avoids `os.kill(pid, 0)`: on Windows that call terminates the process.

```python
# src/storage.py:288-299 — store_records
conn = sqlite3.connect(db_path, isolation_level=None)
conn.execute("BEGIN IMMEDIATE")
for record in records: counts[_upsert(conn, record, now_iso)] += 1
conn.execute("COMMIT")
except BaseException: conn.execute("ROLLBACK"); raise
```
Run rows are written on separate connections outside this transaction, so a rolled-back run is still recorded `failed`.

### 4.9 Log format and one example of each type

Format (`logging_config.py:17-19`): `YYYY-MM-DD HH:MM:SS [LEVEL] logger=<name> EVENT key=value …`. The timestamp is **local time with no zone marker** (here IST); every DB timestamp is UTC `Z` (problem m9). Examples are real lines from the audit runs:

```text
START           2026-09-26 19:24:40 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
FETCH           2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminars-and-talks status=200 duration_ms=2
FETCH_ERROR     2026-09-26 19:24:48 [WARNING] logger=web_monitor.fetcher FETCH_ERROR url=…/tracing-success-… status=none error_type=FetchError message="ReadTimeout: … (read timeout=1.0) …"
(page)          2026-09-26 19:24:40 [INFO] logger=web_monitor Page 1 yielded 10 items
PAGINATE        2026-09-26 19:24:40 [INFO] logger=web_monitor PAGINATE pages_crawled=2 stop_reason=max_pages_reached
PARSE           2026-09-26 19:24:40 [INFO] logger=web_monitor PARSE records=20
DETAIL_FAILURE  2026-09-26 19:24:45 [WARNING] logger=web_monitor.detail DETAIL_FAILURE source_id=iit_bombay_hss_seminars item_url=…/tracing-success-indian-democracy-success-nation-building status=404 error_type=FetchError message="HTTP 404 Not Found for url: …"
ENRICH          2026-09-26 19:24:41 [INFO] logger=web_monitor ENRICH ok=10 failed=0 not_attempted=10
NORMALIZE       2026-09-26 19:24:41 [INFO] logger=web_monitor NORMALIZE records=20
VALIDATION_FAIL 2026-09-26 19:24:59 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=iit_bombay_hss_seminars item_url=…/islands-… errors="starts_at: required"
VALIDATE        2026-09-26 19:24:41 [INFO] logger=web_monitor VALIDATE valid=20 invalid=0
STORE           2026-09-26 19:24:41 [INFO] logger=web_monitor STORE new=20 existing=0 changed=0
END             2026-09-26 19:24:41 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=381
FAILURE         2026-09-26 19:24:50 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=…/events/seminars-and-talks stage=fetch error_type=FetchError message="HTTP 404 Not Found for url: …"
WARNING 0 items 2026-09-26 19:24:54 [WARNING] logger=web_monitor WARNING source_id=iit_bombay_hss_seminars url=…/events/seminars-and-talks stage=parse message="Listing returned HTTP 200 but parsed 0 items: possible silent layout change"
SCHEDULE        2026-09-26 19:24:50 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_hss_seminars interval_minutes=1440 last_started_at=2026-09-26T13:54:49Z next_due_at=2026-09-27T13:54:49Z due=true
RUN_START       2026-09-26 19:24:50 [INFO] logger=web_monitor RUN_START run_id=eec7f4260ed743f79151effb71140f26 source=iit_bombay_hss_seminars
RUN_END         2026-09-26 19:24:50 [ERROR] logger=web_monitor RUN_END run_id=eec7f426… source=iit_bombay_hss_seminars status=failed duration_ms=35 new=0 existing=0 changed=0 failed=0 error="FetchError: HTTP 404 Not Found for url: …"
RUN_SKIPPED     2026-09-26 19:25:17 [INFO] logger=web_monitor RUN_SKIPPED source=iit_bombay_hss_seminars reason=already_running holder=pid:19388@2026-09-26T13:55:17Z
STALE_LOCK      2026-09-26 19:25:22 [WARNING] logger=web_monitor STALE_LOCK source=iit_bombay_hss_seminars holder=pid:None@None reason=max_age_exceeded(age_s=10800,max_s=3600) action=removed
repeated page   2026-09-26 19:25:09 [WARNING] logger=web_monitor Page 2 repeats only already-seen items. Halting.
```
Inconsistencies: runner lines use `source_id=`, scheduler lines use `source=`; "Page N yielded" and "repeats only" lines are free text, not `EVENT key=value`. An HTTP 4xx/5xx response is logged as `FETCH … status=404` at INFO; only no-response errors produce `FETCH_ERROR`.

---

## 5. Separation checks (Part 4)

Raw output in `audit_week2/logs/separation_greps.txt`.

```text
$ grep -nE "import requests|sqlite3|basicConfig|addHandler|Session\(|open\(" sources/iit_bombay.py
exit=1                                   ← no hits (expected none)

$ word-boundary scan of src/*.py for: \biit\b iitb bombay \bhss\b drupal field-event node--type .ac.in
  event-card view-seminars icon-* humanities asia/kolkata +05:30 \bIST\b seminar
(no hits)                                ← no institution / CMS leak in the generic layer (incl. scheduler)

$ grep -nE "requests|urlopen|fetch|Fetcher|sqlite3|open\(" sources/iit_bombay.py src/urls.py
sources/iit_bombay.py:4: … Selectors verified against live HTML fetched …     ← docstring word only, not I/O

$ grep -nE "BeautifulSoup|bs4|select\(|select_one|re\.compile|parse_" src/storage.py
exit=1                                   ← storage does no parsing

$ grep -rn "BeautifulSoup" src/
src/pagination.py:7 / :27                ← generic rel="next" lookup with an adapter-supplied selector (acceptable)
```

A naive case-insensitive `grep -i "ist"` also matches `listing`/`existing`. I replaced it with the word-boundary scan above; the raw file keeps the explanation.

* **Parse functions do no network I/O:** `sources/iit_bombay.py` imports only `re`, `datetime`, `typing`, `bs4`, `src.urls` and works on the string it is given. Case 15 (garbage bytes, truncated HTML) and all fixture tests call it without a network.
* **Storage does no parsing:** confirmed above; it only JSON-encodes `speakers`/`extras`.
* **Scheduler knows only config and source ids:** it imports `src.config`, `src.logging_config`, `src.runner`, `src.storage` and stdlib only.
* **Real layering caveats (not string leaks):** the IST offset, the site title suffix and the `Z`-is-truly-UTC trust all live in the adapter, which is correct. Generic *assumptions* that are not visible to grep are listed in §8.3.

---

## 6. Existing tests and coverage (Part 5)

* `pytest tests -v` in the fresh venv: **97 passed, 1 skipped in 21.87 s** (full output: Appendix A). The skip is `test_enrichment.py::test_live_mistyped_url_is_a_real_404` (needs `LIVE_TESTS=1`).
* **LIVE_TESTS not run:** reachability check `curl --max-time 15 https://www.hss.iitb.ac.in/robots.txt` at 2026-09-26T13:35:36Z → `HTTP 000 … Connection timed out after 15012 ms (exit 28)`. This is consistent with the author's A7/A8 notes.
* Coverage (`pytest --cov=src --cov=sources`; data file kept in `audit_week2/tmp/`):

| Module | Stmts | Miss | Cover | Notable misses |
|---|---|---|---|---|
| sources/iit_bombay.py | 107 | 9 | 92 % | `_to_utc` error branches, listing-fallback parse failures |
| sources/iit_bombay_legacy.py | 67 | 2 | 97 % | |
| src/config.py | 56 | 7 | 88 % | `__post_init__` validation errors, duplicate source_id |
| src/enrich.py | 46 | 0 | 100 % | |
| src/fetcher.py | 100 | 6 | 94 % | robots unreachable / 5xx, **SSL `verify=False` fallback (untested)** |
| src/logging_config.py | 63 | 5 | 92 % | |
| src/pagination.py | 83 | 3 | 96 % | |
| src/runner.py | 75 | 20 | 73 % | parse / normalize / store FAILURE branches, `__main__` |
| src/scheduler.py | 177 | 45 | 75 % | loop mode, CLI `main`, non-Windows pid path |
| src/schema.py | 120 | 24 | 80 % | most `validate_record` error branches |
| src/storage.py | 186 | 7 | 96 % | |
| src/urls.py | 40 | 3 | 92 % | |
| **TOTAL** | 1122 | 131 | **88 %** | |

* **157 warnings**, all `ResourceWarning: unclosed database in <sqlite3.Connection>`. `with sqlite3.connect(...) as conn:` commits but never closes (problem m8).

---

## 7. Behaviour tests on IIT Bombay (Part 6)

**Setup.** `audit_week2/tests/audit_server.py` is a `ThreadingHTTPServer` in a thread that serves the saved real fixtures at the real site paths, with per-path faults: status override, replacement body (str/bytes), content-type override, sleep, and TCP RST (`SO_LINGER 0`). The real `Fetcher`, robots handling, pagination, enrichment, validation, SQLite and scheduler run unmodified; nothing is mocked. Config is the real `iit_bombay_hss_seminars` entry with `listing_url` pointed at the server and `request_delay_s=0` (localhost only). Each test writes its evidence to `audit_week2/logs/evidence/<test>.txt` **before** asserting. Final combined run: **40 passed, 8 failed** (`audit_week2/logs/pytest_audit_all.txt`); every failure below is an observed behaviour, not a test bug. One of my own expectations was wrong and was corrected: with pagination disabled the stop label is `max_pages_reached`, not `no_next_page`.

| # | Case | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| 1 | Full pipeline on fixtures | 2 pages, 20 records, all valid | pages=2 `max_pages_reached`; detail ok=10 not_attempted=10; `new=20`; 20/20 stored rows pass `validate_record`; 13 HTTP requests (robots, 2 listing, 10 detail) | PASS | `test_01…txt`; 5 full records in Appendix E |
| 2 | Second run | new=0, changed=0, rows unchanged | run2 `{'new': 0, 'existing': 20, 'changed': 0}`, rows 20 → 20 | PASS | `test_02…txt` |
| 3 | Enrichment + merge rule | detail wins; empty doesn't erase; item_url from listing; title from `<title>` | distribution ok=10/not_attempted=10; crafted merge: title=detail, venue `"Room A"` kept over `""`, description kept over `None`, `item_url` kept, forged `detail_fetch_status` ignored. Echoes page: `field-event-title`=`"Event Title Echoes of Translation: Echoes of Translation:Audibility…"` (editor typo) vs `<title>` used → normalized `"Echoes of Translation: Audibility and Relationality in Indian Jewish Women’s Songs (OUP, forthcoming 2026)"` | PASS | `test_03…txt` |
| 4 | Normalization | honorifics stripped, affiliation split, label prefixes removed, suffix stripped, UTC Z, IST display = UTC+5:30, is_online from venue | `Prof Salvatore Babones, University of Sydney` → `{name: Salvatore Babones, affiliation: University of Sydney}`; `Dr Sayan Chattopadhyay` → `Sayan Chattopadhyay`; `Abstract: The…`→`The…`, `Description: T…`→`The Bene Israel…`; 0 titles with suffix; 0 non-Z timestamps. IST checks: `Thu, 09/25/2025 - 15:30`→`2025-09-25T10:00:00Z` = stored; `Wed, 09/17/2025 - 15:00`→`09:30:00Z` = stored; `Fri, 08/22/2025 - 15:30`→`10:00:00Z` = stored. `Online Seminar`→`true`, 5 other venues → `null` | PASS | `test_04…txt` |
| 5 | Detail 404 | listing record kept, `failed`, DETAIL_FAILURE via detail logger, others continue | record stored with listing title, `starts_at` from listing date+time, `detail_fetch_status=failed`, `detail_http_status=404`; `ENRICH ok=9 failed=1`; `[WARNING] logger=web_monitor.detail DETAIL_FAILURE … status=404`; no `[ERROR]` | PASS | `test_05…txt` |
| 6 | Detail 500 / timeout / reset | same as 5 | 500: `detail_http_status=500`; timeout (server sleeps 3 s, timeout 1 s): `ReadTimeout`, status null; RST: `ConnectionResetError(10054…)`, status null. All: record kept, ok=9 | PASS | `test_06_*…txt` |
| 7 | Listing 404 / 500 / timeout | FAILURE, run failed, DB unchanged | all three: `FAILURE … stage=fetch`, `RUN_END … status=failed`, runs table `failed`; `records` sha256 and row count identical before/after (e.g. 404: `before sha256=…` = `after`, rows 20=20) | PASS | `test_07_*…txt` |
| 8 | HTML structure changed | loud or at least not "success" | **card class renamed:** 0 items, WARNING `parsed 0 items`, but `runs.status=success`, exit 0, `failed_count=0`. **Container renamed:** `StructuralError`, `FAILURE stage=parse`, run `failed` (loud, good). **Detail article renamed:** 10 × `DETAIL_FAILURE … StructuralError`, listing data kept (good). **Detail speaker field renamed:** `speakers=[]` on all 10 enriched rows, `detail_fetch_status=ok`, **no warning** | PARTIAL | `test_08_*…txt` |
| 9 | Date `UTC ISO` → `"25 September 2025"` | loud error, or at least no silent bad data | **Fresh DB:** `starts_at` still correct via listing fallback, **`ends_at` silently null on 10/10, zero WARNING lines**. **Existing DB:** `STORE new=0 existing=0 changed=10`, stored `ends_at` **erased** (`2025-09-25T11:00:00Z` → `None`), no WARNING. **Listing date also unparseable:** loud, 10 × `VALIDATION_FAILURE starts_at: required`, nothing stored; but the run is still `success` | FAIL | `test_09_*…txt` |
| 10 | Missing optional fields | record valid | speaker, location, end-date removed from detail + venue removed from card → stored, `validate_record` = `[]`, `speakers=[]`, `venue=None`, `ends_at=None` | PASS | `test_10…txt` |
| 11 | URL forms | one item_url, no duplicates | root-relative, `seminar-talk/…` (relative), `//host/…/` (protocol-relative + slash), `?utm_source=…&fbclid=…`, `#abstract`, `HTTP://HOST/events//…/` all → `http://127.0.0.1:PORT/events/seminar-talk/islands-…`; **1 row stored**. Side effect: **6 detail GETs for the one item**; counts `new=1, existing=5` on a first run | PASS (note m3) | `test_11…txt` |
| 12 | Enriched item, later detail fetch fails | not changed, description kept | 500: `changed=0`, identical hash, description kept; timeout: same; not attempted (detail_limit 0): same. **But if the listing shows a different value than the detail page** (venue `LT-101, HSS Building` vs `LT 101`) and the detail then fails → `changed=1` and venue overwritten with the listing value | PARTIAL | `test_12_*…txt` |
| 13 | Real detail change | changed=1 | `{'new': 0, 'existing': 9, 'changed': 1}`, new description stored | PASS | `test_13…txt` |
| 14 | Pagination | max_pages respected, stop on empty/repeated | max_pages=2 of 3 → 2 GETs `max_pages_reached`; empty page 2 → `empty_listing`; page 2 = page 1 → `repeated_items` + WARNING; disabled → 1 GET (label `max_pages_reached`); `?page=3` 404 with max 5 → `fetch_failed`, 30 items kept, `FAILURE` line | PASS | `test_14_*…txt` |
| 15 | Odd encoding / malformed HTML | no crash | cp1252 without charset → sniffed correctly (`Women’s`); cp1252 **declared UTF-8** → stored `Women�s` silently; truncated HTML → parsed, speaker missing, status ok; 10 KB binary garbage → `DETAIL_FAILURE StructuralError` status 200; listing latin-1 declared → fine. No crash in any | PASS (note m12) | `test_15_*…txt` |
| 16 | Two concurrent runs, same source | 2nd logs RUN_SKIPPED, runs shows it | two OS processes (`python -m src.scheduler --once --force`), listing slowed 2 s: lock `{"pid": 23448, "host": "HP", "started_at": "2026-09-26T13:45:05Z", …}`; B: `RUN_SKIPPED … reason=already_running holder=pid:23448@2026-09-26T13:45:05Z`; runs `[success, skipped]`; lock removed | PASS | `test_16…txt` |
| 17 | Stale lock | recovered with WARNING | dead PID → `STALE_LOCK … reason=process_dead(pid=15588)`, success; 3 h old live PID → `max_age_exceeded(age_s=10800,max_s=3600)`, success; corrupt JSON + old mtime → recovered; other host, fresh → skipped (correct). **`started_at` in another format (`"2026-09-26 06:00"`) → `ValueError` escapes `run_once`: whole cycle aborts, lock never cleared** | PARTIAL | `test_17_*…txt` |
| 18 | Failure mid-storage | full rollback, run failed | trigger aborts the 9th of 20 UPDATEs → sha256 `ab9be301…` before = after; trigger aborts an INSERT after 10 UPDATEs + 9 INSERTs → `3df0d3dd…` = after, rows 10 = 10; `FAILURE stage=store error_type=IntegrityError`; runs `[success, failed]` | PASS | `test_18_*…txt` |
| 19 | Schedule change via config copy only | new interval used; no parser change | interval 1440: cycle1 ran, cycle2 `due=false`; edit temp config → 0.02 min: cycle3 `due=true`, ran. 14 `src/`+`sources/` files identical by hash; real `config/sources.json` unchanged | PASS | `test_19…txt` |
| 20 | Two sources together | both run, neither blocks | both due → both success; A listing 500 → A failed, B success; A lock held → A skipped, B success; two concurrent OS processes: B done after 1.0 s while A (slowed) finished at 3.1 s, both exit 0 | PASS | `test_20…txt` |
| 21 | Crawl frequency numbers | match `schedule_notes.md` | recomputed from 30 real listing items: range `2025-01-02 → 2025-09-25 (266 days)`; per month Jan 10, Feb 3, Mar 7, Apr 2, May 0, Jun 0, Jul 2, Aug 4, Sep 2 (mean 3.3); gaps median 4, min 0, mean 9.2, max 91; 7 of 29 gaps ≤ 1 day; weekdays Wed 12, Fri 6, Thu 5, Mon 4, Tue 2, Sat 1; newest vs fetch 365 days; pager links `?page=32` → **0 mismatches**. Chosen frequency: `interval_minutes: 1440` (daily), hourly Task Scheduler trigger | PASS | `test_21…txt` |

**Extra edge cases (found reading the code, not in the list of 21):**

| # | Case | Expected | Actual | Result |
|---|---|---|---|---|
| X1 | Run fails (listing 503), site recovers, next hourly trigger | retry soon | `SCHEDULE … last_started_at=13:45:56Z next_due_at=2026-09-27T13:45:56Z due=false`: **not retried for 24 h**, because `last_run_started_at` counts failed runs (`storage.py:373-379`) | FAIL |
| X2 | Two sources whose listings contain the same URL | separate rows, or at least no churn | 10 rows total, all now owned by the 2nd source (`iit_bombay_hss_seminars=0`), `organizer` overwritten, and **`changed=10` for both sources on every cycle** | FAIL |

---

## 8. Generalization (Part 7): sandbox only

### 8.1 Candidate selection and robots.txt

Every live request (curl probes and `audit_week2/scripts/live_fetch.py`, which uses the project's own `Fetcher` with timeout 10 s, delay 2 s and robots.txt enforcement) is listed with status and timestamp in Appendix D.

| Candidate | robots.txt | Decision |
|---|---|---|
| `www.hss.iitb.ac.in` (other HSS listings) | timeout (host unreachable) | not usable |
| `www.me.iitb.ac.in/events` (IIT Bombay Mechanical Eng.) | 200, Drupal default: `Disallow: /core/ /profiles/ /admin/ /search/ /user/login …`; nothing on `/events` or `/event/`; no Crawl-delay | **chosen as (a)**: same institution, Drupal 9, `rel="next"` pager, `article.node--type-events` detail nodes |
| `www.phy.iitb.ac.in` | 200, Drupal (11) | fetched homepage + `/news-events`; theme very different, kept as recon only |
| `www.iitb.ac.in`, chem, civil, cse, ee, math | 200 (chem: `Crawl-delay: 10`; math: 404) | probed only |
| `talks.cam.ac.uk` | 200: `User-agent: ClaudeBot / anthropic-ai / GPTBot … Disallow: /` | **rejected**: the site opts out of AI agents; our UA differs, but the intent is clear |
| `www.icts.res.in`, `www.imsc.res.in` | 200, Drupal 7, `Crawl-delay: 10` | IMSc homepage fetched (the Fetcher waited ≈10–11 s between robots.txt and the page, per the timestamps in Appendix D: Crawl-delay honoured) |
| `iisc.ac.in` | 301 | not pursued |
| `www.cmi.ac.in/activities/` (Chennai Mathematical Institute) | 404 → allow-all per RFC 9309 | **chosen as (b)**: custom Apache/PHP site, no Drupal, no per-item links |

Fixtures saved once: `audit_week2/fixtures/me_iitb/listing.html` + 3 detail pages; `audit_week2/fixtures/cmi/listing.html`. CMI has **no GET-able detail pages** (abstracts are behind a POST form with a per-request nonce), so no CMI detail pages were fetched. The sandbox config `audit_week2/config/sources.json` is a copy of the real config plus two entries. `audit_week2/scripts/run_generalization.py` points their `listing_url` at a local static server, then calls the **real** `src.scheduler.run_once` → `run_source` into a temp DB (log: Appendix C). The static server reproduces one live behaviour I verified: `GET https://www.cmi.ac.in/activities` → `301 Location: https://www.cmi.ac.in/activities/` (13:53:22Z).

**Item cap:** each source made one listing request and ≤3 detail requests live. The runner has no per-run item cap, though, so the one CMI page yielded 135 parsed items (problem m7).

### 8.2 (a) IIT Bombay Mechanical Engineering events (`audit_week2/sources/me_iitb.py`)

* **Adapter size:** 103 lines, **79 code lines** (vs 146 for HSS).
* **Generic code changes needed:** **none** (`generic_files_unchanged: true`: sha256 of every file in `src/ sources/ config/` identical before/after).
* **Result:** `RUN_END … status=success new=20 existing=0 changed=0 failed=2`; 20 rows, **0 validation errors**. `detail_limit: 3` enriches the *first three* listing items. Only the first of those was among the 3 saved pages, so the other two got a local 404 → `failed`, and the listing data was kept.
* **Reuse of the HSS adapter with only a config change:** tested (`me_with_hss_adapter` entry, `adapter: sources.iit_bombay`). Result: `FAILURE stage=parse error_type=StructuralError message="…'.view-seminars-and-talks .view-content' not found…"`, run `failed`. **Not reusable**: same CMS and the same `node--type-events` detail class, but a different theme and a different listing view.
* **Schema fields unavailable on this source:** `ends_at` (only in free text), `speakers` (only in free text), `event_type`; `venue`/`description` only via detail pages.
* **3 normalized records** (the 3 saved detail pages through the generic `merge_listing_and_detail` → `normalize` → `assemble_record`; all `validate_record` = `[]`; item_url host is the local server):

```json
{"title": "Seminar by Dr. Maciej Mazur (RMIT University) – 26th Sept, 4:00–5:30 PM", "starts_at": "2025-09-26T10:30:00Z", "ends_at": null, "timezone": "Asia/Kolkata", "speakers": [], "venue": "Mechanical Engineering Department Auditorium, second floor, ME Building", "is_online": null, "event_type": null, "organizer": "Department of Mechanical Engineering", "description": "Seminar on \"RMIT-IIT Research Collaboration Opportunities in Additive Manufacturing & Beyond\" by Dr.…", "extras": {"node_id": "3306", "listing_datetime": "2025-09-26T16:00:00Z", "date_text": "26  September,  2025", "raw_href": "/event/seminar-dr-maciej-mazur-rmit-university-26th-sept-400-530-pm "}}
{"title": "Seminar on Machine learning augmented massively parallel flow solvers | Fri 26 Sep @ 2:15 pm | ME Auditorium", "starts_at": "2025-09-26T08:45:00Z", "venue": "ME Auditorium", "organizer": "Department of Mechanical Engineering", "extras": {"node_id": "3304", "listing_datetime": "2025-09-26T14:15:00Z"}}
{"title": "Talk by Dr. P.C. Jain – “Industry–Academia Collaboration: A DRDO Perspective”", "starts_at": "2026-09-28T09:30:00Z", "venue": "ME Auditorium", "description": "Talk by Dr. Prakash Chand Jain , Outstanding Scientist / Scientist 'H' and Group Director, …", "extras": {"node_id": "3696", "listing_datetime": "2026-09-28T15:00:00Z"}}
```
* **Assumptions this source exposed:**
  * **`<time datetime="…Z">` is not always UTC.** On ME the `Z` value equals the IST wall-clock time: the "4:00–5:30 PM" seminar has `16:00:00Z`, the "2:15 pm" one `14:15:00Z`. In 9 of 10 listing items that state a time, the hour matches IST, and none matches UTC. HSS's `_to_utc` (`sources/iit_bombay.py:137-147`) trusts `Z`, which is correct for HSS (case 4, 3/3 verified) but would be 5 h 30 min wrong here. The assumption lives in the adapter, not in `src/`, which is correct layering. `validate_record` (`schema.py:80-83`) can only check the format, so a wrong offset is undetectable generically.
  * Live hrefs end with a space (`"/event/slug "`). `resolve_item_url` strips it (`urls.py:73`): good.
  * The listing mixes seminars with admission notices and condolence meetings. `content_type` only allows `event` (`schema.py:34`), so there is no generic way to label or filter kinds of item.

### 8.3 (b) Chennai Mathematical Institute seminars (`audit_week2/sources/cmi_seminars.py`)

* **Adapter size:** 102 lines, **80 code lines**.
* **Generic code changes needed:** **none were made, and the run succeeded**. It only works because of server behaviour, though, and two capabilities cannot be expressed without generic changes (see the assumptions below).
* **Result:** `VALIDATE valid=127 invalid=8`, `STORE new=127`, `RUN_END status=success failed=8`. 135 items parsed from one page; 127 stored with 0 validation errors on stored rows; 8 rejected (`starts_at: required` ×7 where the page has an empty `Time:` line, `title: required` ×1 with an irregular layout).
* **3 normalized records** (stored rows):

```json
{"item_url": "https://www.cmi.ac.in/activities/show-abstract.php?absref=138&absyear=2026", "source_id": "cmi_seminars", "institution": "Chennai Mathematical Institute", "title": "Observability of eccentricity in merging black hole binaries using gravitational waves", "starts_at": "2026-10-01T05:00:00Z", "ends_at": null, "timezone": "Asia/Kolkata", "speakers": [{"name": "Mukesh Kumar Singh", "affiliation": "Cardiff University"}], "venue": "LH802", "is_online": null, "event_type": "Physics Seminar", "organizer": null, "description": null, "detail_fetch_status": "not_attempted", "extras": {"header_date": "01-10-2026", "date_raw": "Thursday, 1 October 2026", "time_raw": "10:30 am - 11:30 am", "absyear": "2026", "absref": "138"}}
{"item_url": "https://www.cmi.ac.in/activities/show-abstract.php?absref=137&absyear=2026", "title": "Studying the redshift spectrum in next-generation GW detectors", "starts_at": "2026-09-30T10:15:00Z", "speakers": [{"name": "Divyajyoti", "affiliation": "Cardiff University"}], "venue": "Lecture Hall 802", "event_type": "Physics Seminar", "extras": {"date_raw": "Wednesday, 30 September", "time_raw": "3:45pm - 4:45pm"}}
{"item_url": "https://www.cmi.ac.in/activities/show-abstract.php?absref=136&absyear=2026", "title": "Is Ideological Reversal Possible for Political Parties?", "starts_at": "2026-09-30T08:30:00Z", "speakers": [{"name": "Aman Ray", "affiliation": "Madras School of Economics"}], "venue": "LH802", "event_type": "Seminar announcement", "extras": {"time_raw": "2.00 - 3.00 p.m."}}
```
* **Schema fields unavailable:** `description` (POST-only abstract), `ends_at` (not parsed), `organizer`, `is_online` (1/127 inferred).
* **"Fake generic" assumptions this source exposed** (file:line):
  1. **Listing and item URLs are canonicalized before they are fetched.** `pagination.py:71` runs `listing_url` through `resolve_item_url`, which drops the trailing slash (`urls.py:97-98`). The run requested `/activities` and only reached the page via the server's 301. Without the redirect, my first run failed with `FAILURE … HTTP 404 … /activities`, and no config value can prevent it. `enrich.py:76` likewise fetches the canonical item_url. The identity key and the fetch URL are the same string.
  2. **Every item needs a GET-able URL, and detail enrichment is `GET item_url` only** (`enrich.py:67-79`). CMI has no item links; the abstract needs a POST with a nonce. The adapter has to synthesize an identifier (`show-abstract.php?absyear=…&absref=…`, nonce excluded), and `supports_detail` must stay off.
  3. **`starts_at` must be a full UTC timestamp** (`schema.py:32,35`). Date-only seminars (7/135 here) cannot be represented and are dropped with a WARNING; there is no date-only form and no `time_known` flag.
  4. **Pagination = follow a "next" link** (`pagination.py:46-125`). CMI archives by year (`/activities/seminars/2025/`), so the capability has to be switched off; no URL-template paging exists.
  5. **No per-run item cap** (`runner.py:68-83`): 135 items were normalized and stored from one fetch. `max_pages`/`detail_limit` bound requests, not items.
  6. Title-suffix and IST logic: **not** generic leaks (both are adapter-level); the CMI adapter needed neither.
  7. `FETCH url=` logs the requested URL, not `final_url` (`fetcher.py:138`), so the 301 hop is invisible in the run log.

---

## 9. Documentation consistency (Part 8)

| Document | Exists | Complete | Consistent with code + tests? |
|---|---|---|---|
| `assignments/05_enrichment/*` (2 logs, 2 JSON) | yes | yes (10 + 10 merged records) | **Stale format**: both logs were produced by pre-A7 code (`source=` not `source_id=`, `STORE_ENRICHMENT` event, `error_type=HTTPError`); `checkpoint_404_run.log` shows the SSL `verify=False` fallback firing on every live HSS request. The merge rule itself is documented in `src/enrich.py:17-31`; there is no separate A5 notes file |
| `06_schema/schema_review.md` | yes | yes, §(a)–(g) | Accurate for the data it inspected, but describes the **pre-A7 storage** (`items`/`item_enrichment` tables; "source_id not persisted"; "speaker stored as-is"; "content_hash inputs wrong"; "check 7 overwrite-on-failure defect"), all fixed since in `records`/`_carry_forward`/`content_hash`. There is no "superseded by A7" note, so a new reader will think these defects are live |
| `06_schema/records_inspected.json` | yes | 10 records | consistent |
| `07_template/iit_bombay_adapter_notes.md` | yes | yes (§0–5) | (1) **line 80:** config table lists `schedule: 0 6 * * *` (cron). The config has no such key (`interval_minutes: 1440`), and `load_source_configs` would reject it (`config.py:67-69`). (2) **line 109**, brittle #6: "Silent but still correct via the fallback". Only `starts_at` has a fallback; case 9 shows `ends_at` silently lost, and on an existing DB erased with `changed=10`. (3) §5 "146 lines of code": audit count 146 ✓. (4) Brittle #2 and #5 reproduced exactly by case 8 ✓ |
| `08_schedule/schedule_notes.md` | yes | yes | Every number in §1 recomputed exactly (case 21) ✓. Overlap, rollback and config-only change claims reproduced (cases 16, 18, 19) ✓. **Omission:** a failed run blocks retries for a full interval (X1), which matters given the note's own "most runs would just record failures" |
| `README.md` | yes | **no**: covers only A8 Task Scheduler setup; no overview, install, test or architecture section | Flag claims verified (`--source` works on a disabled source: `scheduler.py:199-203`; exit 1 on failure: `:245-246`). **Line 41** "Run history: `runs` table in `data/events.db`": `data/events.db` has no `runs` (or `records`) table; the scheduler has never run against the default DB |
| `01_logging/failure_examples.md` | yes | yes | Log lines predate the A7 formatter (no `logger=`, `source=iit_bombay`); Case 4 message differs from `runner.py:72`; its container `.view-events-listing` is the legacy fixture's |
| `03_patterns/iit_bombay_structure.md` | yes | yes | HSS selectors (`.views-row`, `.views-field-title`) don't match the real saved HTML |
| `04_pagination/*.md` | yes | yes | Pagination notes lines 52-53: fallback selectors / anchor-text matching don't exist (`pagination.py:14` uses `rel="next"` only). Line 92 and `url_canonicalization_notes.md:6` cite `storage.py:21` `items.url UNIQUE` (legacy table; the current key is `records.item_url` PK, `storage.py:195`) |
| "report" (final Week 2 report) | **no** | — | No report/summary file found in the repo |
| Repo-root `assignments/03_patterns`, `04_pagination` | stray copies | — | Older duplicates. `assignments/04_pagination/iit_bombay_pagination_notes.md:124` "Example 3" presents a constructed URL (`HTTPS://WWW.EE.IITB.AC.IN:443/info//news/…#abstract?utm_source=feed`) as "drawn directly from real HTML". The web-monitor copy removed it and says so honestly |

---

## 10. Problems found (ordered by severity; fixes proposed, **not applied**)

### Critical

**C1. The Week 2 deliverable is not in version control.** *Where:* repo root (`git status`, §3.1). *Impact:* `origin/master` has none of A5–A8; a reviewer cloning the repo gets a tree whose committed `src/runner.py` state predates the refactor. One accidental `git clean`/disk loss erases the work. A staged rename plus a later unstaged edit, tracked `.pyc` files and no `.gitignore` make the history noisy. *Fix:* add a `.gitignore` (`__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/*.db`, `locks/`, `logs/`, `audit_week2/venv/`), `git rm --cached` the `.pyc` files, and commit A5–A8 as separate commits.

### Major

**M1. A changed detail date format silently erases `ends_at`.** *Where:* `sources/iit_bombay.py:137-147` (`_to_utc` returns `None` for any unparseable value, without logging), `:191-192` (only `starts_at` has a fallback), `src/storage.py:241-242` (carry-forward is skipped when `detail_fetch_status == "ok"`). *Impact:* case 9: `changed=10`, `ends_at` wiped on every row, zero WARNING lines. A monitor would raise 10 false alerts and lose data. *Fix:* when a detail page yields a datetime attribute that fails to parse, log `WARNING … stage=normalize field=ends_at` and keep the listing/stored value. More generally, have `normalize` return a list of per-field parse warnings that the runner logs, and treat "ok detail but a previously non-empty field is now empty" as suspicious in `_carry_forward` (log it).

**M2. A failed run is not retried until the next full interval.** *Where:* `src/storage.py:373-379` (`last_run_started_at` counts `failed`), `src/scheduler.py:209-211`. *Impact:* X1: one listing timeout means no attempt for 24 h. The HSS host is documented as frequently unreachable, so effective detection latency becomes 48 h+. *Fix:* compute "due" from the last `success` and add a retry back-off for failures (e.g. `retry_after_minutes`, default 60, in config); log `next_due_at` accordingly.

**M3. HTTP 200 with 0 items is recorded as a successful run.** *Where:* `src/runner.py:70-72` (WARNING only), `src/scheduler.py:180-184`. *Impact:* case 8: `runs.status=success`, `failed_count=0`, exit code 0, so Task Scheduler and anyone reading `runs` see a healthy run while the parser is broken. *Fix:* return `status="degraded"` (or raise a `ZeroItemsError`) when page 1 parses to 0 items and the source has previously stored items; record it as `failed` (or add `degraded` to `RUN_STATUSES`) so exit code 1 fires.

**M4. TLS verification is silently disabled on any SSL error.** *Where:* `src/fetcher.py:107-110` (`verify=False` retry + global `urllib3.disable_warnings`). *Impact:* for every HSS request (see `checkpoint_404_run.log`), certificate validation is off: a man-in-the-middle can inject content that the monitor stores as authoritative, and the global warning suppression hides it process-wide. The branch has no test coverage. *Fix:* make it an explicit per-source opt-in (`allow_insecure_tls: false` default) or, better, add the missing intermediate CA to a `verify=<bundle>` path; log at ERROR when it is used; don't disable urllib3 warnings globally.

**M5. `item_url` alone is the primary key across all sources.** *Where:* `src/storage.py:195` (PK), `:274-277` (UPDATE overwrites `source_id`, `institution`, `organizer`). *Impact:* X2: two sources that list the same page (e.g. an institute-wide events page and a department page) take turns owning the row, `changed=N` on every run, and `count_records(source_id)` becomes wrong. This will matter as soon as teammates' sources share the DB. *Fix:* key on `(source_id, item_url)`, or keep `item_url` as the global key but move `source_id`/`organizer` to a `record_sources` link table and exclude per-source fields from the upsert.

**M6. No `requirements.txt`.** *Where:* repo root. *Impact:* reproducibility; the brief expects it. *Fix:* commit `requirements.txt` (`requests>=2.32`, `beautifulsoup4>=4.12`) + `requirements-dev.txt` (`pytest`, `pytest-cov`).

### Minor

* **m1** `src/scheduler.py:100`: `datetime.strptime(started, _TS)` is unguarded. A lock whose `started_at` is not `…Z` format raises `ValueError` out of `run_once`, aborting **every** source in that cycle, every cycle (case 17). *Fix:* catch `ValueError` and fall back to file mtime as the code already does for missing `started_at`.
* **m2** `src/storage.py:244-246`: carry-forward only fills **empty** fields. When listing and detail disagree (venue spelling) and the detail fetch fails, the listing value overwrites the detail value and flags `changed` (case 12). *Fix:* for non-ok detail status, keep stored values for fields the adapter declares detail-sourced (e.g. `DETAIL_FIELDS` constant in the adapter).
* **m3** `src/pagination.py:105-106` / `src/enrich.py:66-79`: duplicate item_urls within one run are neither removed nor enriched once. There were 6 detail GETs for one item, and the first-run counts read `new=1 existing=5` (case 11). *Fix:* dedupe by `item_url` after `collect_listing`, keeping the first occurrence.
* **m4** `src/pagination.py:71`, `src/urls.py:97-98`, `src/enrich.py:76`: canonical form (trailing slash stripped) is used as the **fetch** URL. This depends on the server redirecting (§8.3). *Fix:* fetch the raw resolved URL; use `resolve_item_url` only as the identity key.
* **m5** `src/schema.py:32,35`: no representation for date-only events (CMI 7/135 dropped). *Fix:* allow `starts_at` as `YYYY-MM-DD` with `time_known: false`, or add `starts_on`.
* **m6** `src/enrich.py:76`: detail fetch is GET-only. *Fix:* let an adapter provide `detail_request(item)` when needed (keeps the Fetcher generic).
* **m7** `src/runner.py:68-83`: no per-run item cap. *Fix:* `max_items` config key applied after `collect_listing`.
* **m8** `src/storage.py:27,63,90,162,198,222,229,320,343,354,366,376,384`: `with sqlite3.connect()` doesn't close, which caused 157 `ResourceWarning`s and can keep file handles open on Windows. *Fix:* `contextlib.closing(sqlite3.connect(...))`.
* **m9** `src/logging_config.py:18`: log timestamps are local time without a zone marker, while DB timestamps are UTC `Z`. *Fix:* `formatter.converter = time.gmtime` and a trailing `Z`.
* **m10** `src/fetcher.py:138`: `FETCH` logs the requested URL, not `final_url`. *Fix:* add `final_url=` when it differs.
* **m11** `sources/iit_bombay.py:106-108`: a renamed detail field silently yields `None` (case 8: `speakers=[]` ×10, no warning). This is documented as brittle #5. *Fix:* warn when an `ok` detail page yields no speaker **and** no `starts_at`.
* **m12** `src/fetcher.py:112-113`: encoding is sniffed only when `charset` is missing. A wrong declared charset stores `U+FFFD` silently (case 15). *Fix:* count replacement characters and log a WARNING above a threshold.
* **m13** `src/runner.py:53` + `src/pagination.py:117-119`: with pagination disabled, `stop_reason=max_pages_reached` (cosmetic). *Fix:* report `pagination_disabled`.
* **m14** Documentation drift: see §9 (adapter notes line 80 and 109, pagination notes 52-53/92, failure_examples format, schema_review stale storage, recon selectors, README line 41 and missing overview).
* **m15** Legacy code in generic modules (`src/schema.py:124-196`, `src/storage.py:21-166`, `sources/iit_bombay_legacy.py`) is kept alive for Section 1–4A tests. It enlarges the "generic" surface and keeps two hash definitions. *Fix:* move it to `legacy/` with its tests.
* **m16** `data/events.db` (the live default DB) holds only legacy tables; the A7/A8 pipeline has only ever written fixture DBs. This is expected given the dead host, but the README implies otherwise. *Fix:* say so in the README, or point the docs at `local_fixture_demo.db`.
* **m17** Repo-root `assignments/` duplicates include a constructed "real" URL example. *Fix:* delete the stray copies.

---

## 11. Genuinely good (worth highlighting to a technical reviewer)

* **The generic layer really is generic.** There are no institution strings in `src/`, and this is enforced by a test (`test_architecture.py`) rather than by convention. A second IIT Bombay department ran with a 79-code-line adapter and zero generic edits, and a completely different PHP site ran without generic edits either.
* **Honest, test-backed failure isolation.** Detail failures are per-item and never abort the run. A later failed fetch neither erases content nor raises a false change (`_carry_forward` + content-only hash; cases 12, 13), which is a subtle design and correct for the common case.
* **One transaction per run with a real proof.** Rollback is demonstrated with an actual SQLite `RAISE(ABORT)` trigger mid-batch, both by the author and independently here (case 18, identical checksums), and run rows survive the rollback.
* **Scheduler engineering beyond the brief:** atomic `O_EXCL` lock with pid + host + start time; a Windows-correct liveness check that avoids the `os.kill(pid, 0)`-terminates-the-process trap; stale-lock recovery that also marks abandoned `running` rows; a due-grace that keeps an hourly trigger from drifting a daily job; config re-read every cycle.
* **Politeness is real and verified:** robots.txt per origin (RFC 9309 semantics, including "unreachable → disallow"), `Crawl-delay` honoured (≈10–11 s wait observed on IMSc), per-host delay, timeout on every request.
* **Tests use real HTTP with no mocks**, over real saved HTML with a provenance manifest; 97 tests, 88 % coverage.
* **Evidence-driven decisions and honest docs.** The title comes from `<title>` because a live `field-event-title` has an editor typo, and the doc shows it. Every crawl-frequency number recomputes exactly. The live demo is marked deferred instead of faked. The brittle-assumption table predicted behaviours this audit then reproduced. The author also corrected an earlier fabricated-looking canonicalization example and said so.

---

## Appendices

### Appendix A: full pytest output

**A.1 Existing suite in the fresh audit venv** (`audit_week2/logs/pytest_fresh_venv.txt`)

```text
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.6.0 -- <repo>\Assignment_week_2\web-monitor\audit_week2\venv\Scripts\python.exe
rootdir: <repo>\Assignment_week_2\web-monitor
collecting ... collected 98 items

tests/test_adapter_iit_bombay.py::test_parse_listing_real_pages PASSED   [  1%]
tests/test_adapter_iit_bombay.py::test_parse_listing_redesign_fails_loudly PASSED [  2%]
tests/test_adapter_iit_bombay.py::test_parse_detail_real_page_raw_fields PASSED [  3%]
tests/test_adapter_iit_bombay.py::test_parse_detail_every_saved_page_has_every_field PASSED [  4%]
tests/test_adapter_iit_bombay.py::test_parse_detail_non_event_page_fails_loudly PASSED [  5%]
tests/test_adapter_iit_bombay.py::test_normalize_speakers_honorifics_and_affiliation PASSED [  6%]
tests/test_adapter_iit_bombay.py::test_normalize_description_label_prefixes PASSED [  7%]
tests/test_adapter_iit_bombay.py::test_normalize_title_suffix_stripped PASSED [  8%]
tests/test_adapter_iit_bombay.py::test_normalize_dates_utc_and_listing_fallback_agrees_with_detail PASSED [  9%]
tests/test_adapter_iit_bombay.py::test_normalize_is_online_only_when_stated PASSED [ 10%]
tests/test_adapter_iit_bombay.py::test_normalize_drops_rejected_image_url_and_keeps_node_id_in_extras PASSED [ 11%]
tests/test_architecture.py::test_adapter_has_no_network_storage_or_logging_setup PASSED [ 12%]
tests/test_architecture.py::test_adapter_exposes_the_contract PASSED     [ 13%]
tests/test_architecture.py::test_generic_layer_has_no_institution_specific_strings PASSED [ 14%]
tests/test_architecture.py::test_only_fetcher_uses_requests_and_only_storage_uses_sqlite PASSED [ 15%]
tests/test_architecture.py::test_only_logging_config_configures_handlers PASSED [ 16%]
tests/test_architecture.py::test_scheduler_knows_only_source_ids_and_config PASSED [ 17%]
tests/test_canonicalization.py::test_resolve_url_relative_to_absolute PASSED [ 18%]
tests/test_canonicalization.py::test_resolve_url_query_relative_pagination PASSED [ 19%]
tests/test_canonicalization.py::test_resolve_url_lowercase_scheme_and_host PASSED [ 20%]
tests/test_canonicalization.py::test_resolve_url_strip_default_ports PASSED [ 21%]
tests/test_canonicalization.py::test_resolve_url_strip_fragment_anchors PASSED [ 22%]
tests/test_canonicalization.py::test_resolve_url_strip_tracking_params PASSED [ 23%]
tests/test_canonicalization.py::test_resolve_url_protocol_relative PASSED [ 24%]
tests/test_canonicalization.py::test_resolve_url_path_duplicate_slashes PASSED [ 25%]
tests/test_canonicalization.py::test_canonical_url_deduplication_in_storage PASSED [ 26%]
tests/test_enrichment.py::test_merge_detail_wins_except_item_url PASSED  [ 27%]
tests/test_enrichment.py::test_merge_empty_detail_values_do_not_erase_listing_values PASSED [ 28%]
tests/test_enrichment.py::test_merge_item_url_not_rederived_from_detail_canonical PASSED [ 29%]
tests/test_enrichment.py::test_merge_then_normalize_keeps_correct_title_despite_bad_event_title_field PASSED [ 30%]
tests/test_enrichment.py::test_detail_404_is_isolated PASSED             [ 31%]
tests/test_enrichment.py::test_live_mistyped_url_is_a_real_404 SKIPPED   [ 32%]
tests/test_generic_source.py::test_new_source_needs_only_adapter_and_config PASSED [ 33%]
tests/test_iit_bombay.py::test_parse_expected_number_of_items PASSED     [ 34%]
tests/test_iit_bombay.py::test_parse_title PASSED                        [ 35%]
tests/test_iit_bombay.py::test_parse_url PASSED                          [ 36%]
tests/test_iit_bombay.py::test_missing_optional_field PASSED             [ 37%]
tests/test_iit_bombay.py::test_empty_listing PASSED                      [ 38%]
tests/test_iit_bombay.py::test_normalization_shape PASSED                [ 39%]
tests/test_iit_bombay.py::test_duplicate_item PASSED                     [ 40%]
tests/test_iit_bombay.py::test_changed_card_structure_fails_loudly PASSED [ 41%]
tests/test_pagination.py::test_get_next_page_url_relative_resolution PASSED [ 42%]
tests/test_pagination.py::test_get_next_page_url_page_2 PASSED           [ 43%]
tests/test_pagination.py::test_get_next_page_url_last_page_returns_none PASSED [ 44%]
tests/test_pagination.py::test_get_next_page_url_empty_or_fragment PASSED [ 45%]
tests/test_pagination.py::test_collect_listing_traversal_all_pages PASSED [ 46%]
tests/test_pagination.py::test_collect_listing_stop_condition_max_pages PASSED [ 47%]
tests/test_pagination.py::test_collect_listing_stop_condition_cycle_detection PASSED [ 48%]
tests/test_pagination.py::test_collect_listing_stop_condition_domain_mismatch_safety PASSED [ 50%]
tests/test_pagination.py::test_collect_listing_stop_condition_empty_listing_safety PASSED [ 51%]
tests/test_pagination.py::test_checkpoint_4a_duplicate_item_deduplication PASSED [ 52%]
tests/test_runner.py::test_config_entry_has_every_required_key PASSED    [ 53%]
tests/test_runner.py::test_config_rejects_unknown_keys PASSED            [ 54%]
tests/test_runner.py::test_end_to_end_on_fixtures_all_records_valid PASSED [ 55%]
tests/test_runner.py::test_second_run_is_idempotent PASSED               [ 56%]
tests/test_runner.py::test_failed_detail_fetch_keeps_listing_record PASSED [ 57%]
tests/test_runner.py::test_failed_refetch_of_enriched_item_is_not_a_change_and_keeps_content PASSED [ 58%]
tests/test_runner.py::test_real_content_change_is_detected PASSED        [ 59%]
tests/test_runner.py::test_content_hash_ignores_provenance PASSED        [ 60%]
tests/test_runner.py::test_pagination_disabled_fetches_one_page PASSED   [ 61%]
tests/test_runner.py::test_pagination_respects_max_pages PASSED          [ 62%]
tests/test_runner.py::test_pagination_stops_on_repeated_items PASSED     [ 63%]
tests/test_runner.py::test_page2_failure_is_listing_failure_and_keeps_page1 PASSED [ 64%]
tests/test_runner.py::test_page1_failure_aborts_run PASSED               [ 65%]
tests/test_runner.py::test_zero_items_guard_warns PASSED                 [ 66%]
tests/test_runner.py::test_robots_disallow_is_respected PASSED           [ 67%]
tests/test_runner.py::test_fetcher_waits_for_robots_crawl_delay PASSED   [ 68%]
tests/test_scheduler.py::test_pid_alive_is_safe_and_correct PASSED       [ 69%]
tests/test_scheduler.py::test_held_lock_skips_run_and_records_it PASSED  [ 70%]
tests/test_scheduler.py::test_stale_lock_from_dead_process_is_recovered PASSED [ 71%]
tests/test_scheduler.py::test_stale_lock_older_than_max_age_is_recovered PASSED [ 72%]
tests/test_scheduler.py::test_repeat_scheduled_runs_create_no_duplicates PASSED [ 73%]
tests/test_scheduler.py::test_not_due_until_interval_and_interval_change_is_picked_up PASSED [ 74%]
tests/test_scheduler.py::test_store_records_rolls_back_the_whole_batch PASSED [ 75%]
tests/test_scheduler.py::test_failed_run_mid_storage_leaves_data_untouched_and_is_recorded PASSED [ 76%]
tests/test_scheduler.py::test_failed_listing_fetch_is_recorded_and_changes_nothing PASSED [ 77%]
tests/test_scheduler.py::test_daily_interval_does_not_drift_behind_hourly_trigger PASSED [ 78%]
tests/test_url_resolution.py::test_root_relative_href PASSED             [ 79%]
tests/test_url_resolution.py::test_already_absolute_href PASSED          [ 80%]
tests/test_url_resolution.py::test_query_relative_href_from_real_pager PASSED [ 81%]
tests/test_url_resolution.py::test_pure_relative_href PASSED             [ 82%]
tests/test_url_resolution.py::test_protocol_relative_href PASSED         [ 83%]
tests/test_url_resolution.py::test_lowercases_scheme_and_host_but_not_path PASSED [ 84%]
tests/test_url_resolution.py::test_strips_default_ports_only PASSED      [ 85%]
tests/test_url_resolution.py::test_trailing_slash_policy PASSED          [ 86%]
tests/test_url_resolution.py::test_strips_tracking_and_session_params_keeps_semantic_ones PASSED [ 87%]
tests/test_url_resolution.py::test_fragments_stripped_unless_they_identify_content PASSED [ 88%]
tests/test_url_resolution.py::test_non_http_or_empty_hrefs_resolve_to_empty[mailto:eeoffice@ee.iitb.ac.in] PASSED [ 89%]
tests/test_url_resolution.py::test_non_http_or_empty_hrefs_resolve_to_empty[tel:+912225767401] PASSED [ 90%]
tests/test_url_resolution.py::test_non_http_or_empty_hrefs_resolve_to_empty[javascript:void(0)] PASSED [ 91%]
tests/test_url_resolution.py::test_non_http_or_empty_hrefs_resolve_to_empty[] PASSED [ 92%]
tests/test_url_resolution.py::test_non_http_or_empty_hrefs_resolve_to_empty[   ] PASSED [ 93%]
tests/test_url_resolution.py::test_idempotent PASSED                     [ 94%]
tests/test_url_resolution.py::test_real_href_pairs_resolve_to_same_canonical[/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability-https://www.hss.iitb.ac.in/events/seminars-and-talks-https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability-https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability-https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability] PASSED [ 95%]
tests/test_url_resolution.py::test_real_href_pairs_resolve_to_same_canonical[/info/news/clip_seminar_satish/-https://www.ee.iitb.ac.in/info/news/-https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/-https://www.ee.iitb.ac.in/info/news/clip_seminar_satish/-https://www.ee.iitb.ac.in/info/news/clip_seminar_satish] PASSED [ 96%]
tests/test_url_resolution.py::test_real_href_pairs_resolve_to_same_canonical[https://www.hss.iitb.ac.in/careers-https://www.hss.iitb.ac.in/events/seminars-and-talks-/careers-https://www.hss.iitb.ac.in/events/seminars-and-talks-https://www.hss.iitb.ac.in/careers] PASSED [ 97%]
tests/test_url_resolution.py::test_storage_dedups_on_canonical_url_not_raw_href PASSED [ 98%]
tests/test_url_resolution.py::test_storage_dedups_ee_trailing_slash_variants PASSED [100%]

======================= 97 passed, 1 skipped in 21.87s ========================
```

**A.2 Coverage table** (`audit_week2/logs/pytest_coverage.txt`; 97 passed, 1 skipped, 157 ResourceWarnings)

```text
Name                           Stmts   Miss  Cover   Missing
------------------------------------------------------------
sources\__init__.py                0      0   100%
sources\iit_bombay.py            107      9    92%   143-144, 146, 153, 160-161, 164, 167, 169
sources\iit_bombay_legacy.py      67      2    97%   119-120
src\__init__.py                    2      0   100%
src\config.py                     56      7    88%   40, 42, 44, 46, 48, 57, 72
src\enrich.py                     46      0   100%
src\fetcher.py                   100      6    94%   78-80, 85, 108-110
src\logging_config.py             63      5    92%   35-38, 91
src\pagination.py                 83      3    96%   42, 81-82
src\runner.py                     75     20    73%   14, 63-65, 84-86, 94-95, 124-136
src\scheduler.py                 177     45    75%   25, 55, 69-75, 92-95, 102, 118, 126-127, 134, 148, 202, 205, 221-226, 230-248, 252
src\schema.py                    120     24    80%   69, 73, 78, 83, 87, 90, 94, 99, 103, 105, 107, 110, 113, 116, 119, 147, 153-155, 158, 161, 180-181, 196
src\storage.py                   186      7    96%   83, 118-141, 305-306, 388
src\urls.py                       40      3    92%   88, 91-92
------------------------------------------------------------
TOTAL                           1122    131    88%
97 passed, 1 skipped, 157 warnings in 25.85s
```

**A.3 Audit behaviour tests** (`audit_week2/logs/pytest_audit_all.txt` holds the full output including captured logs)

```text
audit_week2/tests/test_extra_edges.py::test_x1_failed_run_is_not_retried_until_next_interval FAILED
audit_week2/tests/test_extra_edges.py::test_x2_two_sources_listing_the_same_item FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_01_full_pipeline_on_fixtures PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_02_second_run_is_idempotent PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_03_enrichment_distribution_and_merge_rule PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_04_normalization_rules PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_05_detail_404 PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_06_detail_500_timeout_reset[500] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_06_detail_500_timeout_reset[timeout] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_06_detail_500_timeout_reset[connection_reset] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_07_listing_failure_leaves_db_unchanged[404] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_07_listing_failure_leaves_db_unchanged[500] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_07_listing_failure_leaves_db_unchanged[timeout] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_08_html_structure_changed[card_class_renamed] FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_08_html_structure_changed[container_renamed] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_08_html_structure_changed[detail_article_renamed] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_08_html_structure_changed[detail_speaker_field_renamed] FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_09_date_format_changed[detail_datetime_textual] FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_09_date_format_changed[detail_datetime_textual_existing_db] FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_09_date_format_changed[detail_and_listing_dates_unparseable] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_10_missing_optional_fields PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_11_url_forms_canonicalize_to_one_item PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_12_failed_refetch_is_not_a_change[detail_500] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_12_failed_refetch_is_not_a_change[detail_timeout] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_12_failed_refetch_is_not_a_change[beyond_detail_limit] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_12_failed_refetch_is_not_a_change[listing_disagrees_with_detail] FAILED
audit_week2/tests/test_pipeline_behaviour.py::test_13_real_detail_change_is_detected PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_14_pagination[max_pages_2_of_3] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_14_pagination[empty_page_2] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_14_pagination[repeated_page_2] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_14_pagination[pagination_disabled] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_14_pagination[next_page_404] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_15_encoding_and_malformed_html[cp1252_no_charset] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_15_encoding_and_malformed_html[cp1252_declared_utf8] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_15_encoding_and_malformed_html[truncated_html] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_15_encoding_and_malformed_html[binary_garbage] PASSED
audit_week2/tests/test_pipeline_behaviour.py::test_15_encoding_and_malformed_html[listing_latin1_declared] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_16_concurrent_runs_same_source PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_17_stale_lock[dead_pid] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_17_stale_lock[old_timestamp_live_pid] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_17_stale_lock[corrupt_json_old_mtime] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_17_stale_lock[unparseable_started_at] FAILED
audit_week2/tests/test_scheduler_behaviour.py::test_17_stale_lock[other_host_fresh] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_18_failure_mid_storage_rolls_back[update_midway] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_18_failure_mid_storage_rolls_back[insert_midway] PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_19_schedule_change_via_config_only PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_20_two_sources_do_not_block_each_other PASSED
audit_week2/tests/test_scheduler_behaviour.py::test_21_crawl_frequency_numbers PASSED
======================== 8 failed, 40 passed in 56.77s ========================
```

Assertion messages of the 8 failures:

```text
E       AssertionError: a failed run should be retried on the next trigger, not after a full interval
E       assert 0 == 1
E       AssertionError: sources overwrite each other's rows
E       assert (20 == 0)
E           AssertionError: 200-with-0-items should not be a 'success' run
E           assert 'success' == 'failed'
E           AssertionError: a detail page whose speaker field vanished should at least warn
E           assert '[WARNING]' in '2026-09-26 19:24:56 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_hss_seminars interval_minutes=1440 last_started_at=never next_due_at=now due=true\n2026-09-26 19:24:56 [INFO] logger=web_monitor RUN_START run_id=8b0e00c543c24858861edfaccb4948e8 source=iit_bombay_hss_seminars\n2026-09-26 19:24:56 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminars-and-talks status=200 duration_ms=2\n2026-09-26 19:24:56 [INFO] logger=web_monitor Page 1 yielded 10 items\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminars-and-talks?page=1 status=200 duration_ms=3\n2026-09-26 19:24:56 [INFO] logger=web_monitor Page 2 yielded 10 items\n2026-09-26 19:24:56 [INFO] logger=web_monitor PAGINATE pages_crawled=2 stop_reason=max_pages_reached\n2026-09-26 19:24:56 [INFO] logger=web_monitor PARSE records=20\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=15\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetc...tatus=200 duration_ms=2\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminar-talk/prayers-and-curses-utterance-forms-political-speech-and-literary-performance status=200 duration_ms=2\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminar-talk/rortys-revolution status=200 duration_ms=2\n2026-09-26 19:24:56 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:56788/events/seminar-talk/those-four-years-history-19th-century-chinese-migration-nilgiris status=200 duration_ms=3\n2026-09-26 19:24:56 [INFO] logger=web_monitor ENRICH ok=10 failed=0 not_attempted=10\n2026-09-26 19:24:56 [INFO] logger=web_monitor NORMALIZE records=20\n2026-09-26 19:24:56 [INFO] logger=web_monitor VALIDATE valid=20 invalid=0\n2026-09-26 19:24:56 [INFO] logger=web_monitor STORE new=20 existing=0 changed=0\n2026-09-26 19:24:56 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=421\n2026-09-26 19:24:56 [INFO] logger=web_monitor RUN_END run_id=8b0e00c543c24858861edfaccb4948e8 source=iit_bombay_hss_seminars status=success duration_ms=429 new=20 existing=0 changed=0 failed=0 error=""\n'
E           AssertionError: format change produced no warning; ends_at now None
E           assert False
E           AssertionError: format change produced no warning; ends_at now None
E           assert False
E       assert (1 == 0)
E       AssertionError: a malformed lock must not crash the scheduler cycle
E       assert "ValueError: time data '2026-09-26 06:00' does not match format '%Y-%m-%dT%H:%M:%SZ'" is None
```

### Appendix B: full log of one fixture run (case 1: real config, real Fetcher, local HTTP server)

```text
2026-09-26 19:24:40 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminars-and-talks status=200 duration_ms=2
2026-09-26 19:24:40 [INFO] logger=web_monitor Page 1 yielded 10 items
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminars-and-talks?page=1 status=200 duration_ms=3
2026-09-26 19:24:40 [INFO] logger=web_monitor Page 2 yielded 10 items
2026-09-26 19:24:40 [INFO] logger=web_monitor PAGINATE pages_crawled=2 stop_reason=max_pages_reached
2026-09-26 19:24:40 [INFO] logger=web_monitor PARSE records=20
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=3
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=200 duration_ms=2
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup status=200 duration_ms=16
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/experiential-self-and-mitigation-epistemic-injustice status=200 duration_ms=12
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/embodied-translation status=200 duration_ms=26
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/gramsci-and-south-asia-dialogue-subalterns status=200 duration_ms=4
2026-09-26 19:24:40 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/translating-untranslatability-environmental-justice-and-sacredness-spivaks status=200 duration_ms=3
2026-09-26 19:24:41 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/prayers-and-curses-utterance-forms-political-speech-and-literary-performance status=200 duration_ms=20
2026-09-26 19:24:41 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/rortys-revolution status=200 duration_ms=3
2026-09-26 19:24:41 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:61279/events/seminar-talk/those-four-years-history-19th-century-chinese-migration-nilgiris status=200 duration_ms=2
2026-09-26 19:24:41 [INFO] logger=web_monitor ENRICH ok=10 failed=0 not_attempted=10
2026-09-26 19:24:41 [INFO] logger=web_monitor NORMALIZE records=20
2026-09-26 19:24:41 [INFO] logger=web_monitor VALIDATE valid=20 invalid=0
2026-09-26 19:24:41 [INFO] logger=web_monitor STORE new=20 existing=0 changed=0
2026-09-26 19:24:41 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=381
```

### Appendix C: full log of the generalization run (`audit_week2/logs/generalization_run.log`)

Sources `iit_bombay_me_events`, `cmi_seminars` and `me_with_hss_adapter` (config-only reuse check), run by the real `src.scheduler.run_once` against the saved fixtures.

```text
2026-09-26 19:23:34 [INFO] logger=web_monitor SCHEDULE source=iit_bombay_me_events interval_minutes=1440 last_started_at=never next_due_at=now due=true
2026-09-26 19:23:34 [INFO] logger=web_monitor RUN_START run_id=0daff1e1e1c2498fab0031ca2e20a52f source=iit_bombay_me_events
2026-09-26 19:23:34 [INFO] logger=web_monitor START source_id=iit_bombay_me_events
2026-09-26 19:23:34 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/events status=200 duration_ms=18
2026-09-26 19:23:34 [INFO] logger=web_monitor Page 1 yielded 20 items
2026-09-26 19:23:34 [INFO] logger=web_monitor PAGINATE pages_crawled=1 stop_reason=max_pages_reached
2026-09-26 19:23:34 [INFO] logger=web_monitor PARSE records=20
2026-09-26 19:23:34 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/event/talk-dr-pc-jain-industry-academia-collaboration-drdo-perspective status=200 duration_ms=14
2026-09-26 19:23:34 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/event/64th-convocationdepartmental-degree-award-functionddaf status=404 duration_ms=20
2026-09-26 19:23:34 [WARNING] logger=web_monitor.detail DETAIL_FAILURE source_id=iit_bombay_me_events item_url=http://127.0.0.1:65014/event/64th-convocationdepartmental-degree-award-functionddaf status=404 error_type=FetchError message="HTTP 404 Not Found for url: http://127.0.0.1:65014/event/64th-convocationdepartmental-degree-award-functionddaf"
2026-09-26 19:23:34 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/event/prof-anirban-guha-condolence-meeting status=404 duration_ms=15
2026-09-26 19:23:34 [WARNING] logger=web_monitor.detail DETAIL_FAILURE source_id=iit_bombay_me_events item_url=http://127.0.0.1:65014/event/prof-anirban-guha-condolence-meeting status=404 error_type=FetchError message="HTTP 404 Not Found for url: http://127.0.0.1:65014/event/prof-anirban-guha-condolence-meeting"
2026-09-26 19:23:34 [INFO] logger=web_monitor ENRICH ok=1 failed=2 not_attempted=17
2026-09-26 19:23:34 [INFO] logger=web_monitor NORMALIZE records=20
2026-09-26 19:23:34 [INFO] logger=web_monitor VALIDATE valid=20 invalid=0
2026-09-26 19:23:34 [INFO] logger=web_monitor STORE new=20 existing=0 changed=0
2026-09-26 19:23:34 [INFO] logger=web_monitor END source_id=iit_bombay_me_events duration_ms=141
2026-09-26 19:23:34 [INFO] logger=web_monitor RUN_END run_id=0daff1e1e1c2498fab0031ca2e20a52f source=iit_bombay_me_events status=success duration_ms=152 new=20 existing=0 changed=0 failed=2 error=""
2026-09-26 19:23:34 [INFO] logger=web_monitor SCHEDULE source=cmi_seminars interval_minutes=720 last_started_at=never next_due_at=now due=true
2026-09-26 19:23:34 [INFO] logger=web_monitor RUN_START run_id=c864f1498fda435083c05486f5231f06 source=cmi_seminars
2026-09-26 19:23:34 [INFO] logger=web_monitor START source_id=cmi_seminars
2026-09-26 19:23:34 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/activities status=200 duration_ms=31
2026-09-26 19:23:35 [INFO] logger=web_monitor Page 1 yielded 135 items
2026-09-26 19:23:35 [INFO] logger=web_monitor PARSE records=135
2026-09-26 19:23:35 [INFO] logger=web_monitor NORMALIZE records=135
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=124&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=117&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=70&absyear=2026 errors="title: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=38&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=35&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=32&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=28&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [WARNING] logger=web_monitor VALIDATION_FAILURE source_id=cmi_seminars item_url=https://www.cmi.ac.in/activities/show-abstract.php?absref=16&absyear=2026 errors="starts_at: required"
2026-09-26 19:23:35 [INFO] logger=web_monitor VALIDATE valid=127 invalid=8
2026-09-26 19:23:35 [INFO] logger=web_monitor STORE new=127 existing=0 changed=0
2026-09-26 19:23:35 [INFO] logger=web_monitor END source_id=cmi_seminars duration_ms=153
2026-09-26 19:23:35 [INFO] logger=web_monitor RUN_END run_id=c864f1498fda435083c05486f5231f06 source=cmi_seminars status=success duration_ms=164 new=127 existing=0 changed=0 failed=8 error=""
2026-09-26 19:23:35 [INFO] logger=web_monitor SCHEDULE source=me_with_hss_adapter interval_minutes=1440 last_started_at=never next_due_at=now due=true
2026-09-26 19:23:35 [INFO] logger=web_monitor RUN_START run_id=2e689dd4b8d943e19cca599a3f2e4552 source=me_with_hss_adapter
2026-09-26 19:23:35 [INFO] logger=web_monitor START source_id=me_with_hss_adapter
2026-09-26 19:23:35 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:65014/events status=200 duration_ms=16
2026-09-26 19:23:35 [ERROR] logger=web_monitor FAILURE source_id=me_with_hss_adapter url=http://127.0.0.1:65014/events stage=parse error_type=StructuralError message="Structural layout mismatch: Target container '.view-seminars-and-talks .view-content' not found in HTML. Site structure may have changed."
2026-09-26 19:23:35 [ERROR] logger=web_monitor RUN_END run_id=2e689dd4b8d943e19cca599a3f2e4552 source=me_with_hss_adapter status=failed duration_ms=56 new=0 existing=0 changed=0 failed=0 error="StructuralError: Structural layout mismatch: Target container '.view-seminars-and-talks .view-content' not found in HTML. Site structure may have changed."
```

### Appendix D: every URL fetched live during the audit (`audit_week2/logs/live_urls.tsv`)

Rows marked "(fetched by Fetcher before first page)" record the robots.txt request the project's `Fetcher` makes before a page; their timestamp is taken just before that request. The 13:46:58 ME row belongs to a first helper invocation that fetched the ME homepage but crashed while saving it (my helper bug, fixed); that page request is the 13:47:01 row. Total live requests: 9 curl robots probes (8 IIT Bombay hosts + HSS timeout), 5 curl probes of other institutions, 2 extra curl checks (ME raw bytes, CMI redirect), and 11 Fetcher page requests plus 9 robots.txt requests by the Fetcher (once per host per invocation). The ME listing was therefore requested twice: once by the Fetcher (saved as the fixture) and once raw via curl to check its bytes and charset. Same-host spacing was ≥ 2 s (≥ 10 s where a Crawl-delay applied).

| timestamp (UTC) | URL | status | note |
|---|---|---|---|
| 2026-09-26T13:35:36Z | https://www.hss.iitb.ac.in/robots.txt | 000 | curl --max-time 15: timeout (exit 28); HSS unreachable, LIVE_TESTS not run |
| 2026-09-26T13:46:11Z | https://www.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.me.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.phy.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.chem.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.civil.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.cse.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.ee.iitb.ac.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:46:11Z | https://www.math.iitb.ac.in/robots.txt | 404 | curl --max-time 10 probe |
| 2026-09-26T13:46:58Z | https://www.me.iitb.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:47:01Z | https://www.me.iitb.ac.in/robots.txt | 200 | robots check by Fetcher |
| 2026-09-26T13:47:01Z | https://www.me.iitb.ac.in/ | 200 | saved fixtures/recon/www.me.iitb.ac.in__index.html |
| 2026-09-26T13:47:14Z | https://www.phy.iitb.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:47:17Z | https://www.phy.iitb.ac.in/ | 200 | saved fixtures/recon/www.phy.iitb.ac.in__index.html (183778 chars) final_url=https://www.phy.iitb.ac.in/ |
| 2026-09-26T13:47:45Z | https://www.phy.iitb.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:47:47Z | https://www.phy.iitb.ac.in/news-events | 200 | saved fixtures/recon/www.phy.iitb.ac.in__news-events.html (145746 chars) final_url=https://www.phy.iitb.ac.in/news-events |
| 2026-09-26T13:47:47Z | https://www.me.iitb.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:47:50Z | https://www.me.iitb.ac.in/events | 200 | saved fixtures/recon/www.me.iitb.ac.in__events.html (37474 chars) final_url=https://www.me.iitb.ac.in/events |
| 2026-09-26T13:48:27Z | https://www.me.iitb.ac.in/events | 200 | curl raw bytes + headers (encoding check) |
| 2026-09-26T13:48:46Z | https://www.me.iitb.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:48:48Z | https://www.me.iitb.ac.in/event/seminar-dr-maciej-mazur-rmit-university-26th-sept-400-530-pm | 200 | saved fixtures/me_iitb/detail/www.me.iitb.ac.in__event__seminar-dr-maciej-mazur-rmit-university-26th-sept-400-530-pm.html (30225 chars) final_url=https://www.me.iitb.ac.in/event/seminar-dr-maciej-mazur-rmit-university-26th-sept-400-530-pm |
| 2026-09-26T13:48:50Z | https://www.me.iitb.ac.in/event/seminar-machine-learning-augmented-massively-parallel-flow-solvers-fri-26-sep-215-pm-me | 200 | saved fixtures/me_iitb/detail/www.me.iitb.ac.in__event__seminar-machine-learning-augmented-massively-parallel-flow-solvers-fri-26-sep-215-pm-me.html (33613 chars) final_url=https://www.me.iitb.ac.in/event/seminar-machine-learning-augmented-massively-parallel-flow-solvers-fri-26-sep-215-pm-me |
| 2026-09-26T13:48:52Z | https://www.me.iitb.ac.in/event/talk-dr-pc-jain-industry-academia-collaboration-drdo-perspective | 200 | saved fixtures/me_iitb/detail/www.me.iitb.ac.in__event__talk-dr-pc-jain-industry-academia-collaboration-drdo-perspective.html (29440 chars) final_url=https://www.me.iitb.ac.in/event/talk-dr-pc-jain-industry-academia-collaboration-drdo-perspective |
| 2026-09-26T13:49:30Z | https://www.imsc.res.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:49:30Z | https://iisc.ac.in/robots.txt | 301 | curl --max-time 10 probe |
| 2026-09-26T13:49:30Z | https://www.icts.res.in/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:49:30Z | https://www.cmi.ac.in/robots.txt | 404 | curl --max-time 10 probe |
| 2026-09-26T13:49:30Z | https://talks.cam.ac.uk/robots.txt | 200 | curl --max-time 10 probe |
| 2026-09-26T13:49:47Z | https://www.cmi.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:49:50Z | https://www.cmi.ac.in/ | 200 | saved fixtures/recon/www.cmi.ac.in__index.html (6880 chars) final_url=https://www.cmi.ac.in/ |
| 2026-09-26T13:49:50Z | https://www.imsc.res.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:50:01Z | https://www.imsc.res.in/ | 200 | saved fixtures/recon/www.imsc.res.in__index.html (60271 chars) final_url=https://www.imsc.res.in/ |
| 2026-09-26T13:50:12Z | https://www.cmi.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:50:14Z | https://www.cmi.ac.in/events/ | 200 | saved fixtures/recon/www.cmi.ac.in__events.html (38630 chars) final_url=https://www.cmi.ac.in/events/ |
| 2026-09-26T13:50:31Z | https://www.cmi.ac.in/robots.txt | (fetched by Fetcher before first page) | robots check |
| 2026-09-26T13:50:33Z | https://www.cmi.ac.in/activities/ | 200 | saved fixtures/recon/www.cmi.ac.in__activities.html (93807 chars) final_url=https://www.cmi.ac.in/activities/ |
| 2026-09-26T13:53:22Z | https://www.cmi.ac.in/activities | 301 | curl, no redirect follow: checks whether the slash-stripped listing URL redirects; Location=https://www.cmi.ac.in/activities/ |

### Appendix E: 5 stored records from case 1, all fields

```json
{
 "item_url": "http://127.0.0.1:61279/events/seminar-talk/ambedkar-subcontinental-philosopher",
 "source_id": "iit_bombay_hss_seminars",
 "institution": "IIT Bombay",
 "content_type": "event",
 "title": "Ambedkar as Subcontinental Philosopher",
 "starts_at": "2025-03-26T10:00:00Z",
 "ends_at": null,
 "timezone": "Asia/Kolkata",
 "speakers": [],
 "venue": "HSS Seminar Room, Department of HSS",
 "is_online": null,
 "event_type": "Seminar / Talk",
 "organizer": "Department of Humanities and Social Sciences",
 "description": null,
 "listing_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetched_at": null,
 "detail_fetch_status": "not_attempted",
 "detail_http_status": null,
 "detail_error": null,
 "extras": {
  "date_raw": "26th Mar 2025",
  "discovered_on_page": 2,
  "discovered_on_url": "http://127.0.0.1:61279/events/seminars-and-talks?page=1",
  "raw_href": "/events/seminar-talk/ambedkar-subcontinental-philosopher",
  "raw_text": "26 Mar 2025 Seminar / Talk Ambedkar as Subcontinental Philosopher 26th Mar 2025 15:30 PM HSS Seminar Room, Department of HSS",
  "time_raw": "15:30 PM"
 },
 "content_hash": "2b21752067a4cd52b2142c727e65d7f05c7f66b61c99d2277c6611f7d09830a3",
 "first_seen_at": "2026-09-26T13:54:41Z",
 "last_seen_at": "2026-09-26T13:54:41Z"
}
{
 "item_url": "http://127.0.0.1:61279/events/seminar-talk/echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup",
 "source_id": "iit_bombay_hss_seminars",
 "institution": "IIT Bombay",
 "content_type": "event",
 "title": "Echoes of Translation: Audibility and Relationality in Indian Jewish Women’s Songs (OUP, forthcoming 2026)",
 "starts_at": "2025-08-22T10:00:00Z",
 "ends_at": "2025-08-22T12:30:00Z",
 "timezone": "Asia/Kolkata",
 "speakers": [
  {
   "affiliation": null,
   "name": "Anna C. Schultz"
  }
 ],
 "venue": "HSS Seminar Room, Department of HSS",
 "is_online": null,
 "event_type": "Seminar / Talk",
 "organizer": "Department of Humanities and Social Sciences",
 "description": "The Bene Israel are a Jewish community from western India who, over centuries, developed a distinctive identity in relation to other Jewish and non-Jewish communities, translating their sounds, words, and practices to have uniquely Marathi Jewish meanings. Some men sing Marathi Jewish songs, but over the past half century, women have assumed the important cultural role of stewarding these songs for the future. As author Anna C. Schultz demonstrates, the Bene Israel women are translators who creatively mediate the worlds around them through song; while they may not always be visible, they are audible, and this book amplifies their relational soundings. Schultz explores sonic translation among the Bene Israel through the metaphor of the echo: a resonant, transformative, relational phenomenon. The voices of Bene Israel women today, like Ovid’s Echo, resonate empathically with loved ones they have survived, and, faintly, with those they never knew. Singing this repertoire teaches singers and listeners not only how to be Jewish, but how to be Bene Israel. It also fosters sociality, providing a medium through which women echo one another, sharing cultural expertise while securing affective ties. But women also echo with one another, that is, they collectively and audibly translate sacred texts as embodied experience in the here and now. Women’s repertories and practices were shaped in a richly diverse context, coloured by interlinguistic translation between Hebrew, Marathi, Hindi, and English, as well as by other forms of cultural translation: translations from Cochin and Baghdadi Jewish to Bene Israel practice, Christian and Hindu religious discourse to Jewish religious discourse, from one ritual context to another, from men to women, from the written page to embodied performance, and from the past to the present.",
 "listing_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetch_status": "ok",
 "detail_http_status": 200,
 "detail_error": null,
 "extras": {
  "date_raw": "22nd Aug 2025",
  "detail_canonical_url": "https://www.hss.iitb.ac.in/events/seminar-talk/echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup",
  "discovered_on_page": 1,
  "discovered_on_url": "http://127.0.0.1:61279/events/seminars-and-talks",
  "node_id": "2704",
  "raw_href": "/events/seminar-talk/echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup",
  "raw_text": "22 Aug 2025 Seminar / Talk Echoes of Translation: Audibility and Relationality in Indian Jewish Women’s Songs (OUP, forthcoming 2026) 22nd Aug 2025 15:30 PM HSS Seminar Room, Department of HSS",
  "time_raw": "15:30 PM"
 },
 "content_hash": "019c7cf1d0bd0552e65e7e62fc05772008b3c06c9e2c3de894a1c39b7be6df0c",
 "first_seen_at": "2026-09-26T13:54:41Z",
 "last_seen_at": "2026-09-26T13:54:41Z"
}
{
 "item_url": "http://127.0.0.1:61279/events/seminar-talk/embodied-translation",
 "source_id": "iit_bombay_hss_seminars",
 "institution": "IIT Bombay",
 "content_type": "event",
 "title": "Embodied Translation",
 "starts_at": "2025-08-26T09:30:00Z",
 "ends_at": "2025-08-26T11:30:00Z",
 "timezone": "Asia/Kolkata",
 "speakers": [
  {
   "affiliation": null,
   "name": "Anna C. Schultz"
  }
 ],
 "venue": "HSS Seminar Room, Department of HSS",
 "is_online": null,
 "event_type": "Seminar / Talk",
 "organizer": "Department of Humanities and Social Sciences",
 "description": "This seminar introduces my concept of embodied translation to describe how women make religious and cultural meaning not only through language, but also through voice, emotion, memory, and ritual. Embodied translation is discursive and performative; it goes beyond interlingual translation and is more specific than “cultural translation.” Embodied translation transforms speech into song (and vice versa) and extends into domains not traditionally considered semiotic, such as embodied habits, religious practice, and emotions, which in turn produce further habits, practices, and emotions. This ongoing process of translation exists in a political field of power marked by the malleability, contestation, and negotiation of signs. To provide context for this heuristic, we will discuss portions of the following readings: Roman Jakobson, “On Linguistic Aspects of Translation,” in On Translation, ed. Reuben Arthur Brower (Cambridge: Harvard University Press, 1959), 232–239. Talal Asad,Secular Translations: Nation-State, Modern Self, and Calculative Reason(New York: Columbia University Press, 2018), pp. 4–6. Tony Perman,Signs of the Spirit: Music and the Experience of Meaning in Ndau Ceremonial Life(Urbana, Chicago, Springfield: University of Illinois Press, 2020), 76. Case studies: Bene Israel kirtan, a Tamil Christian hymn.",
 "listing_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetch_status": "ok",
 "detail_http_status": 200,
 "detail_error": null,
 "extras": {
  "date_raw": "26th Aug 2025",
  "detail_canonical_url": "https://www.hss.iitb.ac.in/events/seminar-talk/embodied-translation",
  "discovered_on_page": 1,
  "discovered_on_url": "http://127.0.0.1:61279/events/seminars-and-talks",
  "node_id": "2702",
  "raw_href": "/events/seminar-talk/embodied-translation",
  "raw_text": "26 Aug 2025 Seminar / Talk Embodied Translation 26th Aug 2025 15:00 PM HSS Seminar Room, Department of HSS",
  "time_raw": "15:00 PM"
 },
 "content_hash": "7e2b48a032d65c78d5368f3511a82c9556f845ff414e19a7828db6f91556b75d",
 "first_seen_at": "2026-09-26T13:54:41Z",
 "last_seen_at": "2026-09-26T13:54:41Z"
}
{
 "item_url": "http://127.0.0.1:61279/events/seminar-talk/emotion-and-action",
 "source_id": "iit_bombay_hss_seminars",
 "institution": "IIT Bombay",
 "content_type": "event",
 "title": "Emotion and Action",
 "starts_at": "2025-02-24T05:30:00Z",
 "ends_at": null,
 "timezone": "Asia/Kolkata",
 "speakers": [],
 "venue": "Seminar Room No. 3, VMCC, IIT Bombay",
 "is_online": null,
 "event_type": "Seminar / Talk",
 "organizer": "Department of Humanities and Social Sciences",
 "description": null,
 "listing_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetched_at": null,
 "detail_fetch_status": "not_attempted",
 "detail_http_status": null,
 "detail_error": null,
 "extras": {
  "date_raw": "24th Feb 2025",
  "discovered_on_page": 2,
  "discovered_on_url": "http://127.0.0.1:61279/events/seminars-and-talks?page=1",
  "raw_href": "/events/seminar-talk/emotion-and-action",
  "raw_text": "24 Feb 2025 Seminar / Talk Emotion and Action 24th Feb 2025 11:00 AM Seminar Room No. 3, VMCC, IIT Bombay",
  "time_raw": "11:00 AM"
 },
 "content_hash": "a56937818596da789e5daee2021e6a414902832884934808c9092a7f0d3699bb",
 "first_seen_at": "2026-09-26T13:54:41Z",
 "last_seen_at": "2026-09-26T13:54:41Z"
}
{
 "item_url": "http://127.0.0.1:61279/events/seminar-talk/english-studies-india-its-past-and-its-future",
 "source_id": "iit_bombay_hss_seminars",
 "institution": "IIT Bombay",
 "content_type": "event",
 "title": "English Studies in India: Its past and its future",
 "starts_at": "2025-03-11T10:00:00Z",
 "ends_at": null,
 "timezone": "Asia/Kolkata",
 "speakers": [],
 "venue": "HSS Seminar Room, Department of HSS",
 "is_online": null,
 "event_type": "Seminar / Talk",
 "organizer": "Department of Humanities and Social Sciences",
 "description": null,
 "listing_fetched_at": "2026-09-26T13:54:40Z",
 "detail_fetched_at": null,
 "detail_fetch_status": "not_attempted",
 "detail_http_status": null,
 "detail_error": null,
 "extras": {
  "date_raw": "11th Mar 2025",
  "discovered_on_page": 2,
  "discovered_on_url": "http://127.0.0.1:61279/events/seminars-and-talks?page=1",
  "raw_href": "/events/seminar-talk/english-studies-india-its-past-and-its-future",
  "raw_text": "11 Mar 2025 Seminar / Talk English Studies in India: Its past and its future 11th Mar 2025 15:30 PM HSS Seminar Room, Department of HSS",
  "time_raw": "15:30 PM"
 },
 "content_hash": "2018491529d14a07e69d6fc1c31babb6d2b86462f6a09b50a4eadf0456def52d",
 "first_seen_at": "2026-09-26T13:54:41Z",
 "last_seen_at": "2026-09-26T13:54:41Z"
}
```

### Appendix F: audit artefacts

| Path | What |
|---|---|
| `audit_week2/tests/audit_server.py` | fault-injecting local HTTP server over the real fixtures |
| `audit_week2/tests/test_pipeline_behaviour.py` | cases 1–15 |
| `audit_week2/tests/test_scheduler_behaviour.py` | cases 16–21 |
| `audit_week2/tests/test_extra_edges.py` | X1, X2 |
| `audit_week2/logs/evidence/*.txt` | per-test evidence (counts, records, log lines) |
| `audit_week2/sources/me_iitb.py`, `cmi_seminars.py` | sandbox adapters |
| `audit_week2/config/sources.json` | sandbox config (real config + 2 entries) |
| `audit_week2/scripts/live_fetch.py` | one-shot live fetch via the project's Fetcher, logs every URL |
| `audit_week2/scripts/run_generalization.py` | Part 7 runner (real scheduler, fixtures, temp DB) |
| `audit_week2/fixtures/` | ME + CMI fixtures, recon pages, robots.txt copies |
| `audit_week2/tmp/` | DB copies, sha256 before/after, coverage data |
| `audit_week2/logs/separation_greps.txt`, `api_inventory.md`, `git_status.txt`, `generalization_report.json` | raw evidence for §3–§8 |
| `audit_week2/requirements_inferred.txt`, `audit_week2/venv/` | fresh-install check |
