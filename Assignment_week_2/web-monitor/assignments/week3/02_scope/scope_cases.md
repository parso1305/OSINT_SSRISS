# Section 2: scope cases for `iit_bombay_events`

Code: `src/scope.py` (`scope_decision(url, cfg) -> (allowed, reason)`, `is_allowed_item_url(url, cfg)`).
Config: the `scope` block of `iit_bombay_events` in `config/sources.json`.
Tests: `tests/test_scope.py`. `test_scope_case` has one parametrized case per row below, and
`test_every_scope_cases_md_row_has_a_test` fails if this table and the tests drift apart.

The caller canonicalizes first (`resolve_item_url`). The rules apply in this order, and the first one that decides
wins:
1. scheme
2. host: exact, or an explicitly listed parent domain on a dot boundary
3. excluded path prefix
4. excluded query key
5. allowed path prefix, with a trailing slash

```json
"scope": {
  "allowed_hosts": ["www.iitb.ac.in"],
  "allowed_subdomains_of": [],
  "allowed_prefixes": ["/event/", "/events/", "/breaking-news/", "/sites/default/files/"],
  "excluded_prefixes": ["/user/", "/search/", "/iitb-search/", "/admin/", "/node/add/", "/comment/reply/"],
  "allow_external": false,
  "excluded_query_keys": ["search_api_fulltext", "page", "month", "year", "date", "view", "start", "end", "q", "keys"],
  "max_listing_pages": 1, "max_detail_items": 20, "max_discovered_items": 40
}
```

Notes on this config:
- **`allowed_subdomains_of` is empty on purpose.** Department sites (`www.cse.iitb.ac.in`, `www.hss.iitb.ac.in`, …)
  are separate sources with their own adapters, so a link to one is out of scope for the central calendar.
- **The excluded prefixes come from what the target actually uses:**
  - robots.txt disallows `/user/login`, `/search/`, `/admin/`, `/node/add/` and `/comment/reply/`;
  - the site's search form posts to `/iitb-search` with `search_api_fulltext=` (homepage
    `<form action="/iitb-search">`).
- **Excluded query keys.** The target uses `page` (the news pager `?page=1…47`) and `search_api_fulltext`
  (search). `month`, `year`, `date`, `view`, `start` and `end` are the calendar-navigation keys of Drupal calendar
  and FullCalendar views. `q` and `keys` are Drupal's generic search keys.

| # | Case | URL (raw, before canonicalization) | Allowed? | Why? |
|---|---|---|---|---|
| 1 | valid event detail | `https://www.iitb.ac.in/event/institute-lecture-taming-turbulence` | Yes | Allowed host, path under `/event/`. |
| 2 | valid news detail | `https://www.iitb.ac.in/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug` | Yes | Allowed host, path under `/breaking-news/`. In scope; the router labels it `announcement`, so it is not stored as an event. |
| 3 | external registration site | `https://www.iitbombay.org/e/ieor-alumni-meet-2026` | No | `external host: www.iitbombay.org`. Registration and payment pages belong to another site, and `allow_external` is false. |
| 4 | social media link | `https://www.facebook.com/iitbombay` | No | `external host: www.facebook.com`. Footer social links are never items. |
| 5 | PDF | `https://www.iitb.ac.in/sites/default/files/2026-10/institute-lecture-brochure.pdf` | Yes | Under `/sites/default/files/`. In scope as a document; the router labels it `pdf_document` and it is **never detail-fetched as HTML**. |
| 6 | login URL | `https://www.iitb.ac.in/user/login?destination=/events` | No | `excluded prefix: /user/`. Authenticated surface, also disallowed by robots.txt. |
| 7 | search URL | `https://www.iitb.ac.in/iitb-search?search_api_fulltext=lecture` | No | `excluded prefix: /iitb-search/`. Search results are unbounded and not items. The query key `search_api_fulltext` would reject it too. |
| 8 | duplicate with #fragment | `https://www.iitb.ac.in/event/institute-lecture-taming-turbulence#main-content` | Yes | Canonicalizes to row 1's URL (fragment dropped), so it is the **same** item, deduplicated later on that URL. |
| 9 | same page with tracking param | `https://www.iitb.ac.in/event/institute-lecture-taming-turbulence?utm_source=newsletter&utm_medium=email` | Yes | Canonicalizes to row 1's URL (`utm_*` dropped), so it is the same item. |
| 10 | calendar ?month= variant | `https://www.iitb.ac.in/events/calendar?month=2026-11&view=month` | No | `excluded query key (calendar/search/filter explosion): month, view`. This applies even though `/events/` is an allowed prefix. |
| 11 | lookalike host | `https://notiitb.ac.in/event/institute-lecture-taming-turbulence` | No | `external host: notiitb.ac.in`. Hosts match exactly; `endswith("iitb.ac.in")` would wrongly accept it. |
| 12 | /events-archive/ vs /events/ | `https://www.iitb.ac.in/events-archive/2019` | No | `outside allowed prefixes`. Prefixes keep their trailing slash, so `/events/` never matches `/events-archive/`. `/events/x` is allowed (tested separately). |
| 13 | mailto: | `mailto:events@iitb.ac.in` | No | `non-web scheme: mailto:`. Never an item (`resolve_item_url` also returns `""` for it). |

## The calendar-explosion rule

A calendar view can generate a new URL for every month, week, day, view mode or date range
(`?month=2026-11`, `?month=2026-12`, …, `?view=week&date=…`), with no end in either direction. Every one of them
is a valid page that returns HTTP 200, so a crawler that follows "next month" never stops, and each page lists the
same items under a different URL. **Rule:** a URL that carries any key in `excluded_query_keys` is never an item
and is never followed. This holds even under an allowed prefix and even on the allowed host, and it is checked
before the allowed-prefix rule. The same rule stops search and filter explosion (`search_api_fulltext`, `q`,
`keys`, `sort`/`filter` where configured) and pager pages (`page`), which are listing pages, not items.

What still bounds the crawl when a listing has to be paged:
- `max_listing_pages` (1 here: the homepage block already shows the 40 newest events);
- `max_discovered_items` (40);
- `max_detail_items` (20 detail fetches per run).

These caps are the 2–5 listing pages / 20–40 items / 20 details ceiling for live runs.
