"""Scheduler: locking, stale-lock recovery, run records, rollback, repeat runs, schedule changes.

Real local HTTP (scripts/fixture_site.py) and real SQLite; no mocks.
"""

import hashlib
import io
import json
import logging
import os
import socket
import sqlite3
from contextlib import closing
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.fixture_site import FixtureSite
from src.config import DEFAULT_CONFIG_PATH
from src.logging_config import KeyValueFormatter
from src.scheduler import SourceLock, pid_alive, run_once, run_scheduled
from src.config import load_source_configs
from src.storage import count_records, list_runs, start_run, store_records

SOURCE = "local_fixture"
TS = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture
def log_stream():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield stream
    logger.removeHandler(handler)


def write_config(tmp_path: Path, site: FixtureSite, **overrides) -> Path:
    """The real local_fixture entry, pointed at this test's server."""
    entries = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))["sources"]
    entry = dict(next(e for e in entries if e["source_id"] == SOURCE),
                 listing_url=site.listing_url, request_delay_s=0, **overrides)
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [entry]}), encoding="utf-8")
    return path


def records_checksum(db: str) -> str:
    with closing(sqlite3.connect(db)) as conn, conn:
        rows = conn.execute("SELECT * FROM records ORDER BY item_url").fetchall()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def write_lock(lock_dir: Path, pid: int, started_at: datetime) -> Path:
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"{SOURCE}.lock"
    path.write_text(json.dumps({"pid": pid, "host": socket.gethostname(), "started_at": started_at.strftime(TS),
                                "source_id": SOURCE}), encoding="utf-8")
    return path


# -- pid check -------------------------------------------------------------------------

def test_pid_alive_is_safe_and_correct():
    assert pid_alive(os.getpid())   # would terminate this process if it used os.kill(pid, 0) on Windows
    assert not pid_alive(dead_pid())


# -- overlap ---------------------------------------------------------------------------

def test_held_lock_skips_run_and_records_it(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite() as site:
        config = load_source_configs(write_config(tmp_path, site))[SOURCE]
        holder = SourceLock(SOURCE, locks, 1800, logging.getLogger("web_monitor"))
        assert holder.acquire()
        try:
            result = run_scheduled(config, db, locks, logging.getLogger("web_monitor"))
        finally:
            holder.release()
        assert site.requests == []  # the runner never started
    assert result["status"] == "skipped"
    assert f"RUN_SKIPPED source={SOURCE} reason=already_running" in log_stream.getvalue()
    assert [(r["status"], r["error"]) for r in list_runs(db)] == [("skipped", "already_running")]
    assert not (locks / f"{SOURCE}.lock").exists()


def test_stale_lock_from_dead_process_is_recovered(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    pid = dead_pid()
    write_lock(locks, pid, datetime.now(timezone.utc))
    crashed_run = start_run(db, SOURCE)  # the dead process left a 'running' row
    with FixtureSite() as site:
        config = load_source_configs(write_config(tmp_path, site))[SOURCE]
        result = run_scheduled(config, db, locks, logging.getLogger("web_monitor"))
    assert result["status"] == "success"
    assert f"STALE_LOCK source={SOURCE}" in log_stream.getvalue() and f"process_dead(pid={pid})" in log_stream.getvalue()
    runs = {r["run_id"]: r for r in list_runs(db)}
    assert runs[crashed_run]["status"] == "failed" and runs[crashed_run]["error"].startswith("abandoned")
    assert not list(locks.iterdir())


def test_stale_lock_older_than_max_age_is_recovered(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    write_lock(locks, os.getpid(), datetime.now(timezone.utc) - timedelta(hours=3))  # live pid, too old
    with FixtureSite() as site:
        config = load_source_configs(write_config(tmp_path, site))[SOURCE]   # lock_max_age_minutes = 30
        result = run_scheduled(config, db, locks, logging.getLogger("web_monitor"))
    assert result["status"] == "success"
    assert "reason=max_age_exceeded" in log_stream.getvalue()


# -- duplicates / scheduling ---------------------------------------------------------------

def test_repeat_scheduled_runs_create_no_duplicates(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite() as site:
        config_path = write_config(tmp_path, site)
        first = run_once(config_path, db, locks, source_ids=[SOURCE], force=True)
        second = run_once(config_path, db, locks, source_ids=[SOURCE], force=True)
    assert first[0]["counts"]["new"] == 20
    assert second[0]["counts"] == {"new": 0, "existing": 20, "changed": 0}
    assert count_records(db) == 20
    assert [r["status"] for r in list_runs(db)] == ["success", "success"]
    assert log_stream.getvalue().count("RUN_START") == 2 and log_stream.getvalue().count("RUN_END") == 2


def test_not_due_until_interval_and_interval_change_is_picked_up(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite() as site:
        config_path = write_config(tmp_path, site, interval_minutes=60)
        assert len(run_once(config_path, db, locks, source_ids=[SOURCE])) == 1        # never run -> due
        with closing(sqlite3.connect(db)) as conn, conn:                                              # pretend it ran 10 min ago
            ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime(TS)
            conn.execute("UPDATE runs SET started_at = ?", (ten_min_ago,))
        assert run_once(config_path, db, locks, source_ids=[SOURCE]) == []             # 60 min interval: not due
        config_path = write_config(tmp_path, site, interval_minutes=5)                 # config-only change
        assert len(run_once(config_path, db, locks, source_ids=[SOURCE])) == 1        # 5 min interval: due
    log = log_stream.getvalue()
    assert "interval_minutes=60" in log and "due=false" in log and "interval_minutes=5 " in log


# -- atomicity -------------------------------------------------------------------------------

def test_store_records_rolls_back_the_whole_batch():
    import tempfile
    db = str(Path(tempfile.mkdtemp()) / "a.db")
    good = {"item_url": "https://x.org/a", "source_id": "s", "institution": "I", "content_type": "event",
            "title": "A", "starts_at": "2025-01-01T00:00:00Z", "detail_fetch_status": "not_attempted"}
    with pytest.raises(ValueError):
        store_records(db, [good, dict(good, item_url=None)])  # 2nd record fails after the 1st was written
    assert count_records(db) == 0


def test_failed_run_mid_storage_leaves_data_untouched_and_is_recorded(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite() as site:
        config_path = write_config(tmp_path, site)
        run_once(config_path, db, locks, source_ids=[SOURCE], force=True)
        before = records_checksum(db)
        with closing(sqlite3.connect(db)) as conn, conn:  # real SQLite failure partway through the batch
            conn.execute("CREATE TRIGGER fail_mid BEFORE UPDATE ON records WHEN NEW.item_url LIKE '%rortys-revolution' "
                         "BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END")
        result = run_once(config_path, db, locks, source_ids=[SOURCE], force=True)[0]
    assert result["status"] == "failed" and "injected storage failure" in result["error"]
    assert records_checksum(db) == before            # every earlier UPDATE of this run was rolled back
    assert [r["status"] for r in list_runs(db)] == ["success", "failed"]
    assert "status=failed" in log_stream.getvalue()


def test_failed_listing_fetch_is_recorded_and_changes_nothing(tmp_path):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite() as site:
        config_path = write_config(tmp_path, site)
        run_once(config_path, db, locks, source_ids=[SOURCE], force=True)
        before = records_checksum(db)
        site.drop_paths.add("/events/seminars-and-talks")   # connection dropped mid-response
        result = run_once(config_path, db, locks, source_ids=[SOURCE], force=True)[0]
    assert result["status"] == "failed" and "FetchError" in result["error"]
    assert records_checksum(db) == before


def test_daily_interval_does_not_drift_behind_hourly_trigger():
    """Last run started 06:00:05; the next day's 06:00:00 trigger must find it due (not 07:00)."""
    from src.scheduler import due_grace, next_due
    config = load_source_configs()["iit_bombay_hss_seminars"]          # interval_minutes = 1440
    last = datetime(2026, 9, 26, 6, 0, 5, tzinfo=timezone.utc)
    trigger = datetime(2026, 9, 27, 6, 0, 0, tzinfo=timezone.utc)
    due_at = next_due(config, last.strftime(TS))
    assert trigger < due_at and trigger >= due_at - due_grace(config)
    assert due_grace(load_source_configs()["local_fixture"]).total_seconds() <= 0.1 * 60 * 3


# -- retry after failure (audit X1) ------------------------------------------------------------------------

def shift_runs(db: str, minutes_ago: float) -> None:
    """Pretend every recorded run started minutes_ago (keeping their order)."""
    with closing(sqlite3.connect(db)) as conn, conn:
        rows = conn.execute("SELECT run_id FROM runs ORDER BY started_at, rowid").fetchall()
        for i, (run_id,) in enumerate(rows):
            started = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago + (len(rows) - 1 - i))
            conn.execute("UPDATE runs SET started_at = ? WHERE run_id = ?", (started.strftime(TS), run_id))


def schedule_line(log: str) -> str:
    return [line for line in log.splitlines() if "SCHEDULE" in line][-1]


def test_wait_after_failures_backs_off_and_is_capped_at_the_interval():
    from src.scheduler import wait_minutes
    config = load_source_configs()["iit_bombay_hss_seminars"]        # interval 1440, retry_minutes default 60
    assert config.retry_minutes == 60
    assert [wait_minutes(config, n) for n in range(0, 8)] == [1440, 60, 120, 240, 480, 960, 1440, 1440]


def test_failed_run_is_retried_after_retry_minutes_then_success_uses_the_interval(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite(fail_paths=["/events/seminars-and-talks"]) as site:
        config_path = write_config(tmp_path, site, interval_minutes=1440)
        assert run_once(config_path, db, locks, source_ids=[SOURCE])[0]["status"] == "failed"   # never run -> due

        shift_runs(db, 50)                                                       # 50 min after the failure
        assert run_once(config_path, db, locks, source_ids=[SOURCE]) == []
        line = schedule_line(log_stream.getvalue())
        assert "last_status=failed consecutive_failures=1 wait_minutes=60 " in line
        assert "next_due_reason=retry_after_failure due=false" in line

        site.fail_paths.clear()                                                  # site recovers
        shift_runs(db, 60)                                                       # next hourly trigger
        assert run_once(config_path, db, locks, source_ids=[SOURCE])[0]["status"] == "success"
        assert "next_due_reason=retry_after_failure due=true" in schedule_line(log_stream.getvalue())

        shift_runs(db, 60)                                                       # an hour after the success
        assert run_once(config_path, db, locks, source_ids=[SOURCE]) == []
        line = schedule_line(log_stream.getvalue())
    assert "last_status=success consecutive_failures=0 wait_minutes=1440 " in line
    assert "next_due_reason=interval_after_success due=false" in line
    assert [r["status"] for r in list_runs(db)] == ["failed", "success"]


def test_repeated_failures_back_off(tmp_path, log_stream):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite(fail_paths=["/events/seminars-and-talks"]) as site:
        config_path = write_config(tmp_path, site, interval_minutes=1440)
        for _ in range(3):                                                       # 3 consecutive failures
            run_once(config_path, db, locks, source_ids=[SOURCE], force=True)
        shift_runs(db, 200)                                                      # 3rd failure: wait 240 min
        assert run_once(config_path, db, locks, source_ids=[SOURCE]) == []
        assert "consecutive_failures=3 wait_minutes=240 " in schedule_line(log_stream.getvalue())
        shift_runs(db, 240)
        assert len(run_once(config_path, db, locks, source_ids=[SOURCE])) == 1
    assert "next_due_reason=retry_after_failure due=true" in schedule_line(log_stream.getvalue())
    assert [r["status"] for r in list_runs(db)] == ["failed"] * 4


def test_retry_still_respects_the_overlap_lock(tmp_path, log_stream):
    from src.storage import run_history
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    with FixtureSite(fail_paths=["/events/seminars-and-talks"]) as site:
        config_path = write_config(tmp_path, site, interval_minutes=1440)
        run_once(config_path, db, locks, source_ids=[SOURCE])                   # fails
        shift_runs(db, 61)                                                       # retry is due ...
        holder = SourceLock(SOURCE, locks, 1800, logging.getLogger("web_monitor"))
        assert holder.acquire()                                                  # ... but another run holds the lock
        try:
            result = run_once(config_path, db, locks, source_ids=[SOURCE])
        finally:
            holder.release()
        requests_during_lock = len(site.requests)
    assert [r["status"] for r in result] == ["skipped"]
    assert f"RUN_SKIPPED source={SOURCE} reason=already_running" in log_stream.getvalue()
    assert requests_during_lock == 2                                             # only the first run's robots + listing
    assert run_history(db, SOURCE)["consecutive_failures"] == 1                  # a skip does not reset the backoff


# -- malformed lock timestamp (audit m1 / case 17) -----------------------------------------------------------

@pytest.mark.parametrize("pid_state, lock_age_h, expected", [
    ("dead", 0, "success"),     # dead holder: stale by process check
    ("live", 3, "success"),     # live pid but the file is older than lock_max_age: stale by file age
    ("live", 0, "skipped"),     # live pid, fresh file: cannot prove it is stale -> skip, never overlap
])
def test_lock_with_unreadable_started_at_never_crashes_the_cycle(tmp_path, log_stream, pid_state, lock_age_h, expected):
    db, locks = str(tmp_path / "s.db"), tmp_path / "locks"
    locks.mkdir()
    lock = locks / f"{SOURCE}.lock"
    lock.write_text(json.dumps({"pid": dead_pid() if pid_state == "dead" else os.getpid(), "host": socket.gethostname(),
                                "started_at": "2026-09-26 06:00", "source_id": SOURCE}), encoding="utf-8")
    old = datetime.now().timestamp() - lock_age_h * 3600
    os.utime(lock, (old, old))
    with FixtureSite() as site:
        result = run_once(write_config(tmp_path, site), db, locks, source_ids=[SOURCE], force=True)   # must not raise
    assert [r["status"] for r in result] == [expected]
    log = log_stream.getvalue()
    assert "LOCK_WARNING" in log and "started_at='2026-09-26 06:00' unreadable" in log
    assert ("STALE_LOCK" in log) == (expected == "success")
