"""Week 3 D2 (focus area: canonical item URLs): what resolve_item_url() guarantees for discovered URLs.

D2: drop the fragment, drop utm_*/fbclid/gclid/mc_cid/mc_eid, lowercase scheme and host, drop :80/:443, and keep the
remaining params SORTED by key (decided in repair R2; assignments/week3/DECISIONS.md D2).
"""

import pytest

from src.urls import resolve_item_url

ITEM = "https://www.iitb.ac.in/event/institute-lecture-taming-turbulence"


@pytest.mark.parametrize("variant", [
    ITEM + "#main-content",
    ITEM + "?utm_source=rss&utm_medium=feed&utm_campaign=oct",
    ITEM + "?fbclid=IwAR0abc",
    ITEM + "?gclid=Cj0K",
    ITEM + "?mc_cid=5a1b&mc_eid=77c",
    "HTTPS://WWW.IITB.AC.IN/event/institute-lecture-taming-turbulence",
    "https://www.iitb.ac.in:443/event/institute-lecture-taming-turbulence",
    "  " + ITEM + "?utm_source=x#top  ",
])
def test_tracking_fragment_case_and_port_variants_collapse(variant):
    assert resolve_item_url(variant, "") == ITEM


def test_default_http_port_dropped_but_other_ports_kept():
    assert resolve_item_url("http://www.iitb.ac.in:80/event/x", "") == "http://www.iitb.ac.in/event/x"
    assert resolve_item_url("http://127.0.0.1:8765/event/x", "") == "http://127.0.0.1:8765/event/x"


def test_path_case_is_kept():
    assert resolve_item_url("https://WWW.IITB.AC.IN/Event/X", "") == "https://www.iitb.ac.in/Event/X"


def test_semantic_params_are_kept():
    assert resolve_item_url(ITEM + "?page=2&utm_source=x", "") == ITEM + "?page=2"


def test_remaining_params_are_sorted_into_one_canonical_order():
    """D2 (decided in repair R2): remaining query params are sorted by key. Two spellings of the same query are one
    item, so order can never split an item into two keys."""
    canonical = "https://www.iitb.ac.in/events?page=2&view=list"
    assert resolve_item_url("https://www.iitb.ac.in/events?view=list&page=2", "") == canonical
    assert resolve_item_url("https://www.iitb.ac.in/events?page=2&view=list", "") == canonical
    assert resolve_item_url("https://www.iitb.ac.in/events?view=list&utm_source=x&page=2#top", "") == canonical
