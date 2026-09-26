"""Architecture checkpoint: layer boundaries are enforced by reading the source files."""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ADAPTER = PROJECT_ROOT / "sources" / "iit_bombay.py"
GENERIC = sorted((PROJECT_ROOT / "src").glob("*.py"))
PIPELINE_CODE = GENERIC + sorted((PROJECT_ROOT / "sources").glob("*.py"))

FORBIDDEN_IN_ADAPTER = ("import requests", "sqlite3", "logging.basicConfig", "addHandler", "Session(")
INSTITUTION_MARKERS = re.compile(r"iitb|iit[ _]bombay|\bhss\b|humanities|drupal|node--|field-event", re.IGNORECASE)


def test_adapter_has_no_network_storage_or_logging_setup():
    source = ADAPTER.read_text(encoding="utf-8")
    found = [needle for needle in FORBIDDEN_IN_ADAPTER if needle in source]
    assert not found, f"sources/iit_bombay.py must not contain: {found}"


def test_adapter_exposes_the_contract():
    from sources import iit_bombay
    for name in ("parse_listing", "parse_detail", "normalize"):
        assert callable(getattr(iit_bombay, name)), name


def test_generic_layer_has_no_institution_specific_strings():
    hits = [f"{path.name}:{n}: {line.strip()}"
            for path in GENERIC
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if INSTITUTION_MARKERS.search(line)]
    assert not hits, "\n".join(hits)


def test_only_fetcher_uses_requests_and_only_storage_uses_sqlite():
    for path in PIPELINE_CODE:
        source = path.read_text(encoding="utf-8")
        if path.name != "fetcher.py":
            assert not re.search(r"^\s*(import requests|from requests)", source, re.MULTILINE), path.name
        if path.name != "storage.py":
            assert "sqlite3" not in source, path.name


def test_tls_verification_is_never_disabled():
    for path in PIPELINE_CODE:
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"verify\s*=\s*False|disable_warnings|CERT_NONE|check_hostname\s*=\s*False", source), path.name


def test_only_logging_config_configures_handlers():
    for path in PIPELINE_CODE:
        if path.name == "logging_config.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "addHandler" not in source and "basicConfig" not in source, path.name


def test_scheduler_knows_only_source_ids_and_config():
    source = (PROJECT_ROOT / "src" / "scheduler.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+sources\b", source, re.MULTILINE)
    assert "load_adapter" not in source and "http://" not in source and "https://" not in source
    assert not INSTITUTION_MARKERS.search(source)
