"""Entity mentions (Week 3 Sections 5 and 7): people and organizations exactly as a page states them.

Generic and rule-based. No NLP, no inference, no fuzzy matching:
  * a role is assigned only when the page labels it ("Speaker:", "Chair:", "Organized by:", ...). The label
    patterns are the adapter's (sources/<name>.py LABELS); this module only applies them;
  * an affiliation is recorded only when it is written next to the name in the same labelled value;
  * every mention keeps source_text: the labelled line verbatim (whitespace collapsed), so a reviewer can find it;
  * nothing is merged here. Matching across items is name_key() equality (Section 7) plus a review queue.

Splitting a labelled value into people:
  * always on ';' and line breaks, on ' and ' and '&' too, BUT a split point only starts a new person when the text
    after it begins with an explicit honorific (Dr., Prof., Mr., Ms., Mrs., Shri, Smt.), unless the whole value has no
    comma at all (a bare list of names: "Ananya Rao and Ravi Sen"). Affiliations are full of these characters
    ("Social Reformer & Environmentalist; Padma Shri Awardee", "Founder and CEO of ...; Formerly with ...") and a
    comma never separates two people on its own ("Dr. X, Centre for Y" is one name plus an affiliation);
  * within one person: leading honorific(s) -> honorific; the name runs to the first ',', ' — ', ' – ', ' (' or ';';
    the rest is affiliation_raw (email addresses removed: an email is contact data, not an affiliation).
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Optional

HONORIFICS = ("Dr", "Prof", "Mr", "Ms", "Mrs", "Shri", "Smt")
# One or more leading honorifics ("Prof. Dr. Joachim Kopp"); "Professor" / "Dryden" / "Shrinivas" never match.
HONORIFIC_RE = re.compile(r"^((?:(?:Dr|Prof|Mr|Ms|Mrs|Shri|Smt)\.?\s+)+)", re.IGNORECASE)
_STARTS_WITH_HONORIFIC = re.compile(r"^\s*(?:Dr|Prof|Mr|Ms|Mrs|Shri|Smt)\.?\s+[A-Z]", re.IGNORECASE)
_PERSON_SPLIT_RE = re.compile(r"\s*(?:;|\n|\s+and\s+|\s*&\s*)\s*")
_NAME_END_RE = re.compile(r"\s*(?:,|\s—\s|\s–\s|\s-\s|\s\(|;)\s*")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ORG_HEADS = r"(?:the\s+)?(?:Department|Dept\.?|Centre|Center|School|Institute|Laboratory|Lab|Society|Office|Cell|" \
             r"University|College|Foundation|Agency|Division|Group|Council|Ministry|Association|Club)\b"
_ORG_SPLIT_RE = re.compile(r"\s*(?:;|\n)\s*|\s+(?:and|&)\s+(?=" + _ORG_HEADS + ")", re.IGNORECASE)
_ACRONYM_DEF_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<acronym>[A-Z][A-Z0-9&.-]{1,15})\)$")
_ORG_TYPES = (("department", r"\b(?:Department|Dept)\b"), ("centre", r"\b(?:Centre|Center)\b"),
              ("school", r"\bSchool\b"), ("laboratory", r"\b(?:Laboratory|Lab)\b"),
              ("institution", r"\b(?:University|Institute|College)\b"))

ROLES = ("speaker", "chair", "moderator", "host", "organizer", "co-organizer")


@dataclass(frozen=True)
class PersonMention:
    name: str
    honorific: Optional[str]
    role: str
    affiliation_raw: Optional[str]
    profile_url: Optional[str]
    source_text: str


@dataclass(frozen=True)
class OrgMention:
    name: str
    role: str
    org_type: Optional[str]
    parent_raw: Optional[str]
    url: Optional[str]
    source_text: str
    acronym: Optional[str] = None    # only when the same value defines it: "Centre for Policy Research (CPR)"


def collapse(text: str) -> str:
    return " ".join((text or "").split())


# -- labelled lines ---------------------------------------------------------------------------------------------

def labelled_values(lines: Iterable[str], labels: dict) -> list[tuple]:
    """[(role, label, value, source_text)] for lines that START with one of the adapter's labels and a colon.

    labels = {role: ["Speaker", "Speakers", ...]}. Matching is case-insensitive on the whole label, so "About the
    Speaker:" never matches "Speaker". Line breaks inside a line are kept in `value` (they separate people);
    source_text is the line with whitespace collapsed (that is how it appears in the page's visible text).
    """
    patterns = []
    for role, names in labels.items():
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}; expected one of {ROLES}")
        for name in sorted(names, key=len, reverse=True):     # "Co-organized by" before "Organized by"
            patterns.append((role, name, re.compile(rf"^\s*{re.escape(name)}\s*:\s*(?P<value>.+)$", re.I | re.S)))
    found = []
    for line in lines:
        for role, name, pattern in patterns:
            m = pattern.match(line)
            if m and m.group("value").strip():
                found.append((role, name, m.group("value").strip(), collapse(line)))
                break
    return found


def block_lines(node) -> list[str]:
    """Visible text of each block element (p, li, h*, dd, td, leaf div) under a BeautifulSoup node, one string per
    block, with <br> kept as a line break. Nested blocks are not double-counted."""
    blocks = []
    for element in node.find_all(["p", "li", "h2", "h3", "h4", "h5", "dd", "dt", "td", "div"]):
        if element.find(["p", "li", "div", "td"]):
            continue                                            # a container: its children are the blocks
        for br in element.find_all("br"):
            br.replace_with("\n")
        text = "\n".join(collapse(part) for part in element.get_text(" ").split("\n"))
        text = "\n".join(part for part in text.split("\n") if part)
        if text:
            blocks.append(text)
    return blocks


# -- people -----------------------------------------------------------------------------------------------------

def starts_with_honorific(text: str) -> bool:
    return bool(_STARTS_WITH_HONORIFIC.match(text or ""))


def split_honorific(text: str) -> tuple[Optional[str], str]:
    """'Prof. Dr. Joachim Kopp' -> ('Prof. Dr.', 'Joachim Kopp'); 'Ananya Rao' -> (None, 'Ananya Rao')."""
    text = collapse(text)
    m = HONORIFIC_RE.match(text)
    if not m:
        return None, text
    return collapse(m.group(1)), text[m.end():].strip()


def split_people(value: str) -> list[str]:
    """One labelled value -> one string per person (rules in the module docstring)."""
    value = value.strip()
    parts = [p for p in _PERSON_SPLIT_RE.split(value) if p and p.strip()]
    if "," not in value:
        return [collapse(p) for p in parts]
    people: list[str] = []
    for seps_and_part in _split_keep_separators(value):
        if people and not starts_with_honorific(seps_and_part[1]):
            people[-1] = people[-1] + seps_and_part[0] + seps_and_part[1]   # continuation of the affiliation
        else:
            people.append(seps_and_part[1])
    return [collapse(p) for p in people if collapse(p)]


def _split_keep_separators(value: str) -> list[tuple[str, str]]:
    """[(separator_before, part)] so a continuation can be glued back verbatim."""
    out, last, sep = [], 0, ""
    for m in _PERSON_SPLIT_RE.finditer(value):
        out.append((sep, value[last:m.start()]))
        sep, last = m.group(0), m.end()
    out.append((sep, value[last:]))
    return [(s, p) for s, p in out if p.strip()]


def parse_person(text: str, role: str, source_text: str, profile_url: Optional[str] = None) -> Optional[PersonMention]:
    honorific, rest = split_honorific(text)
    m = _NAME_END_RE.search(rest)
    name, affiliation = (rest[:m.start()], rest[m.end():]) if m else (rest, "")
    name = collapse(name).strip(" ,:;")   # periods kept: "Ananya R." and "A. Rao" are written that way
    affiliation = collapse(_EMAIL_RE.sub("", affiliation)).strip(" ,;—–-") or None
    if not name or not re.search(r"[A-Za-z]", name):
        return None
    return PersonMention(name=name, honorific=honorific, role=role, affiliation_raw=affiliation,
                         profile_url=profile_url, source_text=source_text)


# -- organizations ----------------------------------------------------------------------------------------------

def org_type_of(name: str) -> Optional[str]:
    """Structural type from the name's own head word only (Department, Centre, ...); None when it has none."""
    for org_type, pattern in _ORG_TYPES:
        if re.search(pattern, name):
            return org_type
    return None


def split_orgs(value: str) -> list[str]:
    """';' / line breaks always; ' and ' / '&' only before another organization head word, so
    'Department of Science and Technology' stays one organization."""
    return [collapse(p) for p in _ORG_SPLIT_RE.split(value) if p and collapse(p)]


def parse_org(text: str, role: str, source_text: str, url: Optional[str] = None) -> Optional[OrgMention]:
    """'Department of Economics, Example University' -> name 'Department of Economics', parent_raw 'Example University'.
    'Centre for Policy Research (CPR)' -> name 'Centre for Policy Research', acronym 'CPR' (defined right here)."""
    text = collapse(text).strip(" .;")
    name, _, parent = text.partition(", ")
    name = name.strip()
    acronym = None
    m = _ACRONYM_DEF_RE.match(name)
    if m:
        name, acronym = m.group("name").strip(), m.group("acronym")
    if not name:
        return None
    return OrgMention(name=name, role=role, org_type=org_type_of(name), parent_raw=parent.strip() or None, url=url,
                      source_text=source_text, acronym=acronym)


# -- extraction -------------------------------------------------------------------------------------------------

def extract_mentions(lines: Iterable[str], labels: dict) -> tuple[list[PersonMention], list[OrgMention]]:
    """People and organizations from labelled lines.

    speaker / chair / moderator / host values are people. organizer / co-organizer values are people when they
    start with an honorific ("Organizer: Prof. A. Khan") and organizations otherwise ("Organized by: Department of
    Economics"). Duplicates (same name and role in one item) are kept once.
    """
    people: list[PersonMention] = []
    orgs: list[OrgMention] = []
    for role, _label, value, source_text in labelled_values(lines, labels):
        if role in ("organizer", "co-organizer") and not starts_with_honorific(value):
            for part in split_orgs(value):
                org = parse_org(part, role, source_text)
                if org and (org.name, org.role) not in {(o.name, o.role) for o in orgs}:
                    orgs.append(org)
            continue
        for part in split_people(value):
            person = parse_person(part, role, source_text)
            if person and (name_key(person.name), person.role) not in {(name_key(p.name), p.role) for p in people}:
                people.append(person)
    return people, resolve_page_acronyms(orgs)


def speakers_field(people: Iterable[PersonMention]) -> list[dict]:
    """records.speakers from the same extraction: [{"name", "affiliation"}] (Week 2 shape), speakers only."""
    return [{"name": p.name, "affiliation": p.affiliation_raw} for p in people if p.role == "speaker"]


def organizations_field(orgs: Iterable[OrgMention]) -> list[str]:
    """records.organizations from the same extraction: organizer / co-organizer organization names."""
    names: list[str] = []
    for org in orgs:
        if org.role in ("organizer", "co-organizer") and org.name not in names:
            names.append(org.name)
    return names


# -- identity key (Section 7) -----------------------------------------------------------------------------------

_DECORATIVE_RE = re.compile(r"[.,\"'“”‘’`]")


def name_key(name: str) -> str:
    """The ONLY normalization used to decide that two names are the same entity (people.normalized_name,
    organizations.normalized_name). Strip, NFKC, casefold, remove decorative punctuation (periods after initials,
    stray commas and quotes), collapse whitespace. It never drops initials, reorders tokens, drops a surname,
    expands an abbreviation or fuzzy-matches: 'A. Rao' -> 'a rao' and 'Ananya Rao' -> 'ananya rao' stay different.
    The honorific is removed BEFORE keying (it is stored separately): callers pass the name without it."""
    text = unicodedata.normalize("NFKC", name or "").casefold()
    text = _DECORATIVE_RE.sub(" ", text)
    return " ".join(text.split())


# -- rows for storage (Section 6) -------------------------------------------------------------------------------

def resolve_page_acronyms(orgs: list[OrgMention]) -> list[OrgMention]:
    """A bare acronym is an alias ONLY on the page that defines it ("Centre for Policy Research (CPR)"): there,
    a mention named "CPR" is the defined organization. On any other page a bare "CPR" stays "CPR" (Section 7)."""
    defined = {o.acronym: o.name for o in orgs if o.acronym}
    resolved = []
    for org in orgs:
        if org.name in defined and not org.acronym:
            org = OrgMention(name=defined[org.name], role=org.role, org_type=org_type_of(defined[org.name]),
                             parent_raw=org.parent_raw, url=org.url, source_text=org.source_text, acronym=org.name)
        if (org.name, org.role) not in {(o.name, o.role) for o in resolved}:
            resolved.append(org)
    return resolved


def mention_rows(people: Iterable[PersonMention], orgs: Iterable[OrgMention]) -> tuple[list[dict], list[dict]]:
    """Mentions -> rows for storage.write_entity_links, keyed by name_key (the honorific is already split off)."""
    people_rows = [{"normalized_name": name_key(p.name), "display_name": p.name, "honorific": p.honorific,
                    "profile_url": p.profile_url, "role": p.role, "affiliation_raw": p.affiliation_raw,
                    "source_text": p.source_text} for p in people if name_key(p.name)]
    org_rows = [{"normalized_name": name_key(o.name), "display_name": o.name, "org_type": o.org_type, "url": o.url,
                 "role": o.role, "source_text": o.source_text} for o in resolve_page_acronyms(list(orgs))
                if name_key(o.name)]
    return people_rows, org_rows
