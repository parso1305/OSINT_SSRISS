# URL Resolution & Canonicalization Notes (Assignment 4B)

All item URLs, next-page URLs and storage keys in web-monitor go through one function:
`resolve_item_url(href, page_url)` in `src/urls.py`. It is the only `urljoin` call site in
the codebase. Its output is the value stored in the `items.url` column
(`url TEXT UNIQUE NOT NULL`, `src/storage.py:21`), so it is also the deduplication key.

## Sources of evidence

Every example below is quoted verbatim from HTML fetched from the live site. Nothing here is
constructed by hand.

| File | Fetched from | Fetched at (UTC) |
| :--- | :--- | :--- |
| `fixtures/iit_bombay_hss/live_page_1.html` | `https://www.hss.iitb.ac.in/events/seminars-and-talks` | 2026-09-25T14:51:51 (`live_run.json`) |
| `fixtures/iit_bombay_hss/live_page_2.html` | `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1` | 2026-09-25T14:51:53 (`live_run.json`) |

On 2026-09-26 (05:38 UTC) the listing page was re-fetched live. Its set of `href` values is
identical to `live_page_1.html`, so the examples below are still current.

## Canonicalization rules (`src/urls.py`)

1. Resolve `href` against `page_url` (`urljoin`); protocol-relative `//host/...` with no base scheme gets `https:`.
2. Lowercase scheme and host; path case is preserved.
3. Strip default ports (`:80` for http, `:443` for https).
4. Collapse duplicate slashes; drop the trailing slash on every non-root path (root stays `/`).
5. Drop tracking/session query params (`utm_*`, `fbclid`, `gclid`, `sid`, `PHPSESSID`, `jsessionid`, ...) and `;jsessionid=` path params; sort the remaining params by key.
6. Drop fragments, except client-side route fragments (`#!/...`, `#/...`).
7. Return `""` for empty hrefs and non-HTTP(S) schemes (`mailto:`, `tel:`, `javascript:`).

## Before → after examples

### Example 1: Seminar card title link (root-relative)

* **Source**: `fixtures/iit_bombay_hss/live_page_1.html:408`
* **Raw HTML**: `<a href="/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability" hreflang="en">`
* **`page_url`**: `https://www.hss.iitb.ac.in/events/seminars-and-talks`
* **`resolve_item_url` output**: `https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability`
* **What changed**: root-relative path takes the page's scheme and host.

### Example 2: Pager "next" link (query-only relative)

* **Source**: `fixtures/iit_bombay_hss/live_page_1.html:739`
* **Raw HTML**: `<a href="?page=1" title="Go to next page" rel="next" class="page-link">`
* **`page_url`**: `https://www.hss.iitb.ac.in/events/seminars-and-talks`
* **`resolve_item_url` output**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1`
* **What changed**: a query-only href keeps the page's path and replaces its query. `page` is a
  semantic parameter, so it is kept.

### Example 3: Pager "page 1" link: `?page=0` vs the unqueried listing URL (a real awkward case)

* **Sources**:
  * `fixtures/iit_bombay_hss/live_page_1.html:682`: `<a href="?page=0" title="Current page" class="page-link">`
  * `fixtures/iit_bombay_hss/live_page_2.html:688`: `<a href="?page=0" title="Go to previous page" rel="prev" class="page-link">`
  * `fixtures/iit_bombay_hss/live_page_1.html:6`: `<link rel="canonical" href="https://www.hss.iitb.ac.in/events/seminars-and-talks" />`
* **`page_url`**: `https://www.hss.iitb.ac.in/events/seminars-and-talks` (or `...?page=1` for the page-2 link)
* **`resolve_item_url` output**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=0`
* **Why it is awkward**: Drupal's `?page=0` and the bare listing URL are the same page. The site's
  own `<link rel="canonical">` on that page says it is the URL *without* `?page=0`. But
  `resolve_item_url` keeps `page=0`, because `page` is not a tracking param. So one page gets two
  distinct canonical URLs.
* **Impact today**: none in practice. `collect_listing` only follows `rel="next"` links, which
  point forward (`?page=1`, `?page=2`, ...), so it never visits `?page=0`. Listing-page URLs are
  never stored as item keys either. It would matter if a crawler followed `rel="prev"` or
  "first page" links: cycle detection would not recognize `?page=0` as the start URL it already
  visited. This is a known limitation, not something the canonicalizer currently handles.

### No stronger awkward case was found in the fetched HTML

The brief asked for "awkward" real hrefs, such as mixed-case hosts, default ports, tracking
params or double slashes. **None of those occur in the fetched HSS pages.** Every item link is a
clean root-relative path like Example 1. The other real edge cases in `live_page_1.html` are
milder:

| Source | Raw href | `resolve_item_url` output | Note |
| :--- | :--- | :--- | :--- |
| `live_page_1.html:121` (also 175, 241) | `""` (Bootstrap dropdown toggle) | `""` | Empty href is rejected, not resolved to the page itself |
| `live_page_1.html:66` | `#main-content` (skip link) | `https://www.hss.iitb.ac.in/events/seminars-and-talks` | Positional fragment stripped |
| `live_page_1.html:836` | `http://gymkhana.iitb.ac.in` | `http://gymkhana.iitb.ac.in/` | Empty path normalized to `/`; `http` scheme preserved, not upgraded |

The canonicalization rules for mixed case, default ports, tracking params and duplicate slashes
are covered by unit tests in `tests/test_url_resolution.py` (`test_lowercases_...`,
`test_strips_default_ports_only`, `test_trailing_slash_policy`, `test_strips_tracking_...`).
Those tests use **hand-written inputs, not hrefs from fetched HTML.**

## Real differently-formatted hrefs that must dedupe to one key

Tested in `tests/test_url_resolution.py::test_real_href_pairs_resolve_to_same_canonical` and
`::test_storage_dedups_on_canonical_url_not_raw_href`:

* Listing card `/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability`
  (`live_page_1.html:408`) and the detail page's
  `<link rel="canonical" href="https://www.hss.iitb.ac.in/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability" />`.
  The detail page was re-fetched live on 2026-09-26 05:38 UTC, and its canonical link (line 7 of
  that response) matches the value hardcoded in the test exactly.
* HSS "Careers" nav link: absolute `https://www.hss.iitb.ac.in/careers` (`live_page_1.html:272`)
  vs root-relative `/careers` (`live_page_1.html:806`).
