"""A second, unrelated source runs through the generic runner with only an adapter + a config entry.

The adapter is a module object built here; the site is a local HTTP server serving FAKE_HTML
(synthetic, clearly not a real institution).
"""

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup

from scripts.fixture_site import FixtureSite
from src.config import SourceConfig
from src.runner import run_source
from src.storage import count_records, get_record
from src.urls import resolve_item_url

FAKE_HTML = """
<html><body>
  <ul class="talks">
    <li><a href="/talks/quantum-2026">Quantum Algorithms for Cryptanalysis</a>
        <span class="when">2026-10-01T09:00:00Z</span><span class="where">Hall B</span></li>
    <li><a href="/talks/ml-ethics">Ethics of Machine Learning</a>
        <span class="when">2026-10-08T09:00:00Z</span><span class="where">Online</span></li>
  </ul>
</body></html>
"""


def make_fake_adapter() -> types.ModuleType:
    adapter = types.ModuleType("fake_university_adapter")

    def parse_listing(html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        return [{
            "title": li.a.get_text(strip=True),
            "item_url": resolve_item_url(li.a["href"], base_url),
            "when": li.select_one(".when").get_text(strip=True),
            "where": li.select_one(".where").get_text(strip=True),
        } for li in soup.select("ul.talks li")]

    def normalize(record: dict) -> dict:
        return {"title": record["title"], "starts_at": record["when"], "venue": record["where"],
                "is_online": record["where"] == "Online" or None}

    adapter.parse_listing = parse_listing
    adapter.normalize = normalize
    return adapter


def test_new_source_needs_only_adapter_and_config(tmp_path):
    with FixtureSite(overrides={"/talks": FAKE_HTML}) as site:
        config = SourceConfig(source_id="fake_university_talks", institution="Fake University",
                              adapter=make_fake_adapter(), listing_url=site.url + "/talks", request_delay_s=0)
        db = str(tmp_path / "fake.db")
        first = run_source(config, db_path=db)
        second = run_source(config, db_path=db)

    assert first["counts"] == {"new": 2, "existing": 0, "changed": 0}
    assert second["counts"] == {"new": 0, "existing": 2, "changed": 0}
    assert count_records(db, source_id="fake_university_talks") == 2
    stored = get_record(db, site.url + "/talks/quantum-2026")
    assert stored["title"] == "Quantum Algorithms for Cryptanalysis"
    assert stored["institution"] == "Fake University"
    assert stored["detail_fetch_status"] == "not_attempted"


# -- items without their own URL, date-only events (assumptions found on CMI by the Week 2 audit) --------

NO_LINKS_HTML = """
<html><body><ul class="seminars">
  <li data-ref="41"><b>Knot invariants</b> <i>2026-10-02</i> <span>All day</span></li>
  <li data-ref="42"><b>Sheaf cohomology</b> <i>2026-10-05</i> <span>15:00</span></li>
</ul></body></html>
"""


def make_no_links_adapter() -> types.ModuleType:
    from src.urls import synthetic_item_url
    adapter = types.ModuleType("fake_no_links_adapter")

    def parse_listing(html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        return [{"item_url": synthetic_item_url(base_url, li["data-ref"]), "title": li.b.get_text(strip=True),
                 "date": li.i.get_text(strip=True), "time": li.span.get_text(strip=True)}
                for li in soup.select("ul.seminars li")]

    def normalize(record: dict) -> dict:
        timed = record["time"] != "All day"
        return {"title": record["title"], "timezone": "UTC",
                "starts_at": f"{record['date']}T{record['time']}:00Z" if timed else record["date"]}

    adapter.parse_listing, adapter.normalize = parse_listing, normalize
    return adapter


def test_source_without_item_links_and_with_a_date_only_event(tmp_path):
    with FixtureSite(overrides={"/seminars": NO_LINKS_HTML, "/seminars?page=2": NO_LINKS_HTML}) as site:
        config = SourceConfig(source_id="fake_no_links", institution="Fake Institute", adapter=make_no_links_adapter(),
                              listing_url=site.url + "/seminars", request_delay_s=0)
        db = str(tmp_path / "nolinks.db")
        first = run_source(config, db_path=db)
        again = run_source(SourceConfig(**{**config.__dict__, "listing_url": site.url + "/seminars?page=2"}), db_path=db)
    assert first["invalid"] == [] and first["counts"] == {"new": 2, "existing": 0, "changed": 0}
    assert again["counts"] == {"new": 0, "existing": 2, "changed": 0}          # page param does not change identity
    starts = sorted(r["starts_at"] for r in first["records"])
    assert starts == ["2026-10-02", "2026-10-05T15:00:00Z"]
    assert all(r["item_url"].startswith(site.url + "/seminars#/item/") for r in first["records"])
    assert count_records(db, source_id="fake_no_links") == 2
