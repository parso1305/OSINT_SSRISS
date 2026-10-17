# Section 3: discovery interface

`src/discovery/discover.py`:
- `discover_items(source_config, client) -> list[DiscoveryCandidate]`
- `discover(...) -> DiscoveryResult`, which is the same list plus `pages_fetched`, `http_status`, `failures` and
  `raw_count` for run metrics.

## Where the methods come from

The source's registry entry in `config/sources.json`:
- `"discovery"`: one method or a list (`html` · `rss` · `atom` · `sitemap`);
- `"discovery_urls"`: `{method: [urls]}`. `html` defaults to `[listing_url]`.

The HTML selectors come from the adapter's `LISTING_SELECTORS`. Neither the runner nor `discover.py` names a
method or a selector for any source. `test_methods_come_from_the_registry_entry_not_the_code` checks that a source
configured for `rss` never has its HTML page fetched.

The client is the project's `src.fetcher.Fetcher`, so robots.txt, the per-host delay, timeouts and FETCH logging
all apply. There is no new DB code: persisting candidates is the router's job (Section 8, `discovered_items`).

## Dedup on the canonical URL

Every parser returns DiscoveryRecords whose `discovered_url` is already `resolve_item_url()` output, so dedup is a
dict keyed on that URL. One URL found by several methods, or twice by one method, becomes one
`DiscoveryCandidate(record, discovery_methods, category_label, found_on, in_scope, scope_reason)`.

**Which title and timestamp win.** Method priority is `html > rss > atom > sitemap`, applied field by field. The
first method in that order that has a value wins:
- **title:** the HTML listing text is what a reader sees on the source. A feed title is the publisher's summary,
  and a sitemap has no title.
- **timestamp, with its raw string from the same record:** the HTML listing date is the event's own date. pubDate is
  a publishing time. A sitemap lastmod is the least trustworthy; on the one real IITB-family sitemap, all 500 values
  are identical (`01_discovery/findings.md`).

`discovery_methods` lists every method that found the URL, and `found_on` lists every page, feed or sitemap it was
found on.

## Proof

`tests/test_discovery_interface.py`:

| Test | Shows |
|---|---|
| `test_html_discovery` | Only `.views-row` cards on a page with nav, news, footer and mailto links become candidates; the date is from `<time datetime>`; the category label is kept for the router |
| `test_feed_discovery` | RSS and Atom candidates with normalized timestamps and the raw string kept |
| `test_sitemap_discovery` | A sitemap index: only 2 of 3 children are fetched (cap); a URL in both children becomes 1 candidate |
| `test_scope_filter` | An out-of-scope URL stays a candidate with its reason; `max_discovered_items` marks the overflow |
| `test_duplicate_discovery_url` | Three different raw hrefs (relative, `utm_*` + `#fragment`, absolute) collapse to one candidate with `discovery_methods == ("html", "rss", "sitemap")`; the HTML title and date win; for Van Mahotsav, whose HTML card has no datetime, the RSS pubDate fills in |
