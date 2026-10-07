# NEXT-STEPS

Living queue for foicommons. Read this first. Last updated 7 October 2026 (end of the session
that started the repo).

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
  17:23, 7 October). Log: `data/logs/harvest.log`. Resume: `nohup ./run_full.sh >> data/logs/harvest.log 2>&1 &`.
  Estimate 12-25 hours; tens of GB. Phase 2 of the run: fallback discovery for agencies with no log found.
- **Extraction.** pdfplumber over the 49 table-bearing phase 1 documents: 1,038 numeric tables
  (`data/extract/tables_index.csv`). Vision transcription over the 13 unruled documents: 21 tables,
  17 pass every check, 4 flagged for source totals that don't add up (one re-checked against the
  page by Claude). See `docs/plan-phase2-extraction.md`.
- **Analysis.** `analyses/jobseeker-deaths/`: FINDINGS.md, `rebuild.py` (20 asserted figures, all pass).
- **Rights.** `docs/rights.md`: publish extracted figures + links; keep PDFs private; takedown on request.

## Queue (ranked)

1. **Scanned batch (72 documents)**: two independent vision transcriptions per table, A/B must
   agree (`vision_tools.py verify`). Build the queue from `data/survey/survey_docs.csv`
   (class "pdf: scanned/image only") plus scanned pages inside mixed documents. About 2-3 agent runs.
2. **Internet Archive history**: agencies drop documents after about 2 years (FOI 2122-068 is already
   off the current DSS log). Use the Wayback CDX API for old snapshots of each log and their PDFs,
   politely. Biggest source of missing history.
3. **When the all-agency run finishes**: rerun the survey and pdfplumber over everything, count
   pages needing vision, then decide on the Claude API batch interface for scale (cost per page).
4. **Back up extracted tables**: `data/extract/` to GitHub release assets (piggyback pattern).
   Raw PDFs stay local; they can be re-fetched while still online, so the Internet Archive step matters.
5. **Jericho piece follow-ups**: interactive SVG flow chart (site rule; current one is a mermaid
   placeholder); Newstart totals for 2007-2012 to turn the FOI 19/20-073 partial-capacity counts into
   shares; confirm the Coronavirus Supplement's 27 April 2020 start date.
6. **Chart-reading pass**: data-labelled charts skipped by the table pass (NDIS survey charts in
   FOI 2021-064, 1800RESPECT stats in 16/17-082).

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
