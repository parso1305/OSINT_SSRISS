"""Generic pipeline runner: config-driven, with no source-specific code.

run_source(config):
  fetch listing -> adapter.parse_listing -> [pagination if supports_pagination]
  -> [detail enrichment if supports_detail: adapter.parse_detail + merge_listing_and_detail]
  -> adapter.normalize -> assemble shared-schema record -> validate_record -> storage
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import time
from typing import Optional

from src.config import SourceConfig, load_adapter, load_source_configs, DEFAULT_CONFIG_PATH
from src.enrich import enrich_items
from src.fetcher import Fetcher, FetchError
from src.pagination import collect_listing
from src.schema import assemble_record, validate_record
from src.storage import store_records
from src.logging_config import (
    setup_logger, log_start, log_end, log_parse, log_paginate, log_normalize, log_validate,
    log_validation_failure, log_store, log_warning_item, log_failure,
)

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "events.db"


def run_source(
    config: SourceConfig,
    db_path: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    fetcher: Optional[Fetcher] = None,
) -> dict:
    """Runs one configured source end to end. A listing-level failure on page 1 raises."""
    logger = logger or setup_logger()
    adapter = load_adapter(config.adapter, supports_detail=config.supports_detail)
    fetcher = fetcher or Fetcher(timeout_s=config.timeout_s, delay_s=config.request_delay_s,
                                 logger=logger.getChild("fetcher"))
    target_db = str(db_path or DEFAULT_DB_PATH)
    t_start = time.perf_counter()
    log_start(logger, source_id=config.source_id)

    # 1-2. FETCH + PARSE listing (one page, or up to max_pages when pagination is enabled)
    try:
        listing = collect_listing(
            start_url=config.listing_url,
            max_pages=config.max_pages if config.supports_pagination else 1,
            fetch_fn=fetcher.get,
            parse_fn=adapter.parse_listing,
            next_page_selector=getattr(adapter, "NEXT_PAGE_SELECTOR", None),
            source_id=config.source_id,
            logger=logger,
        )
    except FetchError as e:
        log_failure(logger, source_id=config.source_id, url=config.listing_url, stage="fetch", error=e)
        raise
    except Exception as e:
        log_failure(logger, source_id=config.source_id, url=config.listing_url, stage="parse", error=e)
        raise
    if config.supports_pagination:
        log_paginate(logger, pages_crawled=listing["pages_crawled"], stop_reason=listing["stop_reason"])
    items = listing["items"]
    log_parse(logger, records_count=len(items))
    if not items:
        log_warning_item(logger, source_id=config.source_id, url=config.listing_url, stage="parse",
                         message="Listing returned HTTP 200 but parsed 0 items: possible silent layout change")

    # 3. DETAIL ENRICHMENT (optional)
    if config.supports_detail and config.detail_limit > 0:
        merged = enrich_items(items, adapter.parse_detail, fetch_fn=fetcher.get,
                              source_id=config.source_id, max_items=config.detail_limit, logger=logger)
    else:
        merged = [dict(item, detail_fetch_status="not_attempted") for item in items]

    # 4. NORMALIZE (adapter) + assemble shared record (generic)
    try:
        records = [assemble_record(config, m, adapter.normalize(m)) for m in merged]
    except Exception as e:
        log_failure(logger, source_id=config.source_id, url=config.listing_url, stage="normalize", error=e)
        raise
    log_normalize(logger, records_count=len(records))

    # 5. VALIDATE: invalid records are logged and not stored
    valid, invalid = [], []
    for record in records:
        errors = validate_record(record)
        if errors:
            invalid.append({"item_url": record.get("item_url"), "errors": errors})
            log_validation_failure(logger, source_id=config.source_id, item_url=str(record.get("item_url")), errors=errors)
        else:
            valid.append(record)
    log_validate(logger, valid=len(valid), invalid=len(invalid))

    # 6. STORE
    try:
        counts = store_records(target_db, valid)
    except Exception as e:
        log_failure(logger, source_id=config.source_id, url=config.listing_url, stage="store", error=e)
        raise
    log_store(logger, new_count=counts["new"], existing_count=counts["existing"], changed_count=counts["changed"])

    duration_ms = int((time.perf_counter() - t_start) * 1000)
    log_end(logger, source_id=config.source_id, duration_ms=duration_ms)
    return {
        "status": "success",
        "source_id": config.source_id,
        "pages_crawled": listing["pages_crawled"],
        "stop_reason": listing["stop_reason"],
        "detail_status": {s: sum(m["detail_fetch_status"] == s for m in merged) for s in ("ok", "failed", "not_attempted")},
        "counts": counts,
        "records": valid,
        "invalid": invalid,
        "duration_ms": duration_ms,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run configured sources (live network)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--source", default=None, help="source_id to run (default: all enabled)")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()

    configs = load_source_configs(args.config)
    selected = [configs[args.source]] if args.source else [c for c in configs.values() if c.enabled]
    for source_config in selected:
        result = run_source(source_config, db_path=args.db)
        print(f"{result['source_id']}: pages={result['pages_crawled']} stop={result['stop_reason']} "
              f"detail={result['detail_status']} counts={result['counts']} invalid={len(result['invalid'])}")
