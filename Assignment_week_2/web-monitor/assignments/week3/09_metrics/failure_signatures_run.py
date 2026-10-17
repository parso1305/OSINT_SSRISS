"""Week 3 Section 9: run the aggregator through the real scheduler against healthy and deliberately broken local
fixtures, and print each run's summary. The output is pasted into failure_signatures.md; the same scenarios are
asserted in tests/test_metrics.py.

    venv\\Scripts\\python -m assignments.week3.09_metrics.failure_signatures_run

Offline: scripts/aggregator_fixture_site.py on 127.0.0.1 (no network).
"""

import dataclasses
import io
import logging
import socket
import sys
import tempfile
from pathlib import Path

from scripts.aggregator_fixture_site import AggregatorFixtureSite
from src.config import load_source_configs
from src.logging_config import KeyValueFormatter
from src.scheduler import run_scheduled

SOURCE = "local_aggregator_fixture"
KEEP = ("SOURCE:", "STATUS:", "PAGES_FETCHED:", "ITEMS_DISCOVERED:", "ITEMS_PARSED:", "NEW:", "CHANGED:",
        "UNCHANGED:", "NOT_SEEN_THIS_RUN:", "FAILED:", "PEOPLE_EXTRACTED:", "ORGANIZATIONS_EXTRACTED:",
        "RUN_SUMMARY", "COVERAGE_DROP", "FAILURE ", "DISCOVER ", "DISCOVER_EMPTY", "DISCOVER_FAILURE", "RUN_END")


def configured(site_url: str, methods=("html", "rss")):
    config = load_source_configs()[SOURCE]
    urls = {"html": [site_url + "/"], "rss": [site_url + "/events.rss"]}
    return dataclasses.replace(config, listing_url=site_url + "/", request_delay_s=0, discovery=list(methods),
                               discovery_urls={m: urls[m] for m in methods})


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def scenario(db: str, locks: Path, broken=None, variant: str = "base", port: int = 0,
             methods=("html", "rss")) -> tuple[dict, str]:
    """One scheduled run against the fixture site in the given mode. Returns (scheduler result, log + block text).
    Use the same port for every run against one DB: the port is part of every item URL."""
    stream = io.StringIO()
    logger = logging.getLogger(f"week3_metrics_{id(stream)}")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    real_stdout = sys.stdout
    sys.stdout = stream                           # the summary block is printed; capture it with the log
    try:
        with AggregatorFixtureSite(port=port, variant=variant, broken=broken) as site:
            result = run_scheduled(configured(site.url, methods), db, locks, logger)
    finally:
        sys.stdout = real_stdout
        logger.removeHandler(handler)
    return result, stream.getvalue()


def interesting(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if any(k in line for k in KEEP))


SCENARIOS = [
    # (title, db name, broken mode, discovery methods)
    ("1. healthy run 1 (first run: everything new)", "healthy", None, ("html", "rss")),
    ("2. healthy run 2 (nothing new)", "healthy", None, ("html", "rss")),
    ("3. detail labels renamed: 'Speaker:' -> 'Presenter:' (pages still parse)", "healthy", "speaker_label",
     ("html", "rss")),
    ("4. detail parser broke (article class renamed)", "detail", "detail", ("html",)),
    ("5. listing selector broke (events block class renamed), html discovery", "listing", "listing", ("html",)),
    ("6. same broken listing, html + rss discovery (the feed hides it in the totals)", "listing_rss", "listing",
     ("html", "rss")),
    ("7. HTTP failure (listing answers 503)", "http", "http", ("html",)),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix="week3_metrics_"))
    port = free_port()                       # one site address for the whole sequence: same URLs, same items
    for title, db_name, broken, methods in SCENARIOS:
        _, text = scenario(str(tmp / f"{db_name}.db"), tmp / "locks", broken=broken, port=port, methods=methods)
        lines = [line for line in interesting(text).splitlines() if "DETAIL_FAILURE" not in line]
        failures = text.count("DETAIL_FAILURE")
        if failures:
            lines.insert(0, f"({failures} DETAIL_FAILURE warning lines, one per detail page, omitted here)")
        print(f"===== {title}\n" + "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
