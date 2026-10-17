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
| 8 content router | done | a414ee4 (generic) + (this commit) | 323 passed, 1 skipped, 1 xfailed | 43 passed, 3 xfailed | 17 |
