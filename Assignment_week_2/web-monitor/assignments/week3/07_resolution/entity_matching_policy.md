# Section 7: entity matching policy

Code: `src/entities.py`, with `name_key`, `person_match`, `org_match`, `review_pairs` and `resolve_page_acronyms`.
The review queue is `storage.entity_alias_candidates`, filled by `aggregator.write_entities` in the run's
transaction. Tests: `tests/test_matching_policy.py`. `test_every_policy_row_has_a_test` fails if this table and the
tests drift apart.

## `name_key()`: the only normalization

Exactly these steps, in order:
1. NFKC
2. casefold
3. remove decorative punctuation: periods (after initials), stray commas, straight and curly quotes, backticks
4. strip and collapse whitespace

The honorific is removed **before** keying, by `split_honorific`. It is stored separately (`people.honorific`), so
`Prof. Ananya Rao` and `Ananya Rao` key the same.

It never:
- drops or expands initials (`A. Rao` → `a rao`; `Ananya Rao` → `ananya rao`; these are different keys);
- reorders names (`Rao Ananya` stays `rao ananya`);
- drops a surname or a middle name;
- maps spelling variants (`Centre` ≠ `Center`);
- expands acronyms;
- fuzzy-matches.

Equal keys are one entity, because `people.normalized_name` is UNIQUE (D5). Everything else is decided by the table
below.

## Decisions

Three outcomes:
- **safe automatic match**: same `name_key` after the honorific is removed; stored as one row.
- **possible match requiring review**: written to `entity_alias_candidates(kind, a_id, b_id, reason,
  status='needs_review')` and **never merged**.
- **do not match automatically**: nothing is recorded.

### People (fixture: Prof. Ananya Rao · Ananya Rao · Prof Ananya Rao · A. Rao · Ananya R.)

| # | A | B | Decision | Reason |
|---|---|---|---|---|
| P1 | Prof. Ananya Rao | Ananya Rao | safe automatic match | Same name once the honorific is removed; the honorific is stored separately. |
| P2 | Prof. Ananya Rao | Prof Ananya Rao | safe automatic match | Only the period after the honorific differs. |
| P3 | Prof. Ananya Rao | A. Rao | possible match requiring review | "A." is compatible with "Ananya" and the surname is identical, but an initial is not a name; many people are "A. Rao". |
| P4 | Prof. Ananya Rao | Ananya R. | possible match requiring review | The first name is identical and "R." is compatible with "Rao", but a surname initial could be anyone. |
| P5 | Ananya Rao | Prof Ananya Rao | safe automatic match | Same name once the honorific is removed. |
| P6 | Ananya Rao | A. Rao | possible match requiring review | Same reason as P3. |
| P7 | Ananya Rao | Ananya R. | possible match requiring review | Same reason as P4. |
| P8 | Prof Ananya Rao | A. Rao | possible match requiring review | Same reason as P3. |
| P9 | Prof Ananya Rao | Ananya R. | possible match requiring review | Same reason as P4. |
| P10 | A. Rao | Ananya R. | do not match automatically | Both forms are abbreviated, with no full name part in common; too weak even for review. |

### Organizations (fixture: Centre for Policy Research · Centre for Policy Research (CPR) · CPR · Center for Policy Research)

| # | A | B | Decision | Reason |
|---|---|---|---|---|
| O1 | Centre for Policy Research | Centre for Policy Research (CPR) | safe automatic match | Same name; the parenthesis only defines its acronym on that page. |
| O2 | Centre for Policy Research | CPR | do not match automatically | A bare acronym never matches automatically. It is an alias only on the page that defines it. |
| O3 | Centre for Policy Research | Center for Policy Research | possible match requiring review | Centre/Center spelling variant: probably the same, but spelling is never normalized automatically. |
| O4 | Centre for Policy Research (CPR) | CPR | do not match automatically | Across pages, a bare "CPR" is not tied to this definition. On the **same** page it is (see below). |
| O5 | Centre for Policy Research (CPR) | Center for Policy Research | possible match requiring review | Spelling variant, as O3. |
| O6 | CPR | Center for Policy Research | do not match automatically | A bare acronym, and a different spelling as well. |

**The acronym rule.** An acronym becomes an alias only when the same page defines it. On a page that says
`Organized by: Centre for Policy Research (CPR)`, a later `Co-organized by: CPR` on **that page** is linked to the
Centre for Policy Research (`resolve_page_acronyms`; test `test_acronym_is_an_alias_only_on_the_page_that_defines_it`).
A bare `CPR` on any other page stays the organization "CPR", a separate row. "CPR" is also the Commission for
Population Research, the Centre for Pollution Research, cardiopulmonary resuscitation, and so on.

**Centre/Center** variants go to review, never to an automatic match. One spelling is usually a typo, but two
real institutions can differ by exactly that word. A reviewer decides once, and the pair keeps its status.

## Real review queue from the fixture DB (`build_fixture_db.py`)

```
('person', 'Ananya Rao', 'A. Rao', 'needs_review', 'an initial is compatible with a full name part and another part is identical; could be the same person, could be a namesake: a reviewer decides')
('person', 'Ananya Rao', 'Ananya R.', 'needs_review', 'an initial is compatible with a full name part and another part is identical; could be the same person, could be a namesake: a reviewer decides')
```

The second build run adds 0 candidates: the queue is keyed `(kind, a_id, b_id)`, and a reviewer's status survives
re-runs. The three `people` rows stay three rows.

## Why a false merge is worse than a false split

A false merge silently gives one person another person's events, roles and affiliations, and every later query and
report inherits the mistake with no visible trace. A false split only leaves two rows that a reviewer can see side by
side and join later.
