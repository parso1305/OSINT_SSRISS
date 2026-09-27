"""Audit cases 1-15: the real generic runner + IIT Bombay adapter against a local HTTP server.

No mocks of fetch(): the project's Fetcher makes real HTTP requests to 127.0.0.1.
Each test writes its evidence (counts, records, log lines) to logs/after_fixes/evidence/<test>.txt
BEFORE asserting, so a FAIL still leaves the observed behaviour on disk.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from bs4 import BeautifulSoup

from audit_server import AuditSite, Fault, LISTING_PATH, DETAIL_PREFIX, FIXTURES, listing_html, detail_html
from conftest import site_config, db_dump, lines, SOURCE_ID, open_problem

from src.enrich import merge_listing_and_detail
from src.fetcher import FetchError
from src.runner import run_source
from src.schema import validate_record
from src.storage import get_record, count_records
from sources import iit_bombay

ISLANDS = "islands-tri-junction-fragility-and-vulnerability"
TRACING = "tracing-success-indian-democracy-success-nation-building"
ECHOES = "echoes-translation-audibility-and-relationality-indian-jewish-womens-songs-oup"
DETAIL_SLUGS = json.loads((FIXTURES / "detail" / "manifest.json").read_text(encoding="utf-8"))
DETAIL_SLUGS = [m["item_url"].rsplit("/", 1)[-1] for m in DETAIL_SLUGS]
UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def all_records(db: str) -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(db)
    urls = [r[0] for r in conn.execute("SELECT item_url FROM records ORDER BY item_url")]
    conn.close()
    return [get_record(db, u) for u in urls]


# ---------------------------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------------------------

def test_01_full_pipeline_on_fixtures(tmp_path, log_stream, evidence):
    db = str(tmp_path / "t01.db")
    with AuditSite() as site:
        result = run_source(site_config(site), db_path=db)
        requests_made = site.paths()
    stored = all_records(db)
    errors = {r["item_url"]: validate_record(r) for r in stored}
    evidence("counts:", {k: result[k] for k in ("pages_crawled", "stop_reason", "detail_status", "counts")},
             f"invalid (runner) = {result['invalid']}", f"rows in records = {len(stored)}",
             f"validate_record on every stored row: {sum(not e for e in errors.values())}/{len(errors)} valid",
             f"HTTP requests made ({len(requests_made)}): {requests_made}",
             "--- 5 stored records, all fields ---")
    for r in stored[:5]:
        evidence(r)
    evidence("--- full log ---", log_stream.getvalue())
    assert result["counts"] == {"new": 20, "existing": 0, "changed": 0}
    assert len(stored) == 20 and all(not e for e in errors.values())


def test_02_second_run_is_idempotent(tmp_path, evidence):
    db = str(tmp_path / "t02.db")
    with AuditSite() as site:
        first = run_source(site_config(site), db_path=db)
        rows_1 = count_records(db)
        second = run_source(site_config(site), db_path=db)
        rows_2 = count_records(db)
    evidence(f"run1 counts={first['counts']} rows={rows_1}", f"run2 counts={second['counts']} rows={rows_2}")
    assert second["counts"]["new"] == 0 and second["counts"]["changed"] == 0 and rows_1 == rows_2 == 20


def test_03_enrichment_distribution_and_merge_rule(tmp_path, evidence):
    db = str(tmp_path / "t03.db")
    with AuditSite() as site:
        result = run_source(site_config(site), db_path=db)
    evidence("detail_fetch_status distribution:", result["detail_status"])
    by_status = {}
    for r in all_records(db):
        by_status[r["detail_fetch_status"]] = by_status.get(r["detail_fetch_status"], 0) + 1
    evidence("stored rows by detail_fetch_status:", by_status)

    listing = {"item_url": "https://example.org/e/1", "title": "Listing title", "venue": "Room A",
               "description": "listing description", "category": "Seminar"}
    detail = {"item_url": "https://elsewhere.example/other", "title": "Detail title | Humanities and Social Sciences",
              "venue": "", "description": None, "speaker": "Dr Jane Roe", "event_type": "Talk",
              "detail_fetch_status": "forged-by-detail"}
    merged = merge_listing_and_detail(listing, detail)
    evidence("crafted listing:", listing, "crafted detail:", detail, "merged:", merged)

    # title must come from <title>, not field-event-title (Echoes page has a mistyped field-event-title)
    html = detail_html(ECHOES)
    soup = BeautifulSoup(html, "html.parser")
    field_title = soup.select_one(".field--name-field-event-title")
    parsed = iit_bombay.parse_detail(html, "https://www.hss.iitb.ac.in" + DETAIL_PREFIX + ECHOES)
    evidence(f"<title>: {soup.title.get_text()!r}",
             f"field-event-title: {field_title.get_text(' ', strip=True) if field_title else None!r}",
             f"parse_detail title: {parsed['title']!r}",
             f"normalize title: {iit_bombay.normalize(parsed)['title']!r}")

    assert result["detail_status"] == {"ok": 10, "failed": 0, "not_attempted": 10}
    assert merged["title"] == detail["title"]                      # detail wins
    assert merged["venue"] == "Room A"                             # empty detail value does not erase
    assert merged["description"] == "listing description"          # None does not erase
    assert merged["item_url"] == listing["item_url"]               # item_url always from listing
    assert "detail_fetch_status" not in merged                     # provenance key not taken from detail
    assert parsed["title"] == soup.title.get_text(strip=True)


def test_04_normalization_rules(tmp_path, evidence):
    db = str(tmp_path / "t04.db")
    with AuditSite() as site:
        run_source(site_config(site), db_path=db)
        base = site.url
    rows = {r["item_url"].rsplit("/", 1)[-1]: r for r in all_records(db)}
    failures = []
    evidence("slug | raw speaker -> speakers | raw description prefix -> stored prefix | title")
    for slug in DETAIL_SLUGS:
        raw = iit_bombay.parse_detail(detail_html(slug), base + DETAIL_PREFIX + slug)
        rec = rows[slug]
        evidence(f"{slug[:40]:40} | {raw['speaker']!r} -> {rec['speakers']} | "
                 f"{(raw['description'] or '')[:14]!r} -> {(rec['description'] or '')[:14]!r} | {rec['title']!r}")
        if rec["speakers"] and re.match(r"(?i)(prof|dr)\.?\s", rec["speakers"][0]["name"]):
            failures.append(f"honorific kept: {slug}")
        if rec["description"] and re.match(r"(?i)(abstract|description)\s*:", rec["description"]):
            failures.append(f"label kept: {slug}")
    titles_with_suffix = [r["title"] for r in rows.values() if " | Humanities" in (r["title"] or "")]
    bad_utc = [(r["item_url"], r["starts_at"], r["ends_at"]) for r in rows.values()
               if not UTC_Z.match(r["starts_at"] or "") or (r["ends_at"] and not UTC_Z.match(r["ends_at"]))]
    evidence(f"titles still carrying the site suffix: {titles_with_suffix}", f"non-UTC-Z timestamps: {bad_utc}")

    evidence("--- IST display (detail page visible text) vs stored UTC, 3 records ---")
    for slug in DETAIL_SLUGS[:3]:
        visible = BeautifulSoup(detail_html(slug), "html.parser").select_one(
            ".field--name-field-event-date time").get_text(strip=True)          # e.g. 'Thu, 09/25/2025 - 15:30'
        ist = datetime.strptime(visible, "%a, %m/%d/%Y - %H:%M").replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        expected = ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        evidence(f"{slug[:40]:40} visible IST={visible!r} -> UTC {expected} | stored starts_at={rows[slug]['starts_at']} "
                 f"| timezone={rows[slug]['timezone']}")
        if expected != rows[slug]["starts_at"]:
            failures.append(f"IST/UTC mismatch {slug}")

    online = {r["venue"]: r["is_online"] for r in rows.values()}
    evidence("venue -> is_online:", online)
    babones = rows[TRACING]["speakers"]
    evidence(f"affiliation split (Tracing): {babones}")
    evidence(f"failures: {failures}")
    assert not failures and not titles_with_suffix and not bad_utc
    assert babones == [{"name": "Salvatore Babones", "affiliation": "University of Sydney"}]
    assert all(v is True for k, v in online.items() if k and "online" in k.lower())
    assert all(v is None for k, v in online.items() if not k or "online" not in k.lower())


# ---------------------------------------------------------------------------------------------
# Failure and edge cases
# ---------------------------------------------------------------------------------------------

def _detail_failure_case(tmp_path, log_stream, evidence, fault, **cfg):
    db = str(tmp_path / "detail_fail.db")
    target = DETAIL_PREFIX + TRACING
    with AuditSite() as site:
        site.faults[target] = fault
        result = run_source(site_config(site, **cfg), db_path=db)
        stored = get_record(db, site.url + target)
    log = log_stream.getvalue()
    evidence(f"detail_status={result['detail_status']} counts={result['counts']}",
             "stored record for the failing item:", stored,
             "--- relevant log lines ---", lines(log, "DETAIL_FAILURE", "FETCH_ERROR", TRACING, "ENRICH", "FAILURE"))
    assert stored is not None, "listing record must be kept"
    assert stored["detail_fetch_status"] == "failed"
    assert result["detail_status"]["ok"] == 9, "other items must continue"
    assert "logger=web_monitor.detail DETAIL_FAILURE" in log
    assert "[ERROR]" not in log, "a detail failure must not produce a listing-level FAILURE"
    return stored


def test_05_detail_404(tmp_path, log_stream, evidence):
    stored = _detail_failure_case(tmp_path, log_stream, evidence, Fault(status=404))
    assert stored["detail_http_status"] == 404


@pytest.mark.parametrize("kind", ["500", "timeout", "connection_reset"])
def test_06_detail_500_timeout_reset(tmp_path, log_stream, evidence, kind):
    fault = {"500": Fault(status=500), "timeout": Fault(sleep_s=3.0), "connection_reset": Fault(reset=True)}[kind]
    stored = _detail_failure_case(tmp_path, log_stream, evidence, fault, timeout_s=1.0)
    evidence(f"detail_http_status={stored['detail_http_status']} detail_error={stored['detail_error']!r}")


@pytest.mark.parametrize("kind", ["404", "500", "timeout"])
def test_07_listing_failure_leaves_db_unchanged(tmp_path, log_stream, evidence, kind):
    """Through the scheduler (so the run is recorded in `runs`), on a DB that already holds data."""
    import logging
    from src.scheduler import run_once
    from src.storage import list_runs
    from conftest import write_sandbox_config, real_entry
    db, locks = str(tmp_path / "t07.db"), tmp_path / "locks"
    with AuditSite() as site:
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url,
                                                                          request_delay_s=0, timeout_s=1.0)])
        run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=logging.getLogger("web_monitor"))
        before = db_dump(db)
        site.faults[LISTING_PATH] = {"404": Fault(status=404), "500": Fault(status=500), "timeout": Fault(sleep_s=3.0)}[kind]
        mark = len(log_stream.getvalue())
        result = run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=logging.getLogger("web_monitor"))[0]
        after = db_dump(db)
    runs = [(r["status"], r["error"]) for r in list_runs(db)]
    log = log_stream.getvalue()[mark:]
    evidence(f"records before: sha256={before[0][:16]} rows={before[1]}", f"records after:  sha256={after[0][:16]} rows={after[1]}",
             f"scheduler result: {result}", f"runs table: {runs}", "--- log of the failing run ---", log)
    assert result["status"] == "failed" and runs[-1][0] == "failed"
    assert "FAILURE source_id=" in log and "stage=fetch" in log
    assert before == after


@pytest.mark.parametrize("change", ["card_class_renamed", "container_renamed", "detail_article_renamed",
                                    pytest.param("detail_speaker_field_renamed", marks=open_problem(
                                        "m11", "a renamed detail field silently yields None, no warning"))])
def test_08_html_structure_changed(tmp_path, log_stream, evidence, change):
    import logging
    from src.scheduler import run_once
    from src.storage import list_runs
    from conftest import write_sandbox_config, real_entry
    db, locks = str(tmp_path / "t08.db"), tmp_path / "locks"
    with AuditSite() as site:
        if change == "card_class_renamed":
            site.faults[LISTING_PATH] = Fault(body=listing_html().replace("event-card-wrapper", "event-card-box"))
        elif change == "container_renamed":
            site.faults[LISTING_PATH] = Fault(body=listing_html().replace("view-seminars-and-talks", "view-talks-list"))
        else:
            old, new = (("node--type-events", "node--type-talk") if change == "detail_article_renamed"
                        else ("field--name-field-event-speaker", "field--name-field-event-presenter"))
            for slug in DETAIL_SLUGS:
                site.faults[DETAIL_PREFIX + slug] = Fault(body=detail_html(slug).replace(old, new))
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0)])
        result = run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=logging.getLogger("web_monitor"))[0]
    runs = list_runs(db)
    log = log_stream.getvalue()
    rows = count_records(db) if result["status"] == "success" else 0
    speakers = None
    if change == "detail_speaker_field_renamed":
        speakers = [r["speakers"] for r in all_records(db) if r["detail_fetch_status"] == "ok"]
    evidence(f"scheduler result: {result}", f"runs: {[(r['status'], r['new_count'], r['failed_count'], r['error']) for r in runs]}",
             f"rows stored: {rows}", f"speakers on ok-enriched rows: {speakers}",
             "--- WARNING/ERROR/summary lines ---",
             lines(log, "[WARNING]", "[ERROR]", "PARSE records", "ENRICH", "VALIDATE", "STORE", "RUN_END"))
    if change == "card_class_renamed":
        assert "parsed 0 items" in log                                  # the guard fires ...
        assert result["status"] == "failed", "200-with-0-items should not be a 'success' run"   # ... but the run?
    elif change == "container_renamed":
        assert result["status"] == "failed" and "StructuralError" in log
    elif change == "detail_article_renamed":
        assert log.count("DETAIL_FAILURE") == 10 and "StructuralError" in log
    else:
        assert "[WARNING]" in log, "a detail page whose speaker field vanished should at least warn"


@pytest.mark.parametrize("variant", ["detail_datetime_textual", "detail_datetime_textual_existing_db",
                                     "detail_and_listing_dates_unparseable"])
def test_09_date_format_changed(tmp_path, log_stream, evidence, variant):
    db = str(tmp_path / "t09.db")
    with AuditSite() as site:
        cfg = site_config(site, supports_pagination=False)
        baseline = None
        if variant == "detail_datetime_textual_existing_db":
            run_source(cfg, db_path=db)
            baseline = get_record(db, site.url + DETAIL_PREFIX + ISLANDS)
        for slug in DETAIL_SLUGS:
            html = re.sub(r'datetime="[^"]+"', 'datetime="25 September 2025"', detail_html(slug))
            site.faults[DETAIL_PREFIX + slug] = Fault(body=html)
        if variant == "detail_and_listing_dates_unparseable":
            site.faults[LISTING_PATH] = Fault(body=re.sub(r"(icon-calendar\"></i>)[^<]+", r"\g<1>2025/09/25 ", listing_html()))
        mark = len(log_stream.getvalue())
        result = run_source(cfg, db_path=db)
        after = get_record(db, site.url + DETAIL_PREFIX + ISLANDS)
    log = log_stream.getvalue()[mark:]
    evidence(f"counts={result['counts']} detail={result['detail_status']} invalid={len(result['invalid'])}",
             f"baseline (before format change): starts_at={baseline and baseline['starts_at']} ends_at={baseline and baseline['ends_at']}",
             f"after format change:            starts_at={after and after['starts_at']} ends_at={after and after['ends_at']}",
             f"first invalid: {result['invalid'][:1]}",
             "--- WARNING/ERROR lines ---", lines(log, "[WARNING]", "[ERROR]") or "(none)",
             lines(log, "VALIDATE", "STORE"))
    has_warning = "[WARNING]" in log or "[ERROR]" in log
    if variant == "detail_and_listing_dates_unparseable":
        assert result["invalid"] and "VALIDATION_FAILURE" in log      # loud: records rejected
    else:
        # starts_at survives via the listing fallback, but ends_at is silently lost with no log line
        assert has_warning, f"format change produced no warning; ends_at now {after['ends_at']!r}"


def test_10_missing_optional_fields(tmp_path, evidence):
    db = str(tmp_path / "t10.db")
    soup = BeautifulSoup(detail_html(ISLANDS), "html.parser")
    for cls in ("field--name-field-event-speaker", "field--name-field-event-location", "field--name-field-event-end-date"):
        for el in soup.select("." + cls):
            el.decompose()
    lsoup = BeautifulSoup(listing_html(), "html.parser")
    for card in lsoup.select(".event-card-wrapper"):
        if ISLANDS in card.select_one(".event-name a")["href"]:
            for li in card.select(".event-room-details li"):
                if li.select_one("i.icon-marker"):
                    li.decompose()
    with AuditSite() as site:
        site.faults[DETAIL_PREFIX + ISLANDS] = Fault(body=str(soup))
        site.faults[LISTING_PATH] = Fault(body=str(lsoup))
        result = run_source(site_config(site, supports_pagination=False), db_path=db)
        rec = get_record(db, site.url + DETAIL_PREFIX + ISLANDS)
    evidence(f"counts={result['counts']} invalid={result['invalid']}", rec, f"validate_record: {validate_record(rec)}")
    assert rec is not None and validate_record(rec) == []
    assert rec["speakers"] == [] and rec["venue"] is None and rec["ends_at"] is None


# Case 11 (six href forms -> one item) was superseded by the path-as-given fix (2026-09-27). Its replacement,
# matching the intended behaviour, is tests/test_audit_regressions.py::test_case11_href_forms_that_differ_only_in_host_query_or_fragment_are_one_item


@pytest.mark.parametrize("kind", ["detail_500", "detail_timeout", "beyond_detail_limit", pytest.param(
    "listing_disagrees_with_detail", marks=open_problem("m2", "on a failed detail fetch a differing listing value "
                                                              "overwrites the stored detail value"))])
def test_12_failed_refetch_is_not_a_change(tmp_path, log_stream, evidence, kind):
    db = str(tmp_path / "t12.db")
    target = DETAIL_PREFIX + ISLANDS
    with AuditSite() as site:
        if kind == "listing_disagrees_with_detail":
            # Real-world drift: the listing card shows a different venue spelling than the detail page.
            site.faults[LISTING_PATH] = Fault(body=listing_html().replace(
                'icon-marker"></i> LT 101', 'icon-marker"></i> LT-101, HSS Building', 1))
        cfg = site_config(site, supports_pagination=False, timeout_s=1.0)
        run_source(cfg, db_path=db)
        before = get_record(db, site.url + target)
        if kind == "detail_500":
            site.faults[target] = Fault(status=500)
        elif kind == "detail_timeout":
            site.faults[target] = Fault(sleep_s=3.0)
        elif kind == "listing_disagrees_with_detail":
            site.faults[target] = Fault(status=500)
        else:
            cfg = site_config(site, supports_pagination=False, detail_limit=0)
        second = run_source(cfg, db_path=db)
        after = get_record(db, site.url + target)
    changed_fields = [f for f in ("title", "starts_at", "ends_at", "speakers", "venue", "event_type", "description", "is_online")
                      if before[f] != after[f]]
    evidence(f"run1: status={before['detail_fetch_status']} venue={before['venue']!r} desc={before['description'][:50]!r}",
             f"run2: counts={second['counts']} status={after['detail_fetch_status']} venue={after['venue']!r} "
             f"desc={(after['description'] or '')[:50]!r}",
             f"content fields that differ run1 -> run2: {changed_fields}",
             f"content_hash equal: {before['content_hash'] == after['content_hash']}")
    assert second["counts"]["changed"] == 0 and not changed_fields


def test_13_real_detail_change_is_detected(tmp_path, evidence):
    db = str(tmp_path / "t13.db")
    target = DETAIL_PREFIX + ISLANDS
    with AuditSite() as site:
        cfg = site_config(site, supports_pagination=False)
        run_source(cfg, db_path=db)
        site.faults[target] = Fault(body=detail_html(ISLANDS).replace("constitute an unique system", "constitute a unique system"))
        second = run_source(cfg, db_path=db)
        after = get_record(db, site.url + target)
    evidence(f"run2 counts={second['counts']}", f"stored description now: {after['description'][:90]!r}")
    assert second["counts"] == {"new": 0, "existing": 9, "changed": 1}
    assert "constitute a unique system" in after["description"]


@pytest.mark.parametrize("scenario", ["max_pages_2_of_3", "empty_page_2", "repeated_page_2", "pagination_disabled",
                                      "next_page_404"])
def test_14_pagination(tmp_path, log_stream, evidence, scenario):
    db = str(tmp_path / "t14.db")
    with AuditSite() as site:
        cfg = {"max_pages_2_of_3": dict(max_pages=2), "empty_page_2": dict(max_pages=3),
               "repeated_page_2": dict(max_pages=3), "pagination_disabled": dict(supports_pagination=False),
               "next_page_404": dict(max_pages=5)}[scenario]
        if scenario == "empty_page_2":
            soup = BeautifulSoup(listing_html("live_page_2.html"), "html.parser")
            for c in soup.select(".event-card-wrapper"):
                c.decompose()
            site.faults[LISTING_PATH + "?page=1"] = Fault(body=str(soup))
        if scenario == "repeated_page_2":
            site.faults[LISTING_PATH + "?page=1"] = Fault(body=listing_html())
        result = run_source(site_config(site, detail_limit=0, **cfg), db_path=db)
        listing_gets = [p for p in site.paths() if p.startswith(LISTING_PATH)]
    evidence(f"config: {cfg}", f"pages_crawled={result['pages_crawled']} stop_reason={result['stop_reason']} counts={result['counts']}",
             f"listing GETs: {listing_gets}", lines(log_stream.getvalue(), "PAGINATE", "Page ", "FAILURE"))
    expected = {"max_pages_2_of_3": (2, "max_pages_reached"), "empty_page_2": (2, "empty_listing"),
                "repeated_page_2": (2, "repeated_items"), "pagination_disabled": (1, "max_pages_reached"),
                "next_page_404": (3, "fetch_failed")}[scenario]
    assert (result["pages_crawled"], result["stop_reason"]) == expected
    assert len(listing_gets) == {"next_page_404": 4}.get(scenario, expected[0])


@pytest.mark.parametrize("variant", ["cp1252_no_charset", "cp1252_declared_utf8", "truncated_html", "binary_garbage",
                                     "listing_latin1_declared"])
def test_15_encoding_and_malformed_html(tmp_path, log_stream, evidence, variant):
    db = str(tmp_path / "t15.db")
    target = DETAIL_PREFIX + ECHOES
    html = detail_html(ECHOES)
    with AuditSite() as site:
        if variant == "cp1252_no_charset":
            site.faults[target] = Fault(body=html.encode("cp1252", "replace"), content_type="text/html")
        elif variant == "cp1252_declared_utf8":
            site.faults[target] = Fault(body=html.encode("cp1252", "replace"), content_type="text/html; charset=UTF-8")
        elif variant == "truncated_html":
            cut = html.index("field--name-field-event-speaker") + 40
            site.faults[target] = Fault(body=html[:cut])
        elif variant == "binary_garbage":
            site.faults[target] = Fault(body=bytes(range(256)) * 40, content_type="text/html")
        else:
            site.faults[LISTING_PATH] = Fault(body=listing_html().encode("latin-1", "replace"),
                                              content_type="text/html; charset=ISO-8859-1")
        crashed = None
        try:
            result = run_source(site_config(site, supports_pagination=False), db_path=db)
        except Exception as e:  # noqa: BLE001 - recording, not hiding
            crashed, result = f"{type(e).__name__}: {e}", None
        rec = get_record(db, site.url + target) if result else None
    evidence(f"crashed: {crashed}", f"counts={result and result['counts']} detail={result and result['detail_status']}",
             f"record: title={rec and rec['title']!r}", f"speakers={rec and rec['speakers']} status={rec and rec['detail_fetch_status']}",
             f"description[:80]={rec and (rec['description'] or '')[:80]!r}",
             lines(log_stream.getvalue(), "DETAIL_FAILURE", "[ERROR]"))
    assert crashed is None
