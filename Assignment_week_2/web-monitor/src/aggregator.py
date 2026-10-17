"""Central-aggregator pipeline (Week 3 Section 10) and its entity write step (Sections 6-7).

write_entities(conn, links, replace) runs inside the run's single storage transaction (extra_writes): it writes
each item's people / organization links and then queues every possible match for review
(entity_alias_candidates). Nothing is ever merged.
"""

from typing import Any, Iterable, Optional

from src.entities import org_match, person_match, review_pairs
from src.router import classify_with_reason
from src.storage import add_alias_candidates, list_entities, write_entity_links


def write_entities(conn: Any, links: dict, replace: Iterable[str] = ()) -> dict:
    """links = {item_url: (people_rows, org_rows)} (src.entities.mention_rows). Items in `replace` had their detail
    page parsed this run: their links are replaced; the others only gain missing links (storage.write_entity_links).
    Returns {"people_links", "organization_links", "review_candidates"} added this run."""
    replace = set(replace)
    added = {"people_links": 0, "organization_links": 0, "review_candidates": 0}
    for url, (people, orgs) in links.items():
        for key, n in write_entity_links(conn, url, people, orgs, replace=url in replace).items():
            added[key] += n
    added["review_candidates"] += add_alias_candidates(conn, "person",
                                                       review_pairs(list_entities(conn, "person"), person_match))
    added["review_candidates"] += add_alias_candidates(conn, "organization",
                                                       review_pairs(list_entities(conn, "organization"), org_match))
    return added


# -- routing (Section 8) ----------------------------------------------------------------------------------------

def route_candidate(candidate, router_cfg: Optional[dict], content_type: Optional[str] = None) -> tuple[str, str]:
    """(content_class, class_reason) for a discovery candidate; out-of-scope candidates are still classified so the
    discovered_items row says what they were."""
    return classify_with_reason(candidate.record, content_type=content_type,
                                category_label=candidate.category_label, cfg=router_cfg)


def discovered_item_row(candidate, content_class: str, class_reason: str) -> dict:
    """One discovered_items row (storage.upsert_discovered_items) for a candidate and its routing decision."""
    record = candidate.record
    return {"discovered_url": record.discovered_url, "source_name": record.source_name,
            "discovery_methods": list(candidate.discovery_methods), "discovered_title": record.discovered_title,
            "source_timestamp": record.source_timestamp, "source_timestamp_raw": record.source_timestamp_raw,
            "first_discovered_at": record.discovered_at, "last_discovered_at": record.discovered_at,
            "in_scope": candidate.in_scope, "scope_reason": candidate.scope_reason,
            "content_class": content_class, "class_reason": class_reason}
