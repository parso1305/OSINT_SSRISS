# Assignment 7: shared template (generic pipeline + IIT Bombay adapter)

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Split the scraper into a generic, reusable pipeline and a small IIT Bombay-only adapter, driven by a config entry,
with schema validation, logging, controlled pagination and detail enrichment.

## What I built / found

- A generic layer in [`src/`](../../src): fetcher, pagination, enrichment, schema, storage, runner, scheduler,
  config. It contains no institution-specific code, and a test enforces that.
- The HSS adapter [`sources/iit_bombay.py`](../../sources/iit_bombay.py): selectors, `parse_listing`,
  `parse_detail`, `normalize`; 157 lines of code (220 with docstrings), no I/O.
- One config entry in [`config/sources.json`](../../config/sources.json).
- 17 brittle assumptions, each classified loud or silent, with how it would be detected
  ([notes §4](iit_bombay_adapter_notes.md#4-brittle-assumptions)).
- Findings from other sites (§6): ME department timestamps are IST wall-clock time labelled `Z`; talks.cam.ac.uk
  opts out of AI crawlers in robots.txt, so it was not used.

## Key decisions and why

- **Architecture is enforced by tests, not by convention**: only `fetcher.py` uses `requests`, only `storage.py`
  uses `sqlite3`, only `logging_config.py` configures handlers, no institution strings in `src/`, and no
  `verify=False` anywhere ([`tests/test_architecture.py`](../../tests/test_architecture.py)).
- **TLS: `ca_bundle` instead of disabling verification.** HSS omits an intermediate certificate. The old fetcher
  silently retried with `verify=False`; now the source ships certifi + exactly that one intermediate
  ([README, TLS](../../README.md#tls-certificates-ca_bundle)).
- **Adding a source = adapter + config.** Proven with a synthetic source in
  [`tests/test_generic_source.py`](../../tests/test_generic_source.py), and in the audit with two real sites (IIT
  Bombay ME and CMI) and no generic-code change
  ([`generalization_run.log`](../week2_audit/logs/after_fixes/generalization_run.log)).

## Evidence

- [`iit_bombay_adapter_notes.md`](iit_bombay_adapter_notes.md) (generic / source-specific / optional capabilities /
  brittle assumptions / size / other sites)
- [`step5_fixture_run.log`](step5_fixture_run.log), [`step7_logging_run.log`](step7_logging_run.log)
- [`tests/test_architecture.py`](../../tests/test_architecture.py),
  [`tests/test_adapter_iit_bombay.py`](../../tests/test_adapter_iit_bombay.py),
  [`tests/test_runner.py`](../../tests/test_runner.py), [`tests/test_tls.py`](../../tests/test_tls.py)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest tests\test_architecture.py tests\test_adapter_iit_bombay.py tests\test_generic_source.py tests\test_tls.py
venv\Scripts\python scripts\run_fixtures.py --show-records 2        # full pipeline on saved HTML, no network
```

## Status

**PASS.** Known limitations: detail pages reachable only by `POST` (e.g. CMI) cannot be enriched; one `item_url`
listed by two sources is one shared row (audit M5,
[FIXES.md](../week2_audit/FIXES.md#known-limitations-assessed-2026-09-27-not-fixed)).
