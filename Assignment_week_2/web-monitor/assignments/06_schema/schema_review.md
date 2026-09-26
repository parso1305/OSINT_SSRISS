# Schema Review by Inspection: HSS Seminars (Assignment 6)

> **Status (2026-09-27).** Sections (a)-(g) describe the data and storage **as of Assignment 6** (tables `items` +
> `item_enrichment`). The Assignment 7 refactor implemented the proposal, so several defects described below are no
> longer live: the shared-schema `records` table (`src/storage.py`) persists `source_id`, `institution`, `timezone`
> and `listing_fetched_at`; `speakers` is a list of `{name, affiliation}` with honorifics stripped; description
> labels are removed; `content_hash` covers content fields only (no `raw_text`, no provenance); a failed detail
> fetch carries stored content forward (the check 7 overwrite-on-failure defect is fixed), and so does a value the
> adapter cannot parse (Week 2 audit, case 9). Timestamps are UTC `Z`. Section (h) adds what a second,
> non-Drupal source taught us. Read (a)-(g) as the evidence behind the design, not as a description of the current code.

## Data inspected

The 10 records in `data/events.db`, table `item_enrichment` (+ the matching `items` rows), exactly as
stored by the live Phase 1 run of 2026-09-26 05:53 UTC (`scripts/detail_enrichment_run.py --limit 10`,
log in `assignments/05_enrichment/enrichment_run.log`). Every record went through
`src/enrich.py::merge_listing_and_detail`; all 10 have `detail_fetch_status = "ok"`.
A full dump is in [`records_inspected.json`](records_inspected.json). No record here is fabricated,
and the checkpoint DB (`data/checkpoint5_404.db`) was **not** used.

Each record is stored in two places:

* `item_enrichment.merged_record`: the full merged dict (JSON), plus provenance columns.
* `items`: the normalized subset used for dedup and change detection (`content_hash`).

---

## (a) Field table

N = number of the 10 records with a non-empty value. "Normalized (current)" is what the code
stores today, not what it should store.

| Field | Present | Raw representation observed | Normalized representation (current) | Req / Opt | Shared / source-specific | Role |
|---|---|---|---|---|---|---|
| `item_url` (`items.url`, `item_enrichment.url`) | 10/10 | listing `raw_href`, root-relative: `/events/seminar-talk/rortys-revolution` | `https://www.hss.iitb.ac.in/events/seminar-talk/rortys-revolution` (via `resolve_item_url`) | Required | Shared | **Identifier** (primary key) |
| `title` | 10/10 | `<title>` minus `" \| Humanities and Social Sciences"`, e.g. `Rorty's Revolution`; curly quotes/dashes kept (`Women’s`, `–`) | same string, whitespace-collapsed; identical in `items.title` and `merged_record.title` 10/10 | Required | Shared | Content |
| `speaker` | 10/10 | one free-text string per record, **4 formats**: `Prof <name>` ×6 (e.g. `Prof Pankaj Sekhsaria`), `Prof <name>, <affiliation>` ×1 (`Prof Salvatore Babones, University of Sydney`), `Dr <name>` ×1 (`Dr Sayan Chattopadhyay`), bare name ×2 (`Carlin Romano`, `Joe Thomas Karackattu`). No `Prof.` with period. Same speaker on 2 events (`Prof Anna C. Schultz`) | stored as-is; honorific and affiliation **not** separated; not in `items` at all (only in `merged_record`) | Optional (10/10 here, see §g) | Shared (as `speakers`) | Content |
| `starts_at` | 10/10 | Drupal `<time datetime="2025-09-25T10:00:00Z">`, displayed on page as `Thu, 09/25/2025 - 15:30` (IST) | stored = raw UTC string with explicit `Z`, 10/10; IST = UTC+5:30 verified on 3 records (check 6) | Required | Shared | Content |
| `ends_at` | 10/10 | same format; durations 1.0 h ×1, 2.0 h ×6, 2.5 h ×2, 3.0 h ×1 | same, UTC `Z` | Optional | Shared | Content |
| `date_raw` | 10/10 | listing ordinal date: `9th Apr 2025`, `22nd Aug 2025`, `17th Sep 2025` (no zero-padding; `st/nd/rd/th` suffix). The listing card's badge in `raw_text` uses a **second** format for the same date: `09 Apr 2025` | kept raw | Optional | Source-specific (raw) | Provenance (raw input) |
| `time_raw` | 10/10 | `15:00 PM` ×5, `15:30 PM` ×4, `14:30 PM` ×1: **24-hour clock with a `PM` suffix on 10/10**, malformed as published | kept raw; not parsed (the correct time comes from `starts_at`) | Optional | Source-specific (raw) | Provenance (raw input) |
| `published_at` (`items` only) | 10/10 | derived from `date_raw` | `2025-04-09`: **the event date, not a publication date** (misnamed for events); equals the UTC date of `starts_at` 10/10 (all events start 14:30–15:30 IST, so no day-boundary case occurred) | n/a | Should not be shared under this name | Content (misnamed) |
| `venue` | 10/10 | **5 spellings**: `HSS Seminar Room, Department of HSS` ×6, `HSS Seminar room` ×1, `HSS Seminar Room, IIT Bombay` ×1, `LT 101` ×1, `Online Seminar` ×1. Listing and detail agree 10/10 | stored as displayed; no canonicalization of room names | Optional | Shared | Content |
| `event_type` | 10/10 | detail `field-event-type`: `Seminar / Talk` ×10 | as-is | Optional | Shared | Content |
| `category` | 10/10 | listing `.event-category`: `Seminar / Talk` ×10, **identical to `event_type` 10/10** | as-is | n/a | Duplicate of `event_type` | Content (redundant) |
| `description` | 10/10 | detail `body`, 438–1959 chars. **Label prefixes**: `Abstract:` ×7, `Description:` ×1, none ×2 | stored with the prefix still in the text | Optional | Shared | Content |
| `raw_text` | 10/10 | whole listing card flattened: `09 Apr 2025 Seminar / Talk Rorty's Revolution 9th Apr 2025 15:30 PM HSS Seminar room` | as-is; **feeds `content_hash`** | Optional | Source-specific | Provenance (raw input) |
| `image_url` | 10/10 | `https://www.hss.iitb.ac.in/sites/default/files/default_images/event-1.jpg` **on all 10** (default placeholder) | resolved absolute URL | n/a | **Rejected** (§e) | Would be content, but carries no information |
| `node_id` | 10/10 | `data-history-node-id`: `2809, 2807, 2704, 2703, 2702, 2701, 2700, 2699, 2698, 2697` | string | n/a | Source-specific (Drupal) | CMS-internal id, **not** the identifier (§b) |
| `detail_canonical_url` | 10/10 | `<link rel="canonical">`, **equal to `item_url` 10/10** | resolved via `resolve_item_url` | n/a | Source-specific | Provenance (audit) |
| `raw_href` | 10/10 | root-relative 10/10 | raw | n/a | Source-specific | Provenance |
| `discovered_on_url` | 10/10 | `https://www.hss.iitb.ac.in/events/seminars-and-talks` ×10 | raw | Optional | Shared (provenance) | Provenance |
| `detail_fetch_status` | 10/10 | `ok` ×10 | enum `ok`/`failed`/`not_attempted` | Required | Shared | Provenance |
| `detail_http_status` | 10/10 | `200` ×10 | int | Optional | Shared | Provenance |
| `detail_fetched_at` | 10/10 | `2026-09-26T05:53:33+00:00` … `05:53:53+00:00` | ISO 8601 with `+00:00` offset (**not** `Z`, unlike `starts_at`) | Optional | Shared | Provenance |
| `detail_error` | 0/10 | column is `NULL` on all 10; key absent from `merged_record` | null | Optional | Shared | Provenance |
| `content_hash` (`items`) | 10/10 | sha256 of `title\|published_at\|venue\|description\|raw_text` | hex string | n/a | Shared (storage) | Provenance (derived) |
| `first_seen` / `last_seen` (`items`) | 10/10 | e.g. `2026-09-25T20:25:51.937371+00:00` / `2026-09-26T05:53:54.071525+00:00` | ISO 8601, microseconds, `+00:00`. **Named `first_seen`/`last_seen` in SQLite but `first_seen_at`/`last_seen_at` in `NormalizedItem`** (`src/schema.py`): inconsistent inside our own code | n/a | Shared (storage) | Provenance |
| `updated_at` (`item_enrichment`) | 10/10 | `2026-09-26T05:53:54.170292+00:00` (same for all 10: batch write) | ISO 8601 | n/a | Storage-internal | Provenance |

**Not present in any of the 10 records:** `source_id`/`source_name` (the `items` table has no source
column: `NormalizedItem.source_name` is set but never persisted), `institution`, `organizer`,
`timezone`, `is_online`, `listing_fetched_at`.

---

## (b) `item_url` is THE identifier

* **How it's produced:** the listing's raw href (`raw_href`, root-relative on 10/10) goes through
  `resolve_item_url(href, page_url)` in `src/urls.py`, the single `urljoin` call site
  (Section 4). That function lowercases scheme and host, strips default ports, and drops tracking/session
  params and non-route fragments. (At the time it also collapsed and stripped slashes; since 2026-09-27 the path is
  kept as given, see `assignments/04_pagination/url_canonicalization_notes.md`.) The result was the
  `items.url TEXT UNIQUE NOT NULL` key and the `item_enrichment.url` PRIMARY KEY; today it is `records.item_url`
  (PRIMARY KEY).
  Differently formatted hrefs for one item therefore land on one row
  (`tests/test_url_resolution.py::test_storage_dedups_on_canonical_url_not_raw_href`).
* **Why the merge never takes it from the detail page:** `merge_listing_and_detail`
  (`src/enrich.py`) always writes `merged["item_url"] = listing_item["item_url"]`. The key must be
  known *before* the detail fetch (it is the URL we fetch), and it must be the same whether or not the
  detail fetch succeeds. A failed fetch (`detail_fetch_status="failed"`) still has to update the same
  row. If a successful detail page could replace the key, the same item would get different keys
  depending on fetch outcome, breaking dedup and history.
* **Why not `detail_canonical_url`:** it equals `item_url` on 10/10 today, but it is declared by the
  page, is only available when the detail fetch succeeds, and can change at the site's discretion (for
  example, a Drupal alias change to `/node/2809`). It is kept only for auditing mismatches.
* **Why not `node_id`:** it is a Drupal-internal integer. It is unique only within this one CMS
  install, meaningless for non-Drupal sources, and not stable across a site migration or rebuild.

---

## (c) Proposed shared cross-team schema: content_type `"event"`

> **Proposed; not yet confirmed with teammates.**

Adjustments made because the real data contradicts the design as given:

1. **`organizer`**: absent on 0/10 records. No detail or listing field names a host. It can only
   be filled from the source's configuration (the whole site is the HSS department), not from the
   record. Kept as optional, but documented as *source-config-derived*.
2. **`is_online`**: only derivable on 1/10 (`venue = "Online Seminar"`). `event_type` never
   indicates it (`Seminar / Talk` ×10). Inferring `false` from a room name is a guess, so the field
   must be tri-state: `true` / `false` / `null` (unknown). HSS would emit `true` ×1, `null` ×9.
3. **`speakers` as a list** is kept, but **not** because HSS data needs it: 0/10 records have more
   than one speaker (see §d).
4. **`institution`, `source_id`, `timezone`** are not in any record. They are constants per source,
   so they must come from `SourceConfig`, and `source_id` must also be *persisted* (it is currently lost).

| Proposed field | HSS field today (10 records) | Status | Normalization missing |
|---|---|---|---|
| **IDENTIFIERS** | | | |
| `item_url` (str, req) | `item_url` / `items.url`, 10/10 | ✅ matches | none |
| `source_id` (str, req) | `NormalizedItem.source_name = "iit_bombay_hss_seminars"`, **not persisted** in `items` | ⚠️ gap | add a column; value comes from `SourceConfig.name` |
| `institution` (str, req) | not present | ⚠️ gap | constant `"IIT Bombay"` from source config |
| **CONTENT** | | | |
| `content_type` (str, req) | `NormalizedItem.item_type = "seminar"`, not persisted | ⚠️ gap + mismatch | map `seminar` → `"event"`; persist it |
| `title` (str, req) | `title`, 10/10 | ✅ matches | none |
| `starts_at` (ISO UTC `Z`, req) | `starts_at`, 10/10, already `…Z` | ✅ format matches; ⚠️ only in `merged_record` JSON, not in `items` | promote to a column |
| `ends_at` (opt) | `ends_at`, 10/10, `…Z` | ✅ format; ⚠️ same | promote to a column |
| `timezone` (IANA, opt) | not present; page displays IST | ⚠️ gap | constant `"Asia/Kolkata"` from source config |
| `speakers` (list[{name, affiliation}], opt) | `speaker`: single string, 10/10 | ❌ shape differs | wrap in a list; split on first `, ` → affiliation (1/10); strip leading `Prof `/`Dr ` (8/10). Bare names (2/10) pass through |
| `venue` (str, opt) | `venue`, 10/10 | ✅ name matches | whitespace only. Keep spellings as displayed (5 variants); room canonicalization is out of scope |
| `is_online` (bool\|null, opt) | not present | ⚠️ gap | `true` iff venue/type says online (1/10), else `null` |
| `event_type` (str, opt) | `event_type`, 10/10 (`Seminar / Talk`) | ✅ | none; drop the duplicate listing `category` |
| `organizer` (str, opt) | not present, 0/10 | ⚠️ not observable | from source config (`"Department of Humanities and Social Sciences"`), or leave null |
| `description` (str, opt) | `description`, 10/10 | ✅ name; ❌ content | strip leading `Abstract:` (7/10) / `Description:` (1/10) labels |
| **PROVENANCE** | | | |
| `listing_fetched_at` | not recorded | ⚠️ gap | capture the listing fetch time (currently only `items.first_seen`/`last_seen`, which are *store* times) |
| `detail_fetched_at` | 10/10, `+00:00` offset | ⚠️ format | normalize to `Z` to match `starts_at` |
| `detail_fetch_status` | 10/10 (`ok`) | ✅ | none |
| `detail_http_status` | 10/10 (`200`) | ✅ | none |
| `detail_error` | column present, null 10/10 | ✅ | none |
| `content_hash` | `items.content_hash`, 10/10 | ⚠️ inputs wrong | exclude `raw_text`; see §d and the check 7 finding |
| `first_seen_at`, `last_seen_at` | `items.first_seen` / `last_seen` | ⚠️ naming | rename columns to match `NormalizedItem` and the proposal |
| **SOURCE-SPECIFIC (`extras`)** | | | |
| `extras.node_id` | `node_id`, 10/10 | ✅ keep out of shared columns | none |
| `extras.detail_canonical_url` | 10/10, equals `item_url` 10/10 | ✅ audit only | none |
| `extras.date_raw`, `extras.time_raw`, `extras.raw_text`, `extras.raw_href` | 10/10 each | raw inputs; keep for re-parsing | `time_raw` is malformed (`15:00 PM`) on 10/10: never parse it, use `starts_at` |

---

## (d) Questions

**Shared vs HSS-specific, and why.**
Shared: `item_url`, `source_id`, `institution`, `content_type`, `title`, `starts_at`, `ends_at`,
`timezone`, `speakers`, `venue`, `is_online`, `event_type`, `organizer`, `description`, plus the
provenance block. Any institution's event page has these concepts regardless of CMS.
HSS-specific: `node_id` (Drupal), `detail_canonical_url` (audit of this site's own declaration),
`date_raw`/`time_raw`/`raw_text`/`raw_href` (raw inputs whose *format* is this site's markup; e.g. the
`15:00 PM` quirk and the two date formats `9th Apr 2025` vs `09 Apr 2025` inside one card), and
`category` (a listing duplicate of `event_type`).

**Which should be lists.**
`speakers`, justified by cross-source generality, **not** by this data: 0/10 HSS records have more than one
speaker, and there is no `and`/`&`/`;`-joined speaker string. The one comma (`Prof Salvatore Babones,
University of Sydney`) is a name + affiliation, not two people, which is exactly why a naïve
comma-split into a list would be wrong. The list shape is chosen so a panel from another source doesn't
force a rename later; HSS will always emit a 1-element list. No other observed field is multi-valued:
`venue`, `event_type` and `description` are single on 10/10.

**Identifiers vs content.**
Identifier: `item_url` only (plus `source_id`/`institution` as scoping keys). `node_id` and
`detail_canonical_url` look like identifiers but are rejected as keys (§b). Everything under CONTENT is
content.

**Provenance metadata.**
`detail_fetch_status`, `detail_http_status`, `detail_fetched_at`, `detail_error`, `listing_fetched_at`,
`discovered_on_url`, `raw_href`, `first_seen_at`, `last_seen_at`, `updated_at`, `content_hash` (derived),
and the raw-input fields `date_raw`, `time_raw`, `raw_text`. They describe *how and when we saw* the
item, not the event itself.

**Why `content_hash` must use content fields only.**
The hash decides whether an item "changed", which is the signal a monitor alerts on. Provenance
changes on every run by design: `detail_fetched_at` is a new timestamp each time, and
`detail_fetch_status` flips on transient errors. Hashing provenance would therefore mark every item
`changed` on every run.

Verification check 7 showed the same failure happening *indirectly*. Today's hash is
`title|published_at|venue|description|raw_text`. When a detail fetch fails, the record falls back to
listing data only, so `description` becomes `None`, and a fetch problem is recorded as a content
change. Reproduced with a local HTTP server:

* 200 → `new`
* 200 → `existing`
* 404 → `changed`, and the stored description and speaker were **overwritten with null**
* 200 → `changed` again

One transient 404 produces two false alerts plus temporary data loss.

Two consequences for the shared schema:

1. Hash only the shared **content** fields, never provenance.
2. Hash only content that was actually observed on this run. A failed detail fetch must carry
   forward the last good detail content instead of hashing its absence.

`raw_text` should also leave the hash. It is the flattened listing card, so a listing layout
tweak (for example, the badge format `09 Apr 2025`) would change the hash with no content change.
*(Documented only; not fixed in this phase.)*

---

## (e) Fields considered for the shared schema and rejected

**`image_url`: rejected.**
All 10 records have the same value,
`https://www.hss.iitb.ac.in/sites/default/files/default_images/event-1.jpg`, the site's
default placeholder. It carries no information about any event. It is worse than useless in a shared
change-monitoring table: if the site swaps its placeholder (a routine theme change), every HSS row
would register as changed at once, producing a burst of false alerts that says nothing about any
event. If a future source has real per-event images, it can put them in `extras` until at least two
sources show genuine per-item images.

**`node_id`: rejected.**
`2697`–`2809` are Drupal's internal node numbers. They mean nothing for JNU/TISS/IISER sources that
don't run Drupal, and they would be null or a different kind of id for every other source. They are
redundant with `item_url`, which already identifies the item uniquely. They are not stable across a
CMS migration, so they can't serve as a cross-run key either. Kept as `extras.node_id` for
debugging only.

*(Also dropped: `category`. It is identical to `event_type` on 10/10, so keeping both would create two
columns that must never disagree.)*

---

## (f) Checkpoint 6: team alignment

> **Expected alignment, pending peer-review confirmation.** Saanvi (IISER Pune), Mayank (JNU) and
> Soumyadipta (TISS) have not shared field names. Check 10 found no shared schema file in this repo
> or in the other local project folders, so nothing below is a verified comparison.

**Likely to already match (generic, curriculum-standard names):**
`item_url` (the curriculum's Section 4 canonical-URL key; every source needs a dedup key), `title`,
`description`, `venue`, `raw_text`, `date_raw` (week-1 normalization naming, shared by
`Assignment/05_normalization/normalizer.py` and `NormalizedItem`), `content_hash`,
`first_seen_at`/`last_seen_at` (from `NormalizedItem`). These come from the common assignment
scaffolding, so everyone following it likely used them.

**Likely to need alignment:**

* `speaker` (str) vs `speakers` (list): I store a single string today; others may have either.
* **Date/time:** `starts_at`/`ends_at` (mine) vs `published_at` (the week-1 name, which I also still
  store in `items` as the *event* date) vs `event_date` / `date` / `start_time`. Also UTC-`Z` vs
  naive-IST vs date-only values, and whether end times exist at all.
* `venue` vs `location` (Drupal calls it `field-event-location`; some teams may keep the site's name).
* `event_type` vs `category` vs `item_type`/`content_type` (I have all three concepts today).
* **Provenance naming:** `detail_fetch_status` / `detail_fetched_at` vs `fetched_at` / `http_status`
  (the `NormalizedItem` names), and `first_seen` (my SQLite column) vs `first_seen_at`.
* **Source identity:** `source_name` vs `source_id` vs `source`, and whether institution is a separate field.

**Checklist for the peer review with Saanvi (then Mayank and Soumyadipta):**

1. What is your primary key, and is it produced by the Section 4 canonicalizer? (Same trailing-slash and tracking-param rules?)
2. Do you store event start time as ISO 8601 UTC with `Z`? Do your pages give an end time and a timezone?
3. Is `speaker` single or a list? Do you separate honorific and affiliation?
4. `venue` or `location`? Do you have online/hybrid events, and how are they marked?
5. What do you call the event kind: `event_type`, `category`, `item_type`? What values appear?
6. What provenance do you record (fetch time, HTTP status, detail-fetch status), and under which names?
7. What fields feed your `content_hash`? Does it include raw text, timestamps or image URLs?
8. Which of your fields are CMS-specific (node ids, slugs) and should live in `extras`?
9. Do any of your fields exist on some pages but not others (the presence rates I can't observe, §g)?

---

## (g) Known limitations

* All 10 records come from **one Drupal site, one listing page, one content type**, and all 10
  enriched successfully. Field *presence* is therefore uniform (every field 10/10 except
  `detail_error` 0/10). **The "required vs optional" calls are not supported by presence rates
  from this sample.** Presence of 10/10 here says nothing about other sources, or about older HSS
  pages entered under different editorial habits. The calls are design judgments: *required* = needed
  to identify, deduplicate or place the event in time; *optional* = everything else. They should be
  revisited once teammates' records are available.
* The variation that *is* observed is in values: 4 speaker formats, 5 venue spellings, 3 description
  label styles, 2 date formats inside one listing card, a malformed `time_raw` on 10/10, and one title
  typo in `field-event-title` that we avoid by reading `<title>`.
* None of the 10 events crosses a UTC day boundary (all start 14:30–15:30 IST), so the
  `published_at` (IST calendar date) vs `starts_at` (UTC) mismatch that would appear for events after
  18:30 IST is untested on real data.
* The records reflect the pipeline as of 2026-09-26. The check 7 overwrite-on-failure defect has not
  affected these rows because every fetch succeeded.

---

## (h) Added after the Week 2 audit (2026-09-27): two assumptions the HSS data could not reveal

A second, structurally different source (Chennai Mathematical Institute seminars, audit sandbox
`assignments/week2_audit/sources/cmi_seminars.py`) broke two rules that were implicit in this schema.

### 1. Every item has its own URL. It doesn't.

CMI lists 135 seminars with **no per-item link**. The abstract sits behind a `POST` form that carries a
per-request nonce. `item_url` is still the one identifier, so a source like this must *build* a stable one:

* Use the generic helper `src.urls.synthetic_item_url(listing_url, *identity)`, which returns
  `<listing URL without query>#/item/<16 hex chars of sha256(identity)>`.
* **Identity, in order of preference:** (1) an id the site itself assigns (CMI: the form's `absyear` +
  `absref`); (2) otherwise title + start date as displayed. Option 2 makes an edited title a new item, so use
  it only when nothing better exists.
* **Never** use a value that changes per request (the nonce, a session id), or the page an item was found on.
  The helper drops the query, so `?page=N` never changes an item's identity.
* Whitespace is collapsed and case is folded before hashing, so re-rendering noise can't create new items.
* The `#/…` fragment survives `resolve_item_url` (route-fragment rule) and is never sent to a server.
  Such an identifier is **not fetchable**, so keep `supports_detail` off for that source.

The CMI sandbox adapter originally built this key inline as `show-abstract.php?absyear=…&absref=…`. That
looks like a fetchable URL, but a `GET` of it does not return the abstract. It now calls the generic helper.

### 2. Every event has a UTC start instant. Some sites only give a date.

`starts_at` (and `ends_at`) may now be a **date-only** ISO value `YYYY-MM-DD`. It is the event's local calendar
date in `timezone`, never converted to UTC, because a date without a time has no UTC instant. Validation
(`src/schema.py`, `validate_record`) requires `timezone` in that case, and `ends_at` must be date-only exactly
when `starts_at` is. This is a convention rather than an `all_day` column: the value describes itself, existing
rows keep their shape, and no stored `content_hash` changes.

**What the CMI re-run showed.** The audit rejected 8 of 135 CMI items. None of them was actually date-only:

| CMI items (`absref`) | Why the audit rejected them | Now |
|---|---|---|
| 124, 117, 38, 35, 32 | start time on the lines *after* a blank `Time:` or a "usual format:" line (`11:00 - 11:30 am: Pre-seminar`) | valid, starts at the first listed time |
| 70 | different layout: no `Venue:`, title right after `Time:` | valid (title = unlabelled lines before the speaker) |
| 28, 16 | multi-session lecture series, no `Date:` line | valid: the listing's header date is one of the sessions; the full schedule is kept in `extras.time_raw` |

The stricter layout rules also corrected 3 records the audit had counted as valid (`20` and `14` stored
`"Time: …"` as the title; `2` stored a title cut at a stray backslash-newline). They also correctly reject
**one** item (`66`), whose listing entry has no title line (the old rule stored the speaker's name as the
title). Result: **134 valid, 1 rejected with `title: required`** (was 127 / 8). Evidence:
`assignments/week2_audit/logs/after_fixes/generalization_run.log`. The date-only path is exercised by
`tests/test_generic_source.py::test_source_without_item_links_and_with_a_date_only_event` and
`tests/test_audit_regressions.py::test_date_only_events_validate_with_their_rules`.
