"""Every relative link and #anchor in the repository's Markdown files resolves (scripts/check_links.py)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_links import check, github_slug, repo_root


def test_every_markdown_link_in_the_repository_resolves():
    problems = check(repo_root(PROJECT_ROOT))
    assert problems == [], "\n".join(problems)


def test_checker_catches_missing_files_anchors_and_local_paths(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.md").write_text("# Real heading\n\n## TLS certificates (`ca_bundle`)\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("\n".join([
        "[ok](docs/b.md) [ok anchor](docs/b.md#real-heading) [ok code heading](docs/b.md#tls-certificates-ca_bundle)",
        "[web](https://example.org/x) [self](#top)",
        "# Top",
        "[missing](docs/nope.md) [bad anchor](docs/b.md#nope) [local](C:/Project/x.md)",
        "`[not a link](inside/code.md)`",
        "```", "[also not](fenced.md)", "```",
    ]), encoding="utf-8")
    problems = check(tmp_path)
    assert [p.split(": ", 1)[1] for p in problems] == [
        "missing target: docs/nope.md", "missing anchor #nope in b.md", "absolute local path in link: C:/Project/x.md"]


def test_github_slug_matches_githubs_rules():
    assert github_slug("TLS certificates (`ca_bundle`)") == "tls-certificates-ca_bundle"
    assert github_slug("(h) Added after the Week 2 audit (2026-09-27): two assumptions") == \
        "h-added-after-the-week-2-audit-2026-09-27-two-assumptions"
