"""HTTP fetching layer with strict timeouts and error propagation."""

import time
import requests

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_USER_AGENT = "NaaravanceAcademicMonitor/1.0 (+http://naaravance.ai; contact@naaravance.ai)"


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS, headers: dict = None) -> tuple[str, int, int]:
    """
    Fetches raw HTML content from the specified URL.

    Args:
        url: The URL to fetch.
        timeout: Maximum time in seconds to wait for connection and read (mandatory).
        headers: Optional custom HTTP headers.

    Returns:
        tuple: (html_content: str, status_code: int, duration_ms: int)

    Raises:
        requests.exceptions.RequestException: If network, protocol, or connection failure occurs.
    """
    if timeout is None or timeout <= 0:
        timeout = DEFAULT_TIMEOUT_SECONDS

    req_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    if headers:
        req_headers.update(headers)

    start_time = time.perf_counter()
    response = requests.get(url, timeout=timeout, headers=req_headers)
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Raise HTTPError for bad HTTP status codes (4xx, 5xx)
    response.raise_for_status()

    return response.text, response.status_code, duration_ms
