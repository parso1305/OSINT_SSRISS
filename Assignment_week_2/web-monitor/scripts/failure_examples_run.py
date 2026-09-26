"""Regenerates assignments/01_logging/failure_examples.md from real runs of the current code.

Every case runs the real runner (and Fetcher, SQLite, adapter) against the local fixture site
(scripts/fixture_site.py) with one fault injected; the captured log lines are pasted verbatim.
No network: the HSS config entry is pointed at 127.0.0.1.

Usage:  python scripts/failure_examples_run.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dataclasses
import io
import logging
import re
import socket
import tempfile
from datetime import datetime, timezone

from scripts.fixture_site import FIXTURES, LISTING_PATH, FixtureSite
from src.config import load_source_configs
from src.logging_config import KeyValueFormatter
from src.runner import run_source

OUT = PROJECT_ROOT / "assignments" / "01_logging" / "failure_examples.md"
TLS = PROJECT_ROOT / "fixtures" / "tls"
TRACING = "/events/seminar-talk/tracing-success-indian-democracy-success-nation-building"


def config(listing_url: str, **overrides):
    base = load_source_configs()["iit_bombay_hss_seminars"]
    params = dict(listing_url=listing_url, request_delay_s=0, supports_pagination=False, detail_limit=2)
    params.update(overrides)
    return dataclasses.replace(base, **params)


def capture(run) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        run(logger)
    except Exception:  # noqa: BLE001 - the failure is what is being documented; its log lines are the evidence
        pass
    finally:
        logger.removeHandler(handler)
    return stream.getvalue().rstrip()


def db() -> str:
    return str(Path(tempfile.mkdtemp()) / "examples.db")


def listing_html() -> str:
    return (FIXTURES / "listing_2026-09-26.html").read_text(encoding="utf-8")


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    cases = []

    with FixtureSite() as site:
        cases.append(("Baseline: successful run", None, capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))

    cases.append(("Case 1: Invalid listing URL", "invalid_url", capture(
        lambda log: run_source(config("http://"), db_path=db(), logger=log))))

    port = closed_port()
    cases.append(("Case 2: Connection failure", "connection", capture(
        lambda log: run_source(config(f"http://127.0.0.1:{port}{LISTING_PATH}"), db_path=db(), logger=log))))

    with FixtureSite(overrides={LISTING_PATH: listing_html().replace("view-seminars-and-talks", "view-talks-list")}) as site:
        cases.append(("Case 3: Site redesign (listing container renamed)", "redesign", capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))

    empty = listing_html().replace("event-card-wrapper", "event-card-box")
    with FixtureSite(overrides={LISTING_PATH: empty}) as site:
        cases.append(("Case 4a: Empty listing (default: the run fails)", "empty", capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))
        cases.append(("Case 4b: Empty listing on a source with allow_empty_listing: true", "empty_allowed", capture(
            lambda log: run_source(config(site.listing_url, allow_empty_listing=True), db_path=db(), logger=log))))

    bad_db = Path(tempfile.mkdtemp()) / "corrupt.db"
    bad_db.write_bytes(b"this is not an SQLite database" * 100)
    with FixtureSite() as site:
        cases.append(("Case 5: Database write problem", "database", capture(
            lambda log: run_source(config(site.listing_url), db_path=str(bad_db), logger=log))))

    with FixtureSite(tls=(TLS / "selfsigned.pem", TLS / "selfsigned.key")) as site:
        cases.append(("Case 6: TLS certificate cannot be verified", "tls", capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))

    with FixtureSite(fail_paths=[TRACING]) as site:
        cases.append(("Case 7: One detail page fails (non-aborting)", "detail", capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))

    detail = (FIXTURES / "detail" / (TRACING.rsplit("/", 1)[-1] + ".html")).read_text(encoding="utf-8")
    with FixtureSite(overrides={TRACING: re.sub(r'datetime="[^"]+"', 'datetime="17 September 2025"', detail)}) as site:
        cases.append(("Case 8: Date format changed on a detail page (non-aborting)", "parse_warning", capture(
            lambda log: run_source(config(site.listing_url), db_path=db(), logger=log))))

    OUT.write_text(render(cases), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(PROJECT_ROOT)} ({len(cases)} cases)")


NOTES = {
    "invalid_url": (
        "`parse` (reported)", "`ERROR`, run aborts", "`EmptyListingError`",
        "`listing_url` is not a usable http(s) URL, so `resolve_item_url` returns `\"\"` and **no request is made**. "
        "The run fails, which is correct. **The message is misleading**, though: it says \"HTTP 200 … parsed 0 items\" "
        "for a URL that was never fetched. Suggested fix (not applied: outside the agreed audit-fix list): reject "
        "such a `listing_url` when the config is loaded."),
    "connection": (
        "`fetch`", "`ERROR`, run aborts", "`ConnectionError` (FETCH_ERROR), `FetchError` (FAILURE)",
        "Nothing listens on the port. The first request is robots.txt; RFC 9309 treats an unreachable robots.txt "
        "as \"disallow all\", so the run stops there. `FETCH_ERROR` names the underlying cause."),
    "redesign": (
        "`parse`", "`ERROR`, run aborts", "`StructuralError`",
        "The listing container `.view-seminars-and-talks .view-content` is gone. The adapter raises instead of "
        "returning an empty list; nothing is stored."),
    "empty": (
        "`parse`", "`ERROR`, run aborts", "`EmptyListingError`",
        "The page loads (HTTP 200) and the container exists, but the card class was renamed, so 0 items parse. "
        "Since the audit fix this fails the run (scheduler: `status=failed`, exit code 1) before anything is stored; "
        "existing records are untouched."),
    "empty_allowed": (
        "`parse`", "`WARNING`, run continues", "none",
        "Same page, on a source configured with `allow_empty_listing: true` (a feed that may legitimately be empty)."),
    "database": (
        "`store`", "`ERROR`, run aborts", "`DatabaseError`",
        "The DB file is not an SQLite database. Fetch, parse, enrichment and validation succeed; storing fails and "
        "the transaction writes nothing."),
    "tls": (
        "`fetch`", "`ERROR`, run aborts", "`SSLError` (FETCH_ERROR), `FetchError` (FAILURE)",
        "The server's certificate is self-signed. Verification is never switched off: the run fails. A source "
        "whose server omits an intermediate certificate gets a `ca_bundle` instead (README, TLS section)."),
    "detail": (
        "`enrich` (per item)", "`WARNING`, run continues", "`FetchError` (DETAIL_FAILURE)",
        "One detail page answers 404. That item keeps its listing data (`detail_fetch_status=failed`); the other "
        "items are enriched and every record is stored."),
    "parse_warning": (
        "`normalize` (per field)", "`WARNING`, run continues", "none (PARSE_WARNING)",
        "The detail page's `<time datetime>` is text instead of ISO 8601. The value counts as unknown: `starts_at` "
        "falls back to the listing date + time, `ends_at` keeps any stored value, and the change is logged instead "
        "of silently erasing data."),
}


def render(cases) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "# Section 1: Structured Failure Logging Examples\n",
        f"Regenerated {now} by `python scripts/failure_examples_run.py` from **real runs of the current code**: the "
        "real runner, Fetcher, adapter and SQLite, against the local fixture site (`scripts/fixture_site.py`, saved "
        "live HSS HTML) with one fault injected per case. Log lines are pasted verbatim (timestamps are local "
        "time; ports are random).\n",
        "Format (`src/logging_config.py`): `YYYY-MM-DD HH:MM:SS [LEVEL] logger=<name> EVENT key=value …`. "
        "Logger names: `web_monitor` (run stages, FAILURE, WARNING, PARSE_WARNING, VALIDATION_FAILURE), "
        "`web_monitor.fetcher` (FETCH, FETCH_ERROR), `web_monitor.detail` (DETAIL_FAILURE). Every line carries the "
        "source (`source_id=`), the stage, and for failures the error type, so `grep` alone tells what failed where.\n",
        "> The previous version of this file (2026-09-17) was captured before the Assignment 7 refactor: no "
        "`logger=` field, `source=iit_bombay` instead of `source_id=`, and a legacy fixture's container "
        "(`.view-events-listing`). It is in git history.\n",
    ]
    for title, key, log in cases:
        parts.append("---\n")
        parts.append(f"## {title}\n")
        if key:
            stage, severity, error_type, cause = NOTES[key]
            parts.append(f"- **Stage**: {stage}\n- **Severity**: {severity}\n- **Error type**: {error_type}\n"
                         f"- **Cause**: {cause}\n")
        parts.append(f"```text\n{log}\n```\n")
    return "\n".join(parts)


if __name__ == "__main__":
    main()
