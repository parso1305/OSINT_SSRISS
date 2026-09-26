"""HTTP fetching: the only module that uses requests.

One Fetcher per source run. It owns the session, User-Agent, timeout, per-host politeness delay,
robots.txt checks (RFC 9309), status/error handling and structured FETCH logging.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
import urllib3

from src.logging_config import log_fetch, log_fetch_error

DEFAULT_TIMEOUT_SECONDS: float = 10.0
DEFAULT_DELAY_SECONDS: float = 1.0
DEFAULT_USER_AGENT: str = "NaaravanceAcademicMonitor/1.0 (+http://naaravance.ai; contact@naaravance.ai)"
ROBOTS_AGENT: str = "NaaravanceAcademicMonitor"


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    text: str
    duration_ms: int
    fetched_at: str


class FetchError(Exception):
    """Any failed fetch: HTTP >= 400, network error, timeout, or disallowed by robots.txt."""

    def __init__(self, url: str, status: Optional[int], reason: str):
        super().__init__(f"{reason} for url: {url}")
        self.url = url
        self.status = status
        self.reason = reason


class Fetcher:
    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
        delay_s: float = DEFAULT_DELAY_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        respect_robots: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        self.timeout_s = timeout_s if timeout_s and timeout_s > 0 else DEFAULT_TIMEOUT_SECONDS
        self.delay_s = max(delay_s or 0.0, 0.0)
        self.respect_robots = respect_robots
        self.logger = logger or logging.getLogger("web_monitor.fetcher")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._robots: dict[str, Optional[RobotFileParser]] = {}
        self._last_request_at: dict[str, float] = {}

    # -- politeness ---------------------------------------------------------

    def _robots_for(self, url: str) -> Optional[RobotFileParser]:
        """Returns the parsed robots.txt for url's host; None means 'allow all' (robots.txt 4xx)."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        robots_url = origin + "/robots.txt"
        try:
            response = self._request(robots_url)
        except requests.RequestException as e:
            # RFC 9309: robots.txt unreachable -> assume complete disallow
            raise FetchError(url, None, f"robots.txt unreachable ({type(e).__name__})") from e
        self._last_request_at[parts.netloc] = time.monotonic()
        if 400 <= response.status_code < 500:
            parser = None
        elif response.status_code >= 500:
            raise FetchError(url, None, f"robots.txt returned HTTP {response.status_code}")
        else:
            parser = RobotFileParser(robots_url)
            parser.parse(response.text.splitlines())
        self._robots[origin] = parser
        return parser

    def _wait_turn(self, url: str, crawl_delay: float) -> None:
        host = urlsplit(url).netloc
        delay = max(self.delay_s, crawl_delay)
        last = self._last_request_at.get(host)
        if last is not None:
            remaining = delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()

    # -- requests -----------------------------------------------------------

    def _request(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url, timeout=self.timeout_s)
        except requests.exceptions.SSLError as ssl_err:
            self.logger.warning("SSL verification failed for %s (%s). Retrying with verify=False", url, type(ssl_err).__name__)
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = self.session.get(url, timeout=self.timeout_s, verify=False)
        # requests assumes ISO-8859-1 for text/* without a charset; fall back to content sniffing.
        if "charset" not in response.headers.get("Content-Type", "").lower():
            response.encoding = response.apparent_encoding
        return response

    def get(self, url: str) -> FetchResult:
        """GET url politely. Raises FetchError on robots disallow, network error or HTTP >= 400."""
        crawl_delay = 0.0
        if self.respect_robots:
            robots = self._robots_for(url)
            if robots is not None:
                if not robots.can_fetch(ROBOTS_AGENT, url):
                    error = FetchError(url, None, "disallowed by robots.txt")
                    log_fetch_error(self.logger, url=url, status=None, error=error)
                    raise error
                crawl_delay = float(robots.crawl_delay(ROBOTS_AGENT) or 0.0)

        self._wait_turn(url, crawl_delay)
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = time.perf_counter()
        try:
            response = self._request(url)
        except requests.RequestException as e:
            error = FetchError(url, None, f"{type(e).__name__}: {e}")
            log_fetch_error(self.logger, url=url, status=None, error=error)
            raise error from e
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_fetch(self.logger, url=url, status=response.status_code, duration_ms=duration_ms)

        if response.status_code >= 400:
            raise FetchError(url, response.status_code, f"HTTP {response.status_code} {response.reason}")
        return FetchResult(url=url, final_url=response.url, status=response.status_code,
                           text=response.text, duration_ms=duration_ms, fetched_at=fetched_at)
