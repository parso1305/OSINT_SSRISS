"""Assignment 4B evidence tool: live paginated crawl of the configured HSS listing, saving each page.

Hits the real site (capped at 3 pages). Saves pages to fixtures/iit_bombay_hss/live_page_<n>.html
and a summary to assignments/04_pagination/live_run.json. Normal runs use src/runner.py instead.

Usage:  python scripts/live_pagination_run.py [--max-pages 3]
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from src.config import load_adapter, load_source_configs
from src.fetcher import Fetcher
from src.logging_config import setup_logger
from src.pagination import collect_listing

FIXTURE_DIR = PROJECT_ROOT / "fixtures" / "iit_bombay_hss"
RUN_SUMMARY_PATH = PROJECT_ROOT / "assignments" / "04_pagination" / "live_run.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="iit_bombay_hss_seminars")
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 3:
        parser.error("--max-pages is capped at 3 (do not crawl the archive)")

    config = load_source_configs()[args.source]
    adapter = load_adapter(config.adapter)
    logger = setup_logger("web_monitor")
    fetcher = Fetcher(timeout_s=config.timeout_s, delay_s=config.request_delay_s, logger=logger.getChild("fetcher"))
    fetches: list[dict] = []

    def fetch_and_save(url: str):
        result = fetcher.get(url)
        path = FIXTURE_DIR / f"live_page_{len(fetches) + 1}.html"
        path.write_text(result.text, encoding="utf-8")
        fetches.append({"page": len(fetches) + 1, "requested_url": url, "final_url": result.final_url,
                        "http_status": result.status, "fetched_at": result.fetched_at,
                        "saved_as": path.relative_to(PROJECT_ROOT).as_posix()})
        return result

    listing = collect_listing(config.listing_url, max_pages=args.max_pages, fetch_fn=fetch_and_save,
                              parse_fn=adapter.parse_listing, next_page_selector=getattr(adapter, "NEXT_PAGE_SELECTOR", None),
                              source_id=config.source_id, logger=logger)
    summary = {
        "start_url": config.listing_url, "max_pages": args.max_pages, "stop_reason": listing["stop_reason"],
        "pages_crawled": listing["pages_crawled"], "visited_urls": listing["visited_urls"], "fetches": fetches,
        "items_total": len(listing["items"]),
        "items": [{k: it.get(k) for k in ("discovered_on_page", "discovered_on_url", "raw_href", "item_url", "title", "date_raw")}
                  for it in listing["items"]],
    }
    RUN_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"stop_reason={listing['stop_reason']} pages_crawled={listing['pages_crawled']} items={summary['items_total']}")


if __name__ == "__main__":
    main()
