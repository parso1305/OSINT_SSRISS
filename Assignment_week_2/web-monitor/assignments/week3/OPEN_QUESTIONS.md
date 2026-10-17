# Open questions for Parth

Each entry: the question, and what the unattended run did in the meantime.

## Q1 · D2 · Query-parameter order in canonical URLs
Week 3 asks for "keep every other query param in its original order", but two existing Week 2 tests require sorted
params. **Meanwhile:** sorting kept (no Week 2 test edited); the Week 3 order test is xfail. Sorting is also a valid
canonical form (deterministic, so the same item always gets the same key); original order would make `?b=2&a=1` and
`?a=1&b=2` two different items. Decide whether to switch.
