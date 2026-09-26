# IIT Bombay Live Pagination & Canonicalization Analysis (Assignment 4B)

This document details the live pagination mechanics, crawl traversal behavior, stopping conditions, and URL canonicalization rules observed on IIT Bombay's public surface (`https://www.hss.iitb.ac.in/events/seminars-and-talks`).

All findings reflect actual HTTP interactions and live DOM structures from the target site.

---

## 1. Live Pagination Pattern & CMS Mechanics

* **Target Surface**: `https://www.hss.iitb.ac.in/events/seminars-and-talks`
* **Underlying CMS**: Drupal 9/10 (Views Module)
* **Pagination Pattern**: Query String Parameter with 0-indexed page index (`?page=N`).
  * **Page 1 (Base listing)**: `https://www.hss.iitb.ac.in/events/seminars-and-talks` (or implicitly `?page=0`)
  * **Page 2**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1`
  * **Page 3**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=2`
* **Card Batching**: Exactly 10 event cards per page rendered within `.view-seminars-and-talks .view-content`.

### HTML Pager Markup Structure
In the live HTML response, Drupal renders a semantic navigation landmark at the bottom of the listing:

```html
<nav aria-label="Pagination" aria-labelledby="pagination-heading" class="pager" role="navigation">
  <h4 class="visually-hidden" id="pagination-heading">Pagination</h4>
  <ul class="pagination js-pager__items">
    <li aria-current="page" class="page-item is-active active">
      <a class="page-link" href="?page=0" title="Current page">
        <span class="visually-hidden">Current page</span>1
      </a>
    </li>
    <li class="page-item">
      <a class="page-link" href="?page=1" title="Go to page 2">
        <span class="visually-hidden">Page</span>2
      </a>
    </li>
    <li class="page-item pager__item--next">
      <a class="page-link" href="?page=1" rel="next" title="Go to next page">
        <span class="visually-hidden">Next page</span>
        <span aria-hidden="true">Next ›</span>
      </a>
    </li>
  </ul>
</nav>
```

---

## 2. Next Page Discovery in Real HTML

`get_next_page_url(html, current_url)` extracts the next page using standard CSS selectors evaluated in priority order:
1. **Primary Priority**: `a[rel~='next']` (Matches `<a href="?page=1" title="Go to next page" rel="next" class="page-link">`, `fixtures/iit_bombay_hss/live_page_1.html:739`).
2. **Fallback Priority**: `.pager__item--next a`, `li.next a`, `a.pager-link-next`.
3. **Anchor Text Matching**: Searches inside `.pager a` or `.pagination a` for text containing `"Next"` or `"›"`.

The extracted relative `href` (e.g., `?page=1`) is resolved against the current page URL using `resolve_item_url()` (`src/urls.py`):

```
resolve_item_url("?page=1", "https://www.hss.iitb.ac.in/events/seminars-and-talks")
  -> "https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1"
```

---

## 3. Real Live Run & Exact Stopping Condition

A live crawler execution was performed using `collect_listing()` with `max_pages=3`:

### Execution Log Summary
* **Start URL**: `https://www.hss.iitb.ac.in/events/seminars-and-talks`
* **Configured `max_pages`**: `3`
* **Page 1 Fetched**: `https://www.hss.iitb.ac.in/events/seminars-and-talks` (HTTP 200, 10 items parsed)
* **Page 2 Fetched**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1` (HTTP 200, 10 items parsed)
* **Page 3 Fetched**: `https://www.hss.iitb.ac.in/events/seminars-and-talks?page=2` (HTTP 200, 10 items parsed)
* **Total Records Collected**: 30 event items.
* **Exact Fired Stopping Condition**: **`max_pages_reached`**
  * The crawler evaluated `len(visited_urls) >= max_pages` after completing page 3, halting gracefully before traversing page 4 (`?page=3`).

### Exact Discovered-on Page Tracking
Each extracted item record retains the exact listing page URL where it was first discovered via `discovered_on_url`:
* Items 1–10: `discovered_on_url = "https://www.hss.iitb.ac.in/events/seminars-and-talks"`
* Items 11–20: `discovered_on_url = "https://www.hss.iitb.ac.in/events/seminars-and-talks?page=1"`
* Items 21–30: `discovered_on_url = "https://www.hss.iitb.ac.in/events/seminars-and-talks?page=2"`

---

## 4. Handling Cross-Page Duplicates

In paginated systems, new items published during crawl execution can shift item positions across page boundaries, causing an item from Page 1 to appear again on Page 2.

### Ingestion Pipeline Deduplication Strategy
1. **Canonical Key Resolution**: Before database storage, all item URLs pass through `resolve_item_url()` to normalize hostname casing, strip default ports, collapse redundant slashes, and strip fragment anchors or UTM parameters (rules and real examples: [`url_canonicalization_notes.md`](url_canonicalization_notes.md)).
2. **Database Primary Constraint**: The SQLite schema enforces `url TEXT UNIQUE NOT NULL` (`src/storage.py:21`); `url` holds the canonical `item_url`.
3. **Idempotent Storage (`store_all`)**:
   * If an `item_url` does not exist in SQLite $\rightarrow$ Inserted as `new` record with `first_seen_at = now()`.
   * If an `item_url` exists with identical content $\rightarrow$ Tagged as `existing`, updating only `last_seen_at = now()`.
   * If an `item_url` exists with modified fields $\rightarrow$ Tagged as `changed`, updating content fields and `last_seen_at`.

---

## 5. Production Crawl Limits & Recommended Policy

| Crawl Mode | Recommended `max_pages` | Rationale |
| :--- | :--- | :--- |
| **Incremental Monitoring (Hourly Cron)** | **$2 - 3$ Pages** | Departmental event feeds publish at most 1–3 new events per week. Inspecting the top 20–30 items is sufficient to detect newly published announcements while minimizing bandwidth and server load. |
| **Initial Historical Backfill** | **$10 - 15$ Pages** | Captures recent historical archives (100–150 past events) up to 1–2 academic years without putting excessive load on university servers. |
| **Safety Guards** | `empty_listing`, `cycle_detected`, `domain_mismatch` | Built-in circuit breakers halt crawling immediately if a page returns 0 cards, if a loop is detected, or if a next link escapes to an external domain. |

---

## 6. URL Canonicalization

URL resolution rules and real before → after examples (each cited to a fetched-HTML file and line) are in [`url_canonicalization_notes.md`](url_canonicalization_notes.md).
