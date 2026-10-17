"""Content router (Week 3 Section 8): what kind of thing a discovered URL is, from structural evidence only.

classify_discovered_item(record, *, content_type=None, category_label=None, cfg=None) -> label
classify_with_reason(...) -> (label, reason)

Labels: event · announcement · faculty · pdf_document · external_link · unknown

Rules, applied in this order (the first that decides wins; the reason names it):
  1. external host   the URL's host is not one of the source's hosts (cfg["hosts"])          -> external_link
  2. PDF             Content-Type known: application/pdf -> pdf_document; any other type means "not a PDF",
                     even for a URL ending in .pdf (the server's header beats the file name).
                     Content-Type unknown (before fetching): a path ending in .pdf -> pdf_document
  3. category label  the label shown on the listing card, mapped by cfg["category_map"] (exact, case-insensitive)
  4. URL pattern     cfg["url_patterns"] = {label: [path prefix, ...]}, checked in config order
  5. otherwise       unknown (persisted in discovered_items with this reason; never forced into records)

No text classification, no guessing from titles. The router runs before fetching (no Content-Type yet: PDFs and
external links are never detail-fetched as HTML) and again after a fetch with the response's Content-Type.
"""

from typing import Optional, Union
from urllib.parse import urlsplit

LABELS = ("event", "announcement", "faculty", "pdf_document", "external_link", "unknown")
PATTERN_LABELS = ("event", "announcement", "faculty")       # what a category label or URL pattern may assign


def _url(record: Union[str, object]) -> str:
    return record if isinstance(record, str) else record.discovered_url


def _check_cfg(cfg: dict) -> None:
    bad = [label for label in list((cfg.get("url_patterns") or {})) + list((cfg.get("category_map") or {}).values())
           if label not in PATTERN_LABELS]
    if bad:
        raise ValueError(f"router config: labels {bad} not in {PATTERN_LABELS}")


def classify_with_reason(record, *, content_type: Optional[str] = None, category_label: Optional[str] = None,
                         cfg: Optional[dict] = None) -> tuple[str, str]:
    cfg = cfg or {}
    _check_cfg(cfg)
    parts = urlsplit(_url(record))
    host = (parts.hostname or "").lower()
    path = parts.path or "/"

    hosts = [h.lower() for h in cfg.get("hosts") or []]
    if hosts and host not in hosts:
        return "external_link", f"external host {host} (source hosts: {', '.join(hosts)})"

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime:
        if mime == "application/pdf":
            return "pdf_document", "Content-Type application/pdf"
    elif path.lower().endswith(".pdf"):
        return "pdf_document", "path ends in .pdf (no Content-Type known yet)"

    if category_label:
        mapped = {k.casefold(): v for k, v in (cfg.get("category_map") or {}).items()}.get(category_label.strip().casefold())
        if mapped:
            return mapped, f"category label {category_label!r}"

    for label, prefixes in (cfg.get("url_patterns") or {}).items():
        for prefix in prefixes:
            if path.startswith(prefix):
                suffix = f" (Content-Type {mime})" if mime else ""
                return label, f"URL pattern {prefix}{suffix}"

    detail = f"; Content-Type {mime}" if mime else ""
    return "unknown", f"no rule matched (host {host}, path {path}{detail})"


def classify_discovered_item(record, *, content_type: Optional[str] = None, category_label: Optional[str] = None,
                             cfg: Optional[dict] = None) -> str:
    return classify_with_reason(record, content_type=content_type, category_label=category_label, cfg=cfg)[0]


def fetchable_as_html(label: str) -> bool:
    """PDFs and external links are never detail-fetched as HTML."""
    return label not in ("pdf_document", "external_link")
