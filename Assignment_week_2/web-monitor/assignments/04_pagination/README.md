# Assignment 4: pagination and canonical URLs

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Walk a paginated listing safely (with explicit stop conditions), and turn every href into one canonical URL that
serves as the deduplication key.

## What I built / found

- [`src/pagination.py`](../../src/pagination.py) `collect_listing`: follows the adapter's next-page selector
  (default `rel="next"`) and stops on `max_pages`, a cycle, another host, an empty page, a page of repeated items,
  or a fetch failure on page 2+.
- [`src/urls.py`](../../src/urls.py) `resolve_item_url`: the single `urljoin` call site. It lowercases scheme and
  host, strips default ports, tracking/session params and non-route fragments.
- A live 3-page crawl of HSS (30 items, stop reason `max_pages_reached`): [`live_run.json`](live_run.json).
- Real hrefs that must dedupe to one key (listing link vs detail canonical), each cited to a line of saved HTML.

## Key decisions and why

- **The URL path is kept exactly as given** (changed 2026-09-27, after the audit). The canonical URL is also the URL
  that gets fetched. Stripping trailing slashes made the CMI listing `/activities/` work only through a server
  redirect. A trailing slash or `//` can name a different resource, and only the server knows. Redirects are now
  logged (`final_url=… redirect_status=301`).
- **Next page = one selector, no guessing.** No CMS-specific fallbacks in the generic layer; if the pager changes,
  the crawl stops after page 1 with `stop_reason=no_next_page`.

## Evidence

- Notes: [`iit_bombay_pagination_notes.md`](iit_bombay_pagination_notes.md),
  [`url_canonicalization_notes.md`](url_canonicalization_notes.md), [`live_run.json`](live_run.json)
- Tests: [`tests/test_pagination.py`](../../tests/test_pagination.py),
  [`tests/test_url_resolution.py`](../../tests/test_url_resolution.py),
  [`tests/test_canonicalization.py`](../../tests/test_canonicalization.py),
  [`tests/test_audit_regressions.py`](../../tests/test_audit_regressions.py) (case 11, redirect logging)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_pagination.py tests\test_url_resolution.py tests\test_canonicalization.py
```

## Status

**PASS.** Known limitation: Drupal's `?page=0` and the bare listing URL are the same page but different keys. It
doesn't matter today, because only `rel="next"` links are followed ([canonicalization notes, Example 3](url_canonicalization_notes.md#example-3-pager-page-1-link-page0-vs-the-unqueried-listing-url-a-real-awkward-case)).
