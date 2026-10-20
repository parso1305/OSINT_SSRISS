# Section 5: entity extraction

Code:
- `src/entities.py` (generic): `PersonMention`, `OrgMention`, `labelled_values`, `block_lines`, `split_people`,
  `parse_person`, `split_orgs`, `parse_org`, `extract_mentions`, `speakers_field`, `organizations_field`, `name_key`.
- `sources/iit_bombay_events.py` (adapter): `LABELS` and `parse_event_detail`.

Tests: `tests/test_entities_extraction.py` (43 cases).

## Fixtures (20 events)

There are 18 **real** IIT Bombay `/event/<slug>` pages:
- 8 from the Section 0 evidence;
- 12 from a controlled live sample on 2026-10-17
  (`assignments/week3/05_extraction/fetch_sample.py`; 13 requests including robots.txt, all 200, ledger in
  `../live_requests.md`). The evidence had fewer than 10 detail pages, so the sample was allowed.

There are 2 **synthetic** variants of a real page (`scripts/make_week3_synthetic_fixtures.py`). Each keeps the
site's real markup and replaces only the `Speaker:` paragraph. They are needed because none of the 20 real pages has
two people in one field or an `Organized by:` organization line. The real pages are in
`fixtures/week3/iitb_events/detail/`, with `manifest.json` for the live sample.

| Case required by the brief | Fixture | Result |
|---|---|---|
| Two people in one field | `synthetic-two-speakers-and-organizers` (`Speakers: Prof. Ananya Rao, Centre for Policy Research and Dr. Ravi Sen, Department of Economics, IIT Bombay`) | 2 speakers, each with the affiliation written next to it |
| Event with no speaker | real `van-mahotsav-2026`, `5th-japan-india-forum`, `international-conference-quantum-dynamics` | no people, `speakers = []` |
| Unlabelled speaker-like text, so nothing is extracted | real `institute-colloquium-global-health-research-india-world` (`About the Speaker: Dr. Gagandeep Kang is …`, no `Speaker:` line); real `national-engineers-day-1` (chief guest named in prose); synthetic sentence "Our distinguished guest Dr. Unlabelled Person …" | nothing |
| Honorific | real `Prof. Dr. Joachim Kopp` → honorific `Prof. Dr.`; real `Shri Chaitram Pawar`; real `Dr. Vinod G. Mengle`; synthetic `Prof Ananya Rao` (no period) | honorific in its own field; the name is kept as written |
| Organizer line | synthetic `Organized by: Department of Economics, IIT Bombay and Centre for Policy Research (CPR)`, `Co-organized by: Department of Science and Technology`; real `Organizer: Prof. Azizuddin Khan — …` | organizations: name, parent `IIT Bombay`, acronym `CPR` defined on the page; "Science and Technology" is not split. The real one is a **person** with role organizer, email removed from the affiliation |

Across the 18 real pages, 12 label a speaker, 1 labels an organizer, and 5 label no one.

## Rules

- **Labels live in the adapter**, `sources/iit_bombay_events.py::LABELS`:
  - `Speaker`/`Speakers`/…
  - `Chair`/…
  - `Moderator`/…
  - `Host`/…
  - `Organizer`/`Organiser`/`Organized by`/`Organised by`/…
  - `Co-organizer`/`Co-organized by`/…

  The site actually uses `Speaker:` (12 pages) and `Organizer:` (1). The rest are listed so a page that uses them
  is read, never guessed.
- **A label must start the line.** `About the Speaker:` and `A profile of the speaker:` are not `Speaker:`.
- **Roles** (`speaker`, `chair`, `moderator`, `host`, `organizer`, `co-organizer`) come only from the label.
  Organizer and co-organizer values are a **person** when they start with an honorific, otherwise an
  **organization**.
- **Splitting people.** `;`, line breaks (`<br>`), ` and ` and `&` start a new person only when the text after them
  begins with an explicit honorific. The exception is a value with no comma at all (a bare name list), which is split
  on all of them. A comma never separates two people: `Dr. X, Centre for Y` is a name plus an affiliation.

  This rule exists because real affiliations contain every separator:
  - `Shri Chaitram Pawar, Social Reformer & Environmentalist; Padma Shri Awardee`
  - `Dr. Vinod G. Mengle, Founder and CEO of Aero Insights, LLC; Formerly with Boeing …`
  - `Prof. Ponnurangam Kumaraguru, Visiting Scientist, …;<br>Professor, Computer Science, …; and President of ACM India.`

  All three stay one person.
- **Within one person.** The leading honorific(s) go to `honorific` (`Dr.`, `Prof.`, `Mr.`, `Ms.`, `Mrs.`,
  `Shri`, `Smt.`, and stacked forms like `Prof. Dr.`; `Professor`, `Drishti` and `Shrinivas` never match). The name
  runs to the first `,`, ` — `, ` – `, ` - `, ` (` or `;`. The rest is `affiliation_raw`, with email addresses
  removed.
- **Splitting organizations.** `;` and line breaks always. ` and ` / `&` only before another organization head
  word (Department, Centre, School, …), so `Department of Science and Technology` stays one organization. An
  acronym is recorded only when the same value defines it: `Centre for Policy Research (CPR)`.
- **Nothing inferred.** An affiliation is recorded only when it is written next to the name (`Chair: Prof Ananya Rao`
  has `affiliation_raw = None`). There is no topic, ideology or political label, and nothing is merged here.
- **`source_text`** is the labelled line verbatim, whitespace collapsed. For every mention in all 20 fixtures, the
  test checks that it appears in that fixture's visible text.
- **Shared schema stays consistent.** `records.speakers = speakers_field(people)` (`[{name, affiliation}]`, the
  Week 2 shape, speakers only) and `records.organizations = organizations_field(orgs)` are built from the **same**
  extraction that fills the entity tables (`test_records_fields_come_from_the_same_extraction`).

## Also fixed on the way: event times on the detail page

The detail page's `<time datetime="2026-09-03T17:15:00Z">` is IST wall-clock time labelled as UTC. The homepage
block gives `11:45:00Z` for the same 17:15 IST lecture, and the body says "Time: 5:15 p.m.". The adapter drops the
`Z`, reads the value as IST (+05:30; India has no DST) and stores `event_start = 2026-09-03T11:45:00Z` with
`timezone = Asia/Kolkata`. A fixed offset is used because the Windows venv has no IANA tz database (`zoneinfo`
cannot load `Asia/Kolkata`) and adding `tzdata` for one offset was not worth a dependency (DECISIONS.md D19).

## Evidence: IIT Bombay event pages have no organizer field (repair R1)

All 20 real `/event/<slug>` pages (the 18 extraction fixtures plus the 2 no-speaker pages) were checked for every
Drupal field rendered inside `<article class="node--type-event">`:

| Drupal field class | Pages |
|---|---|
| `field--name-title` | 20 / 20 |
| `field--name-field-event-type` | 20 / 20 |
| `field--name-field-event-date` | 20 / 20 |
| `field--name-field-vanue` (the site's spelling of venue) | 20 / 20 |
| `field--name-body` | 20 / 20 |
| `field--name-field-event-image` | 1 / 20 |

There is no organizer, department, host or speaker field: these pages are body, venue, event type and date. The
calendar JSON on `/events` has no organizer either; each entry has only title, url, start and node id.

So `organizations` (and `item_organizations`) can come only from a **labelled line in the body**: `Organized by:`,
`Organiser:`, `Co-organized by:` and so on (`LABELS` in the adapter). Only 1 of the 20 real pages has such a label,
`Organizer: Prof. Azizuddin Khan — …`, and it names a person, not an organization. Prose such as "The Department of
Chemistry, IIT Bombay is organizing …" is **not** extracted, because roles come only from labels and there is no NLP.

This is why real-data runs report `organizations_extracted = 0` and `pct_with_org` near 0. That number is true
coverage, not a parser failure. The organization path is exercised by the synthetic fixture
`synthetic-two-speakers-and-organizers` (3 organizations) and by `tests/test_entities_extraction.py::test_organizer_lines`.

Reproduce:

```
venv\Scripts\python -c "import glob,collections; from bs4 import BeautifulSoup; c=collections.Counter(); [c.update({cl for d in BeautifulSoup(open(f,encoding='utf-8').read(),'html.parser').select_one('article.node--type-event').select('[class*=field--name-]') for cl in d['class'] if cl.startswith('field--name-')}) for f in glob.glob('fixtures/week3/iitb_events/detail/*.html') if 'synthetic' not in f]; print(dict(c))"
```
