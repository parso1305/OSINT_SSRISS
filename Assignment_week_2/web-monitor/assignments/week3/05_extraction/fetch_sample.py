"""Week 3 Section 5: controlled live sample of IIT Bombay event detail pages, saved as extraction fixtures.

Run once (2026-10-17) because the Section 0 evidence held only 8 detail pages (< 10). Budget: <= 20 requests.
Every request goes through src.fetcher.Fetcher (robots.txt, 15 s timeout, honest User-Agent, FETCH log,
>= 3 s between requests). Pages are saved to fixtures/week3/iitb_events/detail/<slug>.html with a manifest.

    venv\\Scripts\\python -m assignments.week3.05_extraction.fetch_sample
"""

import json
import sys
from pathlib import Path

from src.fetcher import Fetcher, FetchError
from src.logging_config import setup_logger

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "fixtures" / "week3" / "iitb_events" / "detail"
MANIFEST = OUT / "manifest.json"
BASE = "https://www.iitb.ac.in/event/"
# Chosen offline from the saved calendar JSON (00_candidates/evidence/www.iitb.ac.in__events.html): the newest
# lecture / colloquium / seminar / symposium entries not already saved, i.e. the pages most likely to label people.
SLUGS = [
    "lecture-strong-interactions-exotic-emergent-particles-and-future-quantum-technologies",
    "seminar-cum-workshop-staggered-difference-differences-designs",
    "national-symposium-ai-innovation-bfsi-services",
    "institute-lecture-movement-polymer-molecules-under-electric-fields-and-relevance-rechargeable",
    "institute-colloquium-tale-two-symmetries",
    "institute-lecture-living-genome-active-material",
    "institute-colloquium-understanding-glue-binds-us-all",
    "institute-lecture-innovations-jet-noise-reduction-technology",
    "institute-lecture-nu-frontier-current-challenges-and-opportunities-neutrino-physics",
    "lecture-future-cern-and-outstanding-questions-particle-physics",
    "lecture-village-development-through-public-participation-water-conservation-forest-protection",
    "institute-colloquium-global-health-research-india-world",
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"pages": []}
    fetcher = Fetcher(timeout_s=15, delay_s=3.0, ca_bundle=str(ROOT / "certs" / "iitb_ca_bundle.pem"),
                      logger=setup_logger("web_monitor").getChild("fetcher"))
    for slug in SLUGS:
        url = BASE + slug
        try:
            result = fetcher.get(url)
        except FetchError as e:
            print(f"FAILED {url}: {e}")
            if e.status in (403, 429) or "robots" in e.reason:
                print("stopping live work on this host (403/429/robots)")
                break
            continue
        (OUT / f"{slug}.html").write_text(result.text, encoding="utf-8")
        manifest["pages"].append({"url": url, "final_url": result.final_url, "status": result.status,
                                  "content_type": result.content_type, "fetched_at": result.fetched_at,
                                  "file": f"{slug}.html", "origin": "live sample 2026-10-17 (Section 5)"})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"saved {len(manifest['pages'])} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
