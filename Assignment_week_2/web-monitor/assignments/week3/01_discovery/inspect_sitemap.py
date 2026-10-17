"""Week 3 1A: print a controlled sample of an XML sitemap (urlset or sitemap index).

    venv\\Scripts\\python -m assignments.week3.01_discovery.inspect_sitemap --file fixtures/week3/discovery/sitemap_index.xml
    venv\\Scripts\\python -m assignments.week3.01_discovery.inspect_sitemap --url https://www.iitb.ac.in/sitemap.xml

--url is fetched through src.fetcher.Fetcher. For a sitemap index, at most --max-children child sitemaps
(default 2) are followed with --url; with --file the children are only listed.
"""

import argparse
import sys
from pathlib import Path

from src.discovery.sitemap import parse_sitemap, walk_sitemaps, DEFAULT_MAX_CHILD_SITEMAPS
from src.fetcher import Fetcher, FetchError
from src.logging_config import setup_logger

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CA_BUNDLE = PROJECT_ROOT / "certs" / "iitb_ca_bundle.pem"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--file")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-children", type=int, default=DEFAULT_MAX_CHILD_SITEMAPS)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.file:
        result = parse_sitemap(Path(args.file).read_bytes())
        origin = f"file:{args.file}"
        items = [(origin, e) for e in result.urls]
        print(f"# <{result.kind}> urls={len(result.urls)} child_sitemaps={len(result.child_sitemaps)}")
        for child in result.child_sitemaps:
            print(f"child sitemap (not followed from a file): {child.loc} | lastmod {child.lastmod} [{child.lastmod_raw}]")
    else:
        fetcher = Fetcher(timeout_s=15, delay_s=3.0, ca_bundle=str(CA_BUNDLE),
                          logger=setup_logger("web_monitor").getChild("fetcher"))

        def fetch_text(url: str) -> bytes:
            r = fetcher.get(url)
            print(f"# fetched {r.final_url} status={r.status} content_type={r.content_type} "
                  f"bytes={len(r.text.encode('utf-8'))} fetched_at={r.fetched_at}")
            return r.text.encode("utf-8")

        try:
            items, not_followed = walk_sitemaps(fetch_text, args.url, max_children=args.max_children)
        except FetchError as e:
            print(f"FETCH FAILED: {e} (status={e.status})")
            return 1
        print(f"# urls={len(items)} child sitemaps not followed (cap {args.max_children}): {not_followed}")

    print(f"# showing {min(args.limit, len(items))}")
    print("URL | lastmod (UTC) [raw] | discovery source")
    for origin, entry in items[: args.limit]:
        print(f"{entry.loc} | {entry.lastmod} [{entry.lastmod_raw}] | sitemap via {origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
