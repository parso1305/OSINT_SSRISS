# Week 3 progress (unattended run on branch `week3-auto`)

Resume rule: after a restart, read this file, DECISIONS.md, OPEN_QUESTIONS.md and `git log`, then continue at the
first section that is not `done`.

Baseline before Week 3 (commit 3471522): main suite 136 passed / 1 skipped; audit suite 43 passed / 3 xfailed.
Live requests before this run: 28 (Section 0 recon, separate budget).

| Section | Status | Commit | Main suite | Audit suite | Live requests (this run, cumulative / 80) |
|---|---|---|---|---|---|
| 1A feed/sitemap inspectors | done | 0b185af | 162 passed, 1 skipped | 43 passed, 3 xfailed | 4 |
| 1B unified discovery record | done | 5ae11e9 | 194 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 4 |
| 2 scope filter | done | ac95879 | 223 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 4 |
| 3 discovery interface | done | 8fe8ed0 | 232 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 4 |
| 4 incremental collection | done | b68ef39 (generic) + e6afaad | 237 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 4 |
| 5 entity extraction | done | 97e5a67 | 280 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
| 6 entity storage | done | a01c7d6 (generic) + 8e56933 | 287 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
| 7 matching policy | done | d1bbdb0 (generic) + 6504fb5 | 312 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
| 8 content router | done | a414ee4 (generic) + d0ed193 | 323 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
| 9 run metrics | done | f3fb696 + 9fa9870 (generic) + 56a27b1 | 337 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
| 10 central aggregator | done (offline + live) | 2f6bdbf | 341 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 61 |
| 11 cross-review prep | done (questions derived, Q4) | aa76a3b | 341 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 61 |
| 12 integration | done | d64efcb | 341 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 61 |
| R1 discovery yield (calendar) | done | ff5b225 (generic) + b1b6262 + 40187ef | 353 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | repair pass 44 / 60 |
| R2 canonical query order | done | ed7ea3b | 354 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R3 enable source | done | a2b942b | 354 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R4 official review questions | done | 1a38c6b | 354 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R8 discovery-drop warning | done | 4ed8de7 | 361 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R6 spec index | done | dace5bf | 361 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R5 repo front page | done | 83cf3a0 | 361 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
| R7 defense notes + status | done | (this commit) | 361 passed, 1 skipped | 43 passed, 3 xfailed | 44 / 60 |
