# Live request ledger (Week 3 run, budget 80)

Counted per invocation: every robots.txt fetch made inside `Fetcher` + every document GET (+ redirect hops).

| # | When (UTC) | Step | Command | Requests | Cumulative |
|---|---|---|---|---|---|
| 1 | 2026-10-16T23:57 | 1A | `inspect_feed --url https://www.iitb.ac.in/rss.xml` | 2 (robots.txt + rss.xml 200) | 2 |
| 2 | 2026-10-16T23:57 | 1A | `inspect_sitemap --url https://www.iitb.ac.in/sitemap.xml` | 2 (robots.txt + sitemap.xml 404) | 4 |
| 3 | 2026-10-17T00:28 | 5 (entity sample) | `python -m assignments.week3.05_extraction.fetch_sample` (12 lecture/colloquium/seminar detail pages; the saved evidence had 8 < 10) | 13 (robots.txt + 12 × 200) | 17 |
| 4 | 2026-10-17T01:17 | 10 (live run 1) | `python -m src.scheduler --once --source iit_bombay_events --force --db data/week3_live.db` | 22 (robots.txt + homepage + 20 details, all 200) | 39 |
| 5 | 2026-10-17T01:18 | 10 (live run 2) | same, back to back | 22 (robots.txt + homepage + 20 details, all 200) | 61 |

**Total: 61 of 80** (1A: 4 · entity sample: 13 · Section 10 live runs: 44). No 403, 429 or robots.txt refusal.
Section 0 recon (28, a separate earlier budget of 30) is not included.

## Repair pass (2026-10-20, budget 60)

| # | When (UTC) | Step | Command | Requests | Cumulative (repair pass) |
|---|---|---|---|---|---|
| R1-1 | 2026-10-20T13:27 | R1 live run 1 (calendar discovery) | `python -m src.scheduler --once --source iit_bombay_events --force --db data/week3_live.db` | 22 (robots.txt + /events + 20 details, all 200) | 22 |
| R1-2 | 2026-10-20T13:28 | R1 live run 2 | same, back to back | 22 | 44 |

**Repair pass total: 44 of 60.** No 403, 429 or robots.txt refusal.
