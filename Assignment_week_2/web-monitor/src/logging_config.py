"""Structured logging configuration for web-monitor crawler."""

import logging
import sys
from typing import Optional


class KeyValueFormatter(logging.Formatter):
    """Formats log records into timestamped [LEVEL] message strings."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, datefmt="%Y-%m-%d %H:%M:%S")
        return f"{timestamp} [{record.levelname}] {record.getMessage()}"


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


def log_start(logger: logging.Logger, source: str) -> None:
    """Logs crawl start."""
    logger.info("START source=%s", source)


def log_fetch(logger: logging.Logger, url: str, status: int, duration_ms: int) -> None:
    """Logs fetch step metrics."""
    logger.info("FETCH url=%s status=%d duration_ms=%d", url, status, duration_ms)


def log_parse(logger: logging.Logger, records_count: int) -> None:
    """Logs parse step metrics."""
    logger.info("PARSE records=%d", records_count)


def log_normalize(logger: logging.Logger, records_count: int) -> None:
    """Logs normalize step metrics."""
    logger.info("NORMALIZE records=%d", records_count)


def log_store(logger: logging.Logger, new_count: int, existing_count: int, changed_count: int) -> None:
    """Logs store step counts."""
    logger.info("STORE new=%d existing=%d changed=%d", new_count, existing_count, changed_count)


def log_end(logger: logging.Logger, duration_ms: int) -> None:
    """Logs crawl completion."""
    logger.info("END duration_ms=%d", duration_ms)


def log_warning_item(logger: logging.Logger, source: str, url: str, stage: str, message: str) -> None:
    """Logs non-aborting recoverable oddities (e.g. empty listing, missing optional field)."""
    clean_msg = message.replace('"', "'")
    logger.warning("WARNING source=%s url=%s stage=%s message=\"%s\"", source, url, stage, clean_msg)


def log_failure(logger: logging.Logger, source: str, url: str, stage: str, error: Exception) -> None:
    """Logs run-aborting failures with source, url, stage, error type, and useful message."""
    error_type = type(error).__name__
    clean_msg = str(error).strip().replace('"', "'").replace("\n", " ")
    logger.error("FAILURE source=%s url=%s stage=%s error_type=%s message=\"%s\"",
                 source, url, stage, error_type, clean_msg)
