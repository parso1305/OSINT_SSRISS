"""Week 3 Assignment 0: offline counts behind every number in iit_bombay_aggregators.md.

Reads only the saved responses in evidence/ (no network), so anyone can re-run it and get the same figures:
    venv\\Scripts\\python -m assignments.week3.00_candidates.count_samples

The selectors and regexes are recon-time measurements, not a parser: the Section 1+ adapter will get its own.
"""

import collections
import html
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

EVIDENCE = Path(__file__).resolve().parent / "evidence"
# Organiser = subject of the body's first sentence when that sentence says "<X> is organising/hosting ...".
ORG_RE = re.compile(r"^(.{3,120}?)[,\s]+(?:is|are|will be)?\s*(?:organi[sz]ing|hosting|in collaboration with)\b")
DEPT_RE = re.compile(r"\b(?:Department|Centre|Center|School) of [A-Z][A-Za-z&, ]+?(?=[,.;(]| IIT| at| and the|$)")


def soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((EVIDENCE / name).read_text(encoding="utf-8"), "html.parser")


def text_of(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def iitb_calendar() -> None:
    raw = (EVIDENCE / "www.iitb.ac.in__events.html").read_text(encoding="utf-8")
    page = BeautifulSoup(raw, "html.parser")
    anchors = [a["href"] for a in page.find_all("a", href=True) if "/event/" in a["href"]]
    settings = json.loads(page.find("script", attrs={"data-drupal-selector": "drupal-settings-json"}).string)
    options = json.loads(settings["fullCalendarView"][0]["calendar_options"])
    events = options["events"]
    print("== C1 IITB events calendar (www.iitb.ac.in/events)")
    print(f"   JS check: <a href=/event/...> in raw HTML markup = {len(anchors)}; "
          f"events inside drupal-settings-json (FullCalendar data) = {len(events)}; "
          f"distinct URLs = {len({e['url'] for e in events})}; calendar timeZone = {options.get('timeZone')}")
    print(f"   start years: {sorted(collections.Counter(e['start'][:4] for e in events).items())}")
    months = collections.Counter(e["start"][:7] for e in events if e["start"] >= "2026-01")
    print(f"   start months 2026+: {sorted(months.items())}")
    keywords = ("Institute Lecture", "Lecture", "Colloquium", "Talk", "Seminar", "Conference", "Symposium",
                "Workshop", "Day", "Diwas", "Week")
    titles = [html.unescape(e["title"]) for e in events]
    print("   title keywords: " + ", ".join(f"{k}={sum(k.lower() in t.lower() for t in titles)}" for k in keywords))
    newest = sorted(events, key=lambda e: int(e["eid"]))[-10:]
    print("   10 newest by node id (eid, start, title):")
    for e in newest:
        print(f"     {e['eid']} {e['start']} {html.unescape(e['title']).strip()[:80]}")
    print(f"   listing fields per event: {sorted(set().union(*(e.keys() for e in events)))}")
    print(f"   first 3 by start date >= 2026-10-16 (compare with the page in a browser): "
          f"{[html.unescape(e['title']).strip()[:50] for e in sorted(events, key=lambda e: e['start']) if e['start'] >= '2026-10-16'][:3]}")
    home = soup("www.iitb.ac.in__root.html")
    home_events = {a["href"]: text_of(a) for a in home.find_all("a", href=True) if a["href"].startswith("/event/")}
    print(f"   homepage events block: {len(home_events)} distinct /event/ links in server HTML markup; "
          f"in calendar JSON too: {sum(h in {e['url'] for e in events} for h in home_events)}/{len(home_events)}")


def iitb_event_details() -> None:
    files = sorted(EVIDENCE.glob("www.iitb.ac.in__event_*.html"))
    print(f"== C1 detail pages sampled: {len(files)}")
    speakers = orgs = 0
    departments: set[str] = set()
    types = collections.Counter()
    for f in files:
        page = soup(f.name)
        art = page.select_one("article.node--type-event")
        etype = art.select_one(".field--name-field-event-type")
        times = [t["datetime"] for t in art.select(".field--name-field-event-date time")]
        venue = art.select_one(".field--name-field-vanue")
        body_node = art.select_one(".field--name-body")
        body = text_of(body_node) if body_node else ""
        speaker = re.search(r"Speaker\s*:\s*([^,;]+)", body)
        org = ORG_RE.search(re.split(r"(?<=[a-z0-9)])\.\s", body, maxsplit=1)[0])
        speakers += bool(speaker)
        orgs += bool(org)
        types[text_of(etype) if etype else None] += 1
        departments.update(DEPT_RE.findall(body))
        print(f"   {f.name.split('__event_')[1][:40]:40} type={text_of(etype) if etype else None!r} time={times[:1]} "
              f"speaker={speaker.group(1)[:40] if speaker else None!r} organiser={org.group(1)[:50] if org else None!r} "
              f"venue={text_of(venue)[6:46] if venue else None!r}")
    print(f"   speaker named (\"Speaker:\" in body): {speakers}/{len(files)}; organiser named in first body sentence: {orgs}/{len(files)}")
    print(f"   event types: {dict(types)}")
    print(f"   departments/centres named in body fields: {sorted(departments)}")


def iitb_news() -> None:
    page = soup("www.iitb.ac.in__news.html")
    rows = page.select(".views-row")
    dates = []
    departments: set[str] = set()
    for r in rows:
        m = re.search(r"\b(\d{2} [A-Z][a-z]{2} \d{4})\b", text_of(r))
        dates.append(m.group(1) if m else None)
        departments.update(DEPT_RE.findall(text_of(r)))
    last = page.find("a", attrs={"title": "Go to last page"})
    print("== C2 IITB news (www.iitb.ac.in/news)")
    print(f"   items on page 1: {len(rows)}; with detail link: {sum(bool(r.find('a', href=re.compile('/breaking-news/'))) for r in rows)}")
    print(f"   card dates: {dates}")
    print(f"   last page link: {last['href'] if last else None}")
    print(f"   departments/centres named in card text: {sorted(departments)}")
    speaker = sum("speaker" in text_of(r).lower() for r in rows)
    print(f"   cards mentioning 'speaker': {speaker}/{len(rows)}")


def iitb_feed_and_sitemap() -> None:
    xml = (EVIDENCE / "www.iitb.ac.in__rss_xml.xml").read_text(encoding="utf-8")
    links = re.findall(r"<item>.*?<link>([^<]+)</link>", xml, re.S)
    kinds = collections.Counter(re.sub(r"https://www\.iitb\.ac\.in/([^/]+)/.*", r"\1", u) for u in links)
    print("== IITB /rss.xml (Drupal front-page feed)")
    print(f"   items: {len(links)}; by path type: {dict(kinds)}; event items: {kinds.get('event', 0)}")
    print(f"   pubDates: {re.findall(r'<pubDate>([^<]+)</pubDate>', xml)}")
    manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
    sm = [e for e in manifest["entries"] if e["url"] == "https://www.iitb.ac.in/sitemap.xml"]
    print(f"   /sitemap.xml: status={sm[0]['status'] if sm else None}; robots.txt Sitemap lines: "
          f"{re.findall(r'(?im)^sitemap:.*$', (EVIDENCE / 'www.iitb.ac.in__robots_txt.txt').read_text(encoding='utf-8'))}")


def acr() -> None:
    page = soup("acr.iitbombay.org__events_upcoming_events.html")
    items = {a["href"]: text_of(a) for a in page.find_all("a", href=True) if "/events_list/" in a["href"]}
    print("== C3 Dean ACR events (acr.iitbombay.org/events/upcoming-events/)")
    print(f"   items: {len(items)}")
    for href, text in items.items():
        date = re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", text)
        print(f"     {date.group(0) if date else None} {href}")
    pager = [a["href"] for a in page.find_all("a", href=True) if re.search(r"/page/\d|[?&]paged?=", a["href"])]
    print(f"   pager links: {pager}")
    detail = text_of(soup("acr.iitbombay.org__events_list_ieor_alumni_meet.html"))
    print(f"   detail sample: 'speaker' mentioned={'speaker' in detail.lower()}; "
          f"departments={sorted(set(re.findall(r'Department of [A-Z][A-Za-z ]+?(?= cordially| invites|[,.;])', detail)))}")
    sm = (EVIDENCE / "acr.iitbombay.org__sitemap_xml.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    lastmods = collections.Counter(d[:10] for d in re.findall(r"<lastmod>([^<]+)</lastmod>", sm))
    sections = collections.Counter(re.sub(r"https://acr\.iitbombay\.org/([^/]*)/?.*", r"\1", u) for u in locs)
    print(f"   sitemap.xml: root=<{re.search(r'<(urlset|sitemapindex)', sm).group(1)}> urls={len(locs)} "
          f"generator comment={'xml-sitemaps.com' in sm} distinct lastmod dates={dict(lastmods)}")
    print(f"   sitemap sections (top 6): {sections.most_common(6)}")
    print(f"   listed upcoming events present in sitemap: {sum(h in sm for h in items)}/{len(items)}")
    feed = (EVIDENCE / "acr.iitbombay.org__feed.xml").read_text(encoding="utf-8")
    print(f"   /feed/: items={feed.count('<item>')} pubDates={re.findall(r'<pubDate>([^<]+)</pubDate>', feed)[:3]}...; "
          f"event items={feed.count('/events_list/')}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # titles contain non-cp1252 characters
    iitb_calendar()
    iitb_event_details()
    iitb_news()
    iitb_feed_and_sitemap()
    acr()


if __name__ == "__main__":
    main()
