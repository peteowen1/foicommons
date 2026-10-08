# NEXT-STEPS

Living queue for foicommons. Read this first. Last updated 8 October 2026 (end of the wayback
extraction session).

## Needs Pete

- [ ] **Lodge the DSS FOI request**: `analyses/jobseeker-deaths/foi-request-draft.md`. Fill in the
  reply email; send direct to DSS or via Right to Know (public, linkable, publishes your name).
  Check `FOI@dss.gov.au` on the DSS FOI page first (taken from search results only). The 30-day
  decision clock starts when it's received.
- [ ] **Send the Right to Know permission request**: `docs/righttoknow-permission-request.md`, via
  their contact form. Until they say yes, no automated access to righttoknow.org.au.
- [ ] **Jericho post prose**: draft at `C:\dev\inthegame-blog\blog\2026-10-07-jobseeker-deaths\index.qmd`
  (`dev`, pushed, `draft: true`). Stats, tables and bullets are in; the writing is Pete's. Preview with
  `quarto preview --no-browser --port 4848 -M draft:false` and check light mode and mouse hover
  (not checked by Claude).

## Where it stands

- **Phase 1 archive.** DSS main log: 349 entries, 214 documents (1.08 GB). Services Australia:
  167 entries, 144 documents (382 MB), October 2024 onward only (older entries are off the page).
  135 DSS entries have no document online (page says pre-November 2025 releases are by email).
- **All-agency archive (running).** Registry of 195 agencies (AGOR, 30 June 2026); 92 with a log
  URL found (155 logs); 22 blocked (403 or challenge pages: ACCC, Ombudsman, APH, FWC, Federal
  Court, ...). `run_full.sh` is harvesting alphabetically (at Attorney-General's Department at
  17:23, 7 October). Log: `data/logs/harvest.log`. It died silently at 17:28 (the `nohup` launch did
  not outlive its Claude session); relaunched 21:06 as a detached Windows process. Resume the same way
  (PowerShell): `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"C:/Program Files/Git/bin/bash.exe" -lc "cd /c/dev/foicommons && ./run_full.sh >> data/logs/harvest.log 2>&1"'}`.
  Check it is alive with `tasklist | grep Rscript`, not Git Bash `ps` (which can't see Rscript.exe).
  Estimate 12-25 hours; tens of GB. **Checked 8 October 13:14: alive, 92 of 155 logs complete (at Treasury),
  65 GB in `data/raw`, no log stopped on a block.** Phase 2 of the run: fallback discovery for agencies with no log found.
- **Extraction.** pdfplumber over the 49 table-bearing phase 1 documents: 1,038 numeric tables
  (`data/extract/tables_index.csv`). Vision transcription over the 13 unruled documents: 21 tables,
  17 pass every check, 4 flagged for source totals that don't add up (one re-checked against the
  page by Claude). See `docs/plan-phase2-extraction.md`.
- **Analysis.** `analyses/jobseeker-deaths/`: FINDINGS.md, `rebuild.py` (20 asserted figures, all pass).
- **Rights.** `docs/rights.md`: publish extracted figures + links; keep PDFs private; takedown on request.

## Queue (ranked)

1. **Scanned batch: done and reviewed 7 October.** 308 tables, 306 pass; 2 flags are a source arithmetic
   error and 3 unresolvable blurry averages (see the plan's status lines). FOI LEX 55799 clean table:
   5,040 rows, every identity passes. Left: open the first PR to `main` once there is a `main` branch.
2. **Internet Archive history: DSS recovered and extracted (8 October); other agencies next.** `R/wayback.R` (pages -> parse ->
   files -> size). 670 files recovered from the old DSS log (2010-11 to 2024; 990 MB; manifest
   `data/manifest_dss_wayback.csv`). Survey (`scripts/survey.py` -> `data/survey/survey_dss_wayback.csv`):
   555 scanned (6,886 pages), 17 with text tables -> 393 numeric tables via pdfplumber (done).
   **Next: triage the 6,886 scanned pages.** Packed contact sheets are built: 431 sheets,
   `data/extract/vision/scanned_wayback/packed_index.json` (tiles labelled "D017 p3" -> file and page).
   Pilot on 20 first-batch sheets with known answers (`scanned_packtest/pilot_*.json`): Sonnet 5.5 caught
   67/70 table pages with 1 false positive (134k tokens); Haiku 4.5 caught 66/70 but listed 81 non-tables
   (93k). Rerun 8 October with the identical prompt on `claude-haiku-5-5` (confirmed in its report):
   69/70 with 1 false positive (147k tokens; `pilot_haiku55.json`). **Use Haiku 5.5 for the full triage.**
   Its only miss is D018 p21; the one false positive (D019 p1) is the same page Sonnet flagged, so the
   answer key may be wrong there (not checked).
   **Full triage done 8 October** (10 Haiku 5.5 agents, ~2.4M tokens; batch 03 wrote its file but never
   reported its model ID). `scripts/merge_triage.py` -> `scanned_wayback/triage.json`: 699 of 6,886
   pages flagged (330 stats, 252 charts, 117 maybe) in 139 documents. Copies of the same document
   dropped (12/13-065 re-released four 12/13-073 docs; D550 = D158): **322 stats pages in 112 documents
   to transcribe** (`to_transcribe.json`). Invoices and fee schedules are kept (batches disagreed;
   filter by title after transcription if unwanted). Charts wait for item 6; the 117 maybes need a
   full-size look. Batch 08's stats include research regression tables (DSP/SCV annexes): decide.
   **Transcription in progress (8 October).** Pete: research/regression tables out for now, later sweep
   (D520 and 2 maybes tagged `out_of_scope` in triage.json; agents log others to `scanned_wayback/skipped/`).
   Maybes checked full size by Haiku 5.5: 25 more stats pages -> 324 pages, 54 batches of 6
   (`scanned_wayback/batches/`, brief `scanned_wayback/BRIEF.md`, Sonnet 5.5, ~20k tokens/page).
   Pages prepared with `python -P scripts/ocr_pages.py queue|ocr|strips data/extract/vision/scanned_wayback`.
   **All 55 batches done 8 October: 556 tables, 387 pass verify, 169 flagged (~6.3M Sonnet tokens).**
   `python -P scripts/sort_flags.py dss_wayback` -> `dss_wayback/flag_sort.csv` groups the flags: 40 OCR misses
   confirmed by printed totals, 16 text-layer false alarms (12/13-044 slides), 3 rounding, 61 OCR-only (278 cells,
   nothing to sum against), 49 sum gaps (28 are the 12/13-037 quirk: printed totals omit Family Supplement).
   Loose agent tolerances were tightened to the smallest passing value. 5 research tables in `skipped/`.
   **Blind re-read done 8 October (~0.9M tokens): 0 misreadings in a random 60 of the 278 OCR-only cells**,
   and 86 of 87 checkable cells in off-total tables agree, so those gaps are in the source documents. 116 cells
   added to `vision/confirmations.csv`. Verify after that: wayback 392 of 556 tables pass (164 flagged, all
   explained in `flag_sort.csv`); whole vision set 719 of 896. `11_12-044__52 p17` Grants Unexpended
   resolved by Pete: (83,065) as printed; the total not reconciling is the source. The 6 cells in tables split across
   pages 5-6 (12/13-037 foi_20037-3 p5 t4, t12) were re-read with both pages: all agree.
   Lesson: a blind item must name the row by all its text cells and include every page the table spans,
   or the reader answers a different row.
   After all: one blind re-read round for flags (as batch 1), set
   rounding tol on wave-1 tables, mark `10/11-015 doc7 p13` a copy of doc5 p11, look at
   `10/11-015 doc4 p10` (total 1,105,715 vs rows 1,817,917) and `10/11-041 document5` (sideways, totals short), `11_12-044__52 p17` (fitted cell reverted, sum flagged),
   `12_13-044 Document_2008 p41` (tiny digits, OCR matched 2/70), `p35` (total 1,819 off), `12_13-007 doc_72 p17`
   (possible Chair row lost at a strip cut). Text-layer-only flags on 12/13-044 slides are false alarms (embedded
   text lacks the numbers; OCR passes): handle as a group.
   Free line-detection pre-filter (`scripts/table_filter.py`) tried: keeps 48% of pages and 162/170 table
   pages on batch 1, but only ~14/22 on documents other than 55799, so not used for this batch.
   Then: transcribe the triaged pages (strips + Sonnet + OCR checks, as batch 1).
   Sizing for other agencies: `data/wayback/sizing.csv`; 11,108 foi-named PDFs archived across answered
   domains (ANAO, DFAT, OAIC, IP Australia, AGD lead); 27 queries failed with archive 503/504 and are retried
   on the next `Rscript R/wayback.R size`; the largest domains need CDX paging.
3. **When the all-agency run finishes**: rerun the survey and pdfplumber over everything, count
   pages needing vision, then decide on the Claude API batch interface for scale (cost per page).
4. **Back up extracted tables: first backup done 8 October.** Private release `extract-backup` on the
   (private) repo holds `foicommons_extract_2026-10-08.tar.gz` (4.4 MB, 9,967 files: all of `data/extract/`
   except page images, which rebuild from the PDFs). Round-trip checked byte-identical. Refresh after each
   extraction run: `tar --force-local --exclude='*.png' -czf <dated>.tar.gz -C data extract` then
   `gh release upload extract-backup <file>`. Never make this release public (`docs/rights.md`). Raw PDFs stay
   local; they can be re-fetched while online, so the Internet Archive step matters.
5. **Jericho piece follow-ups**: interactive SVG flow chart (site rule; current one is a mermaid
   placeholder); Newstart totals for 2007-2012 to turn the FOI 19/20-073 partial-capacity counts into
   shares. (Coronavirus Supplement start date of 27 April 2020 confirmed against the Parliamentary Library, 7 October.)
6. **Chart-reading pass**: data-labelled charts skipped by the table pass (NDIS survey charts in
   FOI 2021-064, 1800RESPECT stats in 16/17-082); plus up to 274 wayback chart pages (a few in duplicate copies) in
   `scanned_wayback/triage.json` (kind "chart"; one chart already transcribed as a table: 10/11-059
   59_doc2 p124 t1).
7. **Research-table sweep** (deferred by Pete 8 October): D520 (23 pages), 2 maybes tagged `out_of_scope` in
   `scanned_wayback/triage.json`, and 5 tables logged in `scanned_wayback/skipped/*.csv`. No printed totals,
   so checks are OCR-only; ~0.6M Sonnet tokens.

## Deliberately not done

- **Right to Know scraping**: house rules ban unapproved automation; paused pending permission.
  Its JSON endpoints also returned Cloudflare challenges. 4 requests were made before the pause.
- **Republishing full PDFs**: release under FOI gives no licence to republish; see `docs/rights.md`.
- **Tesseract OCR**: not installed; vision transcription with code checks replaced it.
- **No `main` branch yet**: create via a reviewed PR when there's something to merge.

## Corrections made during the first session (so they aren't repeated)

- The straight-line estimate of 52 deaths per 100,000 for full-capacity recipients was first called a
  failed sense check; its 95% range (6-98) includes the non-welfare 67, and dropping 2020 gives 68.
- The "at most 18% double counting" bound was superseded by DSS FOI 2122-068: only about half of
  AIHW's JobSeeker deaths were on the payment at death.
- `pdftotext -layout` shifts rows in sparse tables; use pdfplumber or vision for tables.
- Writing Windows paths through `sed`/Python strings mangled `\f` and `\a` into control characters
  three times. Use forward slashes in paths written by scripts.
