# Assignment 3: recon of IIT Bombay surfaces and template suitability

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Compare at least three public IIT Bombay surfaces (listing → detail, pagination, archive, fields, format) and decide
which of them fit a shared crawler template.

## What I built / found

- A comparison of three surfaces: EE announcements, HSS events and HSS news
  ([`iit_bombay_structure.md`](iit_bombay_structure.md)).
- Common fields across them (`title`, `item_url`, `date_raw`, category), all needing a listing → detail crawl, with
  server-rendered HTML (no headless browser).
- Exceptions: HSS news detail pages are wrappers around PDFs, EE and HSS use completely different markup, and EE
  filters on the client side instead of paginating.

## Key decisions and why

- **HSS "Seminars and Talks" was chosen as the live source**: stable Drupal markup, a real `rel="next"` pager, and
  consistent event detail pages.
- **Selectors were re-checked against saved HTML** after the audit found the first draft's HSS selectors
  (`.views-row`, `.views-field-title`) on no saved page. `/events` was fetched once and saved
  ([`recon_events_2026-09-27.html`](../../fixtures/iit_bombay_hss/recon_events_2026-09-27.html)). Its real selectors
  are the ones the adapter uses, and the doc's example item (`11th Nov 2026`, `JALVIHAR CONFERENCE HALL`) is on it.

## Evidence

- [`iit_bombay_structure.md`](iit_bombay_structure.md) (correction note at the top)
- Saved HTML: [`recon_events_2026-09-27.html`](../../fixtures/iit_bombay_hss/recon_events_2026-09-27.html),
  [`listing_2026-09-26.html`](../../fixtures/iit_bombay_hss/listing_2026-09-26.html)
- [`tests/test_adapter_iit_bombay.py`](../../tests/test_adapter_iit_bombay.py): the adapter's selectors on the real pages

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_adapter_iit_bombay.py
```

## Status

**PASS.** Known limitation: the EE and HSS-news findings come from live inspection on 2026-09-25; those pages were not
saved as fixtures, so they can't be re-checked offline.
