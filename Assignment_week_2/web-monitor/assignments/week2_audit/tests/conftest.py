"""Shared helpers for the audit behaviour tests.

Every test writes its evidence to logs/after_fixes/evidence/ (override: AUDIT_EVIDENCE_DIR). The original audit
evidence (2026-09-26, before any fix) is in logs/evidence/ and is never overwritten by a re-run.
"""

import dataclasses
import hashlib
import io
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import pytest

AUDIT_DIR = Path(__file__).resolve().parents[1]          # assignments/week2_audit
PROJECT_ROOT = AUDIT_DIR.parents[1]                      # web-monitor
for p in (str(PROJECT_ROOT), str(AUDIT_DIR / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.config import load_source_configs  # noqa: E402
from src.logging_config import KeyValueFormatter  # noqa: E402

EVIDENCE_DIR = Path(os.environ.get("AUDIT_EVIDENCE_DIR") or AUDIT_DIR / "logs" / "after_fixes" / "evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_ID = "iit_bombay_hss_seminars"


class Evidence:
    def __init__(self, name: str):
        self.path = EVIDENCE_DIR / f"{name}.txt"
        self.path.write_text("", encoding="utf-8")

    def __call__(self, *parts) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            for part in parts:
                fh.write(part if isinstance(part, str) else json.dumps(part, indent=1, ensure_ascii=False, default=str))
                fh.write("\n")


@pytest.fixture
def evidence(request):
    return Evidence(request.node.name.replace("[", "_").replace("]", ""))


@pytest.fixture
def log_stream():
    """Captures every web_monitor* log line in the project's own format."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield stream
    logger.removeHandler(handler)


def open_problem(ref: str, why: str):
    """An audit finding outside the 2026-09-27 fix list: still fails, and is expected to (strict: a fix shows up)."""
    return pytest.mark.xfail(strict=True, reason=f"OPEN audit {ref}: {why} (not in the fix list; see FIXES.md)")


def site_config(site, **overrides):
    """The REAL iit_bombay_hss_seminars config entry, pointed at the local audit server.

    request_delay_s=0 because the host is 127.0.0.1 (the >=1.5 s rule is for real hosts; every live
    request in this audit goes through a Fetcher with delay >= 2 s)."""
    base = load_source_configs()[SOURCE_ID]
    params = dict(listing_url=site.listing_url, request_delay_s=0)
    params.update(overrides)
    return dataclasses.replace(base, **params)


def write_sandbox_config(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps({"sources": entries}, indent=2), encoding="utf-8")
    return path


def real_entry(**overrides) -> dict:
    entries = json.loads((PROJECT_ROOT / "config" / "sources.json").read_text(encoding="utf-8"))["sources"]
    entry = dict(next(e for e in entries if e["source_id"] == SOURCE_ID))
    entry.update(overrides)
    return entry


def db_dump(db: str) -> tuple[str, int]:
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT * FROM records ORDER BY item_url").fetchall()
    conn.close()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest(), len(rows)


def lines(log: str, *needles: str) -> str:
    return "\n".join(l for l in log.splitlines() if any(n in l for n in needles))
