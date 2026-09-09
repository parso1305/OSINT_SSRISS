# IIT Bombay surface Recon 

## Domain 
-Domain : https://www.iitb.ac.in
There are many subdomains and redirects.
subdomains : [bighome,SSO,landing,rnd....]
Redirects : [Aspire,]
None of sso or the redirect targets are useful content surfaces on their own — they're infrastructure, not data — but rnd.iitb.ac.in is a genuinely separate content surface worth tracking alongside the main domain.
## Robots.txt data
URL - https://www.iitb.ac.in/robots.txt
disallowed:
- /core/
- /profiles/
- /admin/
- /search/
- /user/login
- /user/logout
- /user/register
- /user/password
Observation:
all user-agents are considered same (no biasing)
all disallowed are general login and register/passwords. 
The Disallow directories are "core" and "profiles".
but there are some extensions which are allowed like .css , .jpeg,.svg and other realted extension.so, to find what else is present over there which is not these extensions.  
every news and events are mentioned at the homepage. 

## sitemap 
A sitemap was not confirmed. the endpoint did not return a usable sitemap as per recon. 
And also not anything available as the RSS feed which is openly available only some sources as library data is available which is out-dated. 

## Major news and announcement 
All the major news , announcement and the event are highlighted over the homepage itself. 

### Surface: IIT Bombay News

URL:
https://www.iitb.ac.in/news

Type:
News / announcements

Surface type:
Listing page

Contents:
Chronological news articles published by IIT Bombay.

Format:
HTML

Pagination:
Yes. The current page exposes numbered pages and Next/Last navigation.

Example records:
- IAF and IIT Bombay Sign MoA to Advance Flight Test Education and Research
- IIT Bombay Celebrates Van Mahotsav 2026
- IIT Bombay Hosts ‘Khelo India Samvaad – Khel Ki Baat PM Ke Saath’
- IIT Bombay Holds its 64th Convocation and Departmental Degree Award Function

Approximate record count:
The first page currently exposes around 9 records. The complete
historical count should be determined by following pagination rather
than assuming the first page represents the whole collection.

Likely fields:
- title
- publication date
- summary/excerpt
- detail URL

Detail pages:
Yes. Each listing item contains a "Read more" link.

Why good:
- structured listing
- clear dates
- clear titles
- predictable detail-page relationship
- pagination provides a natural crawl boundary
- useful content
- HTML rather than PDF

Why not perfect:
- summaries may differ in structure/length
- pagination needs to be handled
- some articles may contain images or additional links

### Surface: Events Calendar

URL:
https://www.iitb.ac.in/events

Type:
Events / lectures / institutional events

Surface type:
Listing/calendar

Contents:
Upcoming and historical IIT Bombay events including lectures,
conferences, commemorative events and other institutional programs.

Format:
HTML

Pagination:
Needs investigation.

Example records:
- Institute Lecture on "Taming Turbulence"
- National Space Day 2026
- Annual Quantum Conclave
- Lecture on "Strong Interactions, Exotic Emergent Particles
  and Future Quantum Technologies"

Potential fields:
- event title
- date
- start date
- end date
- event/detail URL
- event description
- location, if present

Why good:
Potentially highly structured and directly useful for an events dataset.

Why bad:
The event endpoint was somewhat difficult to retrieve reliably during
this reconnaissance, so implementation/access complexity needs to be
tested before selecting it as the Week 1 target.

### Surface: Research Highlights / Glimpses

URL:
https://rnd.iitb.ac.in/glimpses

Type:
Research updates / research highlights

Surface type:
Listing page

Contents:
Research stories and summaries describing recent IIT Bombay research.

Format:
HTML

Example records:
- The Hard Truth about the Role of Soft Tissue in Brain Cancer Relapse
- IITB Researchers Develop Novel Method to Test the ‘Quantumness’ of Gravity
- Researchers Develop High-Precision AI System to Predict Flood Depths
- Twist in Light Enhances Chiral Discrimination

Potential fields:
- title
- summary
- detail URL
- researcher information, where present
- department/category, where present
- publication/research information, where present

Why good:
The listing is relatively clean and research items have clear
title/summary/detail relationships.

Why bad:
It is on the rnd.iitb.ac.in subdomain rather than the main
www.iitb.ac.in domain, and the individual research pages may contain
more complex content.

### Surface: Announcements

Entry point:
https://www.iitb.ac.in/

Type:
Announcements / notices

Surface type:
Listing embedded on homepage, with a "More" link.

Format:
HTML

Example records:
- Registration and Orientation for New Entrants 2026-2027
- Need for Guest Instructors
- IIT Bombay Open House 2026
- PhD/program admission announcements

Potential fields:
- title
- link
- announcement type
- date, where available
- detail page/PDF URL

Why good:
Useful and relatively easy to discover.

Why bad:
The homepage only exposes a limited number of announcements and the
underlying "More" surface needs separate investigation. Announcement
records may also link to external academic systems or PDFs, making
the data less uniform.