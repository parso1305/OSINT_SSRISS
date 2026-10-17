"""XML sitemap parsing (sitemaps.org 0.9): <urlset> and <sitemapindex>. Takes content; never fetches.

Parsed with defusedxml: a sitemap is untrusted XML from a remote server, and the standard-library parser
accepts entity declarations (billion-laughs / quadratic-blowup expansion) and external entities. defusedxml
refuses those constructs with an exception instead of expanding them.

A <sitemapindex> lists child sitemaps, not items: they are returned separately (child_sitemaps) and the
caller decides whether to follow them (walk_sitemaps, capped, default 2 children).
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Union
from xml.etree.ElementTree import ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

from src.discovery.record import DiscoveryRecord, make_record, utc_now
from src.discovery.timestamps import to_utc_z

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
DEFAULT_MAX_CHILD_SITEMAPS = 2


class SitemapParseError(ValueError):
    """The content is not a well-formed, safe sitemap."""


@dataclass(frozen=True)
class SitemapEntry:
    loc: str                        # as written (not yet canonical)
    lastmod: Optional[str]          # UTC Z, or None (absent, date-only or unreadable)
    lastmod_raw: Optional[str]      # original string


@dataclass(frozen=True)
class SitemapResult:
    kind: str                                   # "urlset" or "sitemapindex"
    urls: list = field(default_factory=list)            # SitemapEntry for items (urlset)
    child_sitemaps: list = field(default_factory=list)  # SitemapEntry for child sitemaps (sitemapindex)


def _local(tag: str) -> str:
    """'{namespace}urlset' -> 'urlset'. Sitemaps without the sitemaps.org namespace are accepted too."""
    return tag.rsplit("}", 1)[-1]


def _child_text(element, name: str) -> Optional[str]:
    for child in element:
        if _local(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def parse_sitemap(content: Union[bytes, str]) -> SitemapResult:
    if isinstance(content, str):
        content = content.encode("utf-8")
    try:
        root = fromstring(content)
    except DefusedXmlException as e:
        raise SitemapParseError(f"unsafe XML refused by defusedxml ({type(e).__name__}): {e}") from e
    except ParseError as e:
        raise SitemapParseError(f"malformed sitemap XML: {e}") from e
    kind = _local(root.tag)
    if kind not in ("urlset", "sitemapindex"):
        raise SitemapParseError(f"not a sitemap: root element is <{kind}>, expected <urlset> or <sitemapindex>")
    entries = []
    for node in root:
        if _local(node.tag) not in ("url", "sitemap"):
            continue
        loc = _child_text(node, "loc")
        if not loc:
            continue
        lastmod_raw = _child_text(node, "lastmod")
        entries.append(SitemapEntry(loc=loc, lastmod=to_utc_z(lastmod_raw), lastmod_raw=lastmod_raw))
    if kind == "urlset":
        return SitemapResult(kind=kind, urls=entries)
    return SitemapResult(kind=kind, child_sitemaps=entries)


def walk_sitemaps(fetch_text: Callable[[str], Union[str, bytes]], start_url: str,
                  max_children: int = DEFAULT_MAX_CHILD_SITEMAPS) -> tuple[list, list]:
    """Parses start_url's sitemap and, if it is an index, at most max_children of its child sitemaps.

    fetch_text(url) is supplied by the caller (it must go through the project's HTTP client); this module
    never makes a request itself. Returns (item entries as (sitemap_url, SitemapEntry), child URLs not followed).
    """
    first = parse_sitemap(fetch_text(start_url))
    items = [(start_url, e) for e in first.urls]
    children = [c.loc for c in first.child_sitemaps]
    for child_url in children[:max_children]:
        child = parse_sitemap(fetch_text(child_url))
        items.extend((child_url, e) for e in child.urls)
    return items, children[max_children:]


def sitemap_records(content: Union[bytes, str], source_name: str, sitemap_url: str,
                    discovered_at: Optional[str] = None) -> tuple[list[DiscoveryRecord], list[str]]:
    """(item records with method "sitemap" and lastmod as source_timestamp, child sitemap URLs).
    A sitemap index yields no item records, only children; following them is the caller's choice."""
    discovered_at = discovered_at or utc_now()
    result = parse_sitemap(content)
    records = []
    for entry in result.urls:
        record = make_record(source_name, entry.loc, sitemap_url, "sitemap", None,
                             entry.lastmod, entry.lastmod_raw, discovered_at)
        if record is not None:
            records.append(record)
    return records, [c.loc for c in result.child_sitemaps]
