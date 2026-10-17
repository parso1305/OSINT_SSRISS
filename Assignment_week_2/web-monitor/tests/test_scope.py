"""Week 3 Section 2: URL scope filter. One case per row of assignments/week3/02_scope/scope_cases.md.

The scope config is the real iit_bombay_events entry from config/sources.json. Raw URLs are canonicalized with
resolve_item_url() first, exactly as the aggregator does.
"""

import re
from pathlib import Path

import pytest

from src.config import load_source_configs
from src.scope import ScopeConfig, is_allowed_item_url, scope_decision
from src.urls import resolve_item_url

ROOT = Path(__file__).resolve().parent.parent
CFG = ScopeConfig.from_dict(load_source_configs()["iit_bombay_events"].scope)
EVENT = "https://www.iitb.ac.in/event/institute-lecture-taming-turbulence"

# (case, raw URL, allowed?, reason must contain)
CASES = [
    ("valid event detail", EVENT, True, "in scope: www.iitb.ac.in /event/"),
    ("valid news detail", "https://www.iitb.ac.in/breaking-news/ground-breaking-ceremony-biodiversity-lab-soneri-baug",
     True, "in scope: www.iitb.ac.in /breaking-news/"),
    ("external registration site", "https://www.iitbombay.org/e/ieor-alumni-meet-2026", False,
     "external host: www.iitbombay.org"),
    ("social media link", "https://www.facebook.com/iitbombay", False, "external host: www.facebook.com"),
    ("PDF", "https://www.iitb.ac.in/sites/default/files/2026-10/institute-lecture-brochure.pdf", True,
     "PDF under /sites/default/files/"),
    ("login URL", "https://www.iitb.ac.in/user/login?destination=/events", False, "excluded prefix: /user/"),
    ("search URL", "https://www.iitb.ac.in/iitb-search?search_api_fulltext=lecture", False,
     "excluded prefix: /iitb-search/"),
    ("duplicate with #fragment", EVENT + "#main-content", True, "in scope: www.iitb.ac.in /event/"),
    ("same page with tracking param", EVENT + "?utm_source=newsletter&utm_medium=email", True,
     "in scope: www.iitb.ac.in /event/"),
    ("calendar ?month= variant", "https://www.iitb.ac.in/events/calendar?month=2026-11&view=month", False,
     "excluded query key (calendar/search/filter explosion): month, view"),
    ("lookalike host", "https://notiitb.ac.in/event/institute-lecture-taming-turbulence", False,
     "external host: notiitb.ac.in"),
    ("/events-archive/ vs /events/", "https://www.iitb.ac.in/events-archive/2019", False,
     "outside allowed prefixes: /events-archive/2019"),
    ("mailto:", "mailto:events@iitb.ac.in", False, "non-web scheme: mailto:"),
]


def canonical(raw: str) -> str:
    # mailto: and friends resolve to "": decide on the raw URL then (the scheme rule rejects it either way).
    return resolve_item_url(raw, "") or raw


@pytest.mark.parametrize("case, raw, allowed, reason", CASES, ids=[c[0] for c in CASES])
def test_scope_case(case, raw, allowed, reason):
    decision = scope_decision(canonical(raw), CFG)
    assert decision == (allowed, decision[1]) and reason in decision[1], decision
    assert is_allowed_item_url(canonical(raw), CFG) is allowed


def test_duplicates_collapse_to_the_same_canonical_url_before_scope():
    assert canonical(EVENT + "#main-content") == canonical(EVENT + "?utm_source=newsletter") == EVENT


def test_events_prefix_never_matches_events_archive_and_bare_listing_is_not_an_item():
    assert is_allowed_item_url("https://www.iitb.ac.in/events/ministry-education-week", CFG)
    assert not is_allowed_item_url("https://www.iitb.ac.in/events-archive/2019", CFG)
    assert not is_allowed_item_url("https://www.iitb.ac.in/events-ministry-education", CFG)
    assert not is_allowed_item_url("https://www.iitb.ac.in/events", CFG)     # the listing page itself


def test_hosts_match_exactly_and_subdomains_only_on_a_dot_boundary():
    assert not is_allowed_item_url("https://www.iitb.ac.in.evil.example/event/x", CFG)
    assert not is_allowed_item_url("https://www.cse.iitb.ac.in/event/x", CFG)        # not listed for this source
    sub = ScopeConfig(allowed_hosts=("www.iitb.ac.in",), allowed_subdomains_of=("iitb.ac.in",),
                      allowed_prefixes=("/event/",))
    assert is_allowed_item_url("https://www.cse.iitb.ac.in/event/x", sub)
    assert not is_allowed_item_url("https://notiitb.ac.in/event/x", sub)
    assert not is_allowed_item_url("https://iitb.ac.in.evil.example/event/x", sub)


@pytest.mark.parametrize("raw", ["javascript:void(0)", "tel:+912225722545", "data:text/html,hi",
                                 "ftp://www.iitb.ac.in/event/x"])
def test_non_web_schemes_rejected(raw):
    assert scope_decision(raw, CFG) == (False, f"non-web scheme: {raw.split(':')[0]}:")


def test_allow_external_admits_other_hosts_but_still_applies_exclusions():
    ext = ScopeConfig(allowed_hosts=("www.iitb.ac.in",), allowed_prefixes=("/event/",), allow_external=True,
                      excluded_prefixes=("/user/",))
    assert scope_decision("https://www.iitbombay.org/e/x", ext)[0]
    assert not scope_decision("https://www.iitbombay.org/user/login", ext)[0]


def test_prefixes_are_stored_with_a_trailing_slash():
    cfg = ScopeConfig.from_dict({"allowed_hosts": ["WWW.IITB.AC.IN"], "allowed_prefixes": ["/events"],
                                 "excluded_prefixes": ["user"]})
    assert cfg.allowed_prefixes == ("/events/",) and cfg.excluded_prefixes == ("/user/",)
    assert cfg.allowed_hosts == ("www.iitb.ac.in",)


def test_scope_config_rejects_unknown_keys_and_missing_hosts():
    with pytest.raises(ValueError, match="unknown keys"):
        ScopeConfig.from_dict({"allowed_hosts": ["x.org"], "max_pages": 3})
    with pytest.raises(ValueError, match="allowed_hosts"):
        ScopeConfig.from_dict({})


def test_every_scope_cases_md_row_has_a_test():
    doc = (ROOT / "assignments" / "week3" / "02_scope" / "scope_cases.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| (.+?) \| `([^`]+)` \| (Yes|No) \|", doc, re.M)
    assert [(case, url, allowed == "Yes") for _, case, url, allowed in rows] == [(c, u, a) for c, u, a, _ in CASES]
