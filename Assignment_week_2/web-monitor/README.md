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

Run history: `runs` table in the scheduler's database (`--db`, default `data/events.db`); per-source locks:
`locks/<source_id>.lock`. Note: the `data/events.db` in this working copy predates the scheduler and holds only the
legacy Section 1-5 tables; the scheduler creates `records` and `runs` there on its first run.
Change a schedule by editing `interval_minutes` in `config/sources.json`. It's re-read every cycle,
so no restart and no code change is needed.

## TLS certificates (`ca_bundle`)

Certificate verification is always on. The fetcher never retries with `verify=False`: a TLS failure is logged as
`FETCH_ERROR … error_type=SSLError` and fails the run.

`www.hss.iitb.ac.in` sends only its leaf certificate (`CN=iitb.ac.in`) and omits the intermediate
*GlobalSign RSA OV SSL CA 2018* (diagnosed 2026-09-26 with `openssl s_client -showcerts`: one certificate in the
chain, `verify error:num=21: unable to verify the first certificate`). Browsers and Windows schannel fetch the
missing intermediate from the leaf's AIA URL. OpenSSL, and therefore Python/requests, does not, so every request
fails with `CERTIFICATE_VERIFY_FAILED`.

The fix is the server's to make. Until then, the source's config entry sets
`"ca_bundle": "certs/iitb_ca_bundle.pem"`, which the fetcher passes to requests as `verify=<path>`. That file is
certifi's CA bundle plus `certs/globalsign_rsa_ov_ssl_ca_2018.pem` (fetched from the leaf's AIA URL; SHA-256 and
provenance in the file header; it chains to *GlobalSign Root CA - R3*, which certifi already trusts).
It adds only the one missing intermediate and trusts nothing beyond that.

* Rebuild after upgrading certifi: `python scripts/build_ca_bundle.py`.
* The intermediate expires 2028-11-21. Re-check the chain before then, or when HSS renews its certificate.
* Any source can use `ca_bundle` (a path relative to the project root; the config is rejected if the file is missing).
