"""Week 3 1B: the unified DiscoveryRecord, HTML listing discovery, and one URL per item across methods."""

import dataclasses
from pathlib import Path

import pytest

from src.discovery.feed import feed_records
from src.discovery.html import HtmlListingConfig, html_records, parse_listing_items
from src.discovery.record import SPEC_FIELDS, DiscoveryRecord
from src.discovery.sitemap import sitemap_records
from src.urls import resolve_item_url

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures" / "week3" / "discovery"
NOW = "2026-10-17T00:00:00Z"
PAGE = "https://www.iitb.ac.in/"
CARDS = HtmlListingConfig(item=".homepage-events .views-row", link=".views-field-title a",
                          date=".views-field-field-event-date time", date_attr="datetime",
                          category=".event-category")
TAMING = "https://www.iitb.ac.in/event/institute-lecture-taming-turbulence"


def record(**overrides) -> DiscoveryRecord:
    values = dict(source_name="iit_bombay_events", discovered_url=TAMING, discovery_method="html",
                  discovered_title="Taming Turbulence", source_timestamp="2026-09-03T11:45:00Z", discovered_at=NOW)
    values.update(overrides)
    return DiscoveryRecord(**values)


# -- the record ------------------------------------------------------------------------------------------------

def test_spec_dict_has_exactly_the_six_spec_fields_and_raw_stays_on_the_object():
    r = record(source_timestamp_raw="03 Sep 2026")
    assert tuple(r.to_spec_dict()) == SPEC_FIELDS == ("source_name", "discovered_url", "discovery_method",
                                                      "discovered_title", "source_timestamp", "discovered_at")
    assert "source_timestamp_raw" not in r.to_spec_dict() and r.source_timestamp_raw == "03 Sep 2026"


def test_record_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        record().discovered_url = "https://x.org/"


@pytest.mark.parametrize("field, value, message", [
    ("discovery_method", "json", "discovery_method"),
    ("discovered_url", "/event/relative", "absolute http"),
    ("discovered_url", "mailto:events@iitb.ac.in", "absolute http"),
    ("discovered_url", "ftp://www.iitb.ac.in/x", "absolute http"),
    ("discovered_url", TAMING + "?utm_source=x", "not canonical"),
    ("discovered_url", TAMING + "#main-content", "not canonical"),
    ("discovered_at", "2026-10-17T00:00:00", "discovered_at"),
    ("discovered_at", "2026-10-17", "discovered_at"),
    ("source_timestamp", "2026-09-03T17:15:00+05:30", "source_timestamp"),
    ("source_timestamp", "03 Sep 2026", "source_timestamp"),
])
def test_post_init_validation(field, value, message):
    with pytest.raises(ValueError, match=message):
        record(**{field: value})


def test_source_timestamp_may_be_none():
    assert record(source_timestamp=None).source_timestamp is None


# -- HTML listing discovery -------------------------------------------------------------------------------------

def test_html_only_item_containers_become_records():
    html = (FIX / "listing_cards.html").read_text(encoding="utf-8")
    items = parse_listing_items(html, PAGE, CARDS, "iit_bombay_events", NOW)
    urls = [i.record.discovered_url for i in items]
    assert urls == [TAMING, "https://www.iitb.ac.in/event/international-conference-quantum-dynamics",
                    "https://www.iitb.ac.in/event/van-mahotsav-2026"]       # nav, news card, footer, mailto: none
    taming, quantum, van = items
    assert taming.record.discovered_title == 'Institute Lecture on "Taming Turbulence"'
    assert taming.record.source_timestamp == "2026-09-03T11:45:00Z" and taming.category_label == "Seminar/Talk"
    assert van.record.source_timestamp is None and van.category_label is None   # <time> without datetime attr
    assert all(i.record.discovery_method == "html" and i.record.discovered_at == NOW for i in items)


def test_html_discovery_on_the_real_homepage_events_block():
    from sources.iit_bombay_events import LISTING_SELECTORS
    html = (ROOT / "fixtures" / "week3" / "iitb_events" / "home_2026-10-16.html").read_text(encoding="utf-8")
    records = html_records(html, PAGE, HtmlListingConfig.from_dict(LISTING_SELECTORS), "iit_bombay_events", NOW)
    assert len(records) == 40 and len({r.discovered_url for r in records}) == 40
    assert all(r.discovered_url.startswith("https://www.iitb.ac.in/event/") for r in records)
    by_url = {r.discovered_url: r for r in records}
    assert by_url[TAMING].source_timestamp == "2026-09-03T11:45:00Z"            # 17:15 IST, correct UTC


# -- 1B checkpoint ---------------------------------------------------------------------------------------------

def test_same_item_same_url_across_methods():
    """One event as (a) a relative href in an HTML listing, (b) an RSS link with tracking params and a #fragment,
    (c) a sitemap <loc>: all three records carry the identical canonical discovered_url."""
    html = (FIX / "listing_cards.html").read_text(encoding="utf-8")
    assert 'href="/event/institute-lecture-taming-turbulence"' in html                                  # (a) relative
    rss_bytes = (FIX / "events_rss.xml").read_bytes()
    assert b"institute-lecture-taming-turbulence?utm_source=rss&amp;utm_medium=feed#main-content" in rss_bytes  # (b)
    assert b"<loc>https://www.iitb.ac.in/event/institute-lecture-taming-turbulence</loc>" in (
        FIX / "urlset_with_lastmod.xml").read_bytes()                                                    # (c)

    from_html = next(r for r in html_records(html, PAGE, CARDS, "iit_bombay_events", NOW) if "taming" in r.discovered_url)
    from_rss = next(r for r in feed_records(rss_bytes, "iit_bombay_events", "https://www.iitb.ac.in/rss.xml", NOW)
                    if "taming" in r.discovered_url)
    sm_records, children = sitemap_records((FIX / "urlset_with_lastmod.xml").read_bytes(), "iit_bombay_events",
                                           "https://www.iitb.ac.in/sitemap.xml", NOW)
    from_sitemap = next(r for r in sm_records if "taming" in r.discovered_url)

    assert from_html.discovered_url == from_rss.discovered_url == from_sitemap.discovered_url == TAMING
    assert from_html.to_spec_dict().keys() == from_rss.to_spec_dict().keys() == from_sitemap.to_spec_dict().keys()
    assert (from_html.discovery_method, from_rss.discovery_method, from_sitemap.discovery_method) == ("html", "rss", "sitemap")
    # They differ only in method, title and timestamps:
    same = {"source_name", "discovered_url", "discovered_at"}
    for a, b in ((from_html, from_rss), (from_rss, from_sitemap), (from_html, from_sitemap)):
        differing = {k for k in SPEC_FIELDS if a.to_spec_dict()[k] != b.to_spec_dict()[k]}
        assert differing <= {"discovery_method", "discovered_title", "source_timestamp"} and not differing & same
    assert from_sitemap.discovered_title is None and children == []


def test_feed_and_sitemap_records_are_canonical_and_typed():
    rss = feed_records((FIX / "events_rss.xml").read_bytes(), "s", "https://www.iitb.ac.in/rss.xml", NOW)
    assert [r.discovered_url for r in rss] == [
        TAMING, "https://www.iitb.ac.in/event/international-conference-quantum-dynamics",   # case, :443, fbclid
        "https://www.iitb.ac.in/event/van-mahotsav-2026",                                  # relative link
        "https://www.iitb.ac.in/event/no-date-fixture"]
    atom = feed_records((FIX / "events_atom.xml").read_bytes(), "s", "https://www.iitb.ac.in/atom.xml", NOW)
    assert {r.discovery_method for r in atom} == {"atom"}
    assert atom[1].discovered_url == "https://www.iitb.ac.in/event/5th-japan-india-forum"   # #register dropped
    records, children = sitemap_records((FIX / "sitemap_index.xml").read_bytes(), "s",
                                        "https://www.iitb.ac.in/sitemap.xml", NOW)
    assert records == [] and len(children) == 3
    for r in rss + atom:
        assert resolve_item_url(r.discovered_url, "") == r.discovered_url
