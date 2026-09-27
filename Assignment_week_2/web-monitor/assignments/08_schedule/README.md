# Assignment 8: scheduled runs

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Run every configured source on its own schedule through the common runner, without overlapping runs, without
duplicates, with every run recorded, and without a failed run corrupting data. Demo on fixtures first, then
optionally live.

## What I built / found

- [`src/scheduler.py`](../../src/scheduler.py): `--once` mode for Windows Task Scheduler (hourly trigger) and a
  loop mode for demos. It knows only source ids and config.
- A per-source lock file (atomic create) with stale-lock recovery; a held lock gives `RUN_SKIPPED`, recorded as a
  `skipped` run.
- A `runs` table (`running` → `success` / `failed` / `skipped`); each run's data is written in one transaction that
  rolls back on error.
- **Retry after failure**: a failed run is retried after 60 min, then 120, 240, … (capped at the 24 h interval).
  Every cycle logs why a source is or isn't due.
- The crawl frequency (daily) is derived from 30 real listing items ([notes §1](schedule_notes.md#1-crawl-frequency-for-iit-bombay-hss-seminars-every-24-h-interval_minutes-1440)).
- **Live demo** on 2026-09-27: two runs against the real HSS site, `new=20` then `new=0 existing=20 changed=0`
  ([`live_demo.log`](live_demo.log)).

## Key decisions and why

- **Task Scheduler + `--once`**, not a long-running loop: it survives sleep and reboots, and the scheduler decides
  what is due, so an hourly trigger catches up.
- **An empty listing counts as `failed`, not a new `suspect` status.** Adding a status would need a migration of
  the `runs` table's CHECK constraint. `failed` already gives exit code 1 and the retry backoff, and the error text
  (`EmptyListingError`) keeps it distinguishable.
- **Unreadable lock timestamp → judge by file age, never remove a live, fresh lock** (overlap is worse than one
  skipped run).

## Evidence

- [`schedule_notes.md`](schedule_notes.md), [`demo1_2_loop.log`](demo1_2_loop.log),
  [`demo3_overlap.log`](demo3_overlap.log), [`live_demo.log`](live_demo.log) (+ [`live_demo_config.json`](live_demo_config.json))
- [`tests/test_scheduler.py`](../../tests/test_scheduler.py) (locks, stale locks, rollback, intervals, retry/backoff)
- [`verification/fresh_clone_scheduler_local_fixture.txt`](../../verification/fresh_clone_scheduler_local_fixture.txt)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_scheduler.py
# in a second terminal: venv\Scripts\python scripts\fixture_site.py --port 8765
venv\Scripts\python -m src.scheduler --once --source local_fixture --db data\demo.db
```

## Status

**PASS**, including the optional live demo (8.3). Task Scheduler registration is documented in the
[README](../../README.md#scheduled-runs-on-windows-task-scheduler); there is no log of it firing on a schedule in this
repository.
