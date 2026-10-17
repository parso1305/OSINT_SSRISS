# Open questions for Parth

Each entry: the question, and what the unattended run did in the meantime.

## Q1 · D2 · Query-parameter order in canonical URLs
Week 3 asks for "keep every other query param in its original order", but two existing Week 2 tests require sorted
params. **Meanwhile:** sorting kept (no Week 2 test edited); the Week 3 order test is xfail. Sorting is also a valid
canonical form (deterministic, so the same item always gets the same key); original order would make `?b=2&a=1` and
`?a=1&b=2` two different items. Decide whether to switch.

## Q2 · D1 / Sections 5-7 · People yield of the target's discovery surface
The homepage events block (40 newest/upcoming events) is mostly observances in October 2026: live, only 1 of 20 parsed
events labels a speaker (`10_aggregator/live_runs.md`). The lectures and colloquia that name speakers are in the full
calendar (`/events`, 643 entries as JSON inside drupal-settings-json; 36 "Institute Lecture", 14 "Colloquium").
**Meanwhile:** discovery stays on the homepage block (plain HTML, inside the 40-item ceiling; D11). Options: (a) keep
it (monitoring what is upcoming); (b) add a calendar-JSON listing function to the adapter and filter to lecture-type
titles/event types; (c) choose rank 2. Your call with D1.

## Q3 · D1 · Enable `iit_bombay_events` for scheduled runs?
It is `enabled: false`, so Task Scheduler's plain `--once` does not run it. **Meanwhile:** both live demo runs used
`--source iit_bombay_events --force`. Flip `enabled` to true after confirming the target.
