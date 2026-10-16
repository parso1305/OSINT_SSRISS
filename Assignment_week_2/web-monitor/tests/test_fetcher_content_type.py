"""FetchResult.content_type (Week 3): the response Content-Type header reaches the caller unchanged.

Week 3 recon records it as evidence and discovery uses it to tell a feed from an HTML error page.
A local 127.0.0.1 server only, so the test runs with outbound HTTP blocked.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.fetcher import Fetcher, FetchResult

FEED = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/feed.xml":
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(FEED)))
            self.end_headers()
            self.wfile.write(FEED)
        elif self.path == "/bare":  # no Content-Type header at all
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
        else:  # robots.txt 404 -> allow all
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_fetch_result_carries_the_response_content_type():
    server, base = _serve()
    try:
        fetcher = Fetcher(delay_s=0, timeout_s=5)
        result = fetcher.get(base + "/feed.xml")
        bare = fetcher.get(base + "/bare")
    finally:
        server.shutdown()
    assert result.content_type == "application/rss+xml; charset=utf-8"
    assert result.text.startswith("<?xml")
    assert bare.content_type is None


def test_content_type_is_optional_for_existing_constructions():
    result = FetchResult(url="u", final_url="u", status=200, text="", duration_ms=0, fetched_at="2026-10-16T00:00:00Z")
    assert result.content_type is None
