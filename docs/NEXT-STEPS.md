# NEXT-STEPS

Living queue for foicommons. Read this first. Last updated 11 November 2026. History of the 7-9 October
sessions: `docs/backlog/journal-2026-10.md`. Decisions and things deliberately not done: `docs/DECISIONS.md`.

## Where it stands

- **Phase 1 archive: done.** All-agency run finished 8 October 20:43 (170/170 logs; NDIS 403 recorded).
  Survey: 19,310 files, 14,312 unique documents (count from `documents`, never raw folders; `docs/data-model.md`).
- **Phase 2 extraction.** pdfplumber over 1,407 unique table-bearing PDFs; vision over phase 1 and DSS
  wayback scans. `facts`: 1,071,409 from 15,741 tables (11 November, after the Haiku naming pass).
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

1. OPEN **Naming pass: one restore.** Pass done and loaded 11 November (`docs/data-model.md`); measures publish
   as machine labels (`docs/DECISIONS.md`). The 510 columns with no measure stay `context needed` by design.
   Dropped "not statistics" tables checked twice (24 by Sonnet: 21 right, 2 borderline, 1 wrong;
   `data/reviews/naming_check/notstats_1114.json`), so ~5% of the 2,137 may hold real numbers: keep the drop.
   Item 8051 restored (`KEEP_TABLES` in `build_facts.py`). Left: re-extract naming item 4752's page (contract
   values in the page text, grid misread; `data/naming/tables.json` has its PDF and page). Done when: done.
2. OPEN **Check-squad seed 15 leads** (`data/reviews/haiku_*_15.md`; Haiku's reading, not verified unless
   marked). Fixed 11 November: identifier columns counted as facts (items 12, 16; 1,785 facts). Left: item 10
   units are the table-level note ("recipients"; "Ave" columns are averages); periods null where the page header gives a date ("As at 26/12/2025",
   items 5 and 8). Scripts: the 4 new ones fixed 11 November (one blocked-host writer, wayback skip by request +
   name, `kept_groups` errors logged, dead `.hv$fail` removed); 15 older ones still open. Catalogue: 52 logs with 0 requests, 239 raw dates not parsed.
   Done when: each is verified against the page or code and fixed or struck.
   **Seed 17** (11 November, `data/reviews/haiku_*_17.md`; seed 16 checked nothing, sampler fixed): values
   57 of 60 right, 3 unverified, 0 wrong. Fixed: leading "+", trailing "^" and dash runs (1,682 facts gained a
   value, 5,897 became nil). Left: measures vague in 21 of 40 labelled facts and wrong in 3 (26 and 40 are
   rule-based column names, 36 is a naming-pass guess); item 5 and 13 periods (as-at date on a sibling
   tile; day dropped); items 18 and 20 lose wave/age dims; sampler never draws `inferred` facts and does not
   record `named_by`; 2 new script notes (`table_filter.py` docstring `run` mode, `merge_triage.py:51` comment).
   **Seed 18** (first check of `inferred`; Haiku's verdicts, not re-verified): text-layer values 39 of 40
   right. Measures, 20 each: `labelled` 2 right / 13 vague / 5 wrong (column-name rule: "trainee pay" for
   points, "dyna mustang 525i" from other rows' cells); `inferred` 2 / 11 / 7 (5 of the 7 wrong had the answer
   printed on the page). Vision `checked` facts: measures 18 of 20 right. So text-layer measures are leads,
   not labels, whichever route named them: decide with Pete how they are published (queue item 3b).
   **Sonnet pilot** (11 November; bundles 33 70 75 261 289 441 539 770 835 846, same brief; Opus judged one
   column per table blind, `scripts/naming_compare.py`, `data/reviews/naming_compare/`): of 100, Sonnet right 59
   / vague 18 / wrong 7 / not statistics 16; Haiku 42 / 32 / 8 / 18. ~10 of Sonnet's vague have no meaning on
   the page at all. Cost 434k Sonnet tokens per 100 tables, so a full pass is ~38M.
3. OPEN **Scale vision: decide with Pete.** Counted 11 November: 6,476 scanned files = 4,355 unique PDFs,
   171,891 pages (166 documents over 200 pages hold 73,103 of them; median 8 pages). At DSS wayback rates
   (triage ~350 Haiku tokens/page; 10% of pages flagged; ~20k Sonnet tokens per transcribed page): triage
   ~60M Haiku tokens, transcription ~17,000 pages ~340M Sonnet tokens. The 10% is DSS-only (unverified for
   other agencies): pilot triage on one agency's 1,000 pages first. Batch API halves the cost but is API
   billing, not session quota.
4. OPEN **Small data fixes**:
   WGEA registry URL points at its IPS page
   (62 "documents" are mostly annual reports): point it at the disclosure-log section; open from squad run 12:
   601 requests with no document row, 18/19-045 p35 column shift.
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
