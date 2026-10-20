# Week 3 — Central Aggregators, Discovery & Entity Extraction

> **Purpose:** Move from individual academic pages to **high-yield central event/news aggregators**, and turn their records into structured data that explicitly represents speakers and organizations as entities.
>
> **How to use this document:** Work through the sections **in order**. Each section contains learning material followed by an assignment. **Complete the assignment and its checkpoint before moving to the next section.**
>
> Week 2 established:
>
> **source adapter → bounded listing/archive traversal → detail enrichment → common runner → tests/logs → scheduled repeat**
>
> Week 3 extends that into:
>
> **discover central surfaces → ingest multiple discovery formats → collect incrementally → extract entities → link entities to items**
>
> The goal is not to crawl entire university domains. The goal is to identify **central, high-yield surfaces** that expose many relevant updates efficiently.

---

## Targets for hands-on work

You should work with:

1. your existing academic framework from Week 2, and
2. at least **one central aggregator surface** that collects events/news/announcements from multiple departments, centers, or units.

The original institutions remain useful starting points:

| Intern | Primary institution |
|---|---|
| **Saanvi** | IISER Pune |
| **Parth** | IIT Bombay |
| **Mayank** | JNU |
| **Soumyadipta** | TISS |

However, Week 3 is specifically about **central/high-yield aggregation**. If the institution does not provide a suitable central surface, choose another approved university/research organization with a public central listing.

Selection criteria:

- public
- appropriate for automated access
- useful central listing or feed
- ordinary HTML, RSS/Atom, sitemap, or similarly low-complexity surface
- ideally exposes multiple departments/organizations/speakers
- no access circumvention required

---

# 0. What Makes a Good Central Aggregator?

A high-yield aggregator gives the monitoring system more useful coverage per request.

Examples:

```text
university-wide events calendar
central seminars page
all-campus news feed
research-center event archive
institution-wide announcements
central calendar/feed
```

A poor target for this week would be:

```text
one professor's profile
one static event page
entire-domain blind crawl
search-engine results page
private/authenticated calendar
```

## Concepts to learn

- high-yield surface
- central aggregator
- department-specific vs institution-wide
- discovery surface vs item/detail page
- coverage
- freshness
- archive depth
- content type
- provenance
- scope boundaries

---

## Assignment 0 — Aggregator Candidate Matrix

Identify at least **three candidate central surfaces**.

Create:

```text
assignments/00_candidates/<institution>_aggregators.md
```

For each candidate:

```text
Name:
URL:
Institution/organization:
Surface type:
HTML / RSS / Atom / sitemap / other:
Content types:
Approximate update frequency:
Departments/units represented:
Detail-page links?:
Pagination/archive?:
Speaker information?:
Organization information?:
Access considerations:
Why this is high-yield or low-yield:
```

Rank the three candidates:

```text
1. Best target
2. Backup target
3. Not recommended
```

Explain the ranking.

### Checkpoint before moving on

You should be able to explain **why one central page is more valuable than crawling ten unrelated low-yield pages**.

---

# 1. Discovery via RSS/Atom, Sitemaps, and Central Listings

Week 1 introduced RSS/Atom and sitemaps conceptually. Week 3 should make them practical discovery mechanisms.

The project should continue preferring low-complexity public surfaces.

## Concepts to learn

### RSS / Atom

A feed commonly exposes:

```text
title
link
published/updated timestamp
summary
identifier
```

### Sitemap

A sitemap commonly exposes:

```text
URL
last modification metadata when supplied
```

A sitemap is not automatically an "events feed." It can still be useful for discovering structured sections of a site.

### HTML listing

A central HTML page may provide:

```text
item cards
detail URLs
dates
departments
speakers
pagination
```

The goal is to treat these as **different discovery adapters** that eventually produce the same normalized candidate items.

## Read

### Sitemaps.org — Protocol
https://www.sitemaps.org/protocol.html

Focus on:

- `<urlset>`
- `<loc>`
- optional `<lastmod>`
- sitemap indexes

### feedparser — Documentation
https://feedparser.readthedocs.io/en/latest/

Focus on:

- parsing a feed
- entries
- title/link/date-like fields

### Python — XML ElementTree
https://docs.python.org/3/library/xml.etree.elementtree.html

Read enough to understand simple XML traversal. You do not need advanced XML processing.

---

## Assignment 1A — Feed/Sitemap Inspection

For your chosen target, determine whether any of these exist:

```text
RSS
Atom
XML sitemap
sitemap index
```

If available, write a small parser that prints a controlled sample of:

```text
URL
title if available
published/updated/lastmod if available
discovery source
```

If the institution does not expose a usable feed/sitemap for the target content, use a local sample fixture to complete the technical exercise.

Save:

```text
assignments/01_discovery/
├── inspect_feed.py
├── inspect_sitemap.py
└── findings.md
```

### Checkpoint

You should be able to explain the difference between:

```text
discovering a URL
```

and:

```text
extracting a complete event record
```

---

## Assignment 1B — Unified Discovery Record

Create a common discovery shape such as:

```json
{
  "source_name": "example",
  "discovered_url": "https://example.org/event/123",
  "discovery_method": "rss",
  "discovered_title": "Example Event",
  "source_timestamp": null,
  "discovered_at": "..."
}
```

Produce the same shape from at least two of:

```text
HTML listing
RSS/Atom
sitemap
```

One of them may be a local fixture if necessary.

### Checkpoint before moving on

The downstream pipeline should not have to care whether an item URL was first found through HTML, RSS, or a sitemap.

---

# 2. Scope Control and the Crawl Frontier

Central pages can contain hundreds or thousands of links.

A monitor needs a clear boundary around which URLs are allowed to enter the collection pipeline.

## Concepts to learn

- crawl frontier
- allowlist rules
- same-site vs external link
- path prefixes
- URL canonicalization
- query parameters
- fragments
- visited URLs
- maximum pages
- maximum detail items per run
- avoiding calendar/search/filter explosion
- avoiding infinite URL spaces

## Read

### Python — `urllib.parse`
https://docs.python.org/3/library/urllib.parse.html

Focus on:

- `urljoin`
- `urlsplit`
- hostname
- path
- query
- fragment

---

## Assignment 2 — URL Scope Filter

Implement something conceptually like:

```python
def is_allowed_item_url(url: str, source_config: dict) -> bool:
    ...
```

Your source config should be able to express simple boundaries such as:

```text
allowed hostname
allowed path prefixes
excluded path prefixes
whether external links are allowed
```

Test with:

```text
valid event detail
valid news detail
external registration site
social media link
PDF
login URL
search URL
duplicate URL with fragment
same page with tracking parameter
```

Create:

```text
assignments/02_scope/scope_cases.md
```

For every example state:

```text
URL:
Allowed?:
Why?:
```

### Checkpoint before moving on

Your aggregator should not blindly follow every link found on the page.

---

# 3. Build Discovery Adapters

By Week 3 the core should support the idea:

```text
DISCOVERY ADAPTER
        ↓
candidate item URLs
        ↓
DETAIL FETCH/PARSE
        ↓
normalized item
```

Possible discovery adapters:

```text
HTML listing adapter
RSS/Atom adapter
sitemap adapter
```

They should not duplicate the database/storage implementation.

---

## Assignment 3 — Aggregator Discovery Interface

Design a small interface such as:

```python
def discover_items(source_config) -> list[dict]:
    ...
```

or separate adapters:

```python
discover_from_html(...)
discover_from_feed(...)
discover_from_sitemap(...)
```

Every discovery result should have the common discovery shape.

Add tests with local fixtures.

Minimum tests:

```text
test_html_discovery
test_feed_discovery
test_sitemap_discovery
test_scope_filter
test_duplicate_discovery_url
```

### Checkpoint before moving on

The same detail parser should be usable regardless of how its URL was discovered.

---

# 4. Incremental Collection and Change Detection

The system should eventually run repeatedly.

It should therefore distinguish:

```text
new item
existing unchanged item
existing changed item
item no longer visible on current listing
```

Do not interpret disappearance from a listing as deletion without stronger evidence.

## Concepts to learn

- `first_seen_at`
- `last_seen_at`
- `fetched_at`
- content hash
- discovery run
- unchanged vs changed
- new vs rediscovered
- why "not found on first page anymore" is not the same as "deleted"
- incremental run
- avoiding full historical recrawl every time

## Read

### Python — `hashlib`
https://docs.python.org/3/library/hashlib.html

Focus on creating stable hashes from normalized content.

### Python — `sqlite3`
https://docs.python.org/3/library/sqlite3.html

Revisit:

- unique constraints
- updates
- transactions at a basic level

---

## Assignment 4 — Classify Run Results

Given a local dataset:

```text
Run 1:
A
B
C

Run 2:
A unchanged
B changed
C absent from current listing
D new
```

Your collector should report something conceptually like:

```text
new=1
changed=1
unchanged=1
not_seen_this_run=1
```

Do **not** delete `C` merely because it was absent in Run 2.

Create:

```text
assignments/04_incremental/run_state_notes.md
```

Answer:

1. What makes an item "new"?
2. What makes an item "changed"?
3. What fields contribute to your content hash?
4. Which volatile fields should **not** contribute to the content hash?
5. Why should `fetched_at` not make every record appear changed?
6. What does absence from a current listing actually prove?

### Checkpoint before moving on

Running an aggregator repeatedly should primarily process **new or changed information**, not behave as if every record is new each time.

---

# 5. Extract Speakers and Organizations as Entities

The Week 3 roadmap requires moving beyond flat strings.

For this week, "entity extraction" means:

> When the source explicitly identifies a speaker, chair, department, center, or organizing institution, represent that value as a structured entity linked to the item.

It does **not** require an AI/NLP system yet.

## Concepts to learn

### Person entity

Possible fields:

```text
name
title/honorific if explicitly provided
affiliation if explicitly provided
profile URL if available
source text
```

### Organization entity

Possible fields:

```text
name
organization type if explicit
parent organization if explicit
URL if available
source text
```

### Relationship

An event may have:

```text
speaker
chair
moderator
host
organizer
co-organizer
```

Preserve the role when the source provides it.

---

## Assignment 5 — Entity Extraction from Explicit Fields

Use 10–20 event records from saved fixtures or a controlled live sample.

Convert source text such as:

```text
Speaker: Dr. Example, Centre for Example Studies
Organized by: Department of Example
Chair: Prof. Sample
```

into structures conceptually like:

```json
{
  "people": [
    {
      "name": "Dr. Example",
      "role": "speaker",
      "affiliation_raw": "Centre for Example Studies"
    },
    {
      "name": "Prof. Sample",
      "role": "chair",
      "affiliation_raw": null
    }
  ],
  "organizations": [
    {
      "name": "Department of Example",
      "role": "organizer"
    }
  ]
}
```

Rules:

- extract only what the page actually supports
- preserve raw text
- do not infer political orientation
- do not infer affiliations not explicitly shown
- do not merge two people solely because their names look similar

### Checkpoint before moving on

You should be able to point from every extracted entity back to the source text that produced it.

---

# 6. Entity Storage and Relationships

Entities should not only be embedded inside one giant JSON blob if the project intends to connect events, speakers, and organizations over time.

Week 3 should introduce a simple relational model.

## Suggested model

```text
items
-----
id
item_url
item_type
title
...

people
------
id
normalized_name
display_name
...

organizations
-------------
id
normalized_name
display_name
...

item_people
-----------
item_id
person_id
role
source_text

item_organizations
------------------
item_id
organization_id
role
source_text
```

Do not over-engineer identity resolution yet.

## Concepts to learn

- entity table
- relationship/join table
- many-to-many relationships
- display value vs normalized matching key
- role
- provenance/source text
- conservative entity creation

---

## Assignment 6 — Store Event ↔ Entity Relationships

Extend your SQLite schema so one event can link to:

- multiple people
- multiple organizations

and the same person/organization can appear in multiple events.

Example query you should be able to answer:

```text
Which events in my local database mention this exact normalized person name?
```

and:

```text
Which organizations have appeared as organizers in my collected sample?
```

Document the schema in:

```text
assignments/06_entities/entity_schema.md
```

### Checkpoint before moving on

You should not need to duplicate the full person record inside every event row.

---

# 7. Conservative Normalization and Entity Resolution

"Dr. A. Kumar" and "A Kumar" may be the same person.

They may also not be.

Week 3 should teach conservative normalization, not aggressive guessing.

## Safe normalization examples

Potentially reasonable transformations:

```text
strip surrounding whitespace
collapse repeated whitespace
normalize Unicode
case-normalized matching key
remove clearly decorative punctuation
```

Be careful with:

```text
removing initials
reordering names
dropping surnames
guessing affiliations
fuzzy-merging near matches
```

## Concepts to learn

- display name
- normalized key
- alias
- exact normalized match
- ambiguity
- false merge
- false split
- why false merges are particularly damaging to entity graphs

---

## Assignment 7 — Entity Matching Exercise

Create a local fixture with names such as:

```text
Prof. Ananya Rao
Ananya Rao
Prof Ananya Rao
A. Rao
Ananya R.
```

and organizations such as:

```text
Centre for Policy Research
Centre for Policy Research (CPR)
CPR
Center for Policy Research
```

For each pair decide:

```text
safe automatic match
possible match requiring review
do not match automatically
```

Write:

```text
assignments/07_resolution/entity_matching_policy.md
```

Define your Week 3 policy.

A good policy should favor:

```text
false split over false merge
```

when identity is uncertain.

### Checkpoint before moving on

Your code should not turn a weak similarity score into an authoritative identity claim.

---

# 8. Multi-Content Central Aggregators

Central pages may mix:

```text
event
seminar
news
announcement
report
PDF
external registration link
```

Your collector should classify what it can and preserve unknowns rather than forcing everything into "event."

## Concepts to learn

- content classification from explicit page structure
- route to content-specific parser
- unknown/unsupported item type
- content-type sniffing
- HTML vs PDF
- explicit metadata vs inference
- preserving discovery records even when full extraction is unsupported

---

## Assignment 8 — Content Router

Create a small routing layer:

```python
def classify_discovered_item(discovery_record) -> str:
    ...
```

Possible results:

```text
event
announcement
faculty
pdf_document
external_link
unknown
```

Do not classify based on political/topic interpretation.

Use structural evidence such as:

```text
URL pattern
explicit category label
MIME/content type
known section
```

Create tests for ambiguous cases.

### Checkpoint before moving on

An unsupported item should be recorded as unsupported/unknown rather than silently disappearing or being forced into the wrong schema.

---

# 9. Source Health and Coverage Metrics

Before adding AI analysis later, the collection layer needs to answer a simpler question:

> **Did the monitor actually work?**

## Useful per-run metrics

```text
source
started_at
finished_at
HTTP status
pages fetched
items discovered
items parsed
new items
changed items
unchanged items
parse failures
detail failures
entities extracted
```

Optional:

```text
percentage of items with date
percentage with speaker
percentage with organization
```

These are collection-quality metrics, not intelligence conclusions.

---

## Assignment 9 — Run Summary

At the end of each aggregator run, generate a summary such as:

```text
SOURCE: example_events
PAGES_FETCHED: 3
ITEMS_DISCOVERED: 26
ITEMS_PARSED: 25
NEW: 4
CHANGED: 2
UNCHANGED: 19
FAILED: 1
PEOPLE_EXTRACTED: 13
ORGANIZATIONS_EXTRACTED: 8
```

Persist the summary or write it to logs in a consistent form.

Then deliberately break one fixture and confirm that the metrics make the failure visible.

### Checkpoint before moving on

A reviewer should be able to distinguish:

```text
source had no new content
```

from:

```text
parser broke and returned zero content
```

---

# 10. Build the Central Aggregator Adapter

Combine the Week 3 capabilities:

```text
CENTRAL SOURCE
      ↓
DISCOVERY
HTML / RSS / SITEMAP
      ↓
SCOPE FILTER
      ↓
CANDIDATE ITEMS
      ↓
DETAIL FETCH
      ↓
CONTENT PARSER
      ↓
NORMALIZED ITEM
      ↓
ENTITY EXTRACTION
      ↓
ITEM + PEOPLE + ORGANIZATIONS
      ↓
SQLITE
      ↓
RUN METRICS
```

The same generic infrastructure from Week 2 should still handle:

```text
HTTP
storage
logging
scheduling
tests
```

---

## Assignment 10 — Central Aggregator Implementation

You should implement one central aggregator using the shared framework.

For the assignment, keep the live crawl controlled.

Suggested ceiling:

```text
2–5 listing/archive pages
or
20–40 discovered item records
```

whichever is more appropriate for the site.

The purpose is to prove architecture, not scrape an entire archive.

Required behavior:

- high-yield central discovery surface
- bounded scope
- common discovery records
- deduplication
- detail parsing where useful
- incremental run behavior
- speaker extraction when explicit
- organization extraction when explicit
- relational entity links
- tests from fixtures
- logs
- run summary

---

# 11. Cross-Review

Pair up:

- **Saanvi ↔ Mayank**
- **Parth ↔ Soumyadipta**

This is intentionally different from Week 2.

Review another intern's aggregator.

## Review questions

1. Is the target genuinely high-yield?
2. Is scope clearly bounded?
3. Could pagination loop indefinitely?
4. Are feeds/sitemaps treated as discovery rather than complete truth?
5. Are item URLs canonicalized consistently?
6. Is a missing field handled without crashing?
7. Are speakers/organizations supported by source text?
8. Are uncertain identities merged too aggressively?
9. Can you tell from logs whether zero new items means "nothing new" or "parser broken"?
10. Could this adapter run repeatedly without duplicating records?

Record at least three substantive review comments.

---

# 12. Week 3 Integration Assignment

By the end of Week 3, you should have a high-yield central source running through the shared framework.

## Required deliverables

```text
1. Aggregator candidate matrix
2. Chosen central source rationale
3. Feed/sitemap/listing discovery exercise
4. URL scope rules
5. Discovery adapter
6. Incremental run/change detection
7. Content router
8. Detail parser where relevant
9. Person entity extraction
10. Organization entity extraction
11. Entity relationship schema
12. Tests and fixtures
13. Logs
14. Run metrics
15. README
16. Peer-review notes
```

## Final architecture to demonstrate

```text
SOURCE CONFIG
     ↓
SCHEDULED RUN
     ↓
DISCOVERY ADAPTER
     ↓
SCOPE CONTROL
     ↓
NEW / CHANGED ITEM CANDIDATES
     ↓
FETCH + PARSE
     ↓
NORMALIZE
     ↓
EXPLICIT ENTITY EXTRACTION
     ↓
ITEM + ENTITY RELATIONSHIPS
     ↓
DATABASE
     ↓
HEALTH / COVERAGE SUMMARY
```

---

# Week 3 Definition of Done

Week 3 is complete when you can explain and demonstrate:

```text
1. How to choose a high-yield central public surface
2. How RSS/Atom, sitemaps, and HTML listings differ as discovery mechanisms
3. How to prevent a central crawler from expanding into an uncontrolled domain crawl
4. How discovery is separated from detail extraction
5. How repeated runs distinguish new, changed, and unchanged items
6. Why absence from a listing is not proof of deletion
7. How speakers and organizations are extracted from explicit source metadata
8. How events/items link to people and organizations relationally
9. Why uncertain names should not be aggressively merged
10. How mixed content is classified structurally
11. How run metrics distinguish "no new data" from "collection failure"
12. How the aggregator uses the same reusable infrastructure created in Week 2
```

The strongest final test for yourself is:

> Given a new central university/research-organization listing, can you identify the best discovery surface, define bounded scope, plug it into the framework, and explain which entities can be extracted without unsupported inference?

---

# What Is Explicitly Out of Scope for Week 3

Do **not** spend Week 3 on:

- AI/LLM-based entity extraction
- ideological or sentiment classification
- fuzzy cross-source person matching at scale
- automated identity claims based on weak name similarity
- CAPTCHA bypasses
- proxy rotation
- anti-bot evasion
- private/authenticated surfaces
- distributed crawling
- production dashboards
- automated briefing generation
- email delivery

Those belong to later phases, if required.

---

# Compact Resource List

### Feeds and sitemaps
- Sitemaps.org — Protocol  
  https://www.sitemaps.org/protocol.html
- feedparser — Documentation  
  https://feedparser.readthedocs.io/en/latest/
- Python — XML ElementTree  
  https://docs.python.org/3/library/xml.etree.elementtree.html

### URL handling and scope
- Python — `urllib.parse`  
  https://docs.python.org/3/library/urllib.parse.html

### Incremental collection
- Python — `hashlib`  
  https://docs.python.org/3/library/hashlib.html
- Python — `sqlite3`  
  https://docs.python.org/3/library/sqlite3.html

### Parsing
- Beautiful Soup — Documentation  
  https://www.crummy.com/software/BeautifulSoup/bs4/doc/

### Testing and observability
- pytest — Getting Started  
  https://docs.pytest.org/en/stable/getting-started.html
- Python — Logging HOWTO  
  https://docs.python.org/3/howto/logging.html

### Scheduling
- APScheduler — User Guide  
  https://apscheduler.readthedocs.io/en/master/userguide.html
