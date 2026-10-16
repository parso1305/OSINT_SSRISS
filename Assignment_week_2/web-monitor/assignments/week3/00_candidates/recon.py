"""Week 3 Assignment 0 recon: fetch candidate aggregator surfaces through the project's generic client and keep the evidence.

Usage (from the web-monitor root; no sys.path hacks, assignments/ is a namespace package):
    venv\\Scripts\\python -m assignments.week3.00_candidates.recon fetch URL [URL ...]
    venv\\Scripts\\python -m assignments.week3.00_candidates.recon summarize

fetch      GETs each URL with src.fetcher.Fetcher (robots.txt checked, explicit timeout, honest User-Agent,
           FETCH logging, >= 3 s between requests to one host) and saves the raw body under evidence/.
           Every attempt, including failures and robots disallows, is appended to evidence/manifest.json.
summarize  offline: prints title, generator, RSS/Atom <link rel=alternate>, link count and JS-app markers
           for every saved HTML page.

Request accounting: the manifest's requests_used counts real HTTP GETs, i.e. robots.txt fetches made inside
Fetcher plus page fetches plus redirect hops. A robots-disallowed URL costs nothing.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from src.fetcher import Fetcher, FetchError
from src.logging_config import setup_logger

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
MANIFEST = EVIDENCE / "manifest.json"
PROJECT_ROOT = HERE.parents[2]
# The IITB intermediate-certificate bundle from Week 2. It adds a missing intermediate; verification stays on.
CA_BUNDLE = PROJECT_ROOT / "certs" / "iitb_ca_bundle.pem"
DELAY_S = 3.0      # assignment rule: at least 3 s between requests to the same host
TIMEOUT_S = 15.0

# Never fetch login, search-result or account surfaces (assignment rule); checked before any request.
FORBIDDEN = re.compile(r"login|signin|sign-in|/user(/|$)|/search|[?&](q|query|search|keys)=", re.IGNORECASE)
JS_MARKERS = re.compile(r"__NEXT_DATA__|ng-app|data-reactroot|id=\"(root|app)\"\s*>\s*</div>|/wp-json/|/api/", re.I)


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"requests_used": 0, "entries": []}


def evidence_name(url: str, content_type: str, text: str) -> str:
    parts = urlsplit(url)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (parts.path + ("_" + parts.query if parts.query else "")).strip("/")) or "root"
    ct = (content_type or "").lower()
    head = text.lstrip()[:200].lower()
    if "html" in ct or head.startswith("<!doctype html") or head.startswith("<html"):
        ext = "html"
    elif "xml" in ct or head.startswith("<?xml") or head.startswith("<rss") or head.startswith("<urlset"):
        ext = "xml"
    else:
        ext = "txt"
    return f"{parts.netloc}__{slug[:120]}.{ext}"


def fetch(urls: list[str]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    logger = setup_logger("web_monitor")
    fetcher = Fetcher(timeout_s=TIMEOUT_S, delay_s=DELAY_S, ca_bundle=str(CA_BUNDLE),
                      logger=logger.getChild("fetcher"))

    # Count every real GET (robots.txt included) by wrapping the client's session; the wrapper only counts.
    counter = {"n": 0}
    session_get = fetcher.session.get

    def counting_get(*args, **kwargs):
        counter["n"] += 1
        response = session_get(*args, **kwargs)
        counter["n"] += len(response.history)  # each redirect hop was a separate request
        return response

    fetcher.session.get = counting_get

    for url in urls:
        if FORBIDDEN.search(url):
            print(f"REFUSED (login/search surface): {url}", file=sys.stderr)
            continue
        entry = {"url": url}
        try:
            result = fetcher.get(url)
        except FetchError as e:
            entry.update(final_url=None, status=e.status, content_type=None, fetched_at=None, bytes=0,
                         file=None, error=e.reason)
        else:
            name = evidence_name(result.final_url, result.content_type or "", result.text)
            body = result.text.encode("utf-8")
            (EVIDENCE / name).write_bytes(body)
            entry.update(final_url=result.final_url, status=result.status, content_type=result.content_type,
                         fetched_at=result.fetched_at, bytes=len(body), file=name)
        manifest["entries"].append(entry)
        print(json.dumps(entry))

    manifest["requests_used"] += counter["n"]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"requests this invocation: {counter['n']}; total requests_used: {manifest['requests_used']}")


def summarize() -> None:
    for path in sorted(EVIDENCE.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None
        gen = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
        feeds = [(l.get("type"), l.get("href")) for l in soup.find_all("link", rel="alternate")
                 if "rss" in (l.get("type") or "") or "atom" in (l.get("type") or "")]
        print(f"== {path.name}")
        print(f"   title={title!r} generator={gen.get('content') if gen else None!r}")
        print(f"   feeds={feeds} links={len(soup.find_all('a', href=True))} "
              f"scripts={len(soup.find_all('script'))} js_markers={sorted(set(JS_MARKERS.findall(html)))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("urls", nargs="+")
    sub.add_parser("summarize")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # page titles contain Devanagari; the Windows console default is cp1252
    fetch(args.urls) if args.cmd == "fetch" else summarize()


if __name__ == "__main__":
    main()
