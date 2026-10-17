"""Run metrics (Week 3 Section 9): one summary per aggregator run, printed, logged and stored on the runs row.

The summary makes failure modes distinguishable (assignments/week3/09_metrics/failure_signatures.md):
  discovered N / parsed ~N / new 0          nothing new (healthy)
  discovered N / parsed 0                   the detail parser broke (or every detail fetch failed: see FAILED)
  discovered 0 with HTTP 200                the listing selector broke, or the page really is empty
  HTTP non-200 (or none)                    the fetch failed

Coverage percentages are taken over the items whose detail page was parsed this run (items_parsed): that is
where dates, speakers and organizations come from. A sharp drop against the previous successful run of the same
source is logged as a WARNING even when the counts look normal (a renamed field silently empties a column):
  COVERAGE_DROP_POINTS = 30   warn when a % falls by >= 30 percentage points (e.g. with-speaker 80% -> 40%),
                              comparing only runs that parsed at least one item.

CLI:  python -m src.metrics --last --db <path> [--source <name>]
"""

import argparse
import logging
import sys
from typing import Optional

COVERAGE_DROP_POINTS = 30.0
BLOCK_FIELDS = (
    ("SOURCE", "source"), ("PAGES_FETCHED", "pages_fetched"), ("ITEMS_DISCOVERED", "items_discovered"),
    ("ITEMS_PARSED", "items_parsed"), ("NEW", "new"), ("CHANGED", "changed"), ("UNCHANGED", "unchanged"),
    ("NOT_SEEN_THIS_RUN", "not_seen_this_run"), ("FAILED", "failed"), ("PEOPLE_EXTRACTED", "people_extracted"),
    ("ORGANIZATIONS_EXTRACTED", "organizations_extracted"),
)
LOG_FIELDS = ("run_id", "source", "status", "http_status", "pages_fetched", "items_discovered", "items_parsed",
              "new", "changed", "unchanged", "not_seen_this_run", "failed", "parse_failures", "detail_failures",
              "people_extracted", "organizations_extracted", "pct_with_date", "pct_with_speaker", "pct_with_org")
COVERAGE_FIELDS = ("pct_with_date", "pct_with_speaker", "pct_with_org")


def pct(part: int, whole: int) -> Optional[float]:
    return round(100.0 * part / whole, 1) if whole else None


def build_summary(*, source: str, status: str, run_id: Optional[str] = None, http_status: Optional[int] = None,
                  pages_fetched: int = 0, items_discovered: int = 0, items_parsed: int = 0,
                  counts: Optional[dict] = None, not_seen_this_run: Optional[int] = None, parse_failures: int = 0,
                  detail_failures: int = 0, invalid: int = 0, people_extracted: int = 0,
                  organizations_extracted: int = 0, parsed_records: Optional[list] = None,
                  error: Optional[str] = None) -> dict:
    """parsed_records: the records built from a parsed detail page this run (coverage % denominators)."""
    counts = counts or {}
    parsed_records = parsed_records or []
    n = len(parsed_records)
    return {
        "run_id": run_id, "source": source, "status": status, "http_status": http_status,
        "pages_fetched": pages_fetched, "items_discovered": items_discovered, "items_parsed": items_parsed,
        "new": counts.get("new", 0), "changed": counts.get("changed", 0), "unchanged": counts.get("unchanged", 0),
        "not_seen_this_run": not_seen_this_run if not_seen_this_run is not None else 0,
        "failed": parse_failures + detail_failures + invalid, "parse_failures": parse_failures,
        "detail_failures": detail_failures, "people_extracted": people_extracted,
        "organizations_extracted": organizations_extracted,
        "pct_with_date": pct(sum(bool(r.get("event_start")) for r in parsed_records), n),
        "pct_with_speaker": pct(sum(bool(r.get("speakers")) for r in parsed_records), n),
        "pct_with_org": pct(sum(bool(r.get("organizations")) for r in parsed_records), n),
        "error": error,
    }


def format_block(summary: dict) -> str:
    lines = [f"{label}: {summary.get(key)}" for label, key in BLOCK_FIELDS]
    lines.insert(1, f"STATUS: {summary.get('status')}")
    return "\n".join(lines)


def format_log_line(summary: dict) -> str:
    fields = " ".join(f"{key}={'none' if summary.get(key) is None else summary.get(key)}" for key in LOG_FIELDS)
    error = (summary.get("error") or "").replace('"', "'").replace("\n", " ")
    return f"RUN_SUMMARY {fields} error=\"{error}\""


def coverage_warnings(summary: dict, previous: Optional[dict]) -> list[str]:
    """Warnings for each coverage % that dropped >= COVERAGE_DROP_POINTS against the previous successful run."""
    if not previous or not summary.get("items_parsed") or not previous.get("items_parsed"):
        return []
    warnings = []
    for key in COVERAGE_FIELDS:
        before, now = previous.get(key), summary.get(key)
        if before is not None and now is not None and before - now >= COVERAGE_DROP_POINTS:
            warnings.append(f"COVERAGE_DROP source={summary['source']} run_id={summary.get('run_id') or 'none'} "
                            f"metric={key} previous={before} now={now} threshold_points={COVERAGE_DROP_POINTS:g} "
                            f"previous_run_id={previous.get('run_id')}")
    return warnings


def runs_row(summary: dict) -> dict:
    """The summary as storage.finish_run metrics (runs table column names)."""
    row = {k: summary.get(k) for k in ("http_status", "pages_fetched", "items_discovered", "items_parsed",
                                       "parse_failures", "detail_failures", "people_extracted",
                                       "organizations_extracted", *COVERAGE_FIELDS)}
    row["not_seen_count"] = summary.get("not_seen_this_run")
    return row


def summary_from_run(run: dict) -> dict:
    """A stored runs row back into summary shape (CLI, previous-run comparison)."""
    return {"run_id": run["run_id"], "source": run["source_id"], "status": run["status"],
            "http_status": run.get("http_status"), "pages_fetched": run.get("pages_fetched"),
            "items_discovered": run.get("items_discovered"), "items_parsed": run.get("items_parsed"),
            "new": run.get("new_count"), "changed": run.get("changed_count"), "unchanged": run.get("unchanged_count"),
            "not_seen_this_run": run.get("not_seen_count"), "failed": run.get("failed_count"),
            "parse_failures": run.get("parse_failures"), "detail_failures": run.get("detail_failures"),
            "people_extracted": run.get("people_extracted"),
            "organizations_extracted": run.get("organizations_extracted"),
            "pct_with_date": run.get("pct_with_date"), "pct_with_speaker": run.get("pct_with_speaker"),
            "pct_with_org": run.get("pct_with_org"), "error": run.get("error")}


def emit(summary: dict, logger: logging.Logger, previous: Optional[dict] = None, stream=None) -> list[str]:
    """Prints the block, logs the key=value line (+ coverage-drop WARNINGs). Returns the warnings."""
    out = stream or sys.stdout
    print(format_block(summary), file=out, flush=True)
    logger.log(logging.INFO if summary.get("status") == "success" else logging.ERROR, format_log_line(summary))
    warnings = coverage_warnings(summary, previous)
    for warning in warnings:
        logger.warning(warning)
    return warnings


def main(argv: Optional[list] = None) -> int:
    from src.storage import last_runs
    parser = argparse.ArgumentParser(description="Print the last run summary from a web-monitor database")
    parser.add_argument("--last", action="store_true", required=True, help="the most recent finished run")
    parser.add_argument("--db", required=True)
    parser.add_argument("--source", default=None)
    args = parser.parse_args(argv)
    runs = last_runs(args.db, source_id=args.source)
    if not runs:
        print(f"no finished runs in {args.db}" + (f" for {args.source}" if args.source else ""))
        return 1
    summary = summary_from_run(runs[0])
    print(f"RUN {summary['run_id']} started {runs[0]['started_at']} finished {runs[0]['finished_at']}")
    print(format_block(summary))
    print(format_log_line(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
