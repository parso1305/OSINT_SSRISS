# Section 8: content router

Code:
- `src/router.py`: `classify_discovered_item`, `classify_with_reason`, `fetchable_as_html`.
- `src/aggregator.py`: `route_candidate` and `discovered_item_row`.
- Storage: `discovered_items` (generic change G7).

Config: the `router` block of `iit_bombay_events` in `config/sources.json`. Tests: `tests/test_router.py`.

## Labels

`event`, `announcement`, `faculty`, `pdf_document`, `external_link`, `unknown`.

## Rules, in this order (the first rule that decides wins; `class_reason` names it)

| # | Rule | Evidence | Result |
|---|---|---|---|
| 1 | External host | The URL's host is not in `router.hosts` (`["www.iitb.ac.in"]`) | `external_link`, never detail-fetched |
| 2 | PDF | If the **Content-Type** is known (after a fetch), `application/pdf` gives `pdf_document`, and any other type means *not a PDF*, even for a URL ending in `.pdf`. If no Content-Type is known yet (before fetching), a path ending in `.pdf` gives `pdf_document`. | `pdf_document`, never detail-fetched as HTML |
| 3 | Explicit category label | The label on the listing card, mapped by `router.category_map` (exact match, case-insensitive) | the mapped class |
| 4 | URL pattern | `router.url_patterns`, checked in config order: `event` ← `/event/`, `/events/`; `announcement` ← `/breaking-news/`, `/announcement-staff/`, `/announcements/`; `faculty` ← `/employee/`, `/faculty/` | that class |
| 5 | Otherwise | — | `unknown`, persisted with the reason, never forced into `records` |

**Why this order.**
- An external link is decided first because nothing else about it matters: we never fetch it. Even a card labelled
  "Seminar/Talk" whose link goes to a registration site is `external_link`.
- PDFs come next because a PDF must never be parsed as HTML, whatever its card says.
- A label the site itself shows is better evidence than our guess from a URL path.
- A URL pattern is better than nothing.
- No text, title or topic classification is used anywhere.

**Content-Type beats the extension.** It comes from the generic change G1 (`FetchResult.content_type`). The router
runs twice:
1. **Before fetching**, with no Content-Type. This keeps PDFs and external links from ever being requested as
   detail pages.
2. **After a detail fetch**, with the response's Content-Type. A `.pdf` URL that the server answers with
   `text/html` (a Drupal node path that only looks like a file) is refined to its URL-pattern class. An
   extensionless URL answered with `application/pdf` becomes `pdf_document`, and its body is not parsed as an event.

The target's real URL types, from the saved evidence and the live `/rss.xml`, are: `/event/…` (event),
`/breaking-news/…` (announcement), `/employee/…` (faculty: `Prof. Indu J.` in the real feed), `/tenders/…`,
`/award/…`, `/research-highlight/…`, `/announcement-staff/…` and `/node/6913`. Tenders, awards, research highlights
and bare `/node/N` paths match no rule and stay `unknown` with the reason. They are also out of scope (Section 2),
so they are recorded but never fetched.

## `discovered_items`: every candidate is kept

Every candidate from `discover_items`, in scope or not, gets one row:

`discovered_url` (PK), `source_name`, `discovery_methods` (JSON), `discovered_title`, `source_timestamp`,
`source_timestamp_raw`, `first_discovered_at`, `last_discovered_at`, `in_scope`, `scope_reason`, `content_class`,
`class_reason`.

The rows are written inside the run's one transaction. `first_discovered_at` is kept on later runs. Unknown and
unsupported items stay here with their reason. They are never dropped and never forced into `records`. Only
`content_class = event` items that are in scope go on to detail fetching, parsing and `records`.

## Which classes become `records` (ITEM_TYPES)

`ITEM_TYPES` stays `("event",)`. Only a class with a parser that writes to `records` may widen it:
- `event`: `sources/iit_bombay_events.py::parse_event_detail`.
- `announcement` (`/breaking-news/…`): **not widened**. The target's news pages have a parseable detail page, but no
  announcement parser or announcement schema rules exist this week, and building one is outside Sections 1–10.
  Announcements are discovered, scoped, routed and kept in `discovered_items` with
  `content_class = announcement`, ready for a later parser (DECISIONS.md D25).
- `faculty`, `pdf_document`, `external_link`, `unknown`: never records.

## Tests (`tests/test_router.py`)

| Brief case | Test | Result |
|---|---|---|
| PDF under `/events/` | `test_pdf_under_events_is_a_pdf_document_and_never_fetched_as_html` | `pdf_document`, `fetchable_as_html` false |
| Event linking to an external registration site | `test_event_link_to_an_external_registration_site` | `external_link`, even with a `Seminar/Talk` label |
| News item with no category label | `test_news_item_with_no_category_label_routes_by_url_pattern` | `announcement` via `/breaking-news/` |
| `text/html` on a `.pdf` URL | `test_text_html_on_a_pdf_url_is_not_a_pdf` | `pdf_document` before the fetch, `event` after it |
| `application/pdf` on an extensionless URL | `test_application_pdf_on_an_extensionless_url` | `pdf_document` |
| Faculty URL pattern | `test_faculty_url_pattern` | `faculty` via `/employee/` |
| Unknown item persisted with its reason | `test_unknown_item_is_persisted_with_its_reason` | the real `/node/6913` stored with `content_class = unknown`, reason `no rule matched (host www.iitb.ac.in, path /node/6913)` |
