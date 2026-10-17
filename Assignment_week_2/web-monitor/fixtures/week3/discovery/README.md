# Week 3 discovery fixtures

| File | Origin | Used for |
|---|---|---|
| `iitb_rss_real_trimmed.xml` | REAL: `https://www.iitb.ac.in/rss.xml` saved 2026-10-16 (Section 0 evidence), first 3 items, `<description>` bodies trimmed | RSS parsing of the target's only feed (Drupal front-page feed; no event items) |
| `acr_sitemap_real_trimmed.xml` | REAL: `https://acr.iitbombay.org/sitemap.xml` saved 2026-10-16, 3 site pages + 5 `events_list` URLs | urlset with lastmod; the "every lastmod identical" trust problem |
| `events_rss.xml` | SYNTHETIC, modelled on `www.iitb.ac.in/event/<slug>` | RSS 2.0 with RFC 822 dates, tracking params, fragments |
| `events_atom.xml` | SYNTHETIC | Atom with ISO 8601 dates and offsets |
| `urlset_with_lastmod.xml`, `urlset_no_lastmod.xml` | SYNTHETIC | urlset with / without lastmod, with / without the sitemaps.org namespace |
| `sitemap_index.xml` | SYNTHETIC | sitemapindex with 3 children (cap of 2) |
| `malformed.xml`, `billion_laughs.xml` | SYNTHETIC | clear errors for malformed and unsafe XML |

The target (`www.iitb.ac.in`) has no event feed and no sitemap (Section 0: `/sitemap.xml` 404, no `Sitemap:` line,
`/rss.xml` holds 0 events), so the event-shaped feed and sitemap fixtures are synthetic. They reuse real event
slugs from the saved calendar so the cross-method tests compare the same URLs the HTML discovery finds.
