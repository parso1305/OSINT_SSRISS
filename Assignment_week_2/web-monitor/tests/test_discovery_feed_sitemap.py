"""Week 3 1A: RSS/Atom and sitemap parsing from content only (offline fixtures in fixtures/week3/discovery/)."""

from pathlib import Path

import pytest

from src.discovery.feed import FeedParseError, parse_feed
from src.discovery.sitemap import SitemapParseError, parse_sitemap, walk_sitemaps
from src.discovery.timestamps import to_utc_z

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "week3" / "discovery"


def read(name: str) -> bytes:
    return (FIX / name).read_bytes()


# -- feeds -----------------------------------------------------------------------------------------------------

def test_rss_rfc822_dates_normalized_to_utc_z_and_raw_kept():
    feed = parse_feed(read("events_rss.xml"))
    assert feed.kind == "rss" and feed.version == "rss20" and len(feed.entries) == 4
    first, second, third, undated = feed.entries
    assert first.title == 'Institute Lecture on "Taming Turbulence"'
    assert first.published == "2026-08-24T04:45:00Z"                  # +0530 converted
    assert first.published_raw == "Mon, 24 Aug 2026 10:15:00 +0530"
    assert second.published == "2026-09-01T06:00:00Z"                 # GMT
    assert third.published == "2026-08-27T09:30:00Z"                  # +0000
    assert first.entry_id == "6737 at https://www.iitb.ac.in"
    assert undated.published is None and undated.timestamp is None


def test_real_target_rss_sample_parses():
    feed = parse_feed(read("iitb_rss_real_trimmed.xml"))
    assert feed.kind == "rss" and len(feed.entries) == 3
    assert feed.entries[0].published == "2026-10-16T09:44:35Z"
    assert all("/event/" not in e.link for e in feed.entries)          # the real feed carries no events


def test_atom_iso_dates_published_and_updated():
    feed = parse_feed(read("events_atom.xml"))
    assert feed.kind == "atom" and feed.version == "atom10"
    saral, forum = feed.entries
    assert saral.published == "2026-10-14T11:00:00Z" and saral.published_raw == "2026-10-14T16:30:00+05:30"
    assert saral.updated == "2026-10-15T09:00:00Z"
    assert saral.timestamp == saral.published                          # published wins over updated
    assert forum.published is None and forum.timestamp == "2026-10-10T05:00:00Z"   # updated-only entry
    assert saral.entry_id == "tag:www.iitb.ac.in,2026:node/6903"


@pytest.mark.parametrize("not_content", [
    "https://www.iitb.ac.in/rss.xml", "http://example.org/feed", "feed://example.org/x", "C:\\feeds\\rss.xml", "",
    b"https://www.iitb.ac.in/rss.xml",
])
def test_feed_parser_rejects_url_or_path_input(not_content):
    """feedparser would fetch a URL itself, bypassing the project's HTTP client: refused before it is called."""
    with pytest.raises(ValueError, match="not a URL or path"):
        parse_feed(not_content)


def test_feed_parser_never_calls_feedparser_with_a_url(monkeypatch):
    import src.discovery.feed as feed_module
    calls = []
    monkeypatch.setattr(feed_module.feedparser, "parse", lambda arg, *a, **k: calls.append(arg))
    with pytest.raises(ValueError):
        parse_feed("https://www.iitb.ac.in/rss.xml")
    assert calls == []


def test_malformed_feed_gives_clear_error():
    with pytest.raises(FeedParseError, match="not an RSS/Atom feed"):
        parse_feed(read("malformed.xml"))


# -- sitemaps --------------------------------------------------------------------------------------------------

def test_urlset_with_lastmod():
    result = parse_sitemap(read("urlset_with_lastmod.xml"))
    assert result.kind == "urlset" and result.child_sitemaps == []
    by_loc = {e.loc: e for e in result.urls}
    assert by_loc["https://www.iitb.ac.in/event/institute-lecture-taming-turbulence"].lastmod == "2026-08-24T04:45:00Z"
    assert by_loc["https://www.iitb.ac.in/event/van-mahotsav-2026"].lastmod == "2026-08-27T09:30:00Z"   # +05:30
    quantum = by_loc["https://www.iitb.ac.in/event/international-conference-quantum-dynamics"]
    assert quantum.lastmod is None and quantum.lastmod_raw == "2026-09-01"                              # date only
    assert by_loc["https://www.iitb.ac.in/breaking-news/iit-bombay-celebrates-van-mahotsav-2026"].lastmod is None


def test_urlset_without_lastmod_and_without_namespace():
    result = parse_sitemap(read("urlset_no_lastmod.xml"))
    assert result.kind == "urlset"
    assert [e.loc for e in result.urls] == ["https://www.iitb.ac.in/event/institute-lecture-taming-turbulence",
                                            "https://www.iitb.ac.in/event/5th-japan-india-forum"]
    assert all(e.lastmod is None and e.lastmod_raw is None for e in result.urls)


def test_sitemaps_org_namespace_handled():
    namespaced = parse_sitemap(read("urlset_with_lastmod.xml"))         # xmlns="http://www.sitemaps.org/..."
    real = parse_sitemap(read("acr_sitemap_real_trimmed.xml"))          # real file: namespace + xsi attributes
    assert len(namespaced.urls) == 4 and len(real.urls) == 8
    assert {e.lastmod for e in real.urls} == {"2024-02-14T06:57:38Z"}   # the identical-lastmod finding


def test_sitemap_index_children_returned_separately():
    result = parse_sitemap(read("sitemap_index.xml"))
    assert result.kind == "sitemapindex" and result.urls == []
    assert [c.loc for c in result.child_sitemaps] == ["https://www.iitb.ac.in/event-sitemap.xml",
                                                       "https://www.iitb.ac.in/news-sitemap.xml",
                                                       "https://www.iitb.ac.in/page-sitemap.xml"]


def test_walk_sitemaps_follows_at_most_two_children_by_default():
    children = {"https://www.iitb.ac.in/event-sitemap.xml": read("urlset_with_lastmod.xml"),
                "https://www.iitb.ac.in/news-sitemap.xml": read("urlset_no_lastmod.xml")}
    fetched = []

    def fetch_text(url):
        fetched.append(url)
        return read("sitemap_index.xml") if url.endswith("/sitemap.xml") else children[url]

    items, not_followed = walk_sitemaps(fetch_text, "https://www.iitb.ac.in/sitemap.xml")
    assert fetched == ["https://www.iitb.ac.in/sitemap.xml", *children]
    assert not_followed == ["https://www.iitb.ac.in/page-sitemap.xml"]
    assert len(items) == 6


def test_malformed_sitemap_gives_clear_error_not_crash():
    with pytest.raises(SitemapParseError, match="malformed sitemap XML: mismatched tag"):
        parse_sitemap(read("malformed.xml"))
    with pytest.raises(SitemapParseError, match="not a sitemap"):
        parse_sitemap(b"<html><body>Page not found</body></html>")


def test_sitemap_refuses_entity_expansion():
    with pytest.raises(SitemapParseError, match="unsafe XML refused by defusedxml"):
        parse_sitemap(read("billion_laughs.xml"))


# -- timestamps ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, offset, expected", [
    ("Fri, 16 Oct 2026 09:44:35 +0000", None, "2026-10-16T09:44:35Z"),
    ("2026-10-16T15:14:35+05:30", None, "2026-10-16T09:44:35Z"),
    ("2026-10-16T09:44:35Z", None, "2026-10-16T09:44:35Z"),
    ("2026-10-21T17:15:00", "+05:30", "2026-10-21T11:45:00Z"),   # naive local time + the source's offset
    ("2026-10-21T17:15:00", None, None),                          # naive without an offset: not an instant
    ("2026-10-16", None, None),                                   # date only
    ("next Tuesday", None, None),
    (None, None, None),
])
def test_to_utc_z(raw, offset, expected):
    assert to_utc_z(raw, offset) == expected
