"""Audit live fetcher: fetches a few URLs ONCE through the project's own Fetcher and saves them as fixtures.

Politeness is the project's: robots.txt checked first (RFC 9309), timeout 10 s, >= 2 s between requests
to the same host (or the site's Crawl-delay if larger). Starts with a 2 s pause so back-to-back invocations
never hit a host faster than that. Every request is appended to audit_week2/logs/live_urls.tsv.

Usage: python audit_week2/scripts/live_fetch.py --out <dir> URL [URL ...]   (max 5 URLs per call)
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

AUDIT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AUDIT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.fetcher import Fetcher, FetchError  # noqa: E402
from src.logging_config import setup_logger  # noqa: E402

URL_LOG = AUDIT_DIR / "logs" / "live_urls.tsv"


def record(url: str, status, note: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = not URL_LOG.exists()
    with URL_LOG.open("a", encoding="utf-8") as fh:
        if new:
            fh.write("timestamp_utc\turl\tstatus\tnote\n")
        fh.write(f"{ts}\t{url}\t{status}\t{note}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("urls", nargs="+")
    args = ap.parse_args()
    if len(args.urls) > 5:
        ap.error("max 5 URLs per call")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    logger = setup_logger("web_monitor")
    fetcher = Fetcher(timeout_s=10, delay_s=2.0, logger=logger.getChild("fetcher"))
    time.sleep(2.0)
    hosts_seen = set()
    for url in args.urls:
        host = urlsplit(url).netloc
        if host not in hosts_seen:
            record(f"{urlsplit(url).scheme}://{host}/robots.txt", "(fetched by Fetcher before first page)", "robots check")
            hosts_seen.add(host)
        try:
            res = fetcher.get(url)
        except FetchError as e:
            record(url, e.status if e.status is not None else "none", f"FetchError: {e.reason}")
            print(f"FAIL {url}: {e}")
            continue
        name = urlsplit(url).netloc + "__" + (urlsplit(url).path.strip("/").replace("/", "__") or "index") + (
            "__" + urlsplit(url).query.replace("=", "-").replace("&", "_") if urlsplit(url).query else "")
        path = out / f"{name}.html"
        path.write_text(res.text, encoding="utf-8")
        record(url, res.status, f"saved {path.relative_to(AUDIT_DIR).as_posix()} ({len(res.text)} chars) final_url={res.final_url}")
        print(f"OK {res.status} {url} -> {path.name} ({len(res.text)} chars)")


if __name__ == "__main__":
    main()
