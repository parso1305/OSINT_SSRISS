"""Week 3 Section 5: entity extraction on 20 event fixtures (18 real IIT Bombay detail pages + 2 synthetic variants
of a real page). Extract only what the page states: labelled roles, affiliations written next to the name."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from sources.iit_bombay_events import LABELS, parse_event_detail
from src.entities import (collapse, extract_mentions, organizations_field, parse_person, speakers_field,
                          split_honorific, split_people)

DETAIL = Path(__file__).resolve().parent.parent / "fixtures" / "week3" / "iitb_events" / "detail"
FIXTURES = [
    # REAL (saved 2026-10-16 in Section 0, or the controlled live sample of 2026-10-17)
    "5th-japan-india-forum", "institute-colloquium-global-health-research-india-world",
    "institute-colloquium-tale-two-symmetries", "institute-colloquium-understanding-glue-binds-us-all",
    "institute-lecture-innovations-jet-noise-reduction-technology", "institute-lecture-living-genome-active-material",
    "institute-lecture-movement-polymer-molecules-under-electric-fields-and-relevance-rechargeable",
    "institute-lecture-nu-frontier-current-challenges-and-opportunities-neutrino-physics",
    "institute-lecture-saral-ai-democratising-scholarly-work-transforming-accessible-multilingual",
    "institute-lecture-taming-turbulence", "international-conference-quantum-dynamics",
    "lecture-future-cern-and-outstanding-questions-particle-physics",
    "lecture-strong-interactions-exotic-emergent-particles-and-future-quantum-technologies",
    "lecture-village-development-through-public-participation-water-conservation-forest-protection",
    "moving-towards-inclusive-neuro-digital-world-mindworkshop", "national-engineers-day-1",
    "seminar-cum-workshop-staggered-difference-differences-designs", "van-mahotsav-2026",
    # SYNTHETIC (scripts/make_week3_synthetic_fixtures.py: real page, Speaker paragraph replaced)
    "synthetic-two-speakers-and-organizers", "synthetic-chair-moderator-host",
]


def parsed(slug: str) -> dict:
    return parse_event_detail((DETAIL / f"{slug}.html").read_text(encoding="utf-8"), f"https://www.iitb.ac.in/event/{slug}")


def visible_text(slug: str) -> str:
    return collapse(BeautifulSoup((DETAIL / f"{slug}.html").read_text(encoding="utf-8"), "html.parser").get_text(" "))


def test_fixture_set_is_10_to_20_events():
    assert 10 <= len(FIXTURES) <= 20 and all((DETAIL / f"{s}.html").exists() for s in FIXTURES)


@pytest.mark.parametrize("slug", FIXTURES)
def test_every_entity_has_source_text_that_appears_verbatim_in_its_fixture(slug):
    result = parsed(slug)
    text = visible_text(slug)
    for mention in result["people"] + result["orgs"]:
        assert mention.source_text, mention
        assert mention.source_text in text, mention.source_text


def test_two_people_in_one_field():
    people = parsed("synthetic-two-speakers-and-organizers")["people"]
    assert [(p.honorific, p.name, p.role, p.affiliation_raw) for p in people] == [
        ("Prof.", "Ananya Rao", "speaker", "Centre for Policy Research"),
        ("Dr.", "Ravi Sen", "speaker", "Department of Economics, IIT Bombay")]
    host = parsed("synthetic-chair-moderator-host")["people"]
    assert [(p.name, p.role) for p in host if p.role == "host"] == [("Meera Iyer", "host"), ("Karan Shah", "host")]


@pytest.mark.parametrize("slug", ["van-mahotsav-2026", "5th-japan-india-forum", "international-conference-quantum-dynamics"])
def test_event_with_no_speaker(slug):
    result = parsed(slug)
    assert result["people"] == [] and result["fields"]["speakers"] == []


def test_unlabelled_speaker_like_text_extracts_nothing():
    # REAL: "About the Speaker: Dr. Gagandeep Kang is a renowned ..." with no "Speaker:" line
    colloquium = parsed("institute-colloquium-global-health-research-india-world")
    assert "Dr. Gagandeep Kang" in visible_text("institute-colloquium-global-health-research-india-world")
    assert colloquium["people"] == []
    # REAL: "Mr. S. N. Subrahmanyan, Chairman and Managing Director, Larsen and Toubro Ltd., will be the Chief Guest"
    assert parsed("national-engineers-day-1")["people"] == []
    # SYNTHETIC: a sentence naming a person, not a labelled line
    assert all("Unlabelled" not in p.name for p in parsed("synthetic-chair-moderator-host")["people"])


@pytest.mark.parametrize("slug, honorific, name", [
    ("institute-lecture-nu-frontier-current-challenges-and-opportunities-neutrino-physics", "Prof. Dr.", "Joachim Kopp"),
    ("lecture-village-development-through-public-participation-water-conservation-forest-protection", "Shri", "Chaitram Pawar"),
    ("institute-lecture-innovations-jet-noise-reduction-technology", "Dr.", "Vinod G. Mengle"),
    ("synthetic-chair-moderator-host", "Prof", "Ananya Rao"),          # "Prof" without a period
])
def test_honorific_moved_to_its_own_field(slug, honorific, name):
    assert (honorific, name) in [(p.honorific, p.name) for p in parsed(slug)["people"]]


def test_honorific_split_never_eats_a_name():
    assert split_honorific("Professor Kumar") == (None, "Professor Kumar")
    assert split_honorific("Drishti Rao") == (None, "Drishti Rao")
    assert split_honorific("Shrinivas Rao") == (None, "Shrinivas Rao")
    assert split_honorific("Smt. Meera Iyer") == ("Smt.", "Meera Iyer")


def test_organizer_lines():
    result = parsed("synthetic-two-speakers-and-organizers")
    assert [(o.name, o.role, o.org_type, o.parent_raw, o.acronym) for o in result["orgs"]] == [
        ("Department of Economics", "organizer", "department", "IIT Bombay", None),
        ("Centre for Policy Research", "organizer", "centre", None, "CPR"),
        ("Department of Science and Technology", "co-organizer", "department", None, None)]   # 'and' not split
    # REAL: "Organizer: Prof. Azizuddin Khan — khanaziz@iitb.ac.in Psychophysiology Laboratory, ..." is a PERSON
    mind = parsed("moving-towards-inclusive-neuro-digital-world-mindworkshop")
    assert [(p.name, p.role) for p in mind["people"]] == [("Azizuddin Khan", "organizer")]
    assert "@" not in mind["people"][0].affiliation_raw and mind["orgs"] == []


def test_affiliation_only_when_written_next_to_the_name():
    chair = next(p for p in parsed("synthetic-chair-moderator-host")["people"] if p.role == "chair")
    assert chair.affiliation_raw is None               # nothing written next to it: nothing inferred
    taming = parsed("institute-lecture-taming-turbulence")["people"][0]
    assert taming.affiliation_raw == "Professor of Mechanical Engineering, Stanford University, California, USA"


def test_records_fields_come_from_the_same_extraction():
    for slug in FIXTURES:
        result = parsed(slug)
        assert result["fields"]["speakers"] == speakers_field(result["people"])
        assert result["fields"]["organizations"] == organizations_field(result["orgs"])
    assert parsed("institute-lecture-taming-turbulence")["fields"]["speakers"] == [
        {"name": "Beverley J. McKeon",
         "affiliation": "Professor of Mechanical Engineering, Stanford University, California, USA"}]


def test_real_speaker_counts_across_the_fixture_set():
    """12 of the 18 real pages label a speaker, 1 more labels an organizer (a person); the 2 synthetic pages add
    the multi-person, organization-line and chair/moderator/host cases."""
    real = FIXTURES[:18]
    assert sum(bool([p for p in parsed(s)["people"] if p.role == "speaker"]) for s in real) == 12
    assert sum(bool(parsed(s)["people"]) for s in real) == 13      # + the MIND workshop's labelled organizer


# -- splitting rules (unit level) -------------------------------------------------------------------------------

@pytest.mark.parametrize("value, people", [
    ("Dr. X Sharma, Centre for Y", ["Dr. X Sharma, Centre for Y"]),                      # comma = affiliation
    ("Ananya Rao and Ravi Sen", ["Ananya Rao", "Ravi Sen"]),                              # bare names
    ("Ananya Rao & Ravi Sen; Meera Iyer", ["Ananya Rao", "Ravi Sen", "Meera Iyer"]),
    ("Prof. A Rao, IITB\nDr. B Sen, TISS", ["Prof. A Rao, IITB", "Dr. B Sen, TISS"]),     # line break
    ("Shri Chaitram Pawar, Social Reformer & Environmentalist; Padma Shri Awardee",
     ["Shri Chaitram Pawar, Social Reformer & Environmentalist; Padma Shri Awardee"]),    # REAL: one person
    ("Dr. Vinod G. Mengle, Founder and CEO of Aero Insights, LLC; Formerly with Boeing",
     ["Dr. Vinod G. Mengle, Founder and CEO of Aero Insights, LLC; Formerly with Boeing"]),
])
def test_split_people(value, people):
    assert split_people(value) == people


def test_parse_person_name_ends_at_dash_or_comma():
    p = parse_person("Prof. A. Khan — a.khan@example.org Psychophysiology Laboratory", "organizer", "src")
    assert (p.honorific, p.name, p.affiliation_raw) == ("Prof.", "A. Khan", "Psychophysiology Laboratory")


def test_labels_must_match_from_the_start_of_the_line():
    people, _ = extract_mentions(["About the Speaker: Dr. Q is a scientist", "A profile of the speaker: x",
                                  "Speaker: Dr. Q, Lab"], LABELS)
    assert [(p.name, p.source_text) for p in people] == [("Q", "Speaker: Dr. Q, Lab")]
