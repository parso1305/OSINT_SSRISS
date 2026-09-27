# Assignment 1: structured failure logging

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Log every pipeline stage in a structured, grep-able way, and show real log output for a successful run and for each
kind of failure.

## What I built / found

- One logging module, [`src/logging_config.py`](../../src/logging_config.py): the only place log handlers are
  configured, with one helper per event (`START`, `FETCH`, `FETCH_ERROR`, `PARSE`, `ENRICH`, `DETAIL_FAILURE`,
  `PARSE_WARNING`, `VALIDATE`, `STORE`, `FAILURE`, `SCHEDULE`, `RUN_END`, …).
- Line format `YYYY-MM-DD HH:MM:SS [LEVEL] logger=<name> EVENT key=value …`: every line names the source
  (`source_id=`), the stage, and for failures the underlying error type (`error_type=SSLError`, `StructuralError`, …).
- [`failure_examples.md`](failure_examples.md): real output for a baseline run and 9 failure cases (invalid config
  URL, connection failure, site redesign, empty listing, database error, TLS, detail 404, changed date format).

## Key decisions and why

- **The examples are generated, not hand-written.** [`scripts/failure_examples_run.py`](../../scripts/failure_examples_run.py)
  injects one fault per case into the real runner (local fixture server, no network) and pastes the captured lines.
  The document can't drift from the code: re-running it rebuilds it.
- **Separate loggers for separate concerns** (`web_monitor`, `.fetcher`, `.detail`), so per-item problems are
  distinguishable from run-level failures.

## Evidence

- [`failure_examples.md`](failure_examples.md), [`scripts/failure_examples_run.py`](../../scripts/failure_examples_run.py)
- [`tests/test_architecture.py`](../../tests/test_architecture.py) (`test_only_logging_config_configures_handlers`)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python scripts\failure_examples_run.py        # rewrites failure_examples.md from real runs
venv\Scripts\python -m pytest tests\test_architecture.py
```

## Status

**PASS.** Known limitation: log timestamps are local time without a zone marker, while database timestamps are UTC
(audit m9, [report §10](../week2_audit/AUDIT_REPORT.md#10-problems-found-ordered-by-severity-fixes-proposed-not-applied)).
