# Assignment Week 2: Academic Scraper Templates & Reliability

## Scheduled runs on Windows (Assignment 8)

The scheduler (`src/scheduler.py`) runs every enabled source in `config/sources.json` on its own
`interval_minutes`. Two modes:

| Command | Use |
|---|---|
| `python -m src.scheduler --once` | Run every **due** source once, then exit. **Recommended:** trigger it from Windows Task Scheduler. |
| `python -m src.scheduler` | Loop: check every 60 s (`--tick-s`). Dies when the machine sleeps or the console closes. For demos. |

Useful flags: `--source <id>` (limit to one source, even a disabled one), `--force` (ignore the
interval), `--db <path>`, `--locks-dir <dir>`. Exit code 1 means at least one run failed.

### Register `--once` in Task Scheduler

`scripts\run_scheduler_once.bat` changes into the project directory, runs
`python -m src.scheduler --once` and appends output to `logs\scheduler.log`. Register it to fire
**hourly**. The scheduler itself decides which sources are due (IIT Bombay: every 1440 min), so an
hourly trigger catches up within an hour after the PC was off or asleep.

```bat
schtasks /Create /TN "WebMonitor\ScheduledRun" /SC HOURLY /MO 1 /F ^
  /TR "\"C:\Project\OSINT_SSRISS\Assignment_week_2\web-monitor\scripts\run_scheduler_once.bat\""
schtasks /Run   /TN "WebMonitor\ScheduledRun"           & rem run now to test
schtasks /Query /TN "WebMonitor\ScheduledRun" /V /FO LIST
```

Then, in Task Scheduler → the task → Properties (settings `schtasks /Create` cannot set):

* **Settings → If the task is already running: "Do not start a new instance"**. This is a second guard next to
  the per-source lock file.
* **Settings → "Run task as soon as possible after a scheduled start is missed"**.
* **Settings → "Stop the task if it runs longer than" 1 hour**. That's longer than a normal run, and
  shorter than `lock_max_age_minutes`.
* **Conditions → optionally "Wake the computer to run this task"**.
* If `python` isn't on the task account's PATH, set a user environment variable
  `WEB_MONITOR_PYTHON` to the full path of `python.exe`.

Run history: `runs` table in `data/events.db`; per-source locks: `locks/<source_id>.lock`.
Change a schedule by editing `interval_minutes` in `config/sources.json`. It's re-read every cycle,
so no restart and no code change is needed.
