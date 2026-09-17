"""Minimal pipeline runner wiring fetch, parse, normalize, and store with structured logging."""

import time
import logging
from typing import Optional

from src.fetch import fetch_page
from sources.iit_bombay import parse_events
from src.schema import normalize_events
from src.storage import init_db, store_all
from src.logging_config import (
    setup_logger,
    log_start,
    log_fetch,
    log_parse,
    log_normalize,
    log_store,
    log_end,
    log_warning_item,
    log_failure
)


def run_pipeline(
    source_name: str,
    url: str,
    db_path: str,
    html_override: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Executes the crawl pipeline for a given source and URL with structured logging.

    Stages:
        1. Fetch (or use html_override)
        2. Parse HTML records
        3. Normalize records
        4. Store in SQLite database

    Returns:
        dict: Summary of the run including status and storage counts.
    """
    if logger is None:
        logger = setup_logger()

    t_start = time.perf_counter()
    log_start(logger, source=source_name)

    # 1. FETCH STAGE
    try:
        if html_override is not None:
            html = html_override
            status_code = 200
            fetch_duration_ms = 0
        else:
            html, status_code, fetch_duration_ms = fetch_page(url)

        log_fetch(logger, url=url, status=status_code, duration_ms=fetch_duration_ms)
    except Exception as e:
        log_failure(logger, source=source_name, url=url, stage="fetch", error=e)
        raise

    # 2. PARSE STAGE
    try:
        raw_items = parse_events(html, base_url=url)
        if len(raw_items) == 0:
            log_warning_item(logger, source=source_name, url=url, stage="parse",
                             message="Empty listing: container exists but contains zero event cards")
        log_parse(logger, records_count=len(raw_items))
    except Exception as e:
        log_failure(logger, source=source_name, url=url, stage="parse", error=e)
        raise

    # 3. NORMALIZE STAGE
    try:
        normalized_items = normalize_events(raw_items, base_url=url)
        log_normalize(logger, records_count=len(normalized_items))
    except Exception as e:
        log_failure(logger, source=source_name, url=url, stage="normalize", error=e)
        raise

    # 4. STORE STAGE
    try:
        init_db(db_path)
        counts = store_all(db_path, normalized_items)
        log_store(logger, new_count=counts["new"], existing_count=counts["existing"], changed_count=counts["changed"])
    except Exception as e:
        log_failure(logger, source=source_name, url=url, stage="store", error=e)
        raise

    total_duration_ms = int((time.perf_counter() - t_start) * 1000)
    log_end(logger, duration_ms=total_duration_ms)

    return {
        "status": "success",
        "counts": counts,
        "duration_ms": total_duration_ms
    }
