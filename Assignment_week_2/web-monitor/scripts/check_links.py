"""Checks every relative link and #anchor in the repository's Markdown files. Exit code 1 on any failure.

Scans all *.md files under the repository root (the folder containing .git, else web-monitor/), skipping venv/ and
hidden folders. For each [text](target) outside code blocks and inline code:
  - http(s)://, mailto: links are not checked (no network);
  - a relative path must exist (resolved from the Markdown file's folder);
  - a #anchor (same file or other .md file) must match a heading, slugged the way GitHub does.
Also flags absolute local paths (C:\\..., /Users/...) in links.

Usage:  python scripts/check_links.py [root]
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

WEB_MONITOR = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"(?<!!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?\s*\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
SKIP_DIRS = {"venv", ".venv", "node_modules", "__pycache__"}


def repo_root(start: Path) -> Path:
    for folder in (start, *start.parents):
        if (folder / ".git").exists():
            return folder
    return start


def github_slug(heading: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)       # [text](url) -> text
    text = text.replace("`", "").replace("*", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)                             # GitHub drops punctuation, keeps _ and -
    return text.replace(" ", "-")


def scan(md: Path) -> tuple[list[tuple[int, str]], set[str]]:
    """Returns ([(line_no, link_target)], {anchors})."""
    links, anchors, counts = [], set(), {}
    in_fence = False
    for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            slug = github_slug(heading.group(2))
            k = counts.get(slug, 0)
            anchors.add(slug if k == 0 else f"{slug}-{k}")
            counts[slug] = k + 1
        for anchor in re.findall(r'<a\s+(?:name|id)="([^"]+)"', line):
            anchors.add(anchor)
        visible = INLINE_CODE_RE.sub("", line)
        links += [(n, t) for t in LINK_RE.findall(visible) + IMAGE_RE.findall(visible)]
    return links, anchors


def markdown_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md")
                  if not any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(root).parts[:-1]))


def check(root: Path) -> list[str]:
    files = markdown_files(root)
    parsed = {p.resolve(): scan(p) for p in files}
    problems = []
    for md in files:
        for n, target in parsed[md.resolve()][0]:
            where = f"{md.relative_to(root).as_posix()}:{n}"
            if re.match(r"^(https?:|mailto:)", target, re.IGNORECASE):
                continue
            if re.match(r"^([A-Za-z]:[\\/]|/Users/|/home/|file:)", target):
                problems.append(f"{where}: absolute local path in link: {target}")
                continue
            path_part, _, anchor = target.partition("#")
            dest = (md.parent / unquote(path_part)).resolve() if path_part else md.resolve()
            if not dest.exists():
                problems.append(f"{where}: missing target: {target}")
                continue
            if anchor:
                if dest.suffix.lower() != ".md":
                    continue                       # anchors into non-Markdown files (e.g. #L10) are not checked
                anchors = parsed.get(dest, scan(dest))[1]
                if unquote(anchor).lower() not in anchors:
                    problems.append(f"{where}: missing anchor #{anchor} in {dest.name}")
    return problems


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else repo_root(WEB_MONITOR)
    problems = check(root)
    count = len(markdown_files(root))
    for problem in problems:
        print(problem)
    print(f"checked {count} Markdown files under {root.name}/: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
