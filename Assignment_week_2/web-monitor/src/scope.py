"""URL scope filter (Week 3 Section 2): is a discovered URL inside what this source is allowed to collect?

Callers canonicalize first (src.urls.resolve_item_url). The decision is then purely structural, made in this
order (the first rule that decides wins; the reason names it):

  1. scheme          only http/https (mailto:, javascript:, tel:, data:, ftp: are never items)
  2. host            exact match against allowed_hosts. A subdomain is allowed only when its parent domain is
                     listed in allowed_subdomains_of, checked on a dot boundary ("x.example.edu" yes,
                     "notexample.edu" no). Never endswith() on the bare name. Other hosts: rejected unless
                     allow_external (default False).
  3. excluded path   excluded_prefixes (login, search, admin, user pages)
  4. query keys      any key in excluded_query_keys (calendar/search/filter explosion: ?month=, ?view=, ...)
  5. allowed path    the path must start with one of allowed_prefixes. Prefixes are stored WITH a trailing slash,
                     so "/events/" never matches "/events-archive/".
  6. in scope.       A PDF inside an allowed prefix is in scope too; the router labels it pdf_document and it is
                     never detail-fetched as HTML.

The per-run caps (max_listing_pages, max_detail_items, max_discovered_items) are carried here because they are
part of the same "how much of this site do we take" decision; the aggregator applies them.
"""

from dataclasses import dataclass, fields
from typing import Optional
from urllib.parse import parse_qsl, urlsplit

WEB_SCHEMES = ("http", "https")


def _with_slash(prefix: str) -> str:
    prefix = prefix if prefix.startswith("/") else "/" + prefix
    return prefix if prefix.endswith("/") else prefix + "/"


@dataclass(frozen=True)
class ScopeConfig:
    allowed_hosts: tuple = ()
    allowed_subdomains_of: tuple = ()
    allowed_prefixes: tuple = ("/",)
    excluded_prefixes: tuple = ()
    allow_external: bool = False
    excluded_query_keys: tuple = ()
    max_listing_pages: int = 1
    max_detail_items: int = 20
    max_discovered_items: int = 40

    def __post_init__(self) -> None:
        # Normalize once: hosts lowercase, prefixes with a trailing slash, query keys lowercase.
        object.__setattr__(self, "allowed_hosts", tuple(h.lower().rstrip(".") for h in self.allowed_hosts))
        object.__setattr__(self, "allowed_subdomains_of",
                           tuple(d.lower().strip(".") for d in self.allowed_subdomains_of))
        object.__setattr__(self, "allowed_prefixes", tuple(_with_slash(p) for p in self.allowed_prefixes))
        object.__setattr__(self, "excluded_prefixes", tuple(_with_slash(p) for p in self.excluded_prefixes))
        object.__setattr__(self, "excluded_query_keys", tuple(k.lower() for k in self.excluded_query_keys))
        if not self.allowed_hosts and not self.allowed_subdomains_of and not self.allow_external:
            raise ValueError("scope: allowed_hosts (or allowed_subdomains_of) is required")
        for cap in ("max_listing_pages", "max_detail_items", "max_discovered_items"):
            if getattr(self, cap) < 0:
                raise ValueError(f"scope: {cap} must be >= 0")

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ScopeConfig":
        data = dict(data or {})
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"scope: unknown keys {sorted(unknown)}")
        for key in ("allowed_hosts", "allowed_subdomains_of", "allowed_prefixes", "excluded_prefixes",
                    "excluded_query_keys"):
            if key in data:
                data[key] = tuple(data[key])
        return cls(**data)

    def host_allowed(self, host: str) -> bool:
        host = (host or "").lower().rstrip(".")
        if host in self.allowed_hosts:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed_subdomains_of)


def _path_matches(path: str, prefix: str) -> bool:
    """Exclusion match: '/search/' matches '/search/x' and '/search' itself, never '/search-tips'."""
    return path.startswith(prefix) or path + "/" == prefix


def scope_decision(url: str, cfg: ScopeConfig) -> tuple[bool, str]:
    """(allowed, reason). `url` must already be canonical (resolve_item_url)."""
    parts = urlsplit(url or "")
    scheme = parts.scheme.lower()
    if scheme not in WEB_SCHEMES:
        return False, f"non-web scheme: {scheme or 'none'}:"
    host = (parts.hostname or "").lower()
    if not host:
        return False, "no host"
    if not cfg.host_allowed(host):
        if not cfg.allow_external:
            return False, f"external host: {host}"
        external = True
    else:
        external = False
    path = parts.path or "/"
    for prefix in cfg.excluded_prefixes:
        if _path_matches(path, prefix):
            return False, f"excluded prefix: {prefix}"
    keys = sorted({k.lower() for k, _ in parse_qsl(parts.query, keep_blank_values=True)} & set(cfg.excluded_query_keys))
    if keys:
        return False, f"excluded query key (calendar/search/filter explosion): {', '.join(keys)}"
    if external:
        return True, f"external host allowed by allow_external: {host}"
    # Strict prefix match here: "/events/" admits "/events/x" but not the bare "/events" listing page itself.
    matched = next((p for p in cfg.allowed_prefixes if path.startswith(p)), None)
    if matched is None:
        return False, f"outside allowed prefixes: {path}"
    if path.lower().endswith(".pdf"):
        return True, f"in scope (PDF under {matched}: routed as pdf_document, never detail-fetched as HTML)"
    return True, f"in scope: {host} {matched}"


def is_allowed_item_url(url: str, cfg: ScopeConfig) -> bool:
    return scope_decision(url, cfg)[0]
