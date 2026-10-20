# Open questions for Parth

Each entry: the question, and what the unattended run did in the meantime.

## Q1 · D2 · Query-parameter order in canonical URLs
Week 3 asks for "keep every other query param in its original order", but two existing Week 2 tests require sorted
params. **Meanwhile:** sorting kept (no Week 2 test edited); the Week 3 order test is xfail. Sorting is also a valid
canonical form (deterministic, so the same item always gets the same key); original order would make `?b=2&a=1` and
`?a=1&b=2` two different items. Decide whether to switch.

## Q2 · D1 / Sections 5-7 · People yield of the target's discovery surface — **CLOSED (repair R1, D33)**
Resolved: discovery now reads the `/events` calendar JSON filtered to lecture-type entries; live `pct_with_speaker` went from 5.0 to 80.0 (16 of 20 parsed events; `10_aggregator/live_runs.md`).

Original question:
The homepage events block (40 newest/upcoming events) is mostly observances in October 2026: live, only 1 of 20 parsed
events labels a speaker (`10_aggregator/live_runs.md`). The lectures and colloquia that name speakers are in the full
calendar (`/events`, 643 entries as JSON inside drupal-settings-json; 36 "Institute Lecture", 14 "Colloquium").
**Meanwhile:** discovery stays on the homepage block (plain HTML, inside the 40-item ceiling; D11). Options: (a) keep
it (monitoring what is upcoming); (b) add a calendar-JSON listing function to the adapter and filter to lecture-type
titles/event types; (c) choose rank 2. Your call with D1.

## Q3 · D1 · Enable `iit_bombay_events` for scheduled runs?
It is `enabled: false`, so Task Scheduler's plain `--once` does not run it. **Meanwhile:** both live demo runs used
`--source iit_bombay_events --force`. Flip `enabled` to true after confirming the target.

## Q4 · 11 · The official Section 11 review questions
The brief for the unattended run referred to "the 10 Section 11 review questions" without listing them.
**Meanwhile:** `11_review/self_review.md` and `review_template.md` use 10 questions derived from Sections 1–10
(politeness, canonical URLs, scope, layer separation, dedup, run states, entity extraction, matching, failure
visibility, reproducibility/generic changes). Swap in the official wording if it differs; the evidence still applies.

## Q5 · R1 · Should ITEMS_DISCOVERED itself be capped at 40?
The calendar lists 122 lecture-type URLs. As before (D16), discovery keeps all of them as candidates, puts 40 in scope
and marks 82 `over max_discovered_items cap (40)` (stored in discovered_items, never fetched), so the summary says
ITEMS_DISCOVERED 122. **Meanwhile:** left as is (the live runs were done with it and a re-run would exceed the 60-request
budget). If "at most 40 discovered" must hold for the metric too, add `"max_entries": 40` to `listing_options` and slice
in `calendar_entries` (one line); the in-scope set would be identical.
