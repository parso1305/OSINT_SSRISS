"""Run pytest with outbound HTTP blocked, from any shell (PowerShell, cmd, bash).

Sets HTTP_PROXY / HTTPS_PROXY to a dead local port (127.0.0.1:9, the discard port) before pytest starts, so any
test that tries to reach the real network fails loudly instead of silently passing online. localhost and
127.0.0.1 stay reachable for the local fixture sites.

    venv/Scripts/python scripts/offline_pytest.py                                 # main suite
    venv/Scripts/python scripts/offline_pytest.py assignments/week2_audit/tests   # audit suite
"""

import os
import sys
import tempfile

import pytest

os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
# The audit suite writes evidence files; by default they would overwrite the frozen Week 2 evidence in
# assignments/week2_audit/logs/after_fixes/evidence/. Send them to a temp dir unless the caller chose one.
os.environ.setdefault("AUDIT_EVIDENCE_DIR", os.path.join(tempfile.gettempdir(), "web_monitor_audit_evidence"))

if __name__ == "__main__":
    sys.exit(pytest.main(sys.argv[1:]))
