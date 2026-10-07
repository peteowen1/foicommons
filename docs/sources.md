# Sources

Checked 7 October 2026. User-Agent: `foicommons-archiver/0.1 (personal research archive)`.

## 1. Department of Social Services (DSS) disclosure log
- URL: https://www.dss.gov.au/access-information/freedom-information/our-freedom-information-disclosure-log (paged with `?page=N`, 20 per page, page 0 to 15).
- robots.txt (www.dss.gov.au): no crawl-delay. Disallows `/search`, `/admin/`, `/taxonomy/` etc. The log and `/system/files/` are not disallowed. No terms page about automated access was found on the FOI pages; we apply 3s between requests.
- Structure: each item is a "card" with Reference number (e.g. FOI LEX 56747), Release date, Publication date (some cards), Decision (e.g. Partial release; some cards lack it), Summary of request, and a list of PDF links with size labels. Files live under `/system/files/documents/YYYY-MM/`. Every label/value pair is kept in `extra_json`.
- Items found: 349 item-document rows across 16 pages (about 315 unique reference numbers; some items have several PDFs).
- Oddities: other DSS logs exist and are NOT yet archived: `portfolio-agencies-freedom-information-disclosure-log` and `portfolio-ministers-freedom-information-disclosure-log`. The older known file `https://dss.gov.au/system/files/foi-attachments/foi-2122-068-document.pdf` returns a 301 from the bare domain and is not on the current log (older log pre-dates the card layout); not yet followed up. Some PDFs are very large (up to ~160 MB).

## 2. Services Australia disclosure log
- URL: https://www.servicesaustralia.gov.au/freedom-information-disclosure-log (single page, one table).
- robots.txt: `Crawl-delay: 10`, which we obey (one request per 10 seconds). Disallows `/search/`, `/admin/`, `/minister/`, `/sites/default/files/job-packs/` etc. The log and `/sites/default/files/` documents are allowed. No terms page about automated access found.
- Structure: table of Date and Detail. Detail has description with LEX number, counts of documents released in full/part, link to a PDF, "Sections of the Act" and "Exemptions". No decision or applicant column. Full text kept in `detail_text`.
- Items found: 167 rows, covering roughly October 2024 to October 2026 only (older entries are not on the page).
- Oddities: some rows say "available upon request" with no online document (recorded with an empty `doc_url` and a note). Titles sometimes include bullet lists. Reference format is "LEX nnnnn".

## 3. Right to Know (righttoknow.org.au)
**Right to Know: automated access paused pending permission from OpenAustralia Foundation (house rules ban unapproved automation).**
- robots.txt allows `.json` pages and `*/request/*/response/*/attach/*` but disallows search, feed, and response pages.
- Before the pause: automated requests to `/body/department_of_social_services.json` and `/body/services_australia.json` both returned 403 with a Cloudflare "Just a moment" challenge. Not bypassed.
- The scraper was deleted. Nothing was crawled beyond the four requests above (robots.txt, two body .json, one help page). Saved only in gitignored `data/probe/` (two challenge pages and the help page).
- Next step: Pete asks OpenAustralia Foundation for permission (Pro/API route). Do not resume without it.

---

# Phase 1b: all Commonwealth agencies (generic harvester), added 7 October 2026

## Method
1. **Registry** (`R/build_registry.R`, then `R/discover_fallback.R`). Entity list = Australian Government Organisations Register (AGOR, 30 June 2026 edition, CSV from data.gov.au dataset `australian-government-organisations-register`; same data as directory.gov.au; saved at `data/registry/source/agor-2026-06-30.csv`; robots.txt on directory.gov.au allows this). Scope: the 195 "primary bodies" (non-corporate entities, corporate entities, Commonwealth companies). Secondary bodies, committees, joint ventures and subsidiaries (1,191 more AGOR rows) are not included, so their own logs (if any) are not covered unless linked from a parent. Every AGOR field is kept as an `agor_*` column. Ministers' offices are not in AGOR; only DSS's ministers log is covered (seeded).
2. **Discovery**: homepage, then a link whose text/URL mentions freedom of information, then links on that page mentioning a disclosure log (one row per log). Fallback pass: `/sitemap.xml` URL matches, then ~16 guessed paths. Results in `data/registry/discovery.csv` (resumable), assembled into `data/registry/agencies.csv`. Found logs are NOT verified by a fetch at discovery time; the harvester reports empty or wrong pages. Some "logs" are a direct file (e.g. APRA zip) and are downloaded as documents.
3. **Harvest** (`R/harvest_log.R`, helpers in `R/harvest_helpers.R`): saves raw HTML of each listing page (pagination found from rel=next, "next" links, `?page=` style links, year/archive sub-pages; sort/filter variants ignored), follows detail pages one level deep, downloads every linked document of any type (streamed to disk), logs mailto/external/other links to the manifest. Items are found as repeated blocks (cards, table rows, list entries), so items without any link are kept too (`link_type = none`). HTML goes to `data/raw_html/<log_slug>/<date>/` (`pages_index.csv` maps files to URLs), documents to `data/raw/<log_slug>/<hash>_<name>`, manifest `data/manifest_<log_slug>.csv`. Detected fields (reference, date, decision) are best-effort regexes; the full item text is always kept in `item_text`.
4. **Politeness**: robots.txt per host (Disallow and Crawl-delay), 3 s minimum per host (Services Australia 10 s), User-Agent as phase 1, redirects followed one hop at a time with robots and throttle on every hop. 429 or a challenge page marks the host blocked at once; 403 on a listing/detail page marks it blocked; 403 on documents blocks the host after 3 in a row. Blocked hosts are written to `data/registry/blocked_hosts.csv` and never retried.

## Registry stats (after the first discovery pass; the fallback pass is still adding logs)
- 195 agencies in scope. 92 have at least one disclosure log URL (155 log rows in total, some agencies have several, e.g. ATSB one page per year, DSS three).
- Not found yet: 41 no FOI page found, 21 FOI page found but no log link detected, 11 no website in AGOR, 4 unreachable, 3 homepage disallowed by robots.txt, 1 error. The fallback pass targets the no-FOI and FOI-page-only groups.
- Blocked (403 or challenge page from our User-Agent, not bypassed): armyholidays.com.au, aafcans.gov.au, asc.com.au, aciar.gov.au, accc.gov.au, humanrights.gov.au, aifs.gov.au, aspi.org.au, csc.gov.au, aph.gov.au, fwc.gov.au, fedcourt.gov.au, frdc.com.au, futurefund.gov.au, grdc.com.au, hsra.gov.au, mdba.gov.au, nfsa.gov.au, nga.gov.au, nma.gov.au, ombudsman.gov.au, moadoph.gov.au, agedcarequality.gov.au, casa.gov.au (CASA blocked mid-test on its listing page 5). The current list is always `data/registry/blocked_hosts.csv`.
- `run_order` in the registry follows AGOR staffing level, but that field is blank for most agencies, so order is effectively alphabetical.

## Test results
Tested with small caps on AFP, ASIC, ATSB (2025-26 page), ARC, APRA and the DSS portfolio-agencies and portfolio-ministers logs. Manifests had reference, date, decision (where the site gives them) and PDFs/zips downloaded with sha256. CASA returned 403 and was marked blocked. Resume tested on AFP (existing documents skipped, listing pages reused).

## DSS notes
- `dss-portfolio-agencies` log is empty ("There are no disclosure log entries at this time"); `dss-portfolio-ministers` has a few entries.
- Raw HTML of the DSS main log is in `data/raw_html/dss-main/` (manifest `data/manifest_dss-main.csv`, HTML only) and Services Australia in `data/raw_html/servicesaustralia-log/` (HTML only). Phase 1 manifests were not touched. The generic harvester found 4 more DSS document links than phase 1 (218 vs 214 unique), e.g. FOI LEX 46667.
- Of phase 1's 135 DSS rows with no document link: 1 (FOI LEX 46667, a 69 MB PDF) did have a document on the listing page that phase 1 missed (now in `data/manifest_dss_detail.csv`); 2 have an inline link to a normal DSS page (FOI LEX 55078 to the 1800RESPECT evaluation page, FOI 2122-125 to an ILC research summary whose 4 document links return 404); the other 132 are cards with a summary only. The page says "For documents released before November 2025, email FOI@dss.gov.au", which explains most of them; the DSS page does not say this per item, so treat "on request" as likely, not confirmed.

## Known limits
JavaScript-rendered logs are not handled (they show up as pages with no items). Detail pages are followed one level only. Search-form-only logs and logs behind blocked hosts are missing. Discovery picks the first FOI page it finds and can pick a wrong page.
