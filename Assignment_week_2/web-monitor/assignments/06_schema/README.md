# Assignment 6: schema review

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Inspect 10 real merged records and propose a shared, cross-team event schema: which fields exist, which are
required, shared or source-specific, which are lists, and which are identifiers, content or provenance.

## What I built / found

- A field table with presence counts from 10 real records
  ([`schema_review.md` §(a)](schema_review.md#a-field-table), [`records_inspected.json`](records_inspected.json)).
- The proposed schema, implemented in [`src/schema.py`](../../src/schema.py): identifiers (`item_url`, `source_id`,
  `institution`), content fields, provenance fields, and `extras` for source-specific values.
- Real value variation: 4 speaker formats, 5 venue spellings, description label prefixes, and a malformed
  `15:00 PM` time on 10/10 records.
- §(h), added after the audit: what a second, non-Drupal source (CMI) showed.

## Key decisions and why

- **`item_url` is the identifier**, not the detail page's canonical link or Drupal's `node_id`. It is known before
  the detail fetch, stays the same whether that fetch succeeds, and means something for every source.
- **`content_hash` covers content fields only.** Provenance (fetch times, statuses) changes every run; hashing it
  would mark every record `changed` every run.
- **`image_url` rejected**: the same placeholder image on 10/10 records carries no information.
- **`speakers` is a list** for other sources' sake. Honestly: 0 of 10 HSS records have more than one speaker.
- **Date-only events**: `starts_at` may be `YYYY-MM-DD` (a local calendar date), a self-describing convention that
  needs no migration and changes no stored hash.
- **Items without a URL of their own** get `listing URL#/item/<hash of a site id, else title + date>`
  (`synthetic_item_url` in [`src/urls.py`](../../src/urls.py)).

## Evidence

- [`schema_review.md`](schema_review.md) (a status note at the top separates the Assignment 6 findings from today's
  code), [`records_inspected.json`](records_inspected.json)
- [`tests/test_audit_regressions.py`](../../tests/test_audit_regressions.py) (date-only validation),
  [`tests/test_generic_source.py`](../../tests/test_generic_source.py) (link-less source, date-only event),
  [`tests/test_runner.py`](../../tests/test_runner.py) (`test_content_hash_ignores_provenance`)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_generic_source.py tests\test_audit_regressions.py tests\test_runner.py
```

## Status

**PASS**, except the team alignment checkpoint (6.7), which is **DEFERRED**: no teammate has shared a schema yet;
the comparison checklist is ready ([§(f)](schema_review.md#f-checkpoint-6-team-alignment)).
