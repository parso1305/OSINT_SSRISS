"""Generic scheduler: runs each configured source through runner.run_source on its own interval.

Knows only source_ids and config (config/sources.json): no adapters, selectors or URLs.

  python -m src.scheduler --once   run every due source once and exit (Windows Task Scheduler mode)
  python -m src.scheduler          loop: check every --tick-s seconds, run what is due

Per source:
  * due        = never run, or interval_minutes elapsed since the last non-skipped run (runs table),
                 minus a small grace (min(120 s, 10%)) so an hourly trigger does not drift;
                 config is re-read every cycle, so an interval change applies without a restart
  * overlap    = atomic lock file locks/<source_id>.lock (os.open O_CREAT|O_EXCL) holding pid + start
                 time; a held lock -> RUN_SKIPPED, recorded as a 'skipped' run
  * stale lock = holder process gone, or lock older than lock_max_age_minutes -> WARNING, removed,
                 its 'running' run rows marked failed
  * run record = runs row (running -> success / failed), RUN_START / RUN_END log lines
  * atomicity  = storage.store_records writes a run's data in one transaction (rollback on error)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.config import SourceConfig, load_source_configs, DEFAULT_CONFIG_PATH
from src.logging_config import (
    setup_logger, log_schedule, log_run_start, log_run_end, log_run_skipped, log_stale_lock,
)
from src.runner import run_source, DEFAULT_DB_PATH
from src.storage import start_run, finish_run, abandon_running_runs, last_run_started_at

DEFAULT_LOCK_DIR = PROJECT_ROOT / "locks"
DEFAULT_TICK_S = 60.0
_TS = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pid_alive(pid: int) -> bool:
    """True if a process with this pid exists. Never signals the process."""
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) would TerminateProcess on Windows; query the process instead.
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: exists, not ours
        try:
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok) and exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SourceLock:
    """Atomic per-source lock file. acquire() -> True if this process now holds it."""

    def __init__(self, source_id: str, lock_dir: Path, max_age_s: float, logger: logging.Logger):
        self.source_id = source_id
        self.path = Path(lock_dir) / f"{source_id}.lock"
        self.max_age_s = max_age_s
        self.logger = logger
        self.holder = ""
        self.recovered_stale = False

    def _read(self) -> Optional[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            return {}  # exists but unreadable (e.g. being written)

    def _stale_reason(self, info: dict) -> Optional[str]:
        started = info.get("started_at")
        if started:
            age_s = (_now() - datetime.strptime(started, _TS).replace(tzinfo=timezone.utc)).total_seconds()
        else:
            age_s = time.time() - self.path.stat().st_mtime
        if age_s > self.max_age_s:
            return f"max_age_exceeded(age_s={int(age_s)},max_s={int(self.max_age_s)})"
        pid = info.get("pid")
        if isinstance(pid, int) and info.get("host") == socket.gethostname() and not pid_alive(pid):
            return f"process_dead(pid={pid})"
        return None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = self._read()
                if info is None:
                    continue  # vanished between open and read: retry
                self.holder = f"pid:{info.get('pid')}@{info.get('started_at')}"
                reason = self._stale_reason(info)
                if not reason:
                    return False
                log_stale_lock(self.logger, self.source_id, self.holder, reason)
                try:
                    os.replace(self.path, self.path.with_name(f"{self.path.name}.stale-{uuid.uuid4().hex[:8]}"))
                except FileNotFoundError:
                    pass  # another process removed it first
                self.recovered_stale = True
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "host": socket.gethostname(),
                           "started_at": _now().strftime(_TS), "source_id": self.source_id}, handle)
            return True
        return False

    def release(self) -> None:
        info = self._read()
        if info and info.get("pid") == os.getpid():
            self.path.unlink(missing_ok=True)
        for stale in self.path.parent.glob(f"{self.path.name}.stale-*"):
            stale.unlink(missing_ok=True)


def due_grace(config: SourceConfig) -> timedelta:
    """Slack so a run started a few seconds after an hourly trigger is due at the next day's same trigger
    instead of drifting one tick later every day: min(120 s, 10% of the interval)."""
    if config.interval_minutes is None:
        return timedelta(0)
    return timedelta(seconds=min(120.0, config.interval_minutes * 60 * 0.10))


def next_due(config: SourceConfig, last_started_at: Optional[str]) -> Optional[datetime]:
    """None = due now (never run). Otherwise last start + interval."""
    if not last_started_at or config.interval_minutes is None:
        return None
    last = datetime.strptime(last_started_at, _TS).replace(tzinfo=timezone.utc)
    return last + timedelta(minutes=config.interval_minutes)


def run_scheduled(config: SourceConfig, db_path: str, lock_dir: Path, logger: logging.Logger) -> dict:
    """Runs one source under its lock and records the run. Never raises for a failed run."""
    lock = SourceLock(config.source_id, lock_dir, config.lock_max_age_minutes * 60, logger)
    if not lock.acquire():
        log_run_skipped(logger, config.source_id, "already_running", lock.holder)
        run_id = start_run(db_path, config.source_id, status="skipped", error="already_running")
        return {"run_id": run_id, "source_id": config.source_id, "status": "skipped"}
    try:
        if lock.recovered_stale:
            abandon_running_runs(db_path, config.source_id, f"abandoned: stale lock {lock.holder}")
        run_id = start_run(db_path, config.source_id)
        log_run_start(logger, run_id, config.source_id)
        t_start = time.perf_counter()
        try:
            result = run_source(config, db_path=db_path, logger=logger)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            finish_run(db_path, run_id, "failed", error=error)
            log_run_end(logger, run_id, config.source_id, "failed", int((time.perf_counter() - t_start) * 1000), error=error)
            return {"run_id": run_id, "source_id": config.source_id, "status": "failed", "error": error}
        failed = result["detail_status"]["failed"] + len(result["invalid"])
        finish_run(db_path, run_id, "success", counts=result["counts"], failed_count=failed)
        log_run_end(logger, run_id, config.source_id, "success", int((time.perf_counter() - t_start) * 1000),
                    counts=result["counts"], failed_count=failed)
        return {"run_id": run_id, "source_id": config.source_id, "status": "success", "counts": result["counts"]}
    finally:
        lock.release()


def run_once(config_path: Path = DEFAULT_CONFIG_PATH, db_path: str = str(DEFAULT_DB_PATH),
             lock_dir: Path = DEFAULT_LOCK_DIR, source_ids: Optional[list[str]] = None,
             force: bool = False, logger: Optional[logging.Logger] = None) -> list[dict]:
    """One scheduler cycle: re-reads config, runs each selected source that is due (or all, with force).

    Selected = the given source_ids (even if disabled: explicit operator choice), else every enabled
    source with an interval_minutes.
    """
    logger = logger or setup_logger()
    configs = load_source_configs(config_path)
    if source_ids:
        unknown = [s for s in source_ids if s not in configs]
        if unknown:
            raise ValueError(f"Unknown source_id(s): {unknown}")
        selected = [configs[s] for s in source_ids]
    else:
        selected = [c for c in configs.values() if c.enabled and c.interval_minutes is not None]

    results = []
    for config in selected:
        last = last_run_started_at(db_path, config.source_id)
        due_at = next_due(config, last)
        due = force or due_at is None or _now() >= due_at - due_grace(config)
        log_schedule(logger, config.source_id, config.interval_minutes, last,
                     due_at.strftime(_TS) if due_at else None, due)
        if due:
            results.append(run_scheduled(config, db_path, lock_dir, logger))
    return results


def run_loop(tick_s: float = DEFAULT_TICK_S, max_cycles: Optional[int] = None, **kwargs) -> None:
    """Plain loop: one run_once cycle every tick_s seconds (max_cycles for demos/tests)."""
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        cycle += 1
        run_once(**kwargs)
        if max_cycles is None or cycle < max_cycles:
            time.sleep(tick_s)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Scheduled local runs of configured sources")
    parser.add_argument("--once", action="store_true", help="run due sources once and exit (Task Scheduler)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--locks-dir", default=str(DEFAULT_LOCK_DIR))
    parser.add_argument("--source", action="append", default=None, help="limit to source_id (repeatable)")
    parser.add_argument("--force", action="store_true", help="run selected sources even if not due")
    parser.add_argument("--tick-s", type=float, default=DEFAULT_TICK_S)
    parser.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args(argv)

    kwargs = dict(config_path=Path(args.config), db_path=args.db, lock_dir=Path(args.locks_dir),
                  source_ids=args.source, force=args.force, logger=setup_logger())
    if args.once:
        results = run_once(**kwargs)
        return 1 if any(r["status"] == "failed" for r in results) else 0
    run_loop(tick_s=args.tick_s, max_cycles=args.max_cycles, **kwargs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
