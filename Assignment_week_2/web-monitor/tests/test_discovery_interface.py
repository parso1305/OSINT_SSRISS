"""Week 3 Section 3: discover_items(source_config, client). Offline: a fake client serves fixture files.

The client has the generic Fetcher's interface (get(url) -> FetchResult, FetchError on failure), so the code
under test is exactly what runs live.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import SourceConfig
from src.discovery import discover as discover_module
from src.discovery.discover import DiscoveryCandidate, discover, discover_items
from src.fetcher import FetchError, FetchResult

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures" / "week3" / "discovery"
HOME = "https://www.iitb.ac.in/"
RSS = "https://www.iitb.ac.in/events.rss"
SITEMAP = "https://www.iitb.ac.in/sitemap.xml"
TAMING = "https://www.iitb.ac.in/event/institute-lecture-taming-turbulence"
QUANTUM = "https://www.iitb.ac.in/event/international-conference-quantum-dynamics"
VAN = "https://www.iitb.ac.in/event/van-mahotsav-2026"
ADAPTER = SimpleNamespace(__name__="fixture_adapter", LISTING_SELECTORS={
    "item": ".homepage-events .views-row", "link": ".views-field-title a",
    "date": ".views-field-field-event-date time", "date_attr": "datetime", "category": ".event-category"})
SCOPE = {"allowed_hosts": ["www.iitb.ac.in"], "allowed_prefixes": ["/event/", "/breaking-news/"],
         "excluded_prefixes": ["/user/"], "excluded_query_keys": ["month"], "max_discovered_items": 40}


class FakeClient:
    def __init__(self, pages: dict):
        self.pages, self.calls = pages, []

    def get(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise FetchError(url, 404, "HTTP 404 Not Found")
        return FetchResult(url=url, final_url=url, status=200, text=(FIX / self.pages[url]).read_text(encoding="utf-8"),
                           duration_ms=1, fetched_at="2026-10-17T00:00:00Z", content_type="text/html")


def config(discovery, urls=None, scope=SCOPE):
    return SourceConfig(source_id="iit_bombay_events", institution="IIT Bombay", adapter=ADAPTER, listing_url=HOME,
                        pipeline="aggregator", discovery=discovery, discovery_urls=urls, scope=scope)


def by_url(candidates):
    return {c.url: c for c in candidates}


def test_html_discovery():
    client = FakeClient({HOME: "listing_cards.html"})
    candidates = discover_items(config("html"), client)
    assert client.calls == [HOME]                          # html defaults to [listing_url]
    assert [c.url for c in candidates] == [TAMING, QUANTUM, VAN]
    taming = by_url(candidates)[TAMING]
    assert isinstance(taming, DiscoveryCandidate) and taming.discovery_methods == ("html",)
    assert taming.category_label == "Seminar/Talk" and taming.found_on == (HOME,)
    assert taming.record.source_timestamp == "2026-09-03T11:45:00Z" and taming.in_scope


def test_feed_discovery():
    candidates = discover_items(config("rss", {"rss": [RSS]}), FakeClient({RSS: "events_rss.xml"}))
    assert [c.url for c in candidates] == [TAMING, QUANTUM, VAN, "https://www.iitb.ac.in/event/no-date-fixture"]
    assert all(c.discovery_methods == ("rss",) for c in candidates)
    assert by_url(candidates)[TAMING].record.source_timestamp_raw == "Mon, 24 Aug 2026 10:15:00 +0530"
    atom = discover_items(config("atom", {"atom": ["https://www.iitb.ac.in/events.atom"]}),
                          FakeClient({"https://www.iitb.ac.in/events.atom": "events_atom.xml"}))
    assert {c.discovery_methods for c in atom} == {("atom",)}


def test_sitemap_discovery():
    children = {"https://www.iitb.ac.in/event-sitemap.xml": "urlset_with_lastmod.xml",
                "https://www.iitb.ac.in/news-sitemap.xml": "urlset_no_lastmod.xml"}
    client = FakeClient({SITEMAP: "sitemap_index.xml", **children})
    candidates = discover_items(config("sitemap", {"sitemap": [SITEMAP]}), client)
    assert client.calls == [SITEMAP, *children]            # index + at most 2 children; page-sitemap.xml not fetched
    urls = by_url(candidates)
    assert TAMING in urls and urls[TAMING].record.source_timestamp == "2026-08-24T04:45:00Z"
    assert urls[TAMING].record.discovered_title is None and urls[TAMING].discovery_methods == ("sitemap",)
    assert len(candidates) == 5                            # Taming appears in both children: one candidate


def test_scope_filter():
    """Out-of-scope URLs stay visible as candidates with a reason, but never count as in scope."""
    narrow = dict(SCOPE, allowed_prefixes=["/event/"])
    candidates = discover_items(config("sitemap", {"sitemap": ["https://www.iitb.ac.in/event-sitemap.xml"]}, narrow),
                                FakeClient({"https://www.iitb.ac.in/event-sitemap.xml": "urlset_with_lastmod.xml"}))
    news = by_url(candidates)["https://www.iitb.ac.in/breaking-news/iit-bombay-celebrates-van-mahotsav-2026"]
    assert not news.in_scope and news.scope_reason == "outside allowed prefixes: /breaking-news/iit-bombay-celebrates-van-mahotsav-2026"
    assert [c.url for c in candidates if c.in_scope] == [TAMING, QUANTUM, VAN]
    capped = discover(config("html", scope=dict(SCOPE, max_discovered_items=2)), FakeClient({HOME: "listing_cards.html"}))
    assert [c.in_scope for c in capped.candidates] == [True, True, False]
    assert capped.candidates[2].scope_reason == "over max_discovered_items cap (2)"


def test_duplicate_discovery_url():
    """The same event as a relative HTML href, an RSS link with utm_* + #fragment, and a sitemap <loc> collapses
    to ONE candidate on the canonical URL, even though the three raw hrefs all differ."""
    raw_html = (FIX / "listing_cards.html").read_text(encoding="utf-8")
    raw_rss = (FIX / "events_rss.xml").read_text(encoding="utf-8")
    assert 'href="/event/institute-lecture-taming-turbulence"' in raw_html
    assert "institute-lecture-taming-turbulence?utm_source=rss&amp;utm_medium=feed#main-content" in raw_rss
    assert 'href="event/international-conference-quantum-dynamics#main-content"' in raw_html     # relative + #
    assert "https://WWW.IITB.AC.IN:443/event/international-conference-quantum-dynamics?fbclid=" in raw_rss

    result = discover(config(["sitemap", "rss", "html"], {"rss": [RSS], "sitemap": [SITEMAP]}),
                      FakeClient({HOME: "listing_cards.html", RSS: "events_rss.xml", SITEMAP: "urlset_with_lastmod.xml"}))
    urls = [c.url for c in result.candidates]
    assert len(urls) == len(set(urls)) and result.raw_count > len(urls)
    taming = by_url(result.candidates)[TAMING]
    assert taming.discovery_methods == ("html", "rss", "sitemap")
    assert taming.record.discovery_method == "html"                       # highest-priority method
    assert taming.record.discovered_title == 'Institute Lecture on "Taming Turbulence"'   # html title wins
    assert taming.record.source_timestamp == "2026-09-03T11:45:00Z"       # html date wins over pubDate/lastmod
    assert taming.found_on == (HOME, RSS, SITEMAP)
    quantum = by_url(result.candidates)[QUANTUM]
    assert quantum.discovery_methods == ("html", "rss", "sitemap")
    van = by_url(result.candidates)[VAN]                                  # html card has no datetime attribute
    assert van.record.source_timestamp == "2026-08-27T09:30:00Z" and van.record.source_timestamp_raw.startswith("Thu, 27 Aug")


def test_methods_come_from_the_registry_entry_not_the_code():
    client = FakeClient({HOME: "listing_cards.html", RSS: "events_rss.xml"})
    discover_items(config("rss", {"rss": [RSS]}), client)
    assert client.calls == [RSS]                                          # html not run: not in the entry


def test_failed_discovery_page_is_reported_and_all_failed_raises():
    result = discover(config(["html", "rss"], {"rss": [RSS]}), FakeClient({HOME: "listing_cards.html"}))
    assert result.pages_fetched == 1 and result.failures == [(RSS, "FetchError: HTTP 404 Not Found")]
    with pytest.raises(FetchError):
        discover(config("html"), FakeClient({}))


def test_missing_discovery_url_for_a_method_is_a_config_error():
    with pytest.raises(ValueError, match="no discovery_urls"):
        discover_items(config("rss"), FakeClient({}))


def test_discovery_module_has_no_method_hardcoded_for_the_runner():
    assert discover_module.METHOD_PRIORITY == ("html", "rss", "atom", "sitemap")
