# Section 11 cross-review template: TISS aggregator (Soumyadipta)

Reviewer: Parth. This template is blank by design; the unattended run did not review the other aggregator.
The questions are the same 10 used in `self_review.md` (derived from the Week 3 requirements; swap in the official
Section 11 list if it differs, see OPEN_QUESTIONS.md Q4).

For every issue: name the exact file and function, say what goes wrong with a concrete input, propose a fix, and
say whether you verified it by running something (command + output), not only by reading.

## Questions

1. Does every live request go through the generic client, politely (robots.txt, timeout, user agent, delay,
   logging; no library fetching on its own)?
2. Is every discovered URL canonical, and the same for the same item across discovery methods (relative href,
   tracking params, fragments, case, ports)? Where is the single canonicalization point?
3. Is the crawl scoped (exact hosts, prefix boundaries, login/search excluded, calendar explosion, caps)?
4. Are fetch, parse, normalize and store separate (parsers take text only)?
5. Is dedup correct within a run, across methods, and across runs (and for entity links)?
6. Are run states right (new / changed / unchanged / not_seen_this_run; hash inputs; volatile fields excluded;
   nothing deleted on absence)?
7. Are entities only what the page states (labelled roles, affiliation next to the name, verbatim source_text,
   no inference)?
8. Can two different people or organizations be merged by mistake (matching rules, review queue)?
9. Would a broken listing, a broken detail parser, or a dead site be noticed (run metrics, signatures, warnings)?
10. Is it reproducible offline, and is every generic-layer change justified and documented?

## Findings

| # | Question | File / function | Issue (concrete input → wrong result) | Proposed fix | Verified by running it? (command + result) |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |

## Summary for the author

- Strongest part:
- Most important fix:
- Tests run (suite command, totals, offline?):
