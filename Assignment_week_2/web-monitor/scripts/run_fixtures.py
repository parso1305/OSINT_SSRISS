"""Runs a configured source end to end against the saved fixtures (scripts/fixture_site.py): no network.

The config entry is used as-is except listing_url (pointed at the local fixture site) and
request_delay_s (0). --max-pages / --fail override the config for demonstrations.

Usage:  python scripts/run_fixtures.py [--db PATH] [--runs 2] [--max-pages 3]
                                       [--fail /events/seminar-talk/<slug>] [--show-records 3]
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import dataclasses
import json
import tempfile

from scripts.fixture_site import FixtureSite
from src.config import load_source_configs
from src.logging_config import setup_logger
from src.runner import run_source
from src.schema import validate_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="iit_bombay_hss_seminars")
    parser.add_argument("--db", default=None, help="SQLite path (default: a new temp file)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--fail", action="append", default=[], help="Path the fixture site answers with 404")
    parser.add_argument("--show-records", type=int, default=0)
    args = parser.parse_args()

    db_path = args.db or str(Path(tempfile.mkdtemp()) / "fixtures_run.db")
    logger = setup_logger("web_monitor")
    with FixtureSite(fail_paths=args.fail) as site:
        config = dataclasses.replace(load_source_configs()[args.source], listing_url=site.listing_url, request_delay_s=0)
        if args.max_pages:
            config = dataclasses.replace(config, max_pages=args.max_pages)
        for run in range(1, args.runs + 1):
            print(f"\n===== run {run} (db={db_path}) =====")
            result = run_source(config, db_path=db_path, logger=logger)
            errors = {r["item_url"]: validate_record(r) for r in result["records"]}
            print(f"summary: pages={result['pages_crawled']} stop={result['stop_reason']} "
                  f"detail={result['detail_status']} counts={result['counts']} "
                  f"validated={len(errors)} valid={sum(not e for e in errors.values())} rejected={len(result['invalid'])}")
        for record in result["records"][:args.show_records]:
            print(json.dumps(record, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
