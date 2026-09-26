
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
