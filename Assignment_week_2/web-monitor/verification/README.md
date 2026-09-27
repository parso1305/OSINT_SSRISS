# Verification logs

Raw output from a **fresh clone** of the repository into a short path (`C:\tmp\wm`), a fresh virtual environment
and `pip install -r requirements.txt`. The numbers quoted in [`../RESULTS.md`](../RESULTS.md) and the READMEs
come from these files. The first line of each file records the commit and the UTC time.

| File | Command | Result |
|---|---|---|
| [`fresh_clone_pytest.txt`](fresh_clone_pytest.txt) | `python -m pytest --cov=src --cov=sources --cov-report=term` | main suite + coverage table |
| [`fresh_clone_audit_tests.txt`](fresh_clone_audit_tests.txt) | `python -m pytest assignments/week2_audit/tests -rx` | audit behaviour tests; the xfails are the known limitations |
| [`fresh_clone_check_links.txt`](fresh_clone_check_links.txt) | `python scripts/check_links.py` | every relative Markdown link and anchor resolves |
| [`fresh_clone_scheduler_local_fixture.txt`](fresh_clone_scheduler_local_fixture.txt) | `python -m src.scheduler --once --source local_fixture --db data/local_fixture_check.db`, with `python scripts/fixture_site.py --port 8765` running | one scheduled run on saved HTML (no network) + the `runs` table |

To reproduce, run the same commands from `Assignment_week_2/web-monitor` in your own clone (see the
[README quickstart](../README.md#setup)).
