"""Discovery interface (Week 3 Section 3): discover_items(source_config, client) -> list[DiscoveryCandidate].

Which methods run comes from the source's registry entry (config "discovery": "html" | "rss" | "atom" |
"sitemap" or a list), never from this module or the runner. Which URLs each method reads comes from
"discovery_urls" ({method: [url, ...]}; html defaults to [listing_url]). The HTML selectors come from the
adapter (LISTING_SELECTORS).

Steps:
  1. fetch each discovery URL with the caller's client (the project's Fetcher: robots.txt, delay, timeout, logs)
  2. parse it with the method's parser (html / feed / sitemap), which returns DiscoveryRecords with canonical URLs
  3. dedup on the canonical discovered_url: the same URL found by several methods (or twice by one) becomes ONE
     DiscoveryCandidate, with every method that found it in discovery_methods
  4. scope: every candidate gets (in_scope, scope_reason) from src.scope; out-of-scope candidates are kept
     (the router persists them with their reason) but never fetched
  5. cap: at most scope.max_discovered_items in-scope candidates; the rest are marked out of scope with the reason

Merge rule when one URL is found by several methods (field by field):
  METHOD_PRIORITY = html, rss, atom, sitemap. For discovered_title and for (source_timestamp, source_timestamp_raw)
  the first method in that order that HAS a value wins. The HTML listing is what a reader sees on the page, a
  feed is the publisher's own summary, a sitemap has no title and its lastmod is the least trustworthy timestamp
  (01_discovery/findings.md). The timestamp and its raw string always come from the same record.
  discovered_at = the earliest discovered_at among the records (all equal within one run).
"""

import dataclasses
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.discovery.feed import feed_records
from src.discovery.html import HtmlListingConfig, parse_listing_items
from src.discovery.record import DiscoveryRecord, utc_now
from src.discovery.sitemap import DEFAULT_MAX_CHILD_SITEMAPS, sitemap_records
from src.fetcher import FetchError
from src.scope import ScopeConfig, scope_decision

METHOD_PRIORITY = ("html", "rss", "atom", "sitemap")


@dataclass(frozen=True)
class DiscoveryCandidate:
    record: DiscoveryRecord                 # merged record (discovery_method = highest-priority method)
    discovery_methods: tuple                # every method that found this URL, in METHOD_PRIORITY order
    category_label: Optional[str] = None    # category shown on the listing card, if the selectors read one
    found_on: tuple = ()                    # discovery page/feed/sitemap URLs it was found on
    in_scope: bool = True
    scope_reason: str = ""

    @property
    def url(self) -> str:
        return self.record.discovered_url


@dataclass
class DiscoveryResult:
    candidates: list = field(default_factory=list)
    pages_fetched: int = 0
    http_status: Optional[int] = None       # status of the first discovery page (run metrics)
    failures: list = field(default_factory=list)   # (url, error) for discovery pages that failed
    raw_count: int = 0                      # records before dedup


def _adapter(config) -> Any:
    return importlib.import_module(config.adapter) if isinstance(config.adapter, str) else config.adapter


def discovery_urls(config) -> dict:
    urls = dict(config.discovery_urls or {})
    if "html" in config.discovery_methods() and not urls.get("html"):
        urls["html"] = [config.listing_url]
    missing = [m for m in config.discovery_methods() if not urls.get(m)]
    if missing:
        raise ValueError(f"{config.source_id}: no discovery_urls for method(s) {missing}")
    return urls


def _parse(method: str, content: str, url: str, config, adapter, discovered_at: str):
    """Returns ([(record, category_label)], child sitemap URLs)."""
    if method == "html":
        selectors = HtmlListingConfig.from_dict(getattr(adapter, "LISTING_SELECTORS"))
        items = parse_listing_items(content, url, selectors, config.source_id, discovered_at)
        return [(i.record, i.category_label) for i in items], []
    if method in ("rss", "atom"):
        records = feed_records(content.encode("utf-8"), config.source_id, url, discovered_at)
        return [(r, None) for r in records], []
    records, children = sitemap_records(content.encode("utf-8"), config.source_id, url, discovered_at)
    return [(r, None) for r in records], children


def merge_records(records: list) -> DiscoveryRecord:
    """One record for one URL from several methods (rule in the module docstring)."""
    ordered = sorted(records, key=lambda r: METHOD_PRIORITY.index(r.discovery_method))
    winner = ordered[0]
    title = next((r.discovered_title for r in ordered if r.discovered_title), None)
    stamped = next((r for r in ordered if r.source_timestamp or r.source_timestamp_raw), None)
    return dataclasses.replace(
        winner, discovered_title=title,
        source_timestamp=stamped.source_timestamp if stamped else None,
        source_timestamp_raw=stamped.source_timestamp_raw if stamped else None,
        discovered_at=min(r.discovered_at for r in ordered))


def discover(config, client, logger: Optional[logging.Logger] = None,
             discovered_at: Optional[str] = None) -> DiscoveryResult:
    """Runs every configured discovery method; raises the first FetchError only if ALL discovery pages failed."""
    logger = logger or logging.getLogger("web_monitor")
    discovered_at = discovered_at or utc_now()
    adapter = _adapter(config)
    scope = ScopeConfig.from_dict(config.scope or {"allowed_hosts": [_host(config.listing_url)]})
    result = DiscoveryResult()
    found: dict[str, list] = {}           # canonical URL -> [(record, label, page)]
    errors: list[FetchError] = []
    for method in sorted(config.discovery_methods(), key=METHOD_PRIORITY.index):
        queue = list(discovery_urls(config)[method])
        children_followed = 0
        while queue:
            url = queue.pop(0)
            try:
                response = client.get(url)
            except FetchError as e:
                errors.append(e)
                if result.http_status is None and not result.failures and result.pages_fetched == 0:
                    result.http_status = e.status          # the FIRST discovery page's status, even when it failed
                result.failures.append((url, f"{e.error_type}: {e.reason}"))
                logger.warning("DISCOVER_FAILURE source_id=%s method=%s url=%s status=%s error=\"%s\"",
                               config.source_id, method, url, e.status, e.reason.replace('"', "'"))
                continue
            if result.http_status is None and not result.failures and result.pages_fetched == 0:
                result.http_status = response.status
            result.pages_fetched += 1
            items, children = _parse(method, response.text, response.final_url or url, config, adapter, discovered_at)
            logger.info("DISCOVER source_id=%s method=%s url=%s status=%s found=%d", config.source_id, method,
                        url, response.status, len(items))
            if not items and not children:
                # HTTP 200 and nothing found: a selector miss or a really empty page. Another method may still find
                # items, which would hide this in the totals, so it is a WARNING of its own.
                logger.warning("DISCOVER_EMPTY source_id=%s method=%s url=%s status=%s found=0 "
                               "hint=\"selector miss or really empty page\"", config.source_id, method, url,
                               response.status)
            for record, label in items:
                found.setdefault(record.discovered_url, []).append((record, label, url))
            result.raw_count += len(items)
            for child in children:   # sitemap index: follow at most DEFAULT_MAX_CHILD_SITEMAPS children
                if children_followed < DEFAULT_MAX_CHILD_SITEMAPS:
                    queue.append(child)
                    children_followed += 1
    if errors and result.pages_fetched == 0:
        raise errors[0]

    in_scope_count = 0
    for url, hits in found.items():       # dict order = first-seen order (page order, method priority)
        record = merge_records([h[0] for h in hits])
        methods = tuple(m for m in METHOD_PRIORITY if any(h[0].discovery_method == m for h in hits))
        label = next((h[1] for h in hits if h[1]), None)
        pages = tuple(dict.fromkeys(h[2] for h in hits))
        allowed, reason = scope_decision(url, scope)
        if allowed:
            if in_scope_count >= scope.max_discovered_items:
                allowed, reason = False, f"over max_discovered_items cap ({scope.max_discovered_items})"
            else:
                in_scope_count += 1
        result.candidates.append(DiscoveryCandidate(record=record, discovery_methods=methods, category_label=label,
                                                    found_on=pages, in_scope=allowed, scope_reason=reason))
    logger.info("DISCOVER_SUMMARY source_id=%s pages_fetched=%d raw=%d unique=%d in_scope=%d out_of_scope=%d",
                config.source_id, result.pages_fetched, result.raw_count, len(result.candidates), in_scope_count,
                len(result.candidates) - in_scope_count)
    return result


def discover_items(source_config, client, logger: Optional[logging.Logger] = None) -> list:
    """The Section 3 interface: every discovered candidate (in and out of scope), one per canonical URL."""
    return discover(source_config, client, logger).candidates


def _host(url: str) -> str:
    from urllib.parse import urlsplit
    return (urlsplit(url).hostname or "").lower()
