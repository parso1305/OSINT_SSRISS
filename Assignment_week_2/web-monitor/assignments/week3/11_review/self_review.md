# Section 11: self-review of the IIT Bombay events aggregator

**About the questions.** The brief for this run did not include the text of the 10 Section 11 review questions, so the
10 below were derived from the Week 3 requirements (Sections 1–10). If the official list differs, swap the headings;
the evidence below still applies (OPEN_QUESTIONS.md Q4). Evidence is given as `file::function`, a test name, or
command output already pasted in the section folders.

---

## 1. Does every live request go through the generic client, politely?

**Yes.**
- `src/fetcher.py::Fetcher.get` is the only code that sends requests. `tests/test_architecture.py::test_only_fetcher_uses_requests_and_only_storage_uses_sqlite`
  covers `src/*.py`, and `tests/test_week3_architecture.py::test_discovery_never_touches_the_network_or_storage`
  covers `src/discovery/`.
- Robots.txt is checked per origin (RFC 9309), with an explicit timeout (15 s for the target), the honest
  User-Agent, and a FETCH line per request.
- `request_delay_s: 3.0` gives ≥ 3 s per host. The live log shows detail fetches about 3 s apart
  (`10_aggregator/live_runs.md`).
- feedparser never fetches: `tests/test_discovery_feed_sitemap.py::test_feed_parser_rejects_url_or_path_input` and
  `test_feed_parser_never_calls_feedparser_with_a_url`.
- Live budget: 61 of 80 requests (`live_requests.md`), with no 403, 429 or robots.txt refusal.

## 2. Is every discovered URL canonical, and the same for the same item across methods? *(focus area: in depth)*

**Yes, with one documented open point (query-parameter order, D2/Q1).**

**Single point of canonicalization.** `src/urls.py::resolve_item_url` is the only `urljoin` call in the code base
(`tests/test_week3_architecture.py::test_urljoin_is_called_only_in_resolve_item_url`). Every discovery parser calls
it through `src/discovery/record.py::make_record`. `DiscoveryRecord.__post_init__` **rejects** a URL that is not
already canonical (`resolve_item_url(u, "") == u`), so no code path can produce a record with a raw href
(`tests/test_discovery_record.py::test_post_init_validation`: `?utm_source=x` and `#main-content` are rejected as
"not canonical").

**What it normalizes, and why each rule is safe:**

| Rule | Example (from tests) | Why it cannot merge two different items |
|---|---|---|
| Resolve relative, protocol-relative and root-relative hrefs against the page | `/event/institute-lecture-taming-turbulence` and `event/international-conference-quantum-dynamics#main-content` on `https://www.iitb.ac.in/` | This is standard RFC 3986 resolution, exactly what a browser does. |
| Lowercase scheme and host; drop `:80` / `:443` | `HTTPS://WWW.IITB.AC.IN:443/event/...` | DNS host names and default ports are case- and port-insensitive by definition. |
| Keep path case and trailing slashes | `/Event/X` stays `/Event/X` | The server decides whether `/a/` and `/a` are the same resource. Week 2 showed real sites where they differ (`test_storage_ee_slash_and_no_slash_are_distinct_keys`). |
| Drop the fragment | `#main-content`, `#register` | A fragment is never sent to the server, so it cannot select a different item. The one exception is route fragments (`#!/…`, `#/…`), kept because on client-routed pages they *are* the item (and `synthetic_item_url` relies on `#/item/<hash>`). |
| Drop tracking and session params | `utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`, `ref`, `sid`, `PHPSESSID`, `;jsessionid=` | They identify the click or the visitor, not the content (`tests/test_week3_canonical.py::test_tracking_fragment_case_and_port_variants_collapse`). |
| Keep every other param (sorted by key) | `?page=2` survives | A semantic param can select a different resource. |

**Proof across methods (the 1B checkpoint).** In `tests/test_discovery_record.py::test_same_item_same_url_across_methods`,
one event appears as:
- a relative HTML href;
- an RSS link with `utm_source=rss&utm_medium=feed#main-content`;
- a sitemap `<loc>`.

All three records carry the identical `discovered_url`, with identical spec keys.
`tests/test_discovery_interface.py::test_duplicate_discovery_url` shows the collapse happening on the canonical URL:
three raw hrefs become one candidate with `discovery_methods == ("html", "rss", "sitemap")`. Offline,
`taming-turbulence` is found by html and rss and stored as **one** `discovered_items` row with
`["html", "rss"]` and one record (`tests/test_aggregator_e2e.py::test_routing_and_detail_fetches`).

**Proof across runs and tables.** The canonical URL is the key everywhere:
- `records.item_url` (PK);
- `discovered_items.discovered_url` (PK);
- `item_people.item_url` / `item_organizations.item_url` (FK, D4).

The duplicate checks after two offline runs, after the changed run, and after two live runs all return 0 rows
(`demo_offline.md`, `live_runs.md`). There is no second key to drift from it.

**Open point.** D2 asked to keep the remaining params in their original order. Two Week 2 tests require sorted
order, so sorting is kept and the Week 3 test is xfail (`tests/test_week3_canonical.py::test_remaining_params_keep_their_original_order`).
Sorting is the *safer* canonical form for dedup, because `?b=2&a=1` and `?a=1&b=2` become one key; the cost is that
the stored URL may not be byte-identical to the one in the page. Parth decides (Q1).

**Known limit.** Canonicalization cannot know that two *different* URLs are the same event, for example after a
site renames a slug and redirects. The redirect is visible in FETCH `final_url=`, but the record key stays the
listing URL. That is a matching problem, deliberately not solved by guessing.

## 3. Is the crawl scoped so it cannot wander or explode?

**Yes.** `src/scope.py::scope_decision` and `tests/test_scope.py` (13 brief cases plus extras; the md table and the
tests are checked against each other). It enforces:
- exact host matching (`notiitb.ac.in` is rejected) and trailing-slash prefixes (`/events/` ≠ `/events-archive/`);
- excluded login and search prefixes;
- calendar-explosion query keys (`month`, `view`, …).

Caps come from the config: 1 listing page, 40 discovered items, 20 detail fetches. Out-of-scope candidates are kept
with their reason, never fetched (`02_scope/scope_cases.md`).

## 4. Are fetch, parse, normalize and store separate?

**Yes.**
- **Fetch:** only in `Fetcher`, driven from `src/discovery/discover.py::discover` and `src/aggregator.py::run_aggregator`.
- **Parse:** `src/discovery/{html,feed,sitemap}.py` and `sources/iit_bombay_events.py::parse_event_detail`, which take
  text and never fetch.
- **Normalize:** `src/schema.py::assemble_record` and `validate_record`.
- **Store:** only `src/storage.py` touches sqlite.

`tests/test_aggregator_e2e.py::test_adapter_stays_short_and_has_no_generic_code` keeps the adapter free of
fetching, storage and logging setup.

## 5. Is dedup correct within a run, across methods, and across runs?

**Yes.**
- **Within a run and across methods:** dedup on the canonical URL, with the merge rule html > rss > atom > sitemap,
  field by field (D15, `03_discovery_interface/notes.md`).
- **Across runs:** `INSERT … ON CONFLICT(item_url)` upsert.
- **Links:** composite keys plus `INSERT OR IGNORE`.
- **Review pairs:** `(kind, a_id, b_id)`.

`tests/test_entity_storage.py::test_second_run_adds_zero_link_rows` and the duplicate checks in both demos.

## 6. Are run states and change detection right?

**Yes.**
- The four states `new` / `changed` / `unchanged` / `not_seen_this_run` (D6, `04_incremental/run_state_notes.md`).
- The hash covers content fields only; lists are sorted before hashing.
- `fetched_at` and other volatile fields never mark a change: `tests/test_incremental.py::test_only_fetched_at_changed_is_unchanged`
  and `test_reordered_speakers_and_organizations_are_unchanged`.
- An absent item is kept and counted, never deleted (`test_four_states_and_absent_item_is_kept`).
- Rediscovery is logged and counted by its hash (`test_absent_then_back_is_logged_rediscovered_and_counted_by_hash`).
- Live run 2 is 40 of 40 unchanged.

## 7. Are entities only what the page states?

**Yes.**
- Labels come from the adapter, roles only from labels, and an affiliation only when it is written next to the name.
- `source_text` is verbatim, and every mention is checked against its fixture:
  `tests/test_entities_extraction.py::test_every_entity_has_source_text_that_appears_verbatim_in_its_fixture`
  (20 fixtures).
- Unlabelled speaker-like text yields nothing (`test_unlabelled_speaker_like_text_extracts_nothing`, real pages).
- There is no NLP or inference. `records.speakers` and `records.organizations` come from the same extraction.

## 8. Can two different people or organizations be merged by mistake?

**Only through an identical `name_key`, which is a documented, accepted identity claim (D5).** Everything else goes
to review and is never merged:
- `src/entities.py::person_match` and `org_match`;
- `tests/test_matching_policy.py`: 10 person pairs and 6 organization pairs, plus
  `test_review_pairs_are_queued_never_merged`, which shows that a reviewer's status survives re-runs.

`name_key` never expands initials (`A. Rao` ≠ `Ananya Rao`). A bare acronym is an alias only on the page that
defines it.

## 9. Would a broken listing, a broken parser, or a dead site be noticed?

**Yes, each with a distinct signature** (`09_metrics/failure_signatures.md`, real output):

| Signature | Meaning |
|---|---|
| discovered 25 / parsed 20 / new 0 | Nothing new |
| discovered 25 / parsed 0 / failed 20 | The detail parser broke |
| discovered 0, HTTP 200, status failed | The listing selector broke |
| HTTP 503, status failed | The site is down |

- `COVERAGE_DROP` catches a silently emptied field when the counts look normal.
- `DISCOVER_EMPTY` catches a broken listing that a second discovery method would hide.
- `tests/test_metrics.py` asserts all of these, including that a failed run's summary is stored on its `runs` row.

## 10. Is it reproducible offline, and is every generic change justified?

**Yes.**
- `scripts/offline_pytest.py` runs both suites with outbound HTTP blocked. The final totals are in
  `assignments/week3/WEEK3_STATUS.md`. A run with Wi-Fi actually off is still "Needs Parth".
- The offline aggregator (`scripts/aggregator_fixture_site.py` plus `local_aggregator_fixture`) reproduces the whole
  pipeline through the scheduler.
- Generic changes G1–G9 are listed with reasons in README "Changes to the generic layer" and DECISIONS.md.
- Existing tests were edited only for the Section 4 `existing` → `unchanged` rename (`git show b68ef39 -- tests`).
