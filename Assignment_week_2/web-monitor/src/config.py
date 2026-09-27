"""Source configuration: loads config/sources.json into SourceConfig objects.

Adding a source = one adapter module (sources/<name>.py) + one entry in config/sources.json.
Optional capabilities (pagination, detail enrichment) are switched on here, never in the runner.
"""

import importlib
import json
from dataclasses import dataclass, fields
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Union
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "sources.json"

# Adapter contract: parse_listing and normalize are required; parse_detail when supports_detail.
REQUIRED_ADAPTER_FUNCTIONS = ("parse_listing", "normalize")


@dataclass
class SourceConfig:
    source_id: str
    institution: str
    adapter: Union[str, ModuleType, Any]  # module path, or a module-like object (tests)
    listing_url: str
    content_type: str = "event"
    organizer: Optional[str] = None
    enabled: bool = True
    supports_pagination: bool = False
    max_pages: int = 1
    supports_detail: bool = False
    detail_limit: int = 0
    request_delay_s: float = 1.0
    timeout_s: float = 10.0
    interval_minutes: Optional[float] = None  # scheduler: run when this long since the last successful run
    retry_minutes: float = 60.0               # scheduler: first retry after a failed run; doubles per consecutive
                                              # failure, capped at interval_minutes
    lock_max_age_minutes: float = 120.0       # scheduler: older locks are stale
    allow_empty_listing: bool = False         # False: HTTP 200 with 0 parsed items fails the run
    ca_bundle: Optional[str] = None           # PEM file for TLS verification (relative to the project root);
                                              # None = default trust store. Verification is never disabled.

    def __post_init__(self) -> None:
        parts = urlsplit(self.listing_url.strip()) if isinstance(self.listing_url, str) else None
        if not parts or parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            raise ValueError(f"{self.source_id}: listing_url must be an absolute http(s) URL, got {self.listing_url!r}")
        if self.ca_bundle:
            path = Path(self.ca_bundle)
            path = path if path.is_absolute() else PROJECT_ROOT / path
            if not path.is_file():
                raise ValueError(f"{self.source_id}: ca_bundle not found: {path}")
            self.ca_bundle = str(path)
        if self.max_pages < 1:
            raise ValueError(f"{self.source_id}: max_pages must be >= 1")
        if self.detail_limit < 0:
            raise ValueError(f"{self.source_id}: detail_limit must be >= 0")
        if self.timeout_s <= 0:
            raise ValueError(f"{self.source_id}: timeout_s must be > 0")
        if self.interval_minutes is not None and self.interval_minutes <= 0:
            raise ValueError(f"{self.source_id}: interval_minutes must be > 0")
        if self.retry_minutes <= 0:
            raise ValueError(f"{self.source_id}: retry_minutes must be > 0")
        if self.lock_max_age_minutes <= 0:
            raise ValueError(f"{self.source_id}: lock_max_age_minutes must be > 0")


def load_adapter(adapter: Union[str, ModuleType, Any], supports_detail: bool = False) -> Any:
    """Imports an adapter by module path (or accepts a module-like object) and checks its contract."""
    module = importlib.import_module(adapter) if isinstance(adapter, str) else adapter
    required = REQUIRED_ADAPTER_FUNCTIONS + (("parse_detail",) if supports_detail else ())
    missing = [name for name in required if not callable(getattr(module, name, None))]
    if missing:
        raise TypeError(f"Adapter {getattr(module, '__name__', module)!r} is missing: {', '.join(missing)}")
    return module


def load_source_configs(path: Union[str, Path] = DEFAULT_CONFIG_PATH) -> dict[str, SourceConfig]:
    """Reads the JSON config file; returns {source_id: SourceConfig}. Unknown keys are rejected."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    allowed = {f.name for f in fields(SourceConfig)}
    configs: dict[str, SourceConfig] = {}
    for entry in data["sources"]:
        unknown = set(entry) - allowed
        if unknown:
            raise ValueError(f"Unknown config keys for {entry.get('source_id')}: {sorted(unknown)}")
        config = SourceConfig(**entry)
        if config.source_id in configs:
            raise ValueError(f"Duplicate source_id: {config.source_id}")
        configs[config.source_id] = config
    return configs
