"""IIT Bombay adapter on real saved HTML: parse_listing, parse_detail, normalize (Section 0 fixtures)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from bs4 import BeautifulSoup

from scripts.fixture_site import FIXTURES
from src.enrich import merge_listing_and_detail
from sources import iit_bombay

LISTING_URL = "https://www.hss.iitb.ac.in/events/seminars-and-talks"
SEMINAR = "https://www.hss.iitb.ac.in/events/seminar-talk/"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def page1() -> list[dict]:
    return iit_bombay.parse_listing(read("listing_2026-09-26.html"), base_url=LISTING_URL)


def merged_page1() -> list[dict]:
    return [merge_listing_and_detail(it, iit_bombay.parse_detail(read(f"detail/{it['item_url'].rsplit('/', 1)[-1]}.html"), it["item_url"]))
            for it in page1()]


# -- parse_listing / parse_detail ------------------------------------------

def test_parse_listing_real_pages():
    items = page1()
    assert len(items) == 10
    first = items[0]
    assert first["item_url"] == SEMINAR + "islands-tri-junction-fragility-and-vulnerability"
    assert first["raw_href"] == "/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability"
    assert first["title"] == "The A&N Islands – At the tri-junction of fragility and vulnerability"
    assert (first["date_raw"], first["time_raw"], first["venue"], first["category"]) == \
        ("25th Sep 2025", "15:30 PM", "LT 101", "Seminar / Talk")
    for name in ("live_page_2.html", "live_page_3.html"):
        assert len(iit_bombay.parse_listing(read(name), base_url=LISTING_URL)) == 10


def test_parse_listing_redesign_fails_loudly():
    soup = BeautifulSoup(read("listing_2026-09-26.html"), "html.parser")
    soup.select_one(".view-seminars-and-talks").decompose()
    with pytest.raises(iit_bombay.StructuralError):
        iit_bombay.parse_listing(str(soup), base_url=LISTING_URL)


def test_parse_detail_real_page_raw_fields():
    url = SEMINAR + "islands-tri-junction-fragility-and-vulnerability"
    d = iit_bombay.parse_detail(read("detail/islands-tri-junction-fragility-and-vulnerability.html"), url)
    assert d["title"] == "The A&N Islands – At the tri-junction of fragility and vulnerability | Humanities and Social Sciences"
    assert d["speaker"] == "Prof Pankaj Sekhsaria"
    assert (d["starts_at"], d["ends_at"]) == ("2025-09-25T10:00:00Z", "2025-09-25T11:00:00Z")
    assert (d["venue"], d["event_type"], d["node_id"]) == ("LT 101", "Seminar / Talk", "2809")
    assert d["description"].startswith("Abstract: The Andaman and Nicobar Islands")
    assert d["detail_canonical_url"] == url


def test_parse_detail_every_saved_page_has_every_field():
    for path in (FIXTURES / "detail").glob("*.html"):
        d = iit_bombay.parse_detail(path.read_text(encoding="utf-8"), SEMINAR + path.stem)
        assert all(d.values()), f"{path.name}: {[k for k, v in d.items() if not v]}"


def test_parse_detail_non_event_page_fails_loudly():
    with pytest.raises(iit_bombay.StructuralError):
        iit_bombay.parse_detail("<html><title>Page not found</title></html>", SEMINAR + "x")


# -- normalize ---------------------------------------------------------------

def by_slug(records: list[dict], slug: str) -> dict:
    return next(iit_bombay.normalize(r) for r in records if r["item_url"].endswith("/" + slug))


def test_normalize_speakers_honorifics_and_affiliation():
    merged = merged_page1()
    assert by_slug(merged, "islands-tri-junction-fragility-and-vulnerability")["speakers"] == \
        [{"name": "Pankaj Sekhsaria", "affiliation": None}]                                   # "Prof X"
    assert by_slug(merged, "tracing-success-indian-democracy-success-nation-building")["speakers"] == \
        [{"name": "Salvatore Babones", "affiliation": "University of Sydney"}]                # "Prof X, Affiliation"
    assert by_slug(merged, "translating-untranslatability-environmental-justice-and-sacredness-spivaks")["speakers"] == \
        [{"name": "Sayan Chattopadhyay", "affiliation": None}]                                # "Dr X"
    assert by_slug(merged, "rortys-revolution")["speakers"] == [{"name": "Carlin Romano", "affiliation": None}]  # bare
    names = [s["name"] for r in merged for s in iit_bombay.normalize(r)["speakers"]]
    assert len(names) == 10 and not any(n.startswith(("Prof", "Dr")) for n in names)


def test_normalize_description_label_prefixes():
    merged = merged_page1()
    abstract = by_slug(merged, "islands-tri-junction-fragility-and-vulnerability")["description"]      # "Abstract:"
    labelled = by_slug(merged, "echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup")["description"]  # "Description:"
    plain = by_slug(merged, "embodied-translation")["description"]                                     # no label
    assert abstract.startswith("The Andaman and Nicobar Islands")
    assert labelled.startswith("The Bene Israel are a Jewish community")
    assert plain.startswith("This seminar introduces my concept of embodied translation")
    assert not any(iit_bombay.normalize(r)["description"].startswith(("Abstract", "Description")) for r in merged)


def test_normalize_title_suffix_stripped():
    for record in merged_page1():
        title = iit_bombay.normalize(record)["title"]
        assert "|" not in title and "Humanities and Social Sciences" not in title


def test_normalize_dates_utc_and_listing_fallback_agrees_with_detail():
    for listing, merged in zip(page1(), merged_page1()):
        from_detail = iit_bombay.normalize(merged)
        from_listing = iit_bombay.normalize(listing)          # no detail: date_raw + time_raw (IST)
        assert from_detail["starts_at"].endswith("Z") and from_detail["ends_at"].endswith("Z")
        assert from_listing["starts_at"] == from_detail["starts_at"]
        assert from_listing["ends_at"] is None
        assert from_detail["timezone"] == "Asia/Kolkata"
    assert iit_bombay.normalize(page1()[0])["starts_at"] == "2025-09-25T10:00:00Z"   # 15:30 IST


def test_normalize_is_online_only_when_stated():
    values = {r["item_url"].rsplit("/", 1)[-1]: iit_bombay.normalize(r)["is_online"] for r in merged_page1()}
    assert values["tracing-success-indian-democracy-success-nation-building"] is True   # "Online Seminar"
    assert sum(v is True for v in values.values()) == 1
    assert all(v is None for k, v in values.items() if k != "tracing-success-indian-democracy-success-nation-building")


def test_normalize_drops_rejected_image_url_and_keeps_node_id_in_extras():
    out = by_slug(merged_page1(), "islands-tri-junction-fragility-and-vulnerability")
    assert "image_url" not in out and "image_url" not in out["extras"]
    assert out["extras"]["node_id"] == "2809"
