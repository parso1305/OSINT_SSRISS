# Live request ledger (Week 3 run, budget 80)

Counted per invocation: every robots.txt fetch made inside `Fetcher` + every document GET (+ redirect hops).

| # | When (UTC) | Step | Command | Requests | Cumulative |
|---|---|---|---|---|---|
| 1 | 2026-10-16T23:57 | 1A | `inspect_feed --url https://www.iitb.ac.in/rss.xml` | 2 (robots.txt + rss.xml 200) | 2 |
| 2 | 2026-10-16T23:57 | 1A | `inspect_sitemap --url https://www.iitb.ac.in/sitemap.xml` | 2 (robots.txt + sitemap.xml 404) | 4 |
