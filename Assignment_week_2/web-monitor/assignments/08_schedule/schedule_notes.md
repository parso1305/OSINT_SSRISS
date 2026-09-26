# Scheduled Local Run (Assignment 8)

Scheduler: `src/scheduler.py` (generic; source_ids + config only). Config: `config/sources.json`.
Assignment 7 chose JSON over YAML: no requirements file declares PyYAML. Runs, locks and data live in
`data/*.db` and `locks/`. All demos ran against `local_fixture`: the saved IIT Bombay HSS HTML
served by `scripts/fixture_site.py` on `127.0.0.1:8765`, parsed by the unchanged `sources.iit_bombay`
adapter. The HSS server was unreachable (`curl … HTTP 000 in 15.0s`, exit 28, 2026-09-26), so the
live demo is **deferred**.

## 1. Crawl frequency for IIT Bombay HSS seminars: every 24 h (`interval_minutes: 1440`)

### Data used

*From the 30 real listing items* (`fixtures/iit_bombay_hss/live_page_{1,2,3}.html`, fetched live
2026-09-25; pages 1–3 of the listing, newest first):

| Measure | Value |
|---|---|
| Date range | 2025-01-02 → 2025-09-25 (266 days) |
| Events per month | Jan 10, Feb 3, Mar 7, Apr 2, **May 0, Jun 0**, Jul 2, Aug 4, Sep 2 → mean **3.3/month** |
| Gap between consecutive events (days) | median **4**, min **0**, mean 9.2, max **91** (Apr→Jul break) |
| Sorted gaps | 0, 1×6, 2×5, 3×2, 4×2, 5×2, 6×2, 8, 10×2, 12, 16, 19, 22, 26, 91 |
| Weekday | Wed 12, Fri 6, Thu 5, Mon 4, Tue 2, Sat 1 |
| Newest event vs listing fetch | 2025-09-25 vs 2026-09-25: **365 days**. **0 upcoming events** listed |
| Archive size | pager links to `?page=32` (`live_page_1.html`), about 330 items |

*Lead time* (how far ahead a seminar is posted) **cannot be measured** from this data. No upcoming
seminar was visible, and neither listing nor detail pages carry a created/published date (a grep for
`published|modified|created|date` meta tags in the 10 detail pages found none).

*From the recon notes:*

* `Assignment/02_recon/IITB_recon.md` lines 9–24: `www.iitb.ac.in/robots.txt` has Disallow rules only
  (`/core/`, `/profiles/`, `/admin/`, `/search/`, `/user/*`) and **no Crawl-delay**.
* The same file, lines 128–130: the events endpoint was "somewhat difficult to retrieve reliably".
  Consistent with that, the HSS host timed out on 2026-09-26 during Phase 1 and again for all of
  Assignments 7–8.
* The HSS subdomain's own robots.txt was never captured, and couldn't be fetched now. The Fetcher
  honours any Crawl-delay it finds at run time.
* `assignments/03_patterns/iit_bombay_structure.md:12` reports a future-dated item (`11th Nov 2026`)
  on the parent `/events` page. **Treat this as unverified**: the same row names selectors
  (`.views-row`, `.views-field-title`) that don't match the saved live seminars HTML
  (`.event-card-wrapper`, `.event-name a`).

### Decision and reasoning

* **Not hourly or more often:** at most ~10 seminars in the busiest month, and dates are day-precision.
  Hourly polling would be ~24× the requests for no gain. Given the host's reliability (above), most
  runs would just record failures.
* **Not weekly:** when the series is active, half the gaps between seminars are ≤ 4 days and 7 of 29
  are ≤ 1 day. Lead time is unknown and could be short. A weekly crawl could discover a seminar
  after it has already happened.
* **Daily:** a new posting is seen within 24 h, well inside the typical 4-day spacing. Load is about
  1 robots.txt + 2 listing + ≤ 10 detail requests per day, 1.5 s apart.
* **Dormant right now:** the series has been quiet for 12 months (newest event 365 days old). If it
  stays that way, daily costs ~13 requests/day, and detection latency stays at 1 day for when it resumes.
* **Trigger:** the scheduler is fired hourly by Task Scheduler (`--once`). The source runs when 24 h have
  passed, so a missed day (PC off) is caught up within an hour of the next boot. A grace of
  `min(120 s, 10 %)` keeps it from drifting an hour later every day.
  (`test_daily_interval_does_not_drift_behind_hourly_trigger`)

## 2. Design choices

**Lock: an atomic lock file, `locks/<source_id>.lock`**, created with `os.open(O_CREAT | O_EXCL | O_WRONLY)`
and holding `{pid, host, started_at, source_id}`. I chose it over a lock row in SQLite because:

* it lives outside the database, so it can't be caught up in (or rolled back with) the run's data
  transaction, and it still works if the DB file is locked or damaged;
* it's visible to an operator (`type locks\*.lock`), and it records the PID, which is what stale detection needs;
* `O_EXCL` creation is atomic on NTFS, with no `fcntl` needed.

**Stale lock handling:** a lock is stale if its holder PID isn't running on this host, or if it's older
than `lock_max_age_minutes` (60 for IIT Bombay; 30 for local_fixture). When that happens:

* a WARNING `STALE_LOCK … reason=process_dead(pid=…)|max_age_exceeded(…) action=removed` is logged;
* the lock is moved aside with `os.replace`, then re-acquired;
* the dead run's `running` rows are marked `failed` ("abandoned: stale lock …").

On Windows, process liveness is checked with `OpenProcess` + `GetExitCodeProcess` (`STILL_ACTIVE`).
**`os.kill(pid, 0)` terminates the process on Windows**, so it's avoided.

**Skip:** if the lock is held, the run logs `RUN_SKIPPED source=<id> reason=already_running holder=pid:…`, a
`skipped` row is written to `runs`, and nothing else happens.

**Runs table** (`storage.py`): `run_id, source_id, started_at, finished_at, status, new_count,
existing_count, changed_count, failed_count, error`.
* Status is `running` while in progress (transient), then `success` / `failed`; skipped runs are `skipped`.
* `failed_count` = detail-fetch failures + records rejected by validation.
* Run rows are written on their own connection, outside the data transaction, so a rolled-back run is
  still recorded as failed.
* Log lines: `RUN_START run_id=… source=…` and `RUN_END run_id=… status=… new/existing/changed/failed error=…`.

**Transaction:** a run's data writes all happen in `store_records`, which uses one connection:
`BEGIN IMMEDIATE`, then every upsert, then `COMMIT`. Any exception triggers `ROLLBACK` and re-raises.
Fetching, parsing and validation all finish before the transaction opens, so it's short.

**Due logic:** a source is due if it has never run, or if `interval_minutes` (minus the grace) has passed
since the last non-skipped run. Config is re-read every cycle.

## 3. Demo outputs (local_fixture, `data/local_fixture_demo.db`)

### 3.1 Scheduled runs: loop mode, 5 cycles, 20 s tick, interval 1 min (`demo1_2_loop.log`)
```
12:28:06 SCHEDULE source=local_fixture interval_minutes=1 last_started_at=never next_due_at=now due=true
12:28:06 RUN_START run_id=de22faeb… source=local_fixture
12:28:07 STORE new=20 existing=0 changed=0
12:28:07 RUN_END run_id=de22faeb… status=success duration_ms=1087 new=20 existing=0 changed=0 failed=0
12:28:27 SCHEDULE … next_due_at=2026-09-26T06:59:06Z due=false
12:28:47 SCHEDULE … next_due_at=2026-09-26T06:59:06Z due=false
12:29:07 SCHEDULE … next_due_at=2026-09-26T06:59:06Z due=true
12:29:07 RUN_START run_id=f21ae224… source=local_fixture
12:29:08 STORE new=0 existing=20 changed=0
12:29:08 RUN_END run_id=f21ae224… status=success duration_ms=1119 new=0 existing=20 changed=0 failed=0
12:29:28 SCHEDULE … next_due_at=2026-09-26T07:00:07Z due=false
```

### 3.2 No uncontrolled duplicates
`records` has 20 rows after run 1 and still 20 after run 2 (`new=0 existing=20`). Both runs rows are `success`.

### 3.3 Overlap: two processes, server slowed to 1 s per request (`demo3_overlap.log`)
```
--- lock file while A runs:
{"pid": 1812, "host": "HP", "started_at": "2026-09-26T06:59:44Z", "source_id": "local_fixture"}
A 12:29:44 RUN_START run_id=5c6eec9a… source=local_fixture
B 12:29:46 RUN_SKIPPED source=local_fixture reason=already_running holder=pid:1812@2026-09-26T06:59:44Z
A 12:29:51 RUN_END run_id=5c6eec9a… status=success duration_ms=6522 new=0 existing=20 changed=0
runs: 5c6eec9a… 06:59:44→06:59:51 success | befa32a5… 06:59:46→06:59:46 skipped error=already_running
```
Both processes used `--force`. Without it, B wouldn't even try: A's `running` row already counts as the
latest run. The lock is what protects forced runs, and the window where two cycles both evaluate "due"
before either has inserted its row.

### 3.4 A failed run doesn't corrupt data
The checksum is sha256 over every column of every `records` row, ordered, including `last_seen_at`.
```
(a) listing connection dropped mid-response (fixture_site --drop)
BEFORE: records=20 sha256=58d05819354f81d7 last_seen_at=[06:59:51Z .. 06:59:51Z]
FETCH_ERROR … ChunkedEncodingError: Connection broken: IncompleteRead(23000 bytes read, 23000 more expected)
RUN_END run_id=3efe7c0f… status=failed error="FetchError: ChunkedEncodingError …"
AFTER:  records=20 sha256=58d05819354f81d7 last_seen_at=[06:59:51Z .. 06:59:51Z]

(b) real SQLite abort partway through the storage transaction (demo trigger on record 9 of 20,
    i.e. after 8 UPDATEs of this run had already executed)
BEFORE: records=20 sha256=58d05819354f81d7 last_seen_at=[06:59:51Z .. 06:59:51Z]
FAILURE source_id=local_fixture … stage=store error_type=IntegrityError message="injected storage failure (demo trigger)"
RUN_END run_id=5819c07b… status=failed error="IntegrityError: injected storage failure (demo trigger)"
AFTER:  records=20 sha256=58d05819354f81d7 last_seen_at=[06:59:51Z .. 06:59:51Z]
(trigger dropped) next run: RUN_END status=success new=0 existing=20 changed=0; checksum 35b72771…
(only last_seen_at moved, to 07:00:36Z)
```
In (b), the 8 earlier UPDATEs had rewritten `last_seen_at`. The identical checksum proves they were
rolled back together.

### 3.5 Schedule change without touching the parser
```
cycle, interval_minutes=1:  SCHEDULE … interval_minutes=1 last_started_at=07:00:35Z next_due_at=07:01:35Z due=false
edit config/sources.json:   local_fixture "interval_minutes": 1 -> 3
cycle, same command:        SCHEDULE … interval_minutes=3 last_started_at=07:00:35Z next_due_at=07:03:35Z due=false
files whose sha256 changed under src/ sources/ config/ scripts/:  config/sources.json   (only)
git diff --no-index --stat:  config/sources.json | 2 +-   1 file changed, 1 insertion(+), 1 deletion(-)
```
Plain `git diff --stat` isn't meaningful here. `config/` is untracked, so git doesn't list it, and
the tracked files still carry uncommitted Assignment 7 changes. Hence the hash manifest.

## 4. Known limits

* **Loop mode dies with the machine.** Sleep, hibernate, logoff or closing the console stops it,
  and nothing restarts it. **Recommended mode: Task Scheduler + `--once`**, hourly (README).
* **Missed runs are caught up, not replayed.** After a week offline the source runs once, not 7 times.
  That's fine for a listing crawl that sees the latest 20 items. Anything that fell off page 2 while
  offline is missed; raise `max_pages` for a catch-up.
* **Lock race (small):** if two processes find the *same* stale lock at the same instant, the
  `os.replace` step can in rare interleavings remove the other's fresh lock. Task Scheduler's
  "do not start a new instance" setting avoids concurrent schedulers. PID reuse is covered by the
  max-age check.
* **A lock left by a killed process blocks that source** until the PID check (immediately) or max age
  (60 min) clears it. The PID check only applies on the same host (`host` field).
* **One SQLite file.** Concurrent runs of *different* sources serialize on `BEGIN IMMEDIATE`, which is
  brief because the transaction only covers storage.
* **The HSS robots.txt is unverified.** The live demo is deferred until the server answers.
* `locks/`, `logs/` and `data/` are runtime directories. There's no `.gitignore` in the repo yet, so
  they currently show as untracked.
