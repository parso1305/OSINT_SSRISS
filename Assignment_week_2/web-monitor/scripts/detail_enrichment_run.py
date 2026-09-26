"""Live detail-enrichment run through the generic runner, with an optional Checkpoint 5 mistype.

--mistype-index N swaps the last two letters of item N's URL (1-based) after parse_listing, so the
real server answers 404 for that detail page. The adapter is wrapped, not modified.

Usage:  python scripts/detail_enrichment_run.py [--limit 5] [--mistype-index 2] [--db data/checkpoint5_404.db]
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import dataclasses
from types import SimpleNamespace

from src.config import load_adapter, load_source_configs
from src.runner import run_source

MAX_DETAIL_FETCHES = 10


def mistype(url: str) -> str:
    head, slug = url.rsplit("/", 1)
    return f"{head}/{slug[:-2]}{slug[-1]}{slug[-2]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="iit_bombay_hss_seminars")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--mistype-index", type=int, default=None)
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "events.db"))
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_DETAIL_FETCHES:
        parser.error(f"--limit must be between 1 and {MAX_DETAIL_FETCHES}")

    config = load_source_configs()[args.source]
    adapter = load_adapter(config.adapter, supports_detail=True)

    def parse_listing(html: str, base_url: str) -> list[dict]:
        items = adapter.parse_listing(html, base_url=base_url)
        if args.mistype_index is not None and len(items) >= args.mistype_index:
            target = items[args.mistype_index - 1]
            target["item_url"] = mistype(target["item_url"])
            print(f"CHECKPOINT mistyped item {args.mistype_index}: -> {target['item_url']}")
        return items

    wrapped = SimpleNamespace(parse_listing=parse_listing, parse_detail=adapter.parse_detail,
                              normalize=adapter.normalize, NEXT_PAGE_SELECTOR=getattr(adapter, "NEXT_PAGE_SELECTOR", None))
    config = dataclasses.replace(config, adapter=wrapped, supports_pagination=False, detail_limit=args.limit)
    result = run_source(config, db_path=args.db)
    print(f"detail={result['detail_status']} counts={result['counts']} invalid={len(result['invalid'])}")


if __name__ == "__main__":
    main()
