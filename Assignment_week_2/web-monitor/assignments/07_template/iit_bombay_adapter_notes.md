# IIT Bombay on the Shared Template (Assignment 7)

Source: IIT Bombay HSS Department "Seminars and Talks"
(`https://www.hss.iitb.ac.in/events/seminars-and-talks`, Drupal 9). All evidence below comes from
the saved live HTML in `fixtures/iit_bombay_hss/` (fetched 2026-09-25/26). The live server was
unreachable during this assignment, so every run here is a fixture run over real local HTTP
(`scripts/fixture_site.py`).

## 0. Inventory before the refactor (Step 1)

| Module | Function / object | Class | Hidden source assumption found |
|---|---|---|---|
| `src/fetch.py` | `fetch`, `fetch_page` | Generic | comment named `ee.iitb.ac.in`; no session, robots.txt or delay |
| `src/urls.py` | `resolve_item_url` | Generic | none |
| `src/pagination.py` | `get_next_page_url` | Generic in name | hard-coded CMS pager classes (`.pager__item--next` Drupal, `a.next`, Bootstrap) |
| `src/pagination.py` | `collect_listing` | Generic in name | **defaulted `parse_fn` to `sources.iit_bombay.parse_events`** (imported an IIT Bombay parser) |
| `src/enrich.py` | `merge_listing_and_detail`, `enrich_items` | Generic | imported `requests` (layer leak); did its own sleep |
| `src/runner.py` | `run_source` | Generic in name | fell back to `normalize_events` with an IIT Bombay default; `max_pages`/`html_override` were call arguments, not config |
| `src/runner.py` | `run_pipeline`, `__main__` | IIT Bombay | default `--source iit_bombay`, default fixture `fixtures/iit_bombay/normal_page.html` |
| `src/schema.py` | `normalize_event(s)` | Generic in name | **default `base_url="https://www.iitb.ac.in"`**; date formats of the legacy fixtures |
| `src/schema.py` | `NormalizedItem`, `SourceConfig` | Generic | config held Python callables, so sources were registered in code |
| `src/storage.py` | `compute_content_hash` | Generic | hashed `raw_text` (listing layout) and `published_at`; missing detail counted as a change (Phase 1 check 7) |
| `src/storage.py` | `init_enrichment_table`, `store_enrichment` | Generic | parallel table for merged JSON |
| `src/logging_config.py` | all | Generic | none |
| `sources/__init__.py` | `SOURCES`, `IIT_BOMBAY_*_CONFIG` | IIT Bombay | source registry in code |
| `sources/iit_bombay.py` (old) | `parse_events`, `normalize_item` | IIT Bombay | targets **hand-written** fixtures (`<!-- Realistic IIT Bombay event listing -->`), not a live page |
| `sources/iit_bombay_hss.py` | `parse_seminars`, `parse_detail`, `parse_hss_date`, `normalize_seminar` | IIT Bombay | `<title>` suffix stripped inside the parser; returned legacy `NormalizedItem` |
| `scripts/*.py` | all | IIT Bombay | used `src.fetch` directly |

**Renames made:**
- The old `sources/iit_bombay.py` is now `sources/iit_bombay_legacy.py`, a fixture-only adapter that isn't in the config, kept so the Section 1–4A tests still run.
- The HSS code moved into `sources/iit_bombay.py`.
- `src/fetch.py` is replaced by `src/fetcher.py`.
- `src/config.py` is new; there was no config loader before.
- Config is JSON (`config/sources.json`): PyYAML is installed, but no requirements file declares it.

## 1. What's generic

None of these files contains an institution, CMS or site string. `tests/test_architecture.py`
enforces this with the pattern `iitb|iit bombay|hss|humanities|drupal|node--|field-event` over `src/*.py`.

| Module | Responsibility | Why it carries no IIT Bombay assumption |
|---|---|---|
| `src/fetcher.py` | `Fetcher.get`: the only `requests` user. Session, User-Agent, timeout, per-host delay, robots.txt (RFC 9309, incl. `Crawl-delay`), `FetchError`, FETCH logging | parameters come from config; behaviour depends only on HTTP |
| `src/pagination.py` | `collect_listing`, `get_next_page_url` | next page = the adapter's `NEXT_PAGE_SELECTOR` (default: HTML-standard `rel="next"`). Stops on max_pages / cycle / other host / empty page / all-repeated items / page-2+ fetch failure |
| `src/enrich.py` | `merge_listing_and_detail`, `enrich_items` | merge rule is field-agnostic; the adapter supplies `parse_detail` |
| `src/runner.py` | `run_source(config)` | stages are switched by `supports_pagination`, `supports_detail` and `detail_limit`; adapter loaded by module path |
| `src/schema.py` | shared event schema, `assemble_record`, `validate_record` | Assignment 6 §(c) fields; identity comes from config |
| `src/storage.py` | `store_records` (table `records`, key `item_url`), `content_hash`, carry-forward | hash = `CONTENT_FIELDS` only; carry-forward keys off `detail_fetch_status` |
| `src/config.py` | `SourceConfig`, `load_source_configs`, `load_adapter` | reads JSON; checks the adapter contract |
| `src/logging_config.py` | the only handler setup, KeyValue lines with `logger=<name>` | none |
| `src/urls.py` | `resolve_item_url` (Section 4) | none |

## 2. What's source-specific

**`sources/iit_bombay.py`** contains only:
- **Constants and selectors:** the listing container, cards, icons and `NEXT_PAGE_SELECTOR`; the detail `article.node--type-events` and `field-event-*` classes; `SITE_TITLE_SUFFIX`; the IST offset; regexes for honorifics, description labels and online venues.
- **`parse_listing(html, base_url)`**
- **`parse_detail(html, item_url)`:** raw fields; the title comes from `<title>` (reason in its docstring).
- **`normalize(record)`:**
  - strips the title suffix;
  - splits speakers into `{name, affiliation}` and removes honorifics;
  - removes `Abstract:`/`Description:` labels;
  - produces UTC `starts_at`/`ends_at`, with a fallback from the listing's date and time (IST);
  - sets `is_online` from the venue;
  - keeps HSS-only fields in `extras`;
  - drops `image_url` (rejected in Assignment 6).

**`config/sources.json`, entry `iit_bombay_hss_seminars`:**

| Key | Value |
|---|---|
| `institution` | IIT Bombay |
| `organizer` | Department of Humanities and Social Sciences |
| `adapter` | `sources.iit_bombay` |
| `supports_pagination` / `max_pages` | true / 2 |
| `supports_detail` / `detail_limit` | true / 10 |
| `request_delay_s` | 1.5 |
| `timeout_s` | 10 |
| `schedule` | `0 6 * * *` (cron, for Assignment 8) |

Adding a source takes one adapter file plus one config entry.
`tests/test_generic_source.py` runs an unrelated source through `run_source` with nothing else added.

## 3. Optional capabilities this source supports

**Pagination: yes.** The evidence:
- `live_page_1.html:739` has `<a href="?page=1" title="Go to next page" rel="next" class="page-link">`.
- `live_page_1.html` also links to `?page=32`.
- The Section 4 live run (`assignments/04_pagination/live_run.json`) fetched `?page=1` and `?page=2` with 10 items each.

The config caps it at `max_pages: 2`. The fixture run stopped with `stop_reason=max_pages_reached` after 20 items. Tests cover `max_pages`, `repeated_items`, `fetch_failed` and pagination switched off (1 page).

**Detail enrichment: yes, limited.**
- `detail_limit: 10`: only the first 10 listing items get a detail fetch; the rest are stored as `not_attempted`, with `starts_at` taken from the listing.
- A failed detail fetch keeps the listing record (`failed`, HTTP status and error recorded).
- On a later run, a failed fetch never counts as a change and never erases stored detail content.
- Politeness comes from the fetcher: `max(request_delay_s, robots Crawl-delay)` between requests to the same host.

## 4. Brittle assumptions

| # | What we assume | How it breaks | Loud or silent | How we'd detect it |
|---|---|---|---|---|
| 1 | Listing container `.view-seminars-and-talks .view-content` | Views block renamed or theme change | **Loud**: `StructuralError`, listing `FAILURE stage=parse`, run aborts | FAILURE line |
| 2 | Cards are `.event-card-wrapper` inside the container | Card class renamed while the container stays | **Silent**: 0 items | **Guard implemented:** `WARNING … Listing returned HTTP 200 but parsed 0 items` (`test_zero_items_guard_warns`) |
| 3 | Card rows identified by `i.icon-calendar` / `icon-time` / `icon-marker` | Icon set changes | **Silent** for enriched items (`starts_at` still comes from detail); **loud** for `not_attempted` items: no `starts_at`, so `VALIDATION_FAILURE` and the record isn't stored | `VALIDATE invalid=N` > 0 |
| 4 | Detail wrapper `article.node--type-events` | Content type or theme renamed | **Loud per item**: `StructuralError`, one `DETAIL_FAILURE` per item, run continues | `ENRICH failed=` ≈ `detail_limit` |
| 5 | Detail fields `.field--name-field-event-{speaker,date,end-date,location,type}` | A single field renamed inside an intact article | **Silent**: that field becomes None, the listing value is kept, speakers empty | not guarded; proposal: warn when an `ok` detail yields no speaker or no `starts_at` |
| 6 | `field-event-date` `<time datetime>` is UTC with `Z` (10/10 observed; IST display = UTC + 5:30 checked on 3) | Drupal emits an offset: handled. Emits a naive time: becomes None, falls back to listing time | **Silent but still correct** via the fallback; wrong only if both change | `test_normalize_dates_utc_and_listing_fallback_agrees_with_detail` (fixtures); no runtime cross-check yet |
| 7 | Listing `time_raw` is a 24-hour clock with a stray `PM` (`15:30 PM` 10/10) | Site switches to 12-hour **without** AM/PM | **Silent**: `starts_at` 12 h off for non-enriched items | runtime listing-vs-detail comparison (not implemented) |
| 8 | `<title>` ends with exactly ` \| Humanities and Social Sciences` | Site renames itself | **Silent**: suffix left in every title, and **every** record flips to `changed` once (noisy but visible) | STORE `changed` ≈ total; titles containing ` \| ` |
| 9 | `<title>` is reliable; `field-event-title` is not (editor-typed; wrong on the Echoes page) | `<title>` becomes generic (e.g. "Events") | **Silent**: identical titles | duplicate-title count across items |
| 10 | Speaker string = honorific (`Prof`/`Dr`) + name + optional `, affiliation` (4 formats seen, no delimiter between people) | Two speakers `A, B` become name A + affiliation B; `A and B` stay one name; `Shri`/`Ms` not stripped | **Silent** | none today; affiliation that looks like a person's name is undetectable without a people list |
| 11 | Detail image is the default placeholder (10/10) | Site adds real images | **Silent omission** (`image_url` is dropped by design) | out of scope until shared across sources |
| 12 | `is_online` only when the venue contains "online" (1/10: `Online Seminar`) | `Zoom`, `Webinar`, `Hybrid`, a link as venue | **Silent**: `null`, never a wrong `false` | periodic venue-value review |
| 13 | Description label is `Abstract:` or `Description:` (7 + 1 of 10) | `Summary:` or `Talk abstract:` | **Silent**, cosmetic | none |
| 14 | Next page is `a[rel~='next']` | Pager markup changes | **Silent**: `stop_reason=no_next_page` after page 1, fewer items | a full page (10 items) with no next link and `max_pages` > 1 could warn (not implemented) |
| 15 | Item URLs (Drupal path aliases) are stable | Aliases regenerated | **Silent-ish**: every item becomes `new` under a new key, old rows go stale | STORE `new` ≈ total on a routine run |
| 16 | robots.txt allows `/events/…` and sets no large Crawl-delay | Disallow added, or the server is down | **Loud**: `FETCH_ERROR … robots.txt`, run aborts | FETCH_ERROR line. **Not verified live** (server unreachable) |
| 17 | This machine can't verify the site's certificate chain (Phase 1) | Fetcher retries with `verify=False` and logs a WARNING | Loud (WARNING), but weakens TLS for this host | WARNING line |

## 5. Size of `sources/iit_bombay.py`

`wc -l` gives 203 lines: about 146 lines of code, plus docstrings and comments. That covers two parsers,
one normalizer and 6 small private helpers.

Judgment: **short enough.** Almost all of it is selectors and cleaning rules this site genuinely
needs. There's no I/O, retry, logging setup or storage, and the architecture test fails the build if
any of that appears.
