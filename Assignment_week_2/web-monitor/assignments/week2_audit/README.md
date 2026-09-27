# Week 2 audit and fixes

[Week 2 README](../../README.md) · [Results](../../RESULTS.md)

## Task

Independently audit the Week 2 pipeline: repository state, architecture, existing tests, 21 behaviour cases on real
fixtures, generalization to other sites, and documentation. Then fix what the audit found, one commit per fix.

## What I built / found

- [`AUDIT_REPORT.md`](AUDIT_REPORT.md) (2026-09-26, kept unchanged as evidence): 58-item benchmark, 21 behaviour
  cases plus 2 extra edge cases, and a ranked problem list.
- Top findings at the time: the Week 2 code was not committed; TLS verification was silently switched off; an empty
  listing was recorded as `success`; a changed date format erased stored data without a warning; a failed run
  wasn't retried for 24 h.
- Generalization: a second IIT Bombay department (ME) and a structurally different site (CMI) ran through the
  generic pipeline with only an adapter + config ([sandbox adapters](sources)).
- [`FIXES.md`](FIXES.md): each problem → the commit that fixed it → the test that proves it, plus the remaining
  known limitations with effort and risk.

## Key decisions and why

- **The audit stays as it was written.** Re-runs write to [`logs/after_fixes/`](logs/after_fixes) and never
  overwrite the original [`logs/evidence/`](logs/evidence).
- **Fixed behaviour is tested in the main suite** ([`tests/test_audit_regressions.py`](../../tests/test_audit_regressions.py)).
  Unfixed items stay here as `xfail(strict=True)`, so a future fix shows up as a test result.

## Evidence

- [`AUDIT_REPORT.md`](AUDIT_REPORT.md), [`FIXES.md`](FIXES.md)
- Audit tests: [`tests/`](tests); fault-injecting local server: [`tests/audit_server.py`](tests/audit_server.py)
- Fresh-clone audit run: [`verification/fresh_clone_audit_tests.txt`](../../verification/fresh_clone_audit_tests.txt)
  (43 passed, 3 xfailed)

## How to verify

```powershell
cd Assignment_week_2\web-monitor
venv\Scripts\python -m pytest assignments\week2_audit\tests -rx
venv\Scripts\python assignments\week2_audit\scripts\run_generalization.py   # ME + CMI on saved fixtures
```

## Status

All problems in the fix list are fixed. **KNOWN LIMITATION**: M5 (cross-source key), m2 (listing vs detail value
after a failed fetch) and m11 (silently renamed detail field) are documented with proposed fixes in
[FIXES.md](FIXES.md#known-limitations-assessed-2026-09-27-not-fixed).
