"""Generic change G10: html discovery through an adapter listing hook named in config (listing_options)."""

from types import SimpleNamespace

import pytest

from src.config import SourceConfig
from src.discovery.discover import discover_items
from src.fetcher import FetchResult

PAGE = "https://events.example.org/calendar"


class OnePage:
    def get(self, url):
        return FetchResult(url=url, final_url=url, status=200, text="<html>{json here}</html>", duration_ms=1,
                           fetched_at="2026-10-20T00:00:00Z", content_type="text/html")


def adapter(seen):
    def entries(text, page_url, options, now_iso):
        seen.append((text, page_url, options, now_iso))
        return [{"href": "/event/a?utm_source=cal#top", "title": "  Lecture A ", "timestamp_raw": "2026-11-01T17:15:00"},
                {"href": "mailto:x@example.org", "title": "not an item"},
                {"href": "/event/b", "title": "Lecture B", "timestamp": "2026-11-02T10:00:00Z", "category": "Talk"}]
    return SimpleNamespace(__name__="hook_adapter", calendar_entries=entries)


def config(adapter_obj, options):
    return SourceConfig(source_id="s", institution="X", adapter=adapter_obj, listing_url=PAGE, pipeline="aggregator",
                        discovery="html", listing_options=options,
                        scope={"allowed_hosts": ["events.example.org"], "allowed_prefixes": ["/event/"]})


def test_hook_receives_the_page_and_the_config_options_and_records_are_canonical():
    seen = []
    options = {"hook": "calendar_entries", "utc_offset": "+05:30", "include_title_keywords": ["Lecture"]}
    candidates = discover_items(config(adapter(seen), options), OnePage())
    assert seen[0][1] == PAGE and seen[0][2] == options and seen[0][3].endswith("Z")
    assert [c.url for c in candidates] == ["https://events.example.org/event/a", "https://events.example.org/event/b"]
    a, b = candidates
    assert a.record.discovered_title == "Lecture A" and a.record.source_timestamp == "2026-11-01T11:45:00Z"
    assert a.record.source_timestamp_raw == "2026-11-01T17:15:00" and a.record.discovery_method == "html"
    assert b.record.source_timestamp == "2026-11-02T10:00:00Z" and b.category_label == "Talk"


def test_missing_hook_is_a_clear_error():
    with pytest.raises(ValueError, match="no listing hook 'nope'"):
        discover_items(config(adapter([]), {"hook": "nope"}), OnePage())


def test_listing_options_need_a_hook_name():
    with pytest.raises(ValueError, match="needs a 'hook'"):
        config(adapter([]), {"include_title_keywords": ["Lecture"]})
