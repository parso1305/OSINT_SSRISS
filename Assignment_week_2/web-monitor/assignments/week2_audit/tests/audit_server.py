"""Audit HTTP server: replays the saved IIT Bombay HSS fixtures on 127.0.0.1 with injectable faults.

Real sockets, real HTTP: the project's Fetcher talks to it exactly as it would to the live site.
Nothing in src/ is mocked.

  /robots.txt                          404 (allow all) unless robots_txt is set
  /events/seminars-and-talks           fixtures/iit_bombay_hss/listing_2026-09-26.html
  /events/seminars-and-talks?page=1    fixtures/iit_bombay_hss/live_page_2.html
  /events/seminars-and-talks?page=2    fixtures/iit_bombay_hss/live_page_3.html
  /events/seminar-talk/<slug>          fixtures/iit_bombay_hss/detail/<slug>.html (else 404)

Per-path faults (dict path -> Fault): status, body (str or bytes), content_type, sleep_s, reset.
"""

import socket
import struct
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parents[3]   # web-monitor (this file: assignments/week2_audit/tests/)
FIXTURES = PROJECT_ROOT / "fixtures" / "iit_bombay_hss"
LISTING_PATH = "/events/seminars-and-talks"
DETAIL_PREFIX = "/events/seminar-talk/"
LISTING_PAGES = {
    LISTING_PATH: "listing_2026-09-26.html",
    LISTING_PATH + "?page=1": "live_page_2.html",
    LISTING_PATH + "?page=2": "live_page_3.html",
}


@dataclass
class Fault:
    status: Optional[int] = None
    body: Optional[Union[str, bytes]] = None
    content_type: Optional[str] = None
    sleep_s: float = 0.0
    reset: bool = False  # close the TCP connection with RST before sending anything


class AuditSite:
    def __init__(self, robots_txt: Optional[str] = None):
        self.robots_txt = robots_txt
        self.faults: dict[str, Fault] = {}
        self.requests: list[tuple[float, str]] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                site.requests.append((time.time(), self.path))
                fault = site.faults.get(self.path, Fault())
                if fault.sleep_s:
                    time.sleep(fault.sleep_s)
                if fault.reset:
                    # SO_LINGER(on, 0) makes close() send RST: a real "connection reset by peer".
                    self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                    self.connection.close()
                    self.close_connection = True
                    return
                status, body, ctype = site.route(self.path)
                if fault.status is not None:
                    status = fault.status
                if fault.body is not None:
                    body = fault.body if isinstance(fault.body, bytes) else fault.body.encode("utf-8")
                if fault.content_type is not None:
                    ctype = fault.content_type
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (ConnectionError, OSError):
                    pass  # client gave up (timeout test)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def listing_url(self) -> str:
        return self.url + LISTING_PATH

    def paths(self) -> list[str]:
        return [p for _, p in self.requests]

    def route(self, path: str) -> tuple[int, bytes, str]:
        html = "text/html; charset=UTF-8"
        if path == "/robots.txt":
            if self.robots_txt is None:
                return 404, b"", "text/plain"
            return 200, self.robots_txt.encode("utf-8"), "text/plain"
        if path in LISTING_PAGES:
            return 200, (FIXTURES / LISTING_PAGES[path]).read_bytes(), html
        if path.startswith(DETAIL_PREFIX):
            detail = FIXTURES / "detail" / (path[len(DETAIL_PREFIX):] + ".html")
            if detail.exists():
                return 200, detail.read_bytes(), html
        return 404, b"<html><head><title>Page not found</title></head><body>Page not found</body></html>", html

    def __enter__(self) -> "AuditSite":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()


def listing_html(page: str = "listing_2026-09-26.html") -> str:
    return (FIXTURES / page).read_text(encoding="utf-8")


def detail_html(slug: str) -> str:
    return (FIXTURES / "detail" / f"{slug}.html").read_text(encoding="utf-8")
