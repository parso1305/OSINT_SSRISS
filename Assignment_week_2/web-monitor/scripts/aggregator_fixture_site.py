"""Local HTTP server for source local_aggregator_fixture: the IIT Bombay events aggregator, offline.

Same pattern as scripts/fixture_site.py (real HTTP on 127.0.0.1, no mocks, no network), serving the files built by
scripts/make_week3_site_fixtures.py and the saved detail pages, with per-path Content-Types:

  /robots.txt                          404 (allow all)
  /                                    site/home.html             (variant "changed": site/home_changed.html)
  /events.rss                          site/events.rss            application/rss+xml
  /event/<slug>                        detail/<slug>.html         (variant "changed": site/detail_changed/ first)
  /events/brochure-iccms-2027.pdf      a tiny PDF                 application/pdf (the router never requests it)
  /breaking-news/<slug>                a small HTML page          (an announcement: never detail-fetched)
  anything else                        404

Failure modes for the Section 9 metric tests:
  broken="listing"   the events block's class is renamed (selector miss: 0 items with HTTP 200)
  broken="detail"    every detail page's <article class="node--type-event"> is renamed (parser cannot find it)
  broken="http"      / answers 503
  broken="speaker_label"  detail pages say "Presenter:" instead of "Speaker:" (pages still parse; speakers vanish)

Standalone:  venv\\Scripts\\python -m scripts.aggregator_fixture_site --port 8766 [--variant changed] [--broken listing]
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent.parent / "fixtures" / "week3" / "iitb_events"
DETAIL, SITE = BASE / "detail", BASE / "site"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
NEWS = b"<html><head><title>News | fixture</title></head><body><article class='node--type-breaking-news'>news</article></body></html>"


class AggregatorFixtureSite:
    def __init__(self, port: int = 0, variant: str = "base", broken: Optional[str] = None):
        self.variant, self.broken = variant, broken
        self.requests: list[str] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                site.requests.append(self.path)
                status, content_type, body = site.route(self.path)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def route(self, path: str) -> tuple[int, str, bytes]:
        html = "text/html; charset=UTF-8"
        if path == "/":
            if self.broken == "http":
                return 503, html, b"<html><body>Service Unavailable</body></html>"
            page = (SITE / ("home_changed.html" if self.variant == "changed" else "home.html")).read_text(encoding="utf-8")
            if self.broken == "listing":
                page = page.replace("homepage-events", "homepage-events-v2")   # a theme update renames the block
            return 200, html, page.encode("utf-8")
        if path == "/events.rss":
            return 200, "application/rss+xml; charset=utf-8", (SITE / "events.rss").read_bytes()
        if path.startswith("/event/"):
            slug = path.split("?")[0].rsplit("/", 1)[-1]
            candidates = ([SITE / "detail_changed" / f"{slug}.html"] if self.variant == "changed" else []) + \
                         [DETAIL / f"{slug}.html"]
            for file in candidates:
                if file.exists():
                    page = file.read_text(encoding="utf-8")
                    if self.broken == "detail":
                        page = page.replace("node--type-event", "node--type-event-v2")
                    if self.broken == "speaker_label":
                        page = page.replace("<strong>Speaker:", "<strong>Presenter:").replace(
                            "<strong>Speakers:", "<strong>Presenters:")
                    return 200, html, page.encode("utf-8")
        if path == "/events/brochure-iccms-2027.pdf":
            return 200, "application/pdf", PDF
        if path.startswith("/breaking-news/"):
            return 200, html, NEWS
        return 404, html, b"<html><head><title>Page not found</title></head><body>Page not found</body></html>"

    def __enter__(self) -> "AggregatorFixtureSite":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Serve the offline IIT Bombay events aggregator on 127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--variant", choices=("base", "changed"), default="base")
    parser.add_argument("--broken", choices=("listing", "detail", "http", "speaker_label"), default=None)
    args = parser.parse_args()
    with AggregatorFixtureSite(port=args.port, variant=args.variant, broken=args.broken) as site:
        print(f"serving aggregator fixtures on {site.url} variant={args.variant} broken={args.broken}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
