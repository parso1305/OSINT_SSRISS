# Week 1: web-scraping fundamentals on IIT Bombay

[Project README](../README.md) · Week 2: [`Assignment_week_2/web-monitor`](../Assignment_week_2/web-monitor)

Five exercises that build the pieces later reused in Week 2: inspecting HTTP responses, reconnoitring the IIT Bombay
site, mapping its DOM, fetching and parsing HTML, and normalizing and storing scraped items.

| Folder | Contents | Status |
|---|---|---|
| [`01_http/`](01_http) | [`http_headers.py`](01_http/http_headers.py): given a URL, prints the final URL, status, content type and length, redirect history, selected headers and the first 2000 characters of HTML. [`findings.md`](01_http/findings.md): a template for five tests (HTML, redirect, JSON, 404, robots.txt) | KNOWN LIMITATION: `findings.md` was never filled in; `http_headers.py` catches `requests.exception.RequestException` (typo for `requests.exceptions`), so a network error raises `AttributeError` instead of being reported |
| [`02_recon/`](02_recon) | [`IITB_recon.md`](02_recon/IITB_recon.md): recon of `www.iitb.ac.in`: subdomains and redirects, the robots.txt disallow list, no usable sitemap or RSS, and four content surfaces (News, Events Calendar, Research Highlights, Announcements) | Done |
| [`03_DOM/`](03_DOM) | [`DOM_map.md`](03_DOM/DOM_map.md): CSS selector map of the homepage's news, research and gallery sections. [`B_Soup.py`](03_DOM/B_Soup.py): prints the `<h2>` headings of [`fixture.html`](03_DOM/fixture.html) | Done. Note: `B_Soup.py` uses the `lxml` parser, which no requirements file installs |
| [`04_fetch/`](04_fetch) | Fetching (`retriving_html.fetch_url`) kept separate from parsing (`parser.parse_events`); [`main.py`](04_fetch/main.py) fetches `https://www.iitb.ac.in/news` and saves it under [`fixtures/`](04_fetch/fixtures); [`test_parser.py`](04_fetch/test_parser.py) is the checkpoint test. Details: [`04_fetch/README.md`](04_fetch/README.md) | KNOWN LIMITATION, see below |
| [`05_normalization/`](05_normalization) | [`normalizer.py`](05_normalization/normalizer.py): whitespace cleanup, absolute URLs, `DD Mon YYYY` → `published_at`; [`run_normalization.py`](05_normalization/run_normalization.py): [`raw.json`](05_normalization/raw.json) → [`iit_bombay_normalized.json`](05_normalization/iit_bombay_normalized.json) (40 items); [`store.py`](05_normalization/store.py): SQLite upsert keyed by URL, with a content hash. Assumptions: [`normalization_notes.md`](05_normalization/normalization_notes.md) | Done |

## Known limitations of `04_fetch`

- **The checkpoint test fails (0 of 10 events).** `parser.py`'s selectors were changed to the real IIT Bombay news
  markup (`.homepage-news .view-content .views-row`), but `test_parser.py` still parses the sample `file.html`,
  whose cards are `.event-container`. Reproduce: `python -m pytest test_parser.py` inside `04_fetch/`.
- `parser.py` still prints `DEBUG:` lines while parsing.
- `retriving_html.fetch_url` sends a browser (Chrome) User-Agent string although its comment calls it descriptive.
  Week 2's fetcher identifies itself instead (`NaaravanceAcademicMonitor/1.0` with a contact address).
- `04_fetch/README.md` says `REAL_URL` starts as `None`; in `main.py` it is already set to `https://www.iitb.ac.in/news`.

These were exercises; the Week 2 system in [`Assignment_week_2/web-monitor`](../Assignment_week_2/web-monitor)
replaces them and has its own tests.

## Running

There is no requirements file for Week 1. Install `requests`, `beautifulsoup4` (and `lxml` for `03_DOM`), then run
each script from inside its own folder, e.g. `python http_headers.py https://www.iitb.ac.in/robots.txt` in `01_http/`.
