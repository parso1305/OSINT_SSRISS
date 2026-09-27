# IIT Bombay on the Shared Template (Assignment 7)

Source: IIT Bombay HSS Department "Seminars and Talks"
(`https://www.hss.iitb.ac.in/events/seminars-and-talks`, Drupal 9). All evidence below comes from
the saved live HTML in `fixtures/iit_bombay_hss/` (fetched 2026-09-25/26). The live server was
unreachable during this assignment, so every run here is a fixture run over real local HTTP
(`scripts/fixture_site.py`).

> **Updated 2026-09-27 after the Week 2 audit** (`assignments/week2_audit/`). Two factual errors are corrected
> (config table: `interval_minutes`, not a cron `schedule`; brittle #6: the fallback did not keep `ends_at`
> correct). Rows #2, #16 and #17 are updated for the fixes, and §6 adds two findings from other sites.

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
- Config is JSON (`config/sources.json`): PyYAML is installed, but no requirements file declared it at the time
  (`requirements.txt` now pins the direct dependencies; PyYAML is not one).

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
| `interval_minutes` | 1440 (Assignment 8: due daily; the scheduler is triggered hourly) |
| `retry_minutes` | not set, default 60 (after a failed run: 60, 120, 240 … min, capped at the interval) |
| `lock_max_age_minutes` | 60 |
| `ca_bundle` | `certs/iitb_ca_bundle.pem` (HSS omits an intermediate certificate; README, TLS section) |
| `allow_empty_listing` | not set, default false (0 parsed items fails the run) |

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
| 2 | Cards are `.event-card-wrapper` inside the container | Card class renamed while the container stays | **Loud** since the audit fix: 0 items → `FAILURE … error_type=EmptyListingError`, run `failed`, exit code 1, nothing stored. (Before: only a WARNING, and the run was recorded `success`.) | `tests/test_audit_regressions.py::test_case08_…` |
| 3 | Card rows identified by `i.icon-calendar` / `icon-time` / `icon-marker` | Icon set changes | **Silent** for enriched items (`starts_at` still comes from detail); **loud** for `not_attempted` items: no `starts_at`, so `VALIDATION_FAILURE` and the record isn't stored | `VALIDATE invalid=N` > 0 |
| 4 | Detail wrapper `article.node--type-events` | Content type or theme renamed | **Loud per item**: `StructuralError`, one `DETAIL_FAILURE` per item, run continues | `ENRICH failed=` ≈ `detail_limit` |
| 5 | Detail fields `.field--name-field-event-{speaker,date,end-date,location,type}` | A single field renamed inside an intact article | **Silent**: that field becomes None, the listing value is kept, speakers empty | not guarded; proposal: warn when an `ok` detail yields no speaker or no `starts_at` |
| 6 | `field-event-date` `<time datetime>` is UTC with `Z` (10/10 observed; IST display = UTC + 5:30 checked on 3) | Drupal emits an offset: handled. Emits a naive or textual value: unparseable | **Corrected:** this row used to say "silent but still correct via the fallback". Only `starts_at` has a listing fallback: the audit (case 9) showed `ends_at` silently erased on 10/10 stored rows, all flagged `changed`, with no log line. **Now loud and non-destructive:** `PARSE_WARNING field=… raw="…"` per value, `starts_at` from the listing, stored `ends_at` kept, `changed=0` | `PARSE_WARNING` lines; `tests/test_audit_regressions.py::test_case09_…` |
| 7 | Listing `time_raw` is a 24-hour clock with a stray `PM` (`15:30 PM` 10/10) | Site switches to 12-hour **without** AM/PM | **Silent**: `starts_at` 12 h off for non-enriched items | runtime listing-vs-detail comparison (not implemented) |
| 8 | `<title>` ends with exactly ` \| Humanities and Social Sciences` | Site renames itself | **Silent**: suffix left in every title, and **every** record flips to `changed` once (noisy but visible) | STORE `changed` ≈ total; titles containing ` \| ` |
| 9 | `<title>` is reliable; `field-event-title` is not (editor-typed; wrong on the Echoes page) | `<title>` becomes generic (e.g. "Events") | **Silent**: identical titles | duplicate-title count across items |
| 10 | Speaker string = honorific (`Prof`/`Dr`) + name + optional `, affiliation` (4 formats seen, no delimiter between people) | Two speakers `A, B` become name A + affiliation B; `A and B` stay one name; `Shri`/`Ms` not stripped | **Silent** | none today; affiliation that looks like a person's name is undetectable without a people list |
| 11 | Detail image is the default placeholder (10/10) | Site adds real images | **Silent omission** (`image_url` is dropped by design) | out of scope until shared across sources |
| 12 | `is_online` only when the venue contains "online" (1/10: `Online Seminar`) | `Zoom`, `Webinar`, `Hybrid`, a link as venue | **Silent**: `null`, never a wrong `false` | periodic venue-value review |
| 13 | Description label is `Abstract:` or `Description:` (7 + 1 of 10) | `Summary:` or `Talk abstract:` | **Silent**, cosmetic | none |
| 14 | Next page is `a[rel~='next']` | Pager markup changes | **Silent**: `stop_reason=no_next_page` after page 1, fewer items | a full page (10 items) with no next link and `max_pages` > 1 could warn (not implemented) |
| 15 | Item URLs (Drupal path aliases) are stable | Aliases regenerated | **Silent-ish**: every item becomes `new` under a new key, old rows go stale | STORE `new` ≈ total on a routine run |
| 16 | robots.txt allows `/events/…` and sets no large Crawl-delay | Disallow added, or the server is down | **Loud**: `FETCH_ERROR url=…/robots.txt error_type=…`, run aborts; the scheduler retries after 60 min, backing off | FETCH_ERROR line. Verified live 2026-09-26: `/robots.txt` HTTP 200 |
| 17 | The server sends only its leaf certificate and omits *GlobalSign RSA OV SSL CA 2018* (diagnosed live 2026-09-26 with `openssl s_client -showcerts`) | The intermediate is renewed or the server is fixed | **Loud**: `FETCH_ERROR … error_type=SSLError`, run fails. Verification is never switched off (the old `verify=False` retry is removed); `ca_bundle` adds exactly the missing intermediate | FETCH_ERROR line; re-check before the intermediate expires (2028-11-21) |

## 5. Size of `sources/iit_bombay.py`

`wc -l` gives 220 lines: 157 lines of code, plus docstrings and comments. (At the audit it was 203 / 146; the
unparseable-date reporting added after the audit accounts for the difference.) That covers two parsers,
one normalizer and 6 small private helpers.

Judgment: **short enough.** Almost all of it is selectors and cleaning rules this site genuinely
needs. There's no I/O, retry, logging setup or storage, and the architecture test fails the build if
any of that appears.

## 6. Findings from other sites (Week 2 audit, 2026-09-26)

### ME department: `<time datetime="…Z">` is IST wall-clock time, not UTC

A second IIT Bombay department (Mechanical Engineering, `https://www.me.iitb.ac.in/events`, also Drupal 9) marks up
event times the same way HSS does, but the `Z` there is false. The values are the IST wall-clock time with a `Z`
appended:

| Event (ME listing, `assignments/week2_audit/fixtures/me_iitb/listing.html`) | Time stated in the title | `datetime` attribute | True UTC |
|---|---|---|---|
| "Seminar by Dr. Maciej Mazur (RMIT University) – 26th Sept, 4:00–5:30 PM" | 4:00 PM IST | `2025-09-26T16:00:00Z` | `10:30:00Z` |
| "Seminar on Machine learning augmented massively parallel flow solvers \| Fri 26 Sep @ 2:15 pm" | 2:15 pm IST | `2025-09-26T14:15:00Z` | `08:45:00Z` |

In 9 of the 10 ME listing items that state a time, the `datetime` hour equals the IST hour; in none does it equal the
UTC hour. HSS's `_to_utc` trusts `Z`. That is correct for HSS, where the display-vs-attribute offset of +5:30 was
verified on 3 pages (audit case 4), but it would store every ME event **5 h 30 min late**, silently.

Why it matters: the brittleness is **per department, not per CMS**. Two sites of the same institution, on the same
Drupal version and with the same `node--type-events` content type, disagree about what `Z` means. So:

* The rule "the `datetime` attribute is UTC" lives in the adapter, never in `src/`. That is where it is today, and it
  must stay there: an ME adapter has to treat the value as naive IST (the audit's sandbox `me_iitb.py` does).
* `validate_record` can only check the *format*. A consistent 5 h 30 min shift is undetectable generically.
* The detection that works is a per-source cross-check between a visible time and the attribute (the HSS test
  `test_normalize_dates_utc_and_listing_fallback_agrees_with_detail` does this on fixtures). A new department
  adapter should get the same test before it goes live.
* The same unchecked assumption would re-appear if the HSS adapter were reused for ME with a config-only change. The
  audit tried this, and it fails loudly anyway (`StructuralError`: different listing view), so there is no silent
  path today.

### `talks.cam.ac.uk`: not used, because its robots.txt opts out of AI crawlers

`https://talks.cam.ac.uk/robots.txt` (saved as `assignments/week2_audit/fixtures/robots/talks.cam.ac.uk.txt`) blocks
`/` for 22 named agents, including `ClaudeBot`, `anthropic-ai`, `GPTBot`, `CCBot` and `Google-Extended`. Its
`User-agent: *` group only disallows edit/admin paths and `/show/archive/`, with `Crawl-delay: 10`.

Our User-Agent (`NaaravanceAcademicMonitor`) is in none of the named groups. The Fetcher's robots check would
therefore **allow** the crawl, by the letter of the rules. We still don't crawl it. The named list shows the site's
intent to keep AI-built or AI-assisted data collection out, and this pipeline is both. Following the letter while
ignoring a clearly stated intent is not the politeness standard this project claims. Decision: rejected as a
candidate source. If it is ever needed, ask the site (the talks.cam team) for permission first.
