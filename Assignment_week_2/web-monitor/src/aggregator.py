"""Central-aggregator pipeline (Week 3 Section 10) and its entity write step (Sections 6-7).

write_entities(conn, links, replace) runs inside the run's single storage transaction (extra_writes): it writes
each item's people / organization links and then queues every possible match for review
(entity_alias_candidates). Nothing is ever merged.
"""

from typing import Any, Iterable

from src.entities import org_match, person_match, review_pairs
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
