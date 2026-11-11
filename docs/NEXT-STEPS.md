# NEXT-STEPS

Living queue for foicommons. Read this first. Last updated 11 November 2026. History of the 7-9 October
sessions: `docs/backlog/journal-2026-10.md`. Decisions and things deliberately not done: `docs/DECISIONS.md`.

## Where it stands

- **Phase 1 archive: done.** All-agency run finished 8 October 20:43 (170/170 logs; NDIS 403 recorded).
  Survey: 19,310 files, 14,312 unique documents (count from `documents`, never raw folders; `docs/data-model.md`).
- **Phase 2 extraction.** pdfplumber over 1,407 unique table-bearing PDFs; vision over phase 1 and DSS
  wayback scans. `facts`: 1,169,701 from 17,377 tables (rebuilt and byte-identical 11 November).
  Rebuild: `python -P scripts/build_catalogue.py` then `python -P scripts/build_facts.py` (~2 min).
- **Backup**: private release `extract-backup`, latest `foicommons_extract_2026-11-11.tar.gz` (40 MB,
  136,640 files, round-trip sha256 checked). Refresh after each extraction run:
  `tar --force-local --exclude='*.png' -czf <dated>.tar.gz -C data extract` then
  `gh release upload extract-backup <file>`. Never make it public (`docs/rights.md`).
- **Analysis**: `analyses/jobseeker-deaths/` (`rebuild.py`, 20 asserted figures).
- **Checks**: Haiku check squad after each chunk of work (see `CLAUDE.md`). Last run: seed 14, 9 October.

## Needs Pete

- [ ] OPEN **Lodge the DSS FOI request**: `analyses/jobseeker-deaths/foi-request-draft.md`. Fill in the reply
  email; send direct to DSS or via Right to Know. Check `FOI@dss.gov.au` on the DSS FOI page first.
  No sign of it in Gmail as of 11 November (Hotmail not checked).
- [ ] OPEN **Send the Right to Know permission request**: `docs/righttoknow-permission-request.md`, via their
  contact form. Until they say yes, no automated access to righttoknow.org.au.
- [ ] OPEN **Jericho post prose**: `C:\dev\inthegame-blog\blog\2026-10-07-jobseeker-deaths\index.qmd`
  (`draft: true`). Preview: `quarto preview --no-browser --port 4848 -M draft:false`.
- [ ] OPEN **Director of National Parks** shares DCCEEW's log, so 785 documents count under both.
  Recommendation: fold Parks into DCCEEW for counting.

## Queue (ranked)

1. OPEN **Text-layer grid quality.** Seed 14 found new-agency grids match the printed page for only 27 of 40
   sampled values (DSS: 72 of 74). Not verified. Done when: a checked sample says whether `labelled` needs a
   quality gate before publishing, and the gate exists if so.
2. OPEN **One Haiku pass over unnamed tables** (Pete, 8 October: one pass). Trigger fired: harvest extracted.
   Covers the vision tables with unclear measure names and the `context needed` text-layer tables (602,642
   facts in 8,683 tables). Do after item 1, so the pass doesn't name bad grids.
3. OPEN **Scale vision**: count scanned pages needing vision (6,476 scanned PDFs in the survey) and price the
   Claude API batch interface per page. Done when: a page count and cost estimate are in this file for Pete.
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
