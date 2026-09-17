"""URL resolution and canonicalization utilities."""

from urllib.parse import urljoin, urlparse, urlunparse


def resolve_url(base_url: str, relative_or_absolute_url: str) -> str:
    """
    Resolves a relative URL against a base URL and returns a canonical absolute URL.
    Handles leading/trailing whitespace, scheme preservation, and query/fragment cleanup.
    """
    if not relative_or_absolute_url:
        return ""
    
    clean_url = relative_or_absolute_url.strip()
    joined = urljoin(base_url.strip(), clean_url)
    
    parsed = urlparse(joined)
    # Ensure scheme and netloc are present and lowercase
    canonical = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        parsed.query,
        ""  # Strip internal page anchors for canonical item URLs
    ))
    return canonical
