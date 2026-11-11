# NEXT-STEPS

Living queue for foicommons. Read this first. Last updated 11 November 2026. History of the 7-9 October
sessions: `docs/backlog/journal-2026-10.md`. Decisions and things deliberately not done: `docs/DECISIONS.md`.

## Where it stands

- **Phase 1 archive: done.** All-agency run finished 8 October 20:43 (170/170 logs; NDIS 403 recorded).
  Survey: 19,310 files, 14,312 unique documents (count from `documents`, never raw folders; `docs/data-model.md`).
- **Phase 2 extraction.** pdfplumber over 1,407 unique table-bearing PDFs; vision over phase 1 and DSS
  wayback scans. `facts`: 1,071,407 from 15,741 tables (11 November, after the Haiku naming pass).
  Rebuild: `python -P scripts/build_catalogue.py` then `python -P scripts/build_facts.py` (~2 min).
- **Backup**: private release `extract-backup`, latest `foicommons_extract_2026-11-11.tar.gz` (40 MB,
  136,640 files, round-trip sha256 checked). Refresh after each extraction run:
  `tar --force-local --exclude='*.png' -czf <dated>.tar.gz -C data extract` then
  `gh release upload extract-backup <file>`. Never make it public (`docs/rights.md`).
- **Analysis**: `analyses/jobseeker-deaths/` (`rebuild.py`, 20 asserted figures).
- **Checks**: Haiku check squad after each chunk of work (see `CLAUDE.md`). Last run: seed 15, 11 November.

## Needs Pete

- [ ] OPEN **Lodge the DSS FOI request**: `analyses/jobseeker-deaths/foi-request-draft.md`. Fill in the reply
  email; send direct to DSS or via Right to Know. Check `FOI@dss.gov.au` on the DSS FOI page first.
  No sign of it in Gmail as of 11 November (Hotmail not checked).
- [ ] OPEN **Send the Right to Know permission request**: `docs/righttoknow-permission-request.md`, via their
  contact form. Until they say yes, no automated access to righttoknow.org.au.
- [ ] OPEN **Jericho post prose**: `C:\dev\inthegame-blog\blog\2026-10-07-jobseeker-deaths\index.qmd`
  (`draft: true`). Preview: `quarto preview --no-browser --port 4848 -M draft:false`.

## Queue (ranked)

1. OPEN **Naming pass follow-ups.** Pass done 11 November (8,698 of 8,698 tables, ~48M Haiku tokens, 59 min,
   run `wf_eb4e574c-7d3`; names in `data/naming/names.csv`, loaded by `apply_names` in `build_facts.py`;
   counts and the 20-table Sonnet check in `docs/data-model.md`). Left: periods from names.csv into facts
   (4,663 tables give one; parse to period_type); 510 value columns with no measure; tables judged not
   statistics were dropped on Haiku's word (4 of 4 right in the check; 2,137 tables, 96,509 facts): sample 20
   more before publishing. Done when: periods loaded and a second check of 20 `labelled` named facts passes.
2. OPEN **Check-squad seed 15 leads** (`data/reviews/haiku_*_15.md`; Haiku's reading, not verified unless
   marked). Fixed 11 November: identifier columns counted as facts (items 12, 16; 1,785 facts). Left: item 10
   units are the table-level note ("recipients"; "Ave" columns are averages); periods null where the page header gives a date ("As at 26/12/2025",
   items 5 and 8). Scripts: 4 new (blocked-host second writer, wayback basename skip, swallowed `kept_groups`
   error, unread `.hv$fail`), 15 still open. Catalogue: 52 logs with 0 requests, 239 raw dates not parsed.
   Done when: each is verified against the page or code and fixed or struck.
3. OPEN **Scale vision: decide with Pete.** Counted 11 November: 6,476 scanned files = 4,355 unique PDFs,
   171,891 pages (166 documents over 200 pages hold 73,103 of them; median 8 pages). At DSS wayback rates
   (triage ~350 Haiku tokens/page; 10% of pages flagged; ~20k Sonnet tokens per transcribed page): triage
   ~60M Haiku tokens, transcription ~17,000 pages ~340M Sonnet tokens. The 10% is DSS-only (unverified for
   other agencies): pilot triage on one agency's 1,000 pages first. Batch API halves the cost but is API
   billing, not session quota.
4. OPEN **Small data fixes**: 109 FOI LEX 55799 tables without a month (it is in the page header);
   month-only release dates become day 01 (140 requests); 185 raw spellings of the decision field;
   `review_samples.py` never samples 21 `tNN_title` vision tables; WGEA registry URL points at its IPS page
   (62 "documents" are mostly annual reports): point it at the disclosure-log section; open from squad run 12:
   field labels as titles (141), 601 requests with no document row, 18/19-045 p35 column shift.
5. OPEN **DSS wayback leftovers** (detail in the journal): blind re-read for flags, rounding tol on wave-1
   tables, `10/11-015 doc7 p13` copy of doc5 p11, `10/11-015 doc4 p10`, `10/11-041 document5`,
   `12_13-044 Document_2008 p41` and `p35`, `12_13-007 doc_72 p17`.
6. OPEN **Internet Archive for other agencies**: `data/wayback/sizing.csv` (11,108 foi-named PDFs; ANAO, DFAT,
   OAIC, IP Australia, AGD lead). Retry the 27 failed queries with `Rscript R/wayback.R size`; large domains
   need CDX paging.
7. OPEN **Speed**: `table_captions.py` took 50 minutes on one process; give it the `--workers` pool from
   `extract_tables.py` before the next run.
8. OPEN **Jericho follow-ups**: interactive SVG flow chart (current one is a mermaid placeholder); Newstart
   totals for 2007-2012 to turn FOI 19/20-073 partial-capacity counts into shares.
9. OPEN **Chart-reading pass**: NDIS survey charts (FOI 2021-064), 1800RESPECT stats (16/17-082), up to 274
   wayback chart pages (kind "chart" in `scanned_wayback/triage.json`).
10. OPEN **Research-table sweep** (deferred by Pete 8 October): D520, 2 `out_of_scope` maybes, 5 tables in
    `scanned_wayback/skipped/*.csv`. ~0.6M Sonnet tokens.
11. OPEN **First PR to `main`**: no `main` branch yet. Create it via a reviewed PR when the extraction work is
    ready to publish.
