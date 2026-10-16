# Assignment 0: IIT Bombay aggregator candidates

Recon date: 2026-10-16 (UTC 13:53–13:58). All requests went through `src.fetcher.Fetcher`: robots.txt was checked,
the timeout was 15 s, the honest User-Agent was sent, every request was FETCH-logged and requests to one host were
at least 3 s apart. Only GET requests were made.

**Live requests used: 28 of 30.** Every raw response used below is saved in [`evidence/`](evidence/), and
[`evidence/manifest.json`](evidence/manifest.json) lists each one's url, final_url, status, content-type, fetched_at
and bytes. Every number below comes from the offline script
[`count_samples.py`](count_samples.py), which anyone can re-run:

```
venv\Scripts\python -m assignments.week3.00_candidates.recon fetch URL ...   # live, through the generic client
venv\Scripts\python -m assignments.week3.00_candidates.recon summarize       # offline: generator, feeds, JS markers
venv\Scripts\python -m assignments.week3.00_candidates.count_samples         # offline: every number in this file
```

## robots.txt

| Host | Rules that matter | Sitemap: line | Crawl-delay |
|---|---|---|---|
| `www.iitb.ac.in` | Standard Drupal file. It disallows `/admin/`, `/search/`, `/user/login`, `/user/register`, `/user/password`, `/node/add/`, `/comment/reply/`, `/core/`, `/profiles/` (and the same paths under `/index.php/`). It does **not** disallow `/events`, `/event/`, `/news`, `/breaking-news/`, `/announcements` or `/rss.xml`. | none | none |
| `acr.iitbombay.org` | Yoast block: `User-agent: *` / `Disallow:` (empty), which allows everything. | `https://acr.iitbombay.org/sitemap.xml` | none |

## How the candidates were found

- **Homepage navigation.** I saved `https://www.iitb.ac.in/`. Its generator meta is "Drupal 10", and it has no
  `<link rel="alternate">` feed tags. Its navigation leads to:
  - "View Event Calendar" → `/events`
  - "Institute Colloquium/ Lectures" → `/institute-colloquium`
  - "View All" → `/news`
  - "More" → `/announcements`
  - "Alumni" / "CSR" → `acr.iitbombay.org`
- **Drupal default paths**, tried because the CMS is identified:
  - `/rss.xml` returned 200 `application/rss+xml`.
  - `/sitemap.xml` returned **404**.
- **acr.iitbombay.org** (Dean ACR office).
  - Its homepage has `<link rel="alternate" type="application/rss+xml">` tags for `/feed/` and `/comments/feed/`.
  - Its "Events" link points to `/events/upcoming-events/`.
  - The `Sitemap:` line in its robots.txt points to `/sitemap.xml`.
- **Checked and rejected as listings.**
  - `/institute-colloquium` is a static description of the lecture series plus a "Propose a Speaker" Microsoft Forms
    link. It contains 0 item links. The individual institute lectures appear in the events calendar instead (36
    calendar titles contain "Institute Lecture").
  - `/announcements` lists admissions and exam notices (UCEED, CEED, JAM, ePGD programmes), not events.

## Candidate matrix

### C1. IIT Bombay institute events calendar

| Attribute | Finding (evidence) |
|---|---|
| Name | IIT Bombay Events calendar ("View Event Calendar") |
| URL | `https://www.iitb.ac.in/events` (listing), `https://www.iitb.ac.in/event/<slug>` (details) |
| Institution | IIT Bombay (institute level, the main site) |
| Surface type | Central events calendar (Drupal 10 + the FullCalendar View module) |
| HTML · RSS · Atom · sitemap | **HTML: yes, with a caveat** (see the JS check). **RSS: no event feed.** `/rss.xml` is the Drupal front-page feed and its 10 items include 0 events (4 tenders, 1 employee, 1 award, 1 research-highlight, 1 announcement-staff, 1 breaking-news, 1 node). **Atom: none.** **Sitemap: none** (`/sitemap.xml` 404, no `Sitemap:` line). |
| Content types | Event `field-event-type` values in the 8-page detail sample: Seminar/Talk 2, Conference/Symposium 2, Social/Cultural 2, CEP Course/School/Workshop 1, Academic Event 1. Title keywords across all 643 calendar entries: "Lecture" 93 (of which "Institute Lecture" 36), "Colloquium" 14, "Talk" 14, "Conference" 38, "Workshop" 38, "Symposium" 7, "Seminar" 1, observance days ("Day" 199, "Diwas" 27, "Week" 16). |
| Approx. update frequency | Events per start month in 2026: Jan 9, Feb 6, Mar 8, Apr 5, May 3, Jun 8, Jul 1, Aug 10, Sep 9, Oct 9, Nov 6, Dec 7, so **about 6–10 per month**, about 1–2 a week. The newest node ids are 6737–6903, and their events start between 2026-08-22 and 2026-11-28, so new entries are being added for the coming months. Events per year: 2019 115, 2020 84, 2021 64, 2022 54, 2023 45, 2024 82, 2025 93, 2026 81. |
| Departments represented | Neither the listing JSON nor any detail field carries a department or organiser field. In the bodies of the 8 sampled detail pages, the first-sentence organiser is the Institute 2, the Department of Chemistry 1, the Psychophysiology Laboratory 1, the Horticulture Section of the Estate Office 1 and JST (external, "in collaboration with IIT Bombay") 1; the other 2 name none. Body text also names the Department of Humanities and Social Sciences. A venue names the Department of Computer Science and Engineering. That is **at least 5 distinct institute units across 8 items**. |
| Detail-page links? | **Yes.** Each of the 643 calendar entries has a `url` (614 distinct; the rest repeat). The homepage events block has 40 `/event/` links, and 40/40 of them are also in the calendar. |
| Pagination or archive? | No pagination is needed: **one response holds the whole archive**, 643 entries starting 2014-12-12 … 2027-12-10. There are no calendar navigation URLs to crawl (`/events?month=…` is never needed). |
| Speaker info? | **Listing: no** (entry fields are only `title, url, start, eid, id, des, colours, editable flags`). **Detail: free text only**, as "Speaker: …" in the body on **2 of 8** sampled pages, both Seminar/Talk Institute Lectures (Prof. Ponnurangam Kumaraguru; Prof. Beverley J. McKeon). National Engineers' Day names a chief guest in prose, but not as "Speaker:". |
| Organization info? | **Listing: no.** **Detail: prose only.** 6 of 8 bodies name an organiser in their first sentence ("The Department of Chemistry, IIT Bombay is organizing …"). There is no structured organiser field. |
| Access considerations | robots.txt allows `/events` and `/event/`, with no Crawl-delay. All 9 requests returned 200 with no redirect and no login. Sizes are large: the listing is 543 KB and the 8 detail pages are 130–136 KB each. **Timestamp trap:** the detail `<time datetime="2026-09-03T17:15:00Z">` labels local IST wall-clock time as UTC. The body says "Time: 5:15 p.m.", and the calendar JSON gives `"start": "2026-09-03T17:15:00"` with `timeZone: Asia/Kolkata`, so the trailing `Z` must not be trusted. |
| JS-rendering check | **The visible calendar is JavaScript-rendered.** The raw `/events` HTML has **0** `<a href="/event/…">` in its markup. All 643 items are in the server response, inside `<script type="application/json" data-drupal-selector="drupal-settings-json">` → `fullCalendarView[0].calendar_options.events`, which FullCalendar draws in the browser. No extra request (AJAX/API) is needed. The data is a single JSON block in the raw HTML. The first 3 upcoming entries by start date are "Institute Lecture on "Saral AI…"", "*Vigilance Awareness Week" and "Rashtriya Ekta Diwas"; **please confirm them against the page in a browser** (I cannot render pages here). The detail pages are plain server-rendered HTML with Drupal field classes (`field--name-field-event-type`, `field--name-field-event-date` `<time>`, `field--name-field-vanue`, `field--name-body`). |
| Why high-yield | It is the only central surface where many units publish events. One request gives every event URL with a start time; detail pages have stable field classes for type, date range and venue, plus a body naming the organiser and speaker. |

**Selection criteria:**
- public: pass
- robots.txt allows: pass
- useful central listing: pass
- low-complexity surface: pass with a caveat. The items are JSON embedded in ordinary HTML, not markup, so the listing parser reads one JSON block, not `<a>` tags. No feed or sitemap exists.
- multiple departments, organisations or speakers: pass, but only on detail pages and only in prose
- no circumvention: pass

### C2. IIT Bombay news ("breaking news")

| Attribute | Finding (evidence) |
|---|---|
| Name | IIT Bombay News |
| URL | `https://www.iitb.ac.in/news` (listing), `https://www.iitb.ac.in/breaking-news/<slug>` (details) |
| Institution | IIT Bombay (institute level) |
| Surface type | Central news listing (Drupal view of `breaking-news` nodes) |
| HTML · RSS · Atom · sitemap | **HTML: yes**, server-rendered `.views-row` cards. **RSS:** only the mixed `/rss.xml`, 1 of whose 10 items is a breaking-news item. **Atom: none. Sitemap: none.** |
| Content types | News reports, mostly after the event: MoUs, visits, celebrations, awards, sessions held. They are not event announcements. |
| Approx. update frequency | Card dates on page 1: 13 Oct, 12 Oct, 02 Oct, 15 Sep, 09 Sep, 09 Sep, 07 Sep, 04 Sep, 03 Sep, 29 Aug 2026. That is **10 items in 45 days, about 1.5 a week**. |
| Departments represented | 0 department names matched in the page-1 card text. The cards name offices and centres in prose (e.g. "The Industrial Research & Consultancy Centre (IRCC)"), but there is no field for them. |
| Detail-page links? | Yes, 10 of 10 cards. |
| Pagination or archive? | Yes: `?page=1` … `?page=47` (the last-page link), which is about 480 items at 10 per page. |
| Speaker info? | Listing: 0 of 10 cards mention a speaker. Detail pages were not sampled, to save the request budget. |
| Organization info? | Listing: prose only (the IRCC example above). |
| Access considerations | robots.txt allows `/news` and `/breaking-news/`. The page is 175 KB. The response was 200 with no redirect. |
| JS-rendering check | The raw HTML contains all 10 cards and the pager (`<ul class="pagination js-pager__items">` with `href="?page=1"`), so it is not JS-dependent. |
| Why medium/low yield for Week 3 | It is technically the easiest surface (plain HTML, paginated, dated cards with detail links). But the items are news reports, not events: there is no start/end time, venue or speaker. They would fit only as a second item type, once Section 8 widens `ITEM_TYPES`. |

**Selection criteria:** public: pass. robots.txt: pass. Useful central listing: pass for news; **for events it fails**, because items are past-tense reports with no event fields. Low complexity: pass. Multiple departments or speakers: **fail on listing pages** (0 named in 10 cards). No circumvention: pass.

### C3. Dean ACR office events (acr.iitbombay.org)

| Attribute | Finding (evidence) |
|---|---|
| Name | Office of the Dean (Alumni & Corporate Relations) events |
| URL | `https://acr.iitbombay.org/events/upcoming-events/` (listing), `https://acr.iitbombay.org/events_list/<slug>/` (details) |
| Institution | IIT Bombay, Dean ACR office (separate WordPress site) |
| Surface type | Office events listing (upcoming only) |
| HTML · RSS · Atom · sitemap | **HTML: yes.** **RSS:** `/feed/` (from `<link rel=alternate>`) has 10 items, **0 of them events**, newest pubDate Thu, 13 Jul 2023, with items such as `testing-title-2`. **Atom: none.** **Sitemap:** `/sitemap.xml` (from robots.txt) is a single `<urlset>` of exactly 500 URLs made by "Free Online Sitemap Generator www.xml-sitemaps.com", with **every lastmod 2024-02-14**. Its sections: awards 204, events_list 94, news 91, …. **0 of the 4 current events are in it.** |
| Content types | Alumni events: reunions, alumni connects, Alumni Day. |
| Approx. update frequency | The listing has 4 items, dated November 21, 2026 (2 items), December 19, 2026 and December 27, 2026. The feed and sitemap are stale (2023 and 2024), so they give no frequency signal. |
| Departments represented | 1 (IEOR, named in the IEOR Alumni Meet detail body). |
| Detail-page links? | Yes, 4 of 4. |
| Pagination or archive? | **No.** The listing shows upcoming events only and has 0 pager links. Past `events_list` URLs are reachable only through the stale static sitemap. |
| Speaker info? | Listing: no. Detail (1 sampled): no; it has date, time, venue and registration links. |
| Organization info? | The detail body names the host department in prose ("The Department of Industrial Engineering and Operations Research cordially invites you"). |
| Access considerations | robots.txt allows everything. All 6 saved ACR responses returned 200. Registration links go to `iitbombay.org/e/…` (payment pages, not followed). |
| JS-rendering check | The raw HTML contains all 4 items with dates in markup, so it is not JS-dependent. |
| Why low-yield | 4 items, 1 department, no speakers, and no archive. Its feed and sitemap are present but useless for discovery: the feed has no events, and the sitemap is a 2024 static snapshot. |

**Selection criteria:** public: pass. robots.txt: pass. **Useful central listing: fail** (4 upcoming items, no archive). Low complexity: pass. **Multiple departments, organisations or speakers: fail** (1 department, 0 speakers). No circumvention: pass.

## Ranking: PROPOSED (you make the final call)

1. **Best target: C1, the IIT Bombay events calendar** (`/events` plus `/event/<slug>` detail pages).
   - It is the only institute-wide event surface: 643 entries back to 2014, about 6–10 new events a month, and at
     least 5 distinct units named in an 8-page sample.
   - One GET returns every event URL and start time.
   - Detail pages carry stable Drupal field classes for event type, date range and venue.
   - The cost, to plan for in Sections 1 and 5–7:
     - Speaker and organiser are **not fields**. They are body prose: a speaker on 2/8 pages (the Institute
       Lectures), an organiser on 6/8.
     - The listing's items are in a JSON block, not `<a>` markup. The homepage's server-rendered events block (40
       `/event/` links) is an HTML fallback for `html.py`.
     - The `<time datetime=…Z>` values are IST mislabelled as UTC.
     - There is no feed or sitemap for events. 1A will therefore need fixtures for RSS, Atom and sitemaps; the
       real `/rss.xml` can serve as the RSS sample.
2. **Backup: C2, IIT Bombay news.** It is server-rendered, paginated (48 pages) and dated, with detail links, so
   it is technically the simplest. But its items are news reports with no event fields and no speakers. It makes
   sense as a second item type, not as the events target.
3. **Not recommended: C3, Dean ACR events.** The technical reasons:
   - the listing has no archive or pagination (4 upcoming items)
   - its RSS feed has no event items and was last updated 2023-07-13
   - its sitemap is a static 500-URL snapshot in which every lastmod is 2024-02-14, and it contains none of the 4
     current events
   - the sampled detail page names no speaker

No IITB candidate fails a hard criterion: none is blocked by robots.txt, needs a login or needs circumvention.

## Section 0 checkpoint: why one central page beats ten unrelated low-yield pages

A central page like the events calendar puts many departments, offices and speakers behind one URL, one robots.txt
decision and one parser. Ten unrelated department pages would mean ten markups to learn, ten adapters to maintain
and ten times the requests, for a handful of items each. Because every unit publishes through the same template,
the fields come out consistent (the same event-type, date and venue classes on every detail page), so records from
different departments land in the shared schema the same way. That consistency also makes the central page the
best place to find cross-department people and organisations, which is exactly what the Week 3 entity sections need.
