"""Week 3 Section 8: content router (structural evidence only) and discovered_items persistence."""

import pytest

from src.aggregator import discovered_item_row, route_candidate
from src.config import load_source_configs
from src.discovery.discover import DiscoveryCandidate
from src.discovery.record import DiscoveryRecord
from src.router import LABELS, classify_discovered_item, classify_with_reason, fetchable_as_html
from src.schema import ITEM_TYPES
from src.storage import _open, get_discovered_item, upsert_discovered_items

CFG = load_source_configs()["iit_bombay_events"].router
NOW = "2026-10-17T00:00:00Z"


def rec(url: str) -> DiscoveryRecord:
    return DiscoveryRecord(source_name="iit_bombay_events", discovered_url=url, discovery_method="html",
                           discovered_title=None, source_timestamp=None, discovered_at=NOW)


def test_pdf_under_events_is_a_pdf_document_and_never_fetched_as_html():
    label, reason = classify_with_reason(rec("https://www.iitb.ac.in/events/brochure-iccms-2027.pdf"), cfg=CFG)
    assert (label, reason) == ("pdf_document", "path ends in .pdf (no Content-Type known yet)")
    assert not fetchable_as_html(label)


def test_event_link_to_an_external_registration_site():
    label, reason = classify_with_reason(rec("https://www.iitbombay.org/e/ieor-alumni-meet-2026"),
                                         category_label="Seminar/Talk", cfg=CFG)
    assert label == "external_link" and reason.startswith("external host www.iitbombay.org")   # before the label
    assert not fetchable_as_html(label)


def test_news_item_with_no_category_label_routes_by_url_pattern():
    url = "https://www.iitb.ac.in/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug"
    assert classify_with_reason(rec(url), cfg=CFG) == ("announcement", "URL pattern /breaking-news/")


def test_text_html_on_a_pdf_url_is_not_a_pdf():
    """The server's Content-Type beats the file extension (after the fetch)."""
    url = "https://www.iitb.ac.in/events/programme.pdf"
    assert classify_discovered_item(rec(url), cfg=CFG) == "pdf_document"              # before fetching
    label, reason = classify_with_reason(rec(url), content_type="text/html; charset=UTF-8", cfg=CFG)
    assert (label, reason) == ("event", "URL pattern /events/ (Content-Type text/html)")


def test_application_pdf_on_an_extensionless_url():
    label, reason = classify_with_reason(rec("https://www.iitb.ac.in/event/download-brochure"),
                                         content_type="application/pdf", cfg=CFG)
    assert (label, reason) == ("pdf_document", "Content-Type application/pdf")


def test_faculty_url_pattern():
    assert classify_with_reason(rec("https://www.iitb.ac.in/employee/prof-indu-j"), cfg=CFG) == \
        ("faculty", "URL pattern /employee/")


def test_category_label_beats_url_pattern_but_not_pdf_or_external():
    assert classify_with_reason(rec("https://www.iitb.ac.in/breaking-news/x"), category_label="seminar/talk",
                                cfg=CFG) == ("event", "category label 'seminar/talk'")
    assert classify_discovered_item(rec("https://www.iitb.ac.in/breaking-news/x.pdf"), category_label="Seminar/Talk",
                                    cfg=CFG) == "pdf_document"


def test_unknown_item_is_persisted_with_its_reason(tmp_path):
    url = "https://www.iitb.ac.in/node/6913"          # REAL /rss.xml item with no type in its URL
    candidate = DiscoveryCandidate(record=rec(url), discovery_methods=("rss",), in_scope=False,
                                   scope_reason="outside allowed prefixes: /node/6913")
    label, reason = route_candidate(candidate, CFG)
    assert (label, reason) == ("unknown", "no rule matched (host www.iitb.ac.in, path /node/6913)")
    db = str(tmp_path / "router.db")
    conn = _open(db)
    with conn:
        assert upsert_discovered_items(conn, [discovered_item_row(candidate, label, reason)]) == 1
    conn.close()
    stored = get_discovered_item(db, url)
    assert stored["content_class"] == "unknown" and stored["class_reason"] == reason
    assert stored["in_scope"] is False and stored["scope_reason"] == "outside allowed prefixes: /node/6913"
    assert stored["discovery_methods"] == ["rss"] and stored["first_discovered_at"] == NOW


def test_first_discovered_at_is_kept_on_rediscovery(tmp_path):
    db = str(tmp_path / "router.db")
    first = discovered_item_row(DiscoveryCandidate(record=rec("https://www.iitb.ac.in/event/x"),
                                                   discovery_methods=("html",)), "event", "URL pattern /event/")
    later = dict(first, last_discovered_at="2026-10-18T00:00:00Z", first_discovered_at="2026-10-18T00:00:00Z",
                 discovery_methods=["html", "rss"])
    conn = _open(db)
    with conn:
        upsert_discovered_items(conn, [first])
        upsert_discovered_items(conn, [later])
    conn.close()
    stored = get_discovered_item(db, "https://www.iitb.ac.in/event/x")
    assert (stored["first_discovered_at"], stored["last_discovered_at"]) == (NOW, "2026-10-18T00:00:00Z")
    assert stored["discovery_methods"] == ["html", "rss"]


def test_only_classes_with_a_records_parser_are_item_types():
    assert ITEM_TYPES == ("event",)          # announcements/faculty/pdfs stay in discovered_items (DECISIONS D25)
    assert set(LABELS) == {"event", "announcement", "faculty", "pdf_document", "external_link", "unknown"}


def test_router_config_rejects_unknown_labels():
    with pytest.raises(ValueError, match="not in"):
        classify_discovered_item(rec("https://www.iitb.ac.in/x"), cfg={"url_patterns": {"seminar": ["/x"]}})
