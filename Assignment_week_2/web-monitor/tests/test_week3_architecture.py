"""Week 3 layer boundaries, checked by reading the source files (like tests/test_architecture.py, but recursive)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = sorted(ROOT.glob("src/**/*.py")) + sorted(ROOT.glob("sources/*.py"))
DISCOVERY = sorted(ROOT.glob("src/discovery/*.py"))


def test_urljoin_is_called_only_in_resolve_item_url():
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in CODE
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "urljoin" in line and p.name != "urls.py"]
    assert hits == []


def test_discovery_never_touches_the_network_or_storage():
    for path in DISCOVERY:
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(requests|urllib\.request|http\.client|sqlite3)\b", source, re.M), path.name
        assert "Fetcher(" not in source and "urlopen" not in source, path.name


def test_feedparser_is_used_only_in_feed_py_and_only_on_bytes():
    users = [p.name for p in CODE if "feedparser" in p.read_text(encoding="utf-8")]
    assert users == ["feed.py"]
    source = (ROOT / "src" / "discovery" / "feed.py").read_text(encoding="utf-8")
    calls = re.findall(r"^\s*\w+\s*=\s*feedparser\.parse\((.+)\)\s*$", source, re.M)   # code, not the docstring
    assert calls == ["_ensure_document(content)"]


def test_sitemaps_use_defusedxml_not_the_stdlib_parser():
    source = (ROOT / "src" / "discovery" / "sitemap.py").read_text(encoding="utf-8")
    assert "from defusedxml.ElementTree import fromstring" in source
    assert not re.search(r"^\s*(import|from)\s+xml\.etree\.ElementTree\s+import\s+(?!ParseError)", source, re.M)
