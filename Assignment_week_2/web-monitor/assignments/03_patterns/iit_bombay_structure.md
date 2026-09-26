# IIT Bombay Public Website Structural Mapping

This document provides a technical structural analysis of three distinct public surfaces on the IIT Bombay (`iitb.ac.in`) domain for OSINT web-monitoring ingestion pipelines. All findings are derived from real live page DOM inspections.

> **Corrected 2026-09-27 (Week 2 audit, §9).** The HSS selectors first written here (`.views-row`,
> `.views-field-title`, `.event-category-title`, `.view-id-events`) do **not** occur in any saved HSS page.
> They were re-checked against real HTML: `/events` (fetched once, 2026-09-26 20:12:56Z, saved as
> `fixtures/iit_bombay_hss/recon_events_2026-09-27.html`) and `/events/seminars-and-talks`
> (`fixtures/iit_bombay_hss/listing_2026-09-26.html`, `live_page_{1,2,3}.html`). Both use the same card markup;
> the selectors below are the real ones and are what `sources/iit_bombay.py` uses. The future-dated example
> item is **verified**: `/events` lists `11th Nov 2026`, `09:00 AM`, `JALVIHAR CONFERENCE HALL`,
> `International Conference / Symposium` (`recon_events_2026-09-27.html:372-395`).

---

## Surface Comparison Matrix

| Surface | Listing URL | Record type | Listing→detail? | Pagination? | Archive? | Listing fields | Detail-only fields | HTML/PDF/other | Suitable for template? | Why? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EE Department Announcements & Events** | `https://www.ee.iitb.ac.in/info/news/` | Seminars, Admissions, Workshops & Department News | Yes (links to `/info/news/<slug>/` via `.ann-action--main`) | Dynamic filtering by category (`All`, `Events`, `Admissions`, etc.) and temporal scope (`Upcoming`, `Past`) | Yes (`#yearSelect` dropdown and interactive monthly calendar widget) | Date (`Sep 23, 2026`), Category pill (`.ann-chip`), Title, Teaser summary, External link button (`.ann-action--link`) | Full abstract body, Speaker name, Speaker affiliation & bio, Exact venue (`EEG-301, GG Building`), Start time (`5:00 PM`), Breadcrumb trail (`.annd-crumb`) | HTML | Yes | Built with Astro + Tailwind CSS. Uses stable, semantic CSS class names (`.ann-ticker-item`, `.ann-chip`, `.ann-action`), server-rendered static HTML, clean slug-based URL hierarchy, and predictable two-tier listing→detail split. |
| **HSS Department Events** | `https://www.hss.iitb.ac.in/events` | International Conferences, Symposia, and Academic Lectures | Yes (links to `/events/<category-slug>/<event-slug>`) | On `/events/seminars-and-talks`: yes, Drupal pager with `<a rel="next">` (`live_page_1.html:739`). On `/events` (1 upcoming item on 2026-09-26): no pager rendered | Yes (Archive navigation links by academic year) | Event Category (`.event-category span`: `International Conference / Symposium`), Title (`.event-name a`), Event date / Time / Location (`.event-room-details li`, identified by `i.icon-calendar` / `icon-time` / `icon-marker`: `11th Nov 2026`, `09:00 AM`, `JALVIHAR CONFERENCE HALL`), Poster thumbnail image | Comprehensive event agenda, Speaker bios, Organizing committee remarks, Registration links, Breadcrumbs (`Home -> Events`) | HTML | Yes | Built on Drupal 9/10 with a custom Bootstrap 5 theme. Cards are `.event-card-wrapper` inside a Views block (`.view-events-page` on `/events`, `.view-seminars-and-talks .view-content` on seminars-and-talks), server-rendered, with consistent `article.node--type-events` detail nodes. |
| **HSS Department News & Announcements** *(Awkward)* | `https://www.hss.iitb.ac.in/news` | Mixed Notices (Ph.D. Shortlists, Convocation Invites, Orientation Notices) | Yes (Two-step traversal: Listing card → Detail node page → Embedded PDF link) | Yes (Drupal view pagination controls) | Yes (Archive menu link) | Title, Publication date (`13th August 2026`), Card thumbnail image | Hosted PDF attachment URL (`/sites/default/files/...pdf`), Formatted publication date (`2026-05-12`), Breadcrumbs | Mixed (HTML detail node serving as a metadata wrapper around attached PDF documents) | No | Heterogeneous payload structure. Unlike standard article feeds, administrative notices and shortlist calls contain zero HTML body paragraphs; the detail page merely houses a direct link to an uploaded `.pdf` file. A standard HTML text-extraction template will yield empty content without dedicated branching logic for binary document downloads. |

---

## Potential common template

Across the 3 surfaces inspected, the following specific fields and extraction behaviors are shared and can be formalized into a shared crawler template:

1. **Common Listing Extracted Fields**:
   * **`title`**: Present as visible anchor text on every listing card (`.ann-ticker-item h3 a` on EE; `.event-name a` on HSS).
   * **`item_url`**: Present as a canonical or relative link on all listing cards. Resolvable to absolute URLs via `urljoin(base_url, href)`.
   * **`date_raw`**: Present in human-readable string formats (e.g., `Sep 23, 2026` on EE; `11th Nov 2026` or `13th August 2026` on HSS).
   * **`category` / `item_type`**: Available on the listing cards (e.g. `.ann-chip` on EE indicating `Events` vs `Admissions`; `.event-category span` on HSS indicating `International Conference / Symposium`).
   * **`listing_summary` / `teaser`**: Short excerpt available on listing cards before clicking through to detail views.

2. **Common Pipeline Behaviors**:
   * **Two-Step Crawl Pattern (Listing → Detail)**: None of the surfaces display full body content inline on the listing page. All 3 surfaces require the scraper to collect item links from the listing and fetch the detail page to capture complete content.
   * **Server-Rendered HTML Delivery**: None of the three listing surfaces require headless browser execution (Puppeteer/Playwright) to extract initial listing cards. Plain HTTP GET requests (`fetch` with standard user-agent headers) return full HTML containing all listing cards.
   * **Breadcrumb Navigation**: Detail pages across both systems provide structured breadcrumbs (`.annd-crumb` in EE; `.breadcrumb` in HSS) that enable deterministic extraction of taxonomy and department hierarchy.

---

## Source-specific exceptions

The following aspects do **not** generalize across the surfaces and require dedicated source adapter handlers:

1. **The PDF Wrapper Phenomenon on Administrative Feeds (HSS News)**:
   * Administrative announcements (such as `https://www.hss.iitb.ac.in/news/shortlisted-candidate-phd-interview-autumn-sem-2026-27`) do not store announcements as HTML text.
   * The detail page is an empty container whose primary payload is an anchor linking to `/sites/default/files/2026-05/Shortlisted%20candidates%20for%20PhD%20Interview%20Autumn%202026-27.pdf`.
   * **Scraper Exception**: The crawler must check for the presence of file attachments (`a[href$=".pdf"]`). If present, the adapter must flag `payload_type = "pdf"`, capture the direct PDF URL, and route the artifact to a PDF text extractor (e.g., `pypdf` or `pdfplumber`) rather than searching for standard article body paragraphs.

2. **CMS Differences & Selector Stability**:
   * **Drupal-backed surfaces (`hss.iitb.ac.in`)**: A Views block per listing (`.view-events-page`, `.view-seminars-and-talks`) wrapping theme cards: `.event-card-wrapper`, `.event-name a`, `.event-category span`, `.event-room-details li` rows told apart by their icon class (`icon-calendar`, `icon-time`, `icon-marker`). The generic Drupal Views row classes (`.views-row`, `.views-field-*`) are **not** used by this theme. Field extraction must strip internal whitespace.
   * **Astro/Tailwind static surfaces (`ee.iitb.ac.in`)**: Rely on utility-driven custom classes (`.ann-ticker-item`, `.ann-chip`, `.ann-action--main`, `.annd-crumb`). The markup is much flatter and cleaner, but uses entirely distinct class hierarchies from Drupal.

3. **External Action Redirects in EE Announcements**:
   * Certain cards on the EE News feed feature two action buttons: `.ann-action--main` (pointing to the internal EE department detail page) and `.ann-action--link` (pointing directly to external Google Sites, seminar workshop portals, or third-party conference registrations).
   * **Scraper Exception**: The normalizer must decide whether to store the internal departmental detail URL or the primary canonical external workshop link.

4. **Pagination vs. Dynamic Client-Side Filtering**:
   * **HSS**: Uses classic HTTP query parameter pagination (`?page=1`, `?page=2`) easily traversable by following standard `<a rel="next">` links.
   * **EE**: Loads items into the DOM grouped by years/months with interactive filtering buttons (`Upcoming`, `Past`, and calendar controls). Traversing past archives requires querying specific archive endpoints or simulating year/month query filters rather than simple sequential page numbers.
