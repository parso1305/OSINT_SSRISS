"""Structured logging: the only place log handlers are configured.

Everything else calls logging.getLogger(...) and the helpers below. Logger names:
  web_monitor            runner (START/END, PARSE, NORMALIZE, VALIDATE, STORE, listing FAILURE)
  web_monitor.fetcher    FETCH / FETCH_ERROR lines
  web_monitor.detail     DETAIL_FAILURE lines (non-aborting, per item)
"""

import logging
import sys
from typing import Optional


class KeyValueFormatter(logging.Formatter):
    """Formats log records into timestamped [LEVEL] logger=<name> message strings."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")
        return f"{timestamp} [{record.levelname}] logger={record.name} {record.getMessage()}"


def setup_logger(name: str = "web_monitor", level: int = logging.INFO, stream: Optional[object] = None) -> logging.Logger:
    """Configures and returns a structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if logger was already initialized
    if not logger.handlers:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(KeyValueFormatter())
        logger.addHandler(handler)
    elif stream is not None:
        # If a specific stream is provided (e.g. for capturing logs in tests), attach it
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        handler.setFormatter(KeyValueFormatter())
        logger.addHandler(handler)

    return logger


def _clean(error: Exception) -> str:
    return str(error).strip().replace('"', "'").replace("\n", " ")


def log_start(logger: logging.Logger, source_id: str) -> None:
    """Logs run start."""
    logger.info("START source_id=%s", source_id)


def log_fetch(logger: logging.Logger, url: str, status: int, duration_ms: int) -> None:
    """Logs fetch step metrics."""
    logger.info("FETCH url=%s status=%d duration_ms=%d", url, status, duration_ms)


def log_fetch_error(logger: logging.Logger, url: str, status: Optional[int], error: Exception) -> None:
    """Logs a request that produced no usable response (TLS/network error, timeout, robots disallow).

    error_type is the underlying cause (SSLError, ReadTimeout, ...) when the error records one."""
    logger.warning("FETCH_ERROR url=%s status=%s error_type=%s message=\"%s\"",
                   url, status if status is not None else "none",
                   getattr(error, "error_type", None) or type(error).__name__, _clean(error))


def log_parse(logger: logging.Logger, records_count: int) -> None:
    """Logs parse step metrics."""
    logger.info("PARSE records=%d", records_count)


def log_normalize(logger: logging.Logger, records_count: int) -> None:
    """Logs normalize step metrics."""
    logger.info("NORMALIZE records=%d", records_count)


def log_paginate(logger: logging.Logger, pages_crawled: int, stop_reason: str) -> None:
    """Logs paginated listing traversal outcome."""
    logger.info("PAGINATE pages_crawled=%d stop_reason=%s", pages_crawled, stop_reason)


def log_detail_failure(logger: logging.Logger, source_id: str, item_url: str, status: Optional[int], error: Exception) -> None:
    """Logs a non-aborting detail-page failure (distinct from listing-level FAILURE lines)."""
    logger.warning("DETAIL_FAILURE source_id=%s item_url=%s status=%s error_type=%s message=\"%s\"",
                   source_id, item_url, status if status is not None else "none", type(error).__name__, _clean(error))


def log_enrich(logger: logging.Logger, ok: int, failed: int, not_attempted: int) -> None:
    """Logs detail enrichment outcome counts."""
    logger.info("ENRICH ok=%d failed=%d not_attempted=%d", ok, failed, not_attempted)


def log_validation_failure(logger: logging.Logger, source_id: str, item_url: str, errors: list[str]) -> None:
    """Logs a record rejected by schema validation (not stored)."""
    logger.warning("VALIDATION_FAILURE source_id=%s item_url=%s errors=\"%s\"", source_id, item_url, "; ".join(errors))


def log_validate(logger: logging.Logger, valid: int, invalid: int) -> None:
    """Logs schema validation counts."""
    logger.info("VALIDATE valid=%d invalid=%d", valid, invalid)


def log_store(logger: logging.Logger, new_count: int, existing_count: int, changed_count: int) -> None:
    """Logs store step counts."""
    logger.info("STORE new=%d existing=%d changed=%d", new_count, existing_count, changed_count)


def log_end(logger: logging.Logger, source_id: str, duration_ms: int) -> None:
    """Logs run completion."""
    logger.info("END source_id=%s duration_ms=%d", source_id, duration_ms)


def log_warning_item(logger: logging.Logger, source_id: str, url: str, stage: str, message: str) -> None:
    """Logs non-aborting recoverable oddities (e.g. empty listing, missing optional field)."""
    clean_msg = message.replace('"', "'")
    logger.warning("WARNING source_id=%s url=%s stage=%s message=\"%s\"", source_id, url, stage, clean_msg)


def log_failure(logger: logging.Logger, source_id: str, url: str, stage: str, error: Exception) -> None:
    """Logs listing-level failures with source_id, url, stage, error type, and useful message."""
    logger.error("FAILURE source_id=%s url=%s stage=%s error_type=%s message=\"%s\"",
                 source_id, url, stage, type(error).__name__, _clean(error))


# -- scheduler ------------------------------------------------------------------

def log_schedule(logger: logging.Logger, source_id: str, interval_minutes: Optional[float],
                 last_started_at: Optional[str], next_due_at: Optional[str], due: bool) -> None:
    """Logs the scheduling decision for one source in one cycle."""
    logger.info("SCHEDULE source=%s interval_minutes=%s last_started_at=%s next_due_at=%s due=%s",
                source_id, interval_minutes, last_started_at or "never", next_due_at or "now", str(due).lower())


def log_run_start(logger: logging.Logger, run_id: str, source_id: str) -> None:
    logger.info("RUN_START run_id=%s source=%s", run_id, source_id)


def log_run_end(logger: logging.Logger, run_id: str, source_id: str, status: str, duration_ms: int,
                counts: Optional[dict] = None, failed_count: int = 0, error: Optional[str] = None) -> None:
    counts = counts or {}
    logger.log(logging.INFO if status == "success" else logging.ERROR,
               "RUN_END run_id=%s source=%s status=%s duration_ms=%d new=%s existing=%s changed=%s failed=%d error=\"%s\"",
               run_id, source_id, status, duration_ms, counts.get("new", 0), counts.get("existing", 0),
               counts.get("changed", 0), failed_count, (error or "").replace('"', "'").replace("\n", " "))


def log_run_skipped(logger: logging.Logger, source_id: str, reason: str, holder: str = "") -> None:
    logger.info("RUN_SKIPPED source=%s reason=%s%s", source_id, reason, f" holder={holder}" if holder else "")


def log_stale_lock(logger: logging.Logger, source_id: str, holder: str, reason: str) -> None:
    logger.warning("STALE_LOCK source=%s holder=%s reason=%s action=removed", source_id, holder, reason)
