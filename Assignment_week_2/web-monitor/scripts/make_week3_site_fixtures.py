"""Builds the offline IIT Bombay events site used by source local_aggregator_fixture (Week 3 Sections 9-10).

From REAL saved pages only:
  fixtures/week3/iitb_events/site/home.html          the real homepage (2026-10-16) with its events block
      rewritten to list every saved detail page (fixtures/week3/iitb_events/detail/*.html), newest event first, in
      the block's real markup, plus three non-event rows the router must handle: an external registration link,
      a PDF brochure and a breaking-news item. Header, navigation, footer and social links are the real ones.
  fixtures/week3/iitb_events/site/home_changed.html  the "next day" listing: two events gone (not seen this run)
      and one new event at the top
  fixtures/week3/iitb_events/site/events.rss         a small RSS feed with three of the same events, linked with
      tracking parameters and #fragments (relative links), so discovery dedup across html + rss is exercised
  fixtures/week3/iitb_events/site/detail_changed/institute-lecture-taming-turbulence.html   venue changed
  fixtures/week3/iitb_events/site/detail_changed/synthetic-new-workshop.html                 the new event

    venv\\Scripts\\python scripts/make_week3_site_fixtures.py
"""

import html
from pathlib import Path

from bs4 import BeautifulSoup

from sources.iit_bombay_events import parse_event_detail

ROOT = Path(__file__).resolve().parent.parent

BASE = ROOT / "fixtures" / "week3" / "iitb_events"
DETAIL, SITE = BASE / "detail", BASE / "site"
HOME_REAL = BASE / "home_2026-10-16.html"
GONE = ("van-mahotsav-2026", "birth-anniversary-gandhi-ji-and-shastri-ji-1")
TEMPLATE = DETAIL / "seminar-cum-workshop-staggered-difference-differences-designs.html"
NOTE = "<!-- {kind} fixture for local_aggregator_fixture (scripts/make_week3_site_fixtures.py) -->\n"


def row(href: str, title: str, start: str, end: str = None) -> str:
    def time_tag(value):
        label = f"{value[8:10]} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(value[5:7]) - 1]} {value[:4]}"
        return f'<time datetime="{value}" class="datetime">{label}</time>'
    dates = time_tag(start) + (f"\n to {time_tag(end)}" if end else "")
    return ('  <div class="views-row">\n    <div class="views-field views-field-field-event-date"><div class="field-content">'
            f"{dates}\n</div></div>\n    <div class=\"views-field views-field-title\"><span class=\"field-content\">"
            f'<a href="{href}" hreflang="en">{html.escape(title, quote=False)}</a></span></div>\n  </div>\n')


def events_from_details(directory: Path, skip=()) -> list[tuple]:
    out = []
    for path in sorted(directory.glob("*.html")):
        if path.stem in skip:
            continue
        fields = parse_event_detail(path.read_text(encoding="utf-8"), path.stem)["fields"]
        out.append((fields["event_start"], fields["event_end"], fields["title"], f"/event/{path.stem}"))
    return out


def block(events: list[tuple]) -> str:
    rows = [row(href, title, start, end) for start, end, title, href in sorted(events, reverse=True)]
    rows.append(row("https://www.iitbombay.org/e/ieor-alumni-meet-2026", "IEOR Alumni Meet (registration)",
                    "2026-11-21T03:30:00Z"))                                       # external: never fetched
    rows.append(row("/events/brochure-iccms-2027.pdf", "ICCMS 2027 brochure (PDF)", "2027-12-01T03:30:00Z"))
    rows.append(row("/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug",
                    "Ground-breaking ceremony of the Biodiversity Lab", "2026-10-12T04:30:00Z"))   # announcement
    return "".join(rows)


def replace_block(page: str, new_rows: str) -> str:
    """Swaps the rows of the real events block (.homepage-events .view-content) for new_rows; the rest of the page,
    including navigation, footer and social links, stays as served."""
    soup = BeautifulSoup(page, "html.parser")
    content = soup.select_one(".homepage-events .view-content")
    content.clear()
    content.append(BeautifulSoup(new_rows, "html.parser"))
    return str(soup)


def changed_detail(slug: str, old: str, new: str) -> str:
    page = (DETAIL / f"{slug}.html").read_text(encoding="utf-8")
    assert page.count(old) >= 1, (slug, old)
    return NOTE.format(kind="CHANGED") + page.replace(old, new)


def main() -> None:
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "detail_changed").mkdir(exist_ok=True)
    home = HOME_REAL.read_text(encoding="utf-8")
    events = events_from_details(DETAIL)
    (SITE / "home.html").write_text(NOTE.format(kind="REAL homepage, events block rebuilt") +
                                    replace_block(home, block(events)), encoding="utf-8")

    # "Next day": two events gone, one new event, and one detail page with a changed venue
    new_page = (TEMPLATE.read_text(encoding="utf-8")
                .replace("Seminar-cum-Workshop on Staggered Difference-in-Differences Designs",
                         "SYNTHETIC Workshop on Research Data Practices")
                .replace("<p><strong>Speaker:</strong> Prof. Partha Deb, Professor of Economics, Hunter College, "
                         "City University of New York</p>",
                         "<p><strong>Speaker:</strong> Dr. Meera Iyer, Department of Physics, IIT Bombay</p>")
                .replace("2026-03-11T14:00:00Z", "2026-12-15T14:00:00Z").replace("2026-03-11T18:00:00Z", "2026-12-15T18:00:00Z"))
    (SITE / "detail_changed" / "synthetic-new-workshop.html").write_text(NOTE.format(kind="NEW (synthetic)") + new_page,
                                                                         encoding="utf-8")
    (SITE / "detail_changed" / "institute-lecture-taming-turbulence.html").write_text(
        changed_detail("institute-lecture-taming-turbulence", "P.C. Saxena Auditorium", "Victor Menezes Convention Centre"),
        encoding="utf-8")
    changed_events = events_from_details(DETAIL, skip=GONE) + events_from_details(SITE / "detail_changed",
                                                                                  skip=("institute-lecture-taming-turbulence",))
    (SITE / "home_changed.html").write_text(NOTE.format(kind="CHANGED homepage") +
                                            replace_block(home, block(changed_events)), encoding="utf-8")

    rss_items = []
    for slug, title, date in (("institute-lecture-taming-turbulence", 'Institute Lecture on "Taming Turbulence"',
                               "Mon, 24 Aug 2026 10:15:00 +0530"),
                              ("international-conference-quantum-dynamics", "International Conference on Quantum Dynamics",
                               "Tue, 01 Sep 2026 06:00:00 GMT"),
                              ("institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual",
                               'Institute Lecture on "Saral AI"', "Wed, 14 Oct 2026 11:00:00 +0000")):
        rss_items.append(f"    <item><title>{html.escape(title)}</title>"
                         f"<link>/event/{slug}?utm_source=rss&amp;utm_medium=feed#main-content</link>"
                         f"<pubDate>{date}</pubDate></item>")
    (SITE / "events.rss").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!-- SYNTHETIC feed for local_aggregator_fixture -->\n'
        '<rss version="2.0"><channel><title>Events (fixture)</title><link>/events</link><description>fixture</description>\n'
        + "\n".join(rss_items) + "\n</channel></rss>\n", encoding="utf-8")
    print(f"events in home.html: {len(events)}; in home_changed.html: {len(changed_events)}")


if __name__ == "__main__":
    main()
