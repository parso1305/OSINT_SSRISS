# 1A: feed and sitemap inspection

Target (D1, auto-selected, pending Parth's review): **IIT Bombay institute events calendar**,
`https://www.iitb.ac.in/events` with item pages at `https://www.iitb.ac.in/event/<slug>`.

Code:
- `src/discovery/feed.py`: `parse_feed(bytes|str)`, RSS 2.0 and Atom via `feedparser`.
- `src/discovery/sitemap.py`: `parse_sitemap(bytes|str)` and `walk_sitemaps(fetch_text, url, max_children=2)`, via `defusedxml`.
- `src/discovery/timestamps.py`: `to_utc_z`.

CLIs (thin, run with `python -m` from the repo root):
- `assignments/week3/01_discovery/inspect_feed.py`
- `assignments/week3/01_discovery/inspect_sitemap.py`

Tests: `tests/test_discovery_feed_sitemap.py`. Fixtures: `fixtures/week3/discovery/` (see its README).

## Which discovery formats exist for the target, and where each was found

| Format | Exists for the target? | Where it was looked for / found | Evidence |
|---|---|---|---|
| RSS 2.0 | **Yes, but not for events.** | Not advertised: no `<link rel="alternate">` on `/`, `/events`, `/news`, `/announcements` or any `/event/` page (`recon.py summarize`). Found at the **Drupal default path** `/rss.xml` (tried because of `<meta name="Generator" content="Drupal 10">`). | `00_candidates/evidence/www.iitb.ac.in__rss_xml.xml`; live run below. It is the site-wide front-page feed: 10 items, of which 4 are tenders, 1 employee, 1 award, 1 research highlight, 1 staff announcement, 1 breaking news and 1 `/node/6913`, with **0 events** on both 2026-10-16 and 2026-10-17. |
| Atom | **No.** | No Atom `<link rel="alternate">` anywhere; Drupal ships no Atom default. | Section 0 `summarize` output (`feeds=[]` on every saved page). |
| XML sitemap (urlset) | **No.** | robots.txt has **no `Sitemap:` line**. The default `/sitemap.xml` returns **404** (Section 0, and again live below). | `00_candidates/evidence/www.iitb.ac.in__robots_txt.txt`, `manifest.json`, live run below. |
| Sitemap index | **No.** | Same: no `Sitemap:` line, `/sitemap.xml` 404. | Same. |
| HTML | **Yes**: the only event discovery surface. | `/events` (from the homepage's "View Event Calendar" link). The 643 calendar entries are JSON inside `drupal-settings-json` in the raw HTML. The homepage's events block has 40 `/event/` links in plain markup. | `00_candidates/iit_bombay_aggregators.md`, C1. |

**Plainly:** the target has **no usable feed or sitemap for its event content**, so the RSS (event-shaped), Atom, urlset
and sitemap-index exercises run on realistic local fixtures (`fixtures/week3/discovery/events_*.xml`,
`urlset_*.xml`, `sitemap_index.xml`). Two fixtures are **real samples** from the evidence:
- `iitb_rss_real_trimmed.xml`: the target's own `/rss.xml`, 3 items, with descriptions trimmed.
- `acr_sitemap_real_trimmed.xml`: the Dean ACR sitemap, the one real IITB-family sitemap found.

The event fixtures reuse real slugs from the calendar, so the 1B cross-method test compares URLs that HTML discovery
really finds.

## Live inspector runs (2026-10-17, 4 live requests: 2 robots.txt + 2 documents)

`inspect_feed --url https://www.iitb.ac.in/rss.xml --limit 10`:

```
2026-10-17 05:27:01 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/rss.xml status=200 duration_ms=326
# fetched https://www.iitb.ac.in/rss.xml status=200 content_type=application/rss+xml; charset=utf-8 bytes=2412569 fetched_at=2026-10-16T23:57:01Z
# rss (rss20) entries=10 showing=10
URL | title | published-or-updated (UTC) [raw] | discovery source
https://www.iitb.ac.in/tenders/cmc-helios-05-uc-focused-ion-beam-scanning-electron-microscope-fib-sem | CMC for Helios 05 UC (Focused Ion  Beam – Scanning electron Microscope  (FIB-SEM)) | 2026-10-16T09:44:35Z [Fri, 16 Oct 2026 09:44:35 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/employee/prof-indu-j | Prof. Indu J. | 2026-10-16T04:58:25Z [Fri, 16 Oct 2026 04:58:25 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/award/national-geomatics-award-applications-year-2026 | The National Geomatics Award – Applications for the year 2026 | 2026-10-16T04:53:14Z [Fri, 16 Oct 2026 04:53:14 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/tenders/protein-purification-system-0 | Protein Purification System | 2026-10-15T12:47:42Z [Thu, 15 Oct 2026 12:47:42 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/node/6913 | Y-Point Venture Capital Fund Makes First Investment, Backs IIT Bombay Spin-out Relsym Solutions | 2026-10-15T11:37:27Z [Thu, 15 Oct 2026 11:37:27 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/tenders/mmdpssq052026-27 | MMD/PS/SQ/05/2026-27 | 2026-10-15T06:05:45Z [Thu, 15 Oct 2026 06:05:45 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/tenders/turbopump-splitfow-3103p-fan | Turbopump Splitfow 310/3P with Fan | 2026-10-14T09:34:38Z [Wed, 14 Oct 2026 09:34:38 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/research-highlight/turning-quantum-uncertainty-precision-quantum-sensing-0 | Turning Quantum Uncertainty Into Precision Quantum Sensing | 2026-10-14T06:57:15Z [Wed, 14 Oct 2026 06:57:15 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/announcement-staff/walk-interview-advt-no-m-62026-27-post-part-time-pre-primary-teacher | Walk in interview - Advt. No. M-6/2026-27 for the post of Part-Time Pre-Primary Teacher. | 2026-10-13T11:14:30Z [Tue, 13 Oct 2026 11:14:30 +0000] | rss via https://www.iitb.ac.in/rss.xml
https://www.iitb.ac.in/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug | Ground-breaking ceremony of the Biodiversity Lab at Soneri Baug | 2026-10-13T05:15:25Z [Tue, 13 Oct 2026 05:15:25 +0000] | rss via https://www.iitb.ac.in/rss.xml
```

`inspect_sitemap --url https://www.iitb.ac.in/sitemap.xml`:

```
2026-10-17 05:27:05 [INFO] logger=web_monitor.fetcher FETCH url=https://www.iitb.ac.in/sitemap.xml status=404 duration_ms=118
FETCH FAILED: HTTP 404 Not Found for url: https://www.iitb.ac.in/sitemap.xml (status=404)
```

Fixture runs (offline) showing the RSS, Atom and sitemap-index output shapes:

```
> inspect_feed --file fixtures/week3/discovery/events_rss.xml
# rss (rss20) entries=4 showing=4
URL | title | published-or-updated (UTC) [raw] | discovery source
https://www.iitb.ac.in/event/institute-lecture-taming-turbulence?utm_source=rss&utm_medium=feed#main-content | Institute Lecture on "Taming Turbulence" | 2026-08-24T04:45:00Z [Mon, 24 Aug 2026 10:15:00 +0530] | rss via file:fixtures/week3/discovery/events_rss.xml
https://WWW.IITB.AC.IN:443/event/international-conference-quantum-dynamics?fbclid=IwAR0abc | International Conference on Quantum Dynamics | 2026-09-01T06:00:00Z [Tue, 01 Sep 2026 06:00:00 GMT] | rss via file:fixtures/week3/discovery/events_rss.xml
/event/van-mahotsav-2026 | Van Mahotsav 2026 | 2026-08-27T09:30:00Z [Thu, 27 Aug 2026 09:30:00 +0000] | rss via file:fixtures/week3/discovery/events_rss.xml
https://www.iitb.ac.in/event/no-date-fixture | Item with no date | None [None] | rss via file:fixtures/week3/discovery/events_rss.xml

> inspect_feed --file fixtures/week3/discovery/events_atom.xml
# atom (atom10) entries=2 showing=2
URL | title | published-or-updated (UTC) [raw] | discovery source
https://www.iitb.ac.in/event/institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual | Institute Lecture on "Saral AI" | 2026-10-14T11:00:00Z [2026-10-14T16:30:00+05:30] | atom via file:fixtures/week3/discovery/events_atom.xml
https://www.iitb.ac.in/event/5th-japan-india-forum#register | 5th Japan–India Forum | 2026-10-10T05:00:00Z [2026-10-10T05:00:00Z] | atom via file:fixtures/week3/discovery/events_atom.xml

> inspect_sitemap --file fixtures/week3/discovery/sitemap_index.xml
# <sitemapindex> urls=0 child_sitemaps=3
child sitemap (not followed from a file): https://www.iitb.ac.in/event-sitemap.xml | lastmod 2026-10-16T09:00:00Z [2026-10-16T09:00:00+00:00]
child sitemap (not followed from a file): https://www.iitb.ac.in/news-sitemap.xml | lastmod 2026-10-13T09:00:00Z [2026-10-13T09:00:00+00:00]
child sitemap (not followed from a file): https://www.iitb.ac.in/page-sitemap.xml | lastmod None [None]
```

The URLs above are printed **as written in the feed**. Canonicalization (`resolve_item_url`) happens when they
become DiscoveryRecords (1B), so the inspector shows what the source really publishes.

## How far `<lastmod>` can be trusted here

- **The target has no sitemap**, so it has no `<lastmod>` at all. Change detection for the target cannot rely
  on lastmod. It has to come from the content hash (Section 4).
- **The one IITB-family sitemap that exists (`acr.iitbombay.org/sitemap.xml`) must not be trusted.**
  - **All 500 `<lastmod>` values are identical: `2024-02-14T06:57:38+00:00`**, down to the second
    (`count_samples.py`: `distinct lastmod dates={'2024-02-14': 500}`; `grep -o "<lastmod>[^<]*" | sort -u` gives
    one line).
  - The file says why: `<!-- created with Free Online Sitemap Generator www.xml-sitemaps.com -->`. That
    lastmod is the **crawl/generation time of a one-off external crawl**, not a per-page modification date.
  - It is identical for pages about events years apart: `events_list/republic-day-celebrations-2022/`,
    `events_list/scipy-india-2021/` and `events_list/pune-alumni-connect-2024/` all claim the same second.
  - Compared with the saved detail pages (5 compared; 9 saved in total):
    - The ACR page `events_list/ieor-alumni-meet/` declares `"datePublished":"2026-10-06T11:43:23+00:00"`,
      `"dateModified":"2026-10-06T11:46:57+00:00"`. It is **absent from the sitemap**, as are all 4 currently
      listed ACR events (`listed upcoming events present in sitemap: 0/4`).
    - Checked: `/event/institute-lecture-taming-turbulence`, `/event/institute-lecture-saral-ai-…`,
      `/event/international-conference-quantum-dynamics` and `/event/5th-japan-india-forum`. These 4 IITB detail
      pages have no sitemap entry to compare with, and none carries a `dateModified` / `article:modified_time`
      meta.
  - Verdict: **flagged. Every lastmod is identical and equals the generator's crawl date. The sitemap is a
    20-month-old snapshot.** A monitor that trusted it would think nothing ever changes and would never find the
    new events.
- **General rule adopted:** lastmod is a hint, never a change signal.
  - `src/discovery/sitemap.py` keeps it as `source_timestamp` (UTC Z) with the raw string beside it.
  - A date-only lastmod (`2026-09-01`) becomes `None` with the raw string kept, because a calendar date is not an
    instant.
  - Section 4 decides "changed" only from the content hash.

## Is the sitemap an events feed or a map of the whole site?

**A map of the whole site.** The ACR sitemap's 500 URLs are:
- `awards` 204
- `events_list` 94
- `news` 91
- `media_gallery` 19
- `csr` 14
- `newsletter` 10
- `resources` 9, `legacy_project` 9, `allstory` 8, `giving-back` 6, … (`count_samples.py`)

Events are under a fifth of it, mixed with every other page type. If a target used this sitemap for discovery, the
scope filter (Section 2) and the router (Section 8) would have to separate `events_list/` items from everything else.
That is why discovery never trusts a sitemap URL to be an event: the URL pattern and Content-Type decide. The target
itself has no sitemap.

## Why defusedxml

A sitemap or feed is untrusted XML from a remote server.
- Python's standard-library XML parsers process DTD entity declarations. A tiny document can expand into gigabytes
  ("billion laughs", quadratic blowup), and some parsers resolve external entities.
- `defusedxml` parses the same documents but **refuses** entity declarations and external references with an
  exception instead of expanding them.
- `tests/test_discovery_feed_sitemap.py::test_sitemap_refuses_entity_expansion` feeds a billion-laughs document and
  gets a clear `SitemapParseError: unsafe XML refused by defusedxml (EntitiesForbidden)`, not a hang.
- Malformed XML gives `SitemapParseError: malformed sitemap XML: mismatched tag: line 4, column 2`, not a crash.

(feedparser uses its own SAX handling with entity expansion limits. Feeds are additionally only ever passed as
bytes, so feedparser cannot fetch anything.)

## 1A checkpoint: discovering a URL is not the same as extracting an event record

A feed entry or sitemap `<loc>` tells you **that a page exists**: at most a link, a title and a timestamp. Those
are the six fields of a DiscoveryRecord, and the timestamp is the publisher's (when the post was published or the
sitemap was generated), not when the event happens.

The `records` table needs what only the item's own page says:
- the event's start and end time (`event_start`, `event_end`, `timezone`)
- the `location`
- the `speakers` with their affiliations
- the `organizations`
- the `event_type` and `description`

And the record must pass validation: `event_start` is required.

On this target the gap is concrete:
- The real RSS pubDate `Fri, 16 Oct 2026 09:44:35 +0000` is when a tender was posted.
- The detail page's `Speaker: Prof. Beverley J. McKeon, Professor of Mechanical Engineering, Stanford University…`
  appears in no feed.
- The listing's start time is local IST, while the detail page's `<time datetime="…Z">` mislabels that same local
  time as UTC.

So discovery only produces candidates. A record exists only after the detail page is fetched, parsed, normalized and
validated (Sections 3, 8 and 10).
