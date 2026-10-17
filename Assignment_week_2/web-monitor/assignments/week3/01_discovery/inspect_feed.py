"""Week 3 1A: print a controlled sample of an RSS/Atom feed.

    venv\\Scripts\\python -m assignments.week3.01_discovery.inspect_feed --file fixtures/week3/discovery/events_rss.xml
    venv\\Scripts\\python -m assignments.week3.01_discovery.inspect_feed --url https://www.iitb.ac.in/rss.xml --limit 10

--url is fetched through src.fetcher.Fetcher (robots.txt, timeout, User-Agent, FETCH log, >= 3 s per host);
the parser only ever sees the downloaded content.
"""

import argparse
import sys
from pathlib import Path

from src.discovery.feed import parse_feed
from src.fetcher import Fetcher, FetchError
from src.logging_config import setup_logger

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CA_BUNDLE = PROJECT_ROOT / "certs" / "iitb_ca_bundle.pem"   # adds IITB's missing intermediate; still verified


def load(url: str = None, file: str = None) -> tuple[bytes, str]:
    if file:
        return Path(file).read_bytes(), f"file:{file}"
    fetcher = Fetcher(timeout_s=15, delay_s=3.0, ca_bundle=str(CA_BUNDLE),
                      logger=setup_logger("web_monitor").getChild("fetcher"))
    result = fetcher.get(url)
    print(f"# fetched {result.final_url} status={result.status} content_type={result.content_type} "
          f"bytes={len(result.text.encode('utf-8'))} fetched_at={result.fetched_at}")
    return result.text.encode("utf-8"), url


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--file")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        content, origin = load(args.url, args.file)
    except FetchError as e:
        print(f"FETCH FAILED: {e} (status={e.status})")
        return 1
    feed = parse_feed(content)
    print(f"# {feed.kind} ({feed.version}) entries={len(feed.entries)} showing={min(args.limit, len(feed.entries))}")
    print("URL | title | published-or-updated (UTC) [raw] | discovery source")
    for entry in feed.entries[: args.limit]:
        print(f"{entry.link} | {entry.title} | {entry.timestamp} [{entry.timestamp_raw}] | {feed.kind} via {origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
