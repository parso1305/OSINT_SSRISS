"""URL resolution and canonicalization.

resolve_item_url() is the single place in web-monitor where hrefs are resolved
(the only urljoin call site). Every parser, normalizer and the pagination walker
goes through it, so the canonical URL it returns is the storage dedup key.
"""

import re
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

TRACKING_QUERY_PARAMS = {
    # Analytics / campaign tracking (utm_* is matched by prefix below)
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
    "ref",
    "ref_src",
    # Session identifiers
    "sid",
    "phpsessid",
    "jsessionid",
    "aspsessionid",
    "sessionid",
    "session_id",
}

DEFAULT_PORTS = {"http": "80", "https": "443"}

# ;jsessionid=ABC123 path parameters (Java servlet containers)
_PATH_SESSION_RE = re.compile(r";(?:jsessionid|phpsessid|sid)=[^/?#]*", re.IGNORECASE)

# Fragments that select content in client-side routed pages (#!/item/42, #/item/42)
_IDENTITY_FRAGMENT_RE = re.compile(r"^!?/")


def _is_tracking_param(key: str) -> bool:
    k = key.lower()
    return k.startswith("utm_") or k in TRACKING_QUERY_PARAMS


def resolve_item_url(href: Optional[str], page_url: Optional[str]) -> str:
    """
    Resolves a raw href found on page_url into a canonical absolute URL.

    Resolution (href forms):
      - already-absolute   "https://host/a"           -> used as-is
      - protocol-relative  "//host/a"                 -> scheme taken from page_url (https if none)
      - root-relative      "/a/b"                     -> page_url's scheme + host
      - pure-relative      "b", "../b", "?page=1"     -> relative to page_url's directory / path

    Canonicalization:
      1. Scheme and host lowercased (path case preserved).
      2. Default ports stripped (:80 for http, :443 for https).
      3. Duplicate slashes in the path collapsed.
      4. Trailing slash removed from every non-root path ("/a/b/" -> "/a/b"; root stays "/").
      5. Tracking and session query params removed (utm_*, fbclid, gclid, sid, PHPSESSID, ...)
         along with ;jsessionid= path params. Remaining params are sorted by key.
      6. Fragments stripped, except client-side route fragments ("#!/..." or "#/...")
         which identify the item rather than a position within it.

    Returns "" when href is empty or resolves to a non-HTTP(S) scheme
    (mailto:, tel:, javascript:, data:).
    """
    if not href or not href.strip():
        return ""

    clean_href = href.strip()
    clean_base = page_url.strip() if page_url else ""

    # Protocol-relative href with no base scheme to borrow: assume https
    if clean_href.startswith("//") and not urlsplit(clean_base).scheme:
        clean_href = "https:" + clean_href

    parts = urlsplit(urljoin(clean_base, clean_href))

    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        return ""

    host = (parts.hostname or "").rstrip(".")
    if not host:
        return ""
    try:
        port = parts.port
    except ValueError:  # non-numeric or out-of-range port
        return ""
    netloc = host if port is None or str(port) == DEFAULT_PORTS[scheme] else f"{host}:{port}"

    path = _PATH_SESSION_RE.sub("", parts.path)
    path = re.sub(r"/{2,}", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    if not path:
        path = "/"

    query_params = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(k)
    ]
    query_params.sort(key=lambda pair: pair[0])
    query = urlencode(query_params)

    fragment = parts.fragment if _IDENTITY_FRAGMENT_RE.match(parts.fragment) else ""

    return urlunsplit((scheme, netloc, path, query, fragment))
