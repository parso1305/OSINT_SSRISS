"""Adapter: IIT Bombay institute events calendar (Week 3 central aggregator target, D1).

Site-specific values only: selectors, label patterns and the detail-page parser. Everything generic
(discovery, scope, routing, fetching, storage, entity extraction helpers, metrics) lives in src/.

Discovery (HTML): the homepage's events block, a server-rendered view of the same Drupal "events" view that
/events draws client-side with FullCalendar (its items are only JSON in drupal-settings-json; see
assignments/week3/00_candidates/iit_bombay_aggregators.md, C1 JS check).
"""

# The homepage events block: one .views-row per event, <time datetime> in correct UTC (e.g. 17:15 IST ->
# "2026-09-03T11:45:00Z"), the title link inside .views-field-title.
LISTING_SELECTORS = {
    "item": ".homepage-events .views-row",
    "link": ".views-field-title a",
    "date": ".views-field-field-event-date time",
    "date_attr": "datetime",
}
