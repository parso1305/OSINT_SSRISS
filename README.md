# OSINT SSRISS: academic web monitoring (Naaravance.ai internship)

This repository contains my work for the Naaravance.ai OSINT web-monitoring internship. The target is IIT Bombay's
public academic pages, starting with the Humanities and Social Sciences (HSS) department's "Seminars and Talks"
listing. Week 1 covers the basics: HTTP inspection, site recon, DOM mapping, fetching and normalization. Week 2
builds a monitoring system. On a schedule, it fetches the listing politely (robots.txt, delays, timeouts, verified
TLS), follows pagination and detail pages, and normalizes each event into a shared schema. It then validates and
stores the events in SQLite, and flags which ones are new, unchanged or changed. Each site plugs in through a small
adapter and a config entry. Every result below links to the test, log or file that proves it.

## Start here

| Time | Read |
|---|---|
| 5 min | this page → [Week 2 results](Assignment_week_2/web-monitor/RESULTS.md) (benchmark, test numbers, known limitations) |
| 20 min | [Week 2 README](Assignment_week_2/web-monitor/README.md) (architecture, how to run, how to add a source) → [audit fixes](Assignment_week_2/web-monitor/assignments/week2_audit/FIXES.md) (each problem → commit → test) |
| Deep dive | the [audit report](Assignment_week_2/web-monitor/assignments/week2_audit/AUDIT_REPORT.md), then the per-assignment READMEs listed in the [Week 2 README](Assignment_week_2/web-monitor/README.md#assignment-documents) |

## Weeks

| Week | Folder | What it contains | Status |
|---|---|---|---|
| 1 | [`Assignment/`](Assignment) | Exercises: HTTP inspection, IIT Bombay recon, DOM selector map, fetch + parse, normalization + SQLite dedup | Done as exercises; KNOWN LIMITATION: see its README |
| 2 | [`Assignment_week_2/web-monitor/`](Assignment_week_2/web-monitor) | The monitoring system: assignments 1 and 3–8, the audit and its fixes | 56 of 58 benchmark items PASS; 1 DEFERRED, 1 NOT STARTED |
| — | Assignment 9 | Template swap with a teammate's framework; scheduled next. | NOT STARTED |

## Headline results (Week 2)

| Result | Evidence |
|---|---|
| **133 tests pass, 1 skipped** (the live test, opt-in); **92 % line coverage**; 0 warnings. Run from a fresh clone, fresh venv, pinned requirements | [`fresh_clone_pytest.txt`](Assignment_week_2/web-monitor/verification/fresh_clone_pytest.txt) |
| **Benchmark: 56 PASS · 1 DEFERRED · 1 NOT STARTED** of 58 items (team schema alignment is DEFERRED; Assignment 9 is NOT STARTED) | [`RESULTS.md`](Assignment_week_2/web-monitor/RESULTS.md) |
| **Live run against the real HSS site**: run 1 stored 20 events, run 2 found `new=0 existing=20 changed=0` (no duplicates, no false changes); TLS verified | [`live_demo.log`](Assignment_week_2/web-monitor/assignments/08_schedule/live_demo.log) |
| **Generalization**: a second IIT Bombay department (Mechanical Engineering, 20 events) and a structurally different site (Chennai Mathematical Institute: 134 stored, 1 correctly rejected) ran through the same pipeline with only an adapter + config | [`generalization_run.log`](Assignment_week_2/web-monitor/assignments/week2_audit/logs/after_fixes/generalization_run.log), [`schema_review.md` §(h)](Assignment_week_2/web-monitor/assignments/06_schema/schema_review.md) |
| **Audit → fixes**: an independent audit found 1 critical and 6 major problems (uncommitted code, TLS silently disabled, empty listing recorded as success, unparseable dates erasing data, no retry after a failure, no `requirements.txt`, cross-source key). 6 are fixed, one commit each with a regression test; the cross-source key (M5) and two minor items are documented as known limitations | [`AUDIT_REPORT.md`](Assignment_week_2/web-monitor/assignments/week2_audit/AUDIT_REPORT.md), [`FIXES.md`](Assignment_week_2/web-monitor/assignments/week2_audit/FIXES.md) |

## Repository layout

```text
OSINT_SSRISS/
├── README.md                        this page
├── Assignment/                      Week 1 exercises (01_http … 05_normalization)
└── Assignment_week_2/web-monitor/   Week 2 system
    ├── README.md  RESULTS.md        how it works / what it achieved
    ├── src/                         generic pipeline: fetcher, pagination, enrichment, schema, storage, runner, scheduler
    ├── sources/                     site adapters (IIT Bombay HSS)
    ├── config/sources.json          one entry per monitored source
    ├── tests/                       main test suite (local HTTP server over saved real HTML; no mocks)
    ├── fixtures/                    saved real HTML with provenance; test-only TLS certificates
    ├── assignments/                 one folder per assignment: README, notes, logs; week2_audit/
    ├── verification/                raw fresh-clone outputs quoted in RESULTS.md
    ├── scripts/                     fixture server, Task Scheduler entry point, generators, link checker
    └── certs/                       CA bundle for the HSS server's incomplete certificate chain
```

## Quickstart (no network needed)

```powershell
git clone <this-repo> OSINT_SSRISS          # keep the path short on Windows (long fixture names)
cd OSINT_SSRISS\Assignment_week_2\web-monitor
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m pytest                                    # main suite, no network

# a scheduled run on saved HTML: start the local fixture site, then run the scheduler once
Start-Process venv\Scripts\python -ArgumentList "scripts\fixture_site.py", "--port", "8765"
venv\Scripts\python -m src.scheduler --once --source local_fixture --db data\demo.db
```

The expected output of both commands is in [`verification/`](Assignment_week_2/web-monitor/verification). More options
(live runs, Windows Task Scheduler, adding a source): [Week 2 README](Assignment_week_2/web-monitor/README.md).

## Rules this project follows

| Rule | How | Evidence |
|---|---|---|
| Public pages only | No logins, forms or authenticated areas; only published listing and event pages | [`config/sources.json`](Assignment_week_2/web-monitor/config/sources.json) |
| robots.txt is obeyed | Checked per host before any page (RFC 9309; unreachable robots.txt = disallow all); `Crawl-delay` honoured | [`src/fetcher.py`](Assignment_week_2/web-monitor/src/fetcher.py), `tests/test_runner.py::test_robots_disallow_is_respected` |
| Opt-outs are respected in spirit | A site whose robots.txt blocks AI crawlers (talks.cam.ac.uk) is not used, even though our User-Agent isn't named | [adapter notes §6](Assignment_week_2/web-monitor/assignments/07_template/iit_bombay_adapter_notes.md#talkscamacuk-not-used-because-its-robotstxt-opts-out-of-ai-crawlers) |
| Timeouts and delays | 10 s timeout per request; ≥ 1.5 s between requests to one host (live HSS config); small page and detail limits | [`config/sources.json`](Assignment_week_2/web-monitor/config/sources.json) |
| No evasion | A descriptive User-Agent with contact details; no proxies, no User-Agent rotation, no CAPTCHA or login bypass. (Week 1's fetch exercise used a browser User-Agent string; Week 2 does not.) | [`src/fetcher.py`](Assignment_week_2/web-monitor/src/fetcher.py) |
| TLS is always verified | No `verify=False`, enforced by a test; the HSS server's missing intermediate certificate is added through a documented CA bundle | [README, TLS](Assignment_week_2/web-monitor/README.md#tls-certificates-ca_bundle), [`tests/test_tls.py`](Assignment_week_2/web-monitor/tests/test_tls.py) |
