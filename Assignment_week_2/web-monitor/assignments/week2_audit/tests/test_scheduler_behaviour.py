"""Audit cases 16-21: the real src/scheduler.py (in-process and as separate OS processes) against the audit server."""

import hashlib
import json
import logging
import os
import re
import socket
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from audit_server import AuditSite, Fault, LISTING_PATH, FIXTURES
from conftest import PROJECT_ROOT, SOURCE_ID, write_sandbox_config, real_entry, db_dump, lines, open_problem

from src.scheduler import SourceLock, run_once
from src.storage import list_runs, count_records

LOG = logging.getLogger("web_monitor")
TS = "%Y-%m-%dT%H:%M:%SZ"


def scheduler_cmd(cfg: Path, db: str, locks: Path, *extra: str) -> list[str]:
    return [sys.executable, "-m", "src.scheduler", "--once", "--config", str(cfg), "--db", db,
            "--locks-dir", str(locks), *extra]


def env() -> dict:
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def tree_sha(*dirs: str) -> dict:
    out = {}
    for d in dirs:
        for p in sorted((PROJECT_ROOT / d).rglob("*.py")):
            if "__pycache__" not in p.parts:
                out[str(p.relative_to(PROJECT_ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def test_16_concurrent_runs_same_source(tmp_path, evidence):
    db, locks = str(tmp_path / "t16.db"), tmp_path / "locks"
    with AuditSite() as site:
        site.faults[LISTING_PATH] = Fault(sleep_s=2.0)          # slow listing keeps process A inside the lock
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0)])
        a = subprocess.Popen(scheduler_cmd(cfg, db, locks, "--force"), cwd=PROJECT_ROOT, env=env(),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lock_file = locks / f"{SOURCE_ID}.lock"
        deadline = time.time() + 15
        while not lock_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        lock_contents = lock_file.read_text() if lock_file.exists() else "(no lock file seen)"
        b = subprocess.run(scheduler_cmd(cfg, db, locks, "--force"), cwd=PROJECT_ROOT, env=env(),
                           capture_output=True, text=True, timeout=60)
        a_out, _ = a.communicate(timeout=60)
    runs = [(r["status"], r["error"], r["started_at"], r["finished_at"]) for r in list_runs(db)]
    evidence(f"lock file while A runs: {lock_contents}",
             "--- process A ---", lines(a_out, "RUN_START", "RUN_END", "RUN_SKIPPED", "STORE"),
             f"--- process B (exit {b.returncode}) ---", lines(b.stdout, "RUN_START", "RUN_END", "RUN_SKIPPED", "SCHEDULE"),
             f"runs table: {runs}", f"records rows: {count_records(db)}", f"lock left behind: {lock_file.exists()}")
    assert "RUN_SKIPPED" in b.stdout and "reason=already_running" in b.stdout
    assert sorted(r[0] for r in runs) == ["skipped", "success"]
    assert not lock_file.exists()


@pytest.mark.parametrize("kind", ["dead_pid", "old_timestamp_live_pid", "corrupt_json_old_mtime",
                                  pytest.param("unparseable_started_at", marks=open_problem(
                                      "m1", "a lock with a non-Z started_at raises ValueError out of run_once")),
                                  "other_host_fresh"])
def test_17_stale_lock(tmp_path, log_stream, evidence, kind):
    db, locks = str(tmp_path / "t17.db"), tmp_path / "locks"
    locks.mkdir()
    lock = locks / f"{SOURCE_ID}.lock"
    now = datetime.now(timezone.utc)
    content = {
        "dead_pid": {"pid": dead_pid(), "host": socket.gethostname(), "started_at": now.strftime(TS)},
        "old_timestamp_live_pid": {"pid": os.getpid(), "host": socket.gethostname(),
                                   "started_at": (now - timedelta(hours=3)).strftime(TS)},
        "unparseable_started_at": {"pid": os.getpid(), "host": socket.gethostname(), "started_at": "2026-09-26 06:00"},
        "other_host_fresh": {"pid": 4242, "host": "some-other-machine", "started_at": now.strftime(TS)},
    }.get(kind)
    lock.write_text("{not json" if content is None else json.dumps(content), encoding="utf-8")
    if kind == "corrupt_json_old_mtime":
        old = time.time() - 3 * 3600
        os.utime(lock, (old, old))
    crashed = None
    with AuditSite() as site:
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0)])
        try:
            result = run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=LOG)
        except Exception as e:  # noqa: BLE001
            crashed, result = f"{type(e).__name__}: {e}", None
    runs = [(r["status"], r["error"]) for r in list_runs(db)] if Path(db).exists() else []
    evidence(f"lock content: {lock.read_text() if lock.exists() else '(removed)'}", f"crashed: {crashed}",
             f"result: {result}", f"runs: {runs}", lines(log_stream.getvalue(), "STALE_LOCK", "RUN_SKIPPED", "RUN_END"))
    assert crashed is None, "a malformed lock must not crash the scheduler cycle"
    if kind == "other_host_fresh":
        assert result[0]["status"] == "skipped"
    else:
        assert "STALE_LOCK" in log_stream.getvalue() and result[0]["status"] == "success"


@pytest.mark.parametrize("where", ["update_midway", "insert_midway"])
def test_18_failure_mid_storage_rolls_back(tmp_path, log_stream, evidence, where):
    db, locks = str(tmp_path / "t18.db"), tmp_path / "locks"
    with AuditSite() as site:
        first_pages = 2 if where == "update_midway" else 1
        cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0,
                                                                          max_pages=first_pages)])
        run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=LOG)
        before = db_dump(db)
        conn = sqlite3.connect(db)
        if where == "update_midway":   # fails on the 9th of 20 UPDATEs (rortys-revolution)
            conn.execute("CREATE TRIGGER audit_fail BEFORE UPDATE ON records WHEN NEW.item_url LIKE '%rortys-revolution' "
                         "BEGIN SELECT RAISE(ABORT, 'audit injected failure'); END")
        else:                          # 10 UPDATEs + 10 INSERTs; fail on the last page-2 INSERT
            conn.execute("CREATE TRIGGER audit_fail BEFORE INSERT ON records WHEN (SELECT COUNT(*) FROM records) >= 19 "
                         "BEGIN SELECT RAISE(ABORT, 'audit injected failure'); END")
            cfg = write_sandbox_config(tmp_path / "sources.json", [real_entry(listing_url=site.listing_url, request_delay_s=0,
                                                                              max_pages=2)])
        conn.commit()
        conn.close()
        mark = len(log_stream.getvalue())
        result = run_once(cfg, db, locks, source_ids=[SOURCE_ID], force=True, logger=LOG)[0]
        after = db_dump(db)
    runs = [(r["status"], r["new_count"], r["error"]) for r in list_runs(db)]
    evidence(f"before: sha256={before[0][:16]} rows={before[1]}", f"after:  sha256={after[0][:16]} rows={after[1]}",
             f"result: {result}", f"runs: {runs}", lines(log_stream.getvalue()[mark:], "FAILURE", "RUN_END"))
    assert before == after and result["status"] == "failed" and runs[-1][0] == "failed"


def test_19_schedule_change_via_config_only(tmp_path, log_stream, evidence):
    db, locks = str(tmp_path / "t19.db"), tmp_path / "locks"
    code_before = tree_sha("src", "sources")
    real_cfg_before = hashlib.sha256((PROJECT_ROOT / "config" / "sources.json").read_bytes()).hexdigest()
    with AuditSite() as site:
        cfg = tmp_path / "sources.json"
        write_sandbox_config(cfg, [real_entry(listing_url=site.listing_url, request_delay_s=0)])      # interval 1440
        r1 = run_once(cfg, db, locks, source_ids=[SOURCE_ID], logger=LOG)
        r2 = run_once(cfg, db, locks, source_ids=[SOURCE_ID], logger=LOG)
        write_sandbox_config(cfg, [real_entry(listing_url=site.listing_url, request_delay_s=0, interval_minutes=0.02)])
        time.sleep(1.5)
        r3 = run_once(cfg, db, locks, source_ids=[SOURCE_ID], logger=LOG)
    code_after = tree_sha("src", "sources")
    real_cfg_after = hashlib.sha256((PROJECT_ROOT / "config" / "sources.json").read_bytes()).hexdigest()
    evidence(f"cycle 1 (interval 1440, never run): ran={len(r1)}", f"cycle 2 (interval 1440): ran={len(r2)}",
             f"cycle 3 (temp config edited to interval 0.02 min): ran={len(r3)}",
             lines(log_stream.getvalue(), "SCHEDULE"),
             f"src/ + sources/ file hashes identical before/after: {code_before == code_after} ({len(code_before)} files)",
             f"real config/sources.json unchanged: {real_cfg_before == real_cfg_after}")
    assert (len(r1), len(r2), len(r3)) == (1, 0, 1) and code_before == code_after and real_cfg_before == real_cfg_after


def test_20_two_sources_do_not_block_each_other(tmp_path, log_stream, evidence):
    db, locks = str(tmp_path / "t20.db"), tmp_path / "locks"
    other = "audit_second_source"
    with AuditSite() as site_a, AuditSite() as site_b:
        cfg = write_sandbox_config(tmp_path / "sources.json", [
            real_entry(listing_url=site_a.listing_url, request_delay_s=0),
            real_entry(source_id=other, institution="Audit Second Institution", listing_url=site_b.listing_url,
                       request_delay_s=0, detail_limit=3)])
        both = run_once(cfg, db, locks, logger=LOG)                              # no --source: all enabled + due
        site_a.faults[LISTING_PATH] = Fault(status=500)
        a_fails = run_once(cfg, db, locks, force=True, logger=LOG)
        del site_a.faults[LISTING_PATH]
        holder = SourceLock(SOURCE_ID, locks, 3600, LOG)
        assert holder.acquire()
        try:
            a_locked = run_once(cfg, db, locks, force=True, logger=LOG)
        finally:
            holder.release()
        # true concurrency: two OS processes, one per source, A slowed down
        site_a.faults[LISTING_PATH] = Fault(sleep_s=2.0)
        t0 = time.time()
        pa = subprocess.Popen(scheduler_cmd(cfg, db, locks, "--force", "--source", SOURCE_ID), cwd=PROJECT_ROOT, env=env(),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        pb = subprocess.Popen(scheduler_cmd(cfg, db, locks, "--force", "--source", other), cwd=PROJECT_ROOT, env=env(),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out_b, _ = pb.communicate(timeout=60)
        t_b = time.time() - t0
        out_a, _ = pa.communicate(timeout=60)
        t_a = time.time() - t0
    summary = lambda rs: [(r["source_id"], r["status"]) for r in rs]  # noqa: E731
    evidence(f"cycle 1 (both due): {summary(both)}", f"cycle 2 (A listing 500): {summary(a_fails)}",
             f"cycle 3 (A lock held): {summary(a_locked)}",
             f"concurrent processes: B exit={pb.returncode} after {t_b:.1f}s, A exit={pa.returncode} after {t_a:.1f}s",
             lines(out_a, "RUN_END"), lines(out_b, "RUN_END"),
             f"records per source: {SOURCE_ID}={count_records(db, SOURCE_ID)} {other}={count_records(db, other)}")
    assert summary(both) == [(SOURCE_ID, "success"), (other, "success")]
    assert summary(a_fails) == [(SOURCE_ID, "failed"), (other, "success")]
    assert summary(a_locked) == [(SOURCE_ID, "skipped"), (other, "success")]
    assert pa.returncode == 0 and pb.returncode == 0 and t_b < t_a


def test_21_crawl_frequency_numbers(evidence):
    """Recompute schedule_notes.md section 1 from the 30 saved live listing items (pages 1-3)."""
    from sources import iit_bombay
    items = []
    for n in (1, 2, 3):
        html = (FIXTURES / f"live_page_{n}.html").read_text(encoding="utf-8")
        items += iit_bombay.parse_listing(html, "https://www.hss.iitb.ac.in/events/seminars-and-talks")
    dates = sorted(datetime.strptime(re.sub(r"(\d+)(st|nd|rd|th)", r"\1", i["date_raw"]).strip(), "%d %b %Y").date()
                   for i in items)
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    months = Counter(d.strftime("%Y-%m") for d in dates)
    span_months = [f"2025-{m:02d}" for m in range(dates[0].month, dates[-1].month + 1)]
    per_month = {m: months.get(m, 0) for m in span_months}
    weekdays = Counter(d.strftime("%a") for d in dates)
    fetched = json.loads((PROJECT_ROOT / "assignments" / "04_pagination" / "live_run.json").read_text(encoding="utf-8"))
    fetched_at = fetched["fetches"][0]["fetched_at"]
    page32 = "page=32" in (FIXTURES / "live_page_1.html").read_text(encoding="utf-8")
    recomputed = {
        "items": len(dates), "range": f"{dates[0]} -> {dates[-1]} ({(dates[-1] - dates[0]).days} days)",
        "per_month": per_month, "mean_per_month": round(sum(per_month.values()) / len(per_month), 1),
        "gap_median": statistics.median(gaps), "gap_min": min(gaps), "gap_mean": round(statistics.mean(gaps), 1),
        "gap_max": max(gaps), "sorted_gaps": sorted(gaps), "gaps_le_4": sum(g <= 4 for g in gaps),
        "gaps_le_1": sum(g <= 1 for g in gaps), "n_gaps": len(gaps), "weekdays": dict(weekdays.most_common()),
        "newest_vs_fetch_days": (datetime.strptime(fetched_at[:10], "%Y-%m-%d").date() - dates[-1]).days,
        "fetched_at": fetched_at, "pager_links_page_32": page32,
    }
    evidence(recomputed)
    claimed = {"range": "2025-01-02 -> 2025-09-25 (266 days)", "mean_per_month": 3.3, "gap_median": 4, "gap_min": 0,
               "gap_mean": 9.2, "gap_max": 91, "newest_vs_fetch_days": 365, "gaps_le_1": 7, "n_gaps": 29,
               "per_month": {"2025-01": 10, "2025-02": 3, "2025-03": 7, "2025-04": 2, "2025-05": 0, "2025-06": 0,
                             "2025-07": 2, "2025-08": 4, "2025-09": 2},
               "weekdays": {"Wed": 12, "Fri": 6, "Thu": 5, "Mon": 4, "Tue": 2, "Sat": 1}}
    mismatches = {k: (v, recomputed[k]) for k, v in claimed.items() if recomputed[k] != v}
    evidence("claimed vs recomputed mismatches:", mismatches)
    assert not mismatches
