# Section 4: run states and incremental collection

Code:
- `src/storage.py`: `store_records_detailed`, `_upsert`, `content_hash` / `_hash_view`, `count_not_seen`
- `src/runner.py`: STORE step
- `src/scheduler.py`: passes `run_id`, the run's `started_at` and the previous run's `started_at`
- `src/logging_config.py`: `log_store`, `log_rediscovered`, `log_run_end`

Tests: `tests/test_incremental.py`. Generic change G3/G4 (DECISIONS.md D17).

## The four states

| State | Definition | Where it is decided |
|---|---|---|
| **new** | No row with this canonical `item_url` exists yet. | `_upsert`: the `SELECT` finds nothing |
| **changed** | A row exists and the new `content_hash` differs from the stored one. | `_upsert` |
| **unchanged** | A row exists and the `content_hash` is identical. Was called `existing` in Week 2; renamed everywhere (return values, `runs.unchanged_count`, log keys). | `_upsert` |
| **not_seen_this_run** | A row of this source whose `last_seen_at` is older than this run's `started_at` (D6). No new column. | `count_not_seen(db, source, run_started_at)`, after the writes |

Every row stored in a run gets `last_seen_at` = **the run's `started_at`**. The scheduler passes the `runs` row's
`started_at` into the runner, so "seen this run" and "not seen this run" are an exact comparison, not a race with
the clock.

**Rediscovered (D6).** A row is rediscovered if its stored `last_seen_at` was older than the previous run's
`started_at` for this source. That means it was absent from at least one run and is listed again. It is logged as
`REDISCOVERED run_id=… source_id=… item_url=… rediscovered=true state=unchanged|changed`, and it is counted in the
buckets **by its hash** (`unchanged` or `changed`), never as `new`. Its `first_seen_at` is kept.
Test: `test_absent_then_back_is_logged_rediscovered_and_counted_by_hash`.

**Writes:**
- One transaction per run: `BEGIN IMMEDIATE … COMMIT`, `ROLLBACK` on any error.
- Each row is one `INSERT … ON CONFLICT(item_url) DO UPDATE` statement. `first_seen_at` is written only on insert.
- Log lines carry `run_id=`. Example: `STORE new=0 unchanged=1 changed=0 not_seen_this_run=1 run_id=…` and
  `RUN_END … new=0 unchanged=1 changed=0 not_seen_this_run=1 failed=0`.

What storage already did before Week 3: one transaction per run, rollback, and carry-forward of values that a failed
detail fetch or an unparseable field would otherwise erase. What was missing and added:
- the `unchanged` name;
- `not_seen_this_run`;
- rediscovery;
- `run_id` on the STORE line;
- the `ON CONFLICT` form;
- sorted list fields in the hash.

## What makes an item new / changed

- **new:** its canonical URL has never been stored, so identity is the URL from `resolve_item_url()`. A tracking
  parameter or `#fragment` variant of a known URL is not new
  (`tests/test_url_resolution.py::test_storage_dedups_on_canonical_url_not_raw_href`).
- **changed:** at least one hashed content field differs after normalization. Example from the test: run 2 stores
  B with a new title, giving `changed=1`.

## Hash inputs, field by field

`content_hash` = sha256 of the JSON (keys sorted, compact) of `schema.CONTENT_FIELDS`:

| Field | Why it is content |
|---|---|
| `item_type` | What kind of item it is. |
| `title` | Visible title. |
| `event_start`, `event_end`, `timezone` | When it happens; a reschedule is the most important change. |
| `speakers` | Who speaks. **Sorted by (name, affiliation) before hashing**, so a reorder on the page is not a change. Stored in page order. |
| `location` | Where; a venue change matters. |
| `is_online` | Online or in person. |
| `event_type` | The site's category (Seminar/Talk, Conference/Symposium, …). |
| `organizations` | Who organizes. **Sorted alphabetically before hashing.** |
| `description` | Abstract or body text. |

## Excluded volatile fields (never hashed)

| Field | Why excluded |
|---|---|
| `fetched_at`, `discovered_at`, `detail_fetched_at` | When *we* looked. They change on every run by definition. |
| `http_status`, `detail_http_status`, `detail_fetch_status`, `detail_error` | How the fetch went, not what the page says. A 200 vs 304, or a one-off detail failure, is not new content (a failed detail fetch also keeps the stored values: `_carry_forward`). |
| `raw_text` | The raw card text includes relative phrasing ("posted 3 days ago") and layout noise that changes daily with no content change. |
| relative times, view counts, CSRF/session tokens, cache-busters | Same reason. If an adapter ever scrapes them, they go in `extras`, which is never hashed. |
| `source_url`, `source_name`, `institution`, `item_url` | Identity and provenance: they describe where the record came from, not the event. |
| `first_seen_at`, `last_seen_at`, `content_hash` | Storage bookkeeping. |

Test: `test_hash_inputs_are_content_fields_only` changes each volatile field (hash identical) and each content
field (hash different).

## Why fetched_at must not mark changes

`fetched_at` is different on every run, even when the page is byte-for-byte identical. If it fed the hash, every
run would report every item as `changed`, and the `changed` count, which is the signal that a speaker was replaced
or an event moved, would be pure noise. Test: `test_only_fetched_at_changed_is_unchanged`. Changing `fetched_at`,
`http_status` (200 → 304), `raw_text` and the `detail_*` provenance together still gives `unchanged=1`.

## What absence from a listing actually proves

Very little. An item missing from this run's listing (`not_seen_this_run`) may have:
- scrolled off a capped listing (the homepage block shows the 40 newest);
- moved to page 2;
- been filtered by a scope or cap change;
- vanished because the listing fetch was partial or the markup changed;
- been temporarily unpublished;
- or really been cancelled or deleted.

None of these can be told apart from the listing alone. So absence is only counted and logged, and **nothing is
ever deleted**. Row C in `test_four_states_and_absent_item_is_kept` is still in the database with its old
`last_seen_at`. Only an explicit signal, such as a detail page that returns 404 or 410 repeatedly or says
"cancelled", could justify marking an item gone, and that would be a separate, logged state, not a delete.
