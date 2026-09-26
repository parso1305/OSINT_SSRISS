"""Local HTTP server that replays the saved live HSS HTML under the real site paths.

Real HTTP (no mocks, no network): the pipeline's Fetcher talks to 127.0.0.1. Used by the fixture
tests and by scripts/run_fixtures.py.

  /robots.txt                          404 (allow all), unless robots_txt is given
  /events/seminars-and-talks           fixtures/iit_bombay_hss/listing_2026-09-26.html
  /events/seminars-and-talks?page=1    fixtures/iit_bombay_hss/live_page_2.html
  /events/seminars-and-talks?page=2    fixtures/iit_bombay_hss/live_page_3.html
  /events/seminar-talk/<slug>          fixtures/iit_bombay_hss/detail/<slug>.html, else 404
  anything in fail_paths               404 "Page not found"
  anything in drop_paths               headers + half the body, then the connection is closed
  delay_s                              sleep before every response (slow server, for overlap demos)
  tls=(certfile, keyfile)              serve HTTPS with that certificate (fixtures/tls/, TLS tests)

Standalone:  python scripts/fixture_site.py --port 8765 [--delay-s 1] [--fail PATH] [--drop PATH]
"""

import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable, Optional

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "iit_bombay_hss"
LISTING_PATH = "/events/seminars-and-talks"
LISTING_PAGES = {
    LISTING_PATH: "listing_2026-09-26.html",
    LISTING_PATH + "?page=1": "live_page_2.html",
    LISTING_PATH + "?page=2": "live_page_3.html",
}
NOT_FOUND = b"<html><head><title>Page not found | Humanities and Social Sciences</title></head><body>Page not found</body></html>"


class FixtureSite:
    def __init__(self, fail_paths: Iterable[str] = (), robots_txt: Optional[str] = None,
                 overrides: Optional[dict[str, str]] = None, port: int = 0, delay_s: float = 0.0,
                 drop_paths: Iterable[str] = (), tls: Optional[tuple[Path, Path]] = None):
        self.fail_paths = set(fail_paths)
        self.drop_paths = set(drop_paths)
        self.delay_s = delay_s
        self.robots_txt = robots_txt
        self.overrides = dict(overrides or {})  # path -> html body
        self.requests: list[str] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test/demo output clean
                pass

            def do_GET(self):
                site.requests.append(self.path)
                if site.delay_s:
                    time.sleep(site.delay_s)
                status, body = site.route(self.path)
                self.send_response(status)
                self.send_header("Content-Type", "text/plain" if self.path == "/robots.txt" else "text/html; charset=UTF-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.path in site.drop_paths:
                    self.wfile.write(body[: len(body) // 2])
                    self.wfile.flush()
                    self.close_connection = True
                    self.connection.shutdown(2)
                    return
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.scheme = "http"
        if tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=str(tls[0]), keyfile=str(tls[1]))
            # A client that rejects the certificate aborts the handshake inside accept(); the server
            # drops that connection (OSError) and never sees an HTTP request.
            self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
            self.scheme = "https"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self._server.server_address[1]}"

    @property
    def listing_url(self) -> str:
        return self.url + LISTING_PATH

    def route(self, path: str) -> tuple[int, bytes]:
        if path in self.fail_paths:
            return 404, NOT_FOUND
        if path in self.overrides:
            return 200, self.overrides[path].encode("utf-8")
        if path == "/robots.txt":
            return (200, self.robots_txt.encode("utf-8")) if self.robots_txt is not None else (404, b"")
        if path in LISTING_PAGES:
            return 200, (FIXTURES / LISTING_PAGES[path]).read_bytes()
        if path.startswith("/events/seminar-talk/"):
            detail = FIXTURES / "detail" / (path.rsplit("/", 1)[-1] + ".html")
            if detail.exists():
                return 200, detail.read_bytes()
        return 404, NOT_FOUND

    def __enter__(self) -> "FixtureSite":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Serve the saved HSS fixtures on 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--delay-s", type=float, default=0.0)
    parser.add_argument("--fail", action="append", default=[])
    parser.add_argument("--drop", action="append", default=[])
    args = parser.parse_args()
    with FixtureSite(fail_paths=args.fail, drop_paths=args.drop, port=args.port, delay_s=args.delay_s) as site:
        print(f"serving fixtures on {site.url} delay_s={args.delay_s} fail={args.fail} drop={args.drop}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
