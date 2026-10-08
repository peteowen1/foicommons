# Phase 2 plan: getting tables out of released documents

Set 7 October 2026. Status lines at the bottom; update them as batches finish.

## Methods by document type

| Document type | Method | Checks before a table counts as extracted |
|---|---|---|
| Ruled tables (gridlines), text layer | pdfplumber default strategy (`scripts/extract_tables.py`) | Spot-check a sample against rendered page images |
| Unruled tables, text layer | Vision: render page (`vision_tools.py render`), transcribe to CSV | (1) every number appears in the page's text layer; (2) declared row sums / column totals |
| Scanned (no text layer) | Vision, two independent transcriptions (A and B) | (1) A and B agree cell by cell; (2) declared row sums / column totals |

`python scripts/vision_tools.py verify` runs every check and writes `data/extract/vision/verify_report.csv`.
A table with status `flag` is never published until a human or a re-transcription clears it.

Why vision: pdfplumber misses tables without gridlines (12 of 49 table documents), and its text
strategy splits words mid-token. pdftotext `-layout` shifts rows in sparse tables (FOI LEX 56898).
Reading the rendered page is the most reliable method; the checks make it auditable.

Proven on 16/17-018 (Newstart/Youth Allowance monthly recipients and spending, 2012/13-2015/16):
288 of 288 numbers found in the text layer, all row sums and annual totals pass. A deliberate
one-digit change was caught by two checks.

## Transcription rules (for whoever transcribes)

1. One CSV per logical table. Tidy format: one header row of short snake_case column names; one
   row per observation; repeat group labels (e.g. financial year) on every row instead of
   merged cells. Put units in meta.json, not in cell values.
2. Copy numbers exactly as printed, including suppression markers like `<5` and `n.p.`. Keep
   thousands separators out (write 559533, not 559,533). Never compute, round or fill a value.
3. Totals rows printed in the table: leave them out of the CSV and record them in
   meta.json `col_totals` so the verifier checks the rows against them.
4. Declare every arithmetic relationship the table claims (`row_sums`, `col_totals`), with a
   tolerance only where the source rounds (e.g. $000 figures: 0.0005 per component).
5. If a page is unreadable or ambiguous, write the CSV anyway and say what's uncertain in
   meta.json `notes`; the table will be flagged, not silently trusted.
6. meta.json must have `source_pdf`, `pages`, `title`, `units`, `transcriber`, `notes`.
7. Skip a page if `data/extract/tables_index.csv` already holds a good pdfplumber numeric table
   for it (2+ cols, under 60% empty, 30%+ numeric). Note the skip in the batch report.

## Queues

- `data/extract/vision/queue_unruled.json`: 13 text-layer documents, 53 candidate pages.
- Scanned: 72 documents (survey class "pdf: scanned/image only") plus scanned pages inside
  mixed documents. Queue to be built after the unruled batch is reviewed.

## Scale-up decision (later)

In-session and subagent transcription is fine for hundreds of pages. For the full archive
(thousands of pages across ~150 logs), use the Claude API batch interface instead: cheaper
per page and runs unattended. Decide once the archive run finishes and page counts are known.

## Status

- 7 October 2026: pdfplumber run on 49 documents (1,038 numeric tables). Vision method proven
  on 16/17-018. Unruled batch (13 documents) launched.
- 7 October 2026: unruled batch done (2 agents, 13 documents, 53 candidate pages). 20 tables
  transcribed: 16 pass all checks, 4 flag. All 4 flags are source tables whose printed totals
  don't equal their rows (FOI LEX 55869 zero-rate column 25,535 vs printed 26,090; LEX 56636 Tiwi
  subtotal; LEX 91814 operating subtotals; FOI 2122-042 two support rows). One flag (55869)
  independently re-checked against the page image: every transcribed value matches; the
  discrepancy is in the source. Flagged tables stay flagged, with the reason in meta.json notes.
- Skipped pages were mostly charts (NDIS survey bar charts in FOI 2021-064, 1800RESPECT web
  stats, homelessness line charts). Open gap: a chart-reading pass for data-labelled charts.
- Next: scanned queue (72 documents) with two independent transcriptions per table.
- 7 October 2026 (evening): scanned batch done. 72 scanned documents, 1,929 pages triaged from contact
  sheets (`vision_tools.py sheets`) to 178 table pages (`ocr_pages.py queue`). Pages cut into zoomed table
  strips (`vision_tools.py strips`; very wide tables into labelled column tiles, `tiles`) and transcribed by
  Sonnet agents, one pass each. The second transcription was replaced by an independent free check: every
  number must appear in a RapidOCR reading of the page (`ocr_pages.py ocr`; tile OCR for the wide pages),
  plus printed row sums and totals. Result: 308 scanned tables, 226 pass, 82 flag. 81 flags are numbers
  OCR did not find (136 numbers in all, mostly 1-4 per table; the transcriber says each is clearly printed,
  which is not yet independently confirmed). 1 flag is a source arithmetic error (FOI 2122-026 p36 t5, 72.3).
- Pilot findings: Haiku on full pages invented rows and numbers (all 3 tables flagged); Haiku on strips
  still disagreed with Sonnet on 16 of 300 cells; Sonnet on strips read every checked cell correctly for
  similar tokens. Zoomed strips matter more than the model. Resuming an agent to relabel costs as much as
  the original run (~110k tokens): do label fixes with a script over the CSVs.
- FOI LEX 55799 tables are copied AS PRINTED, including its export misalignment (a group heading row
  carries the first category's numbers; that category's own row is blank). Label prefixes differ between
  batches. Both are for a cleaning step that writes a separate clean table; design it with Pete on rows first.
- Known tile bug: `cmd_tiles` takes the first gridline past 5% of the width as the label column's edge; on
  the 55799 wide tables that swallowed 1-2 data columns, repeated on every tile. Agents worked around it
  (row sums pass). Fix before reuse.
- 7 October 2026 (late): flags settled. The 136 numbers OCR could not find: 95 corroborated by arithmetic
  (row sums, or the 16 group identities in `clean_55799.py`), 40 by a blind second reading that agreed
  (reader given row and column, not the value), 1 by a printed note ($726.35 x 4). Recorded in
  `data/extract/vision/confirmations.csv`; verify reports these as "pass (confirmed N)".
  Now: 308 scanned tables, 307 pass; the 1 flag is a source arithmetic error (FOI 2122-026 p36 t5, 72.3).
  One real transcription error was found by the clean-table identities and fixed (55799 April Not
  Specified, AIC, Rent Assistance n/a: transcribed 20, page prints 0).
- FOI LEX 55799 clean table: `scripts/clean_55799.py` -> data/extract/clean/foi_lex_55799_student_recipients.csv,
  5,040 rows (after the review fix), 12 monthly reports (31 Jan to 26 Dec 2025) x 6 sectors. Moves each group's first category off
  the heading line (rule agreed with Pete on part-2 p2 rows); every identity passes in every block.
  Report dates come from the "as at" dates in the page OCR.
- Tried and rejected: Windows built-in OCR (Windows.Media.Ocr via PowerShell 5.1) on the 55799 pages split
  numbers ("16 620"), garbled labels and lost reading order; RapidOCR (pip `rapidocr-onnxruntime`) was used.
- 7 October 2026 (review fixes): the pre-PR review found real gaps, now fixed. (1) 55799 March 2025 Higher
  Education was missing 18 rows (transcription stopped at a strip cut; every check passed because identity
  checks skipped the block): transcribed by the lead; the clean script now fails on any missing block, row or
  untested identity. (2) Confirmations were matched by value, not cell: now by (table, line, column).
  (3) The OCR check skipped one-digit decimals and its digits-only match ignored the decimal point: both
  tightened, which exposed 18 more cells. (4) Arithmetic now confirms a cell only when an identity holds
  EXACTLY (rounding to 5 can hide a misread of 5 or 10 within tolerance); cells that had relied on tolerance
  went to a second blind reading. Also a faint 0 left blank (Dec VET, AIC, State) and the tile label-column bug.
  Final: 154 OCR-missed cells; 71 exact arithmetic, 78 blind second reading agreed, 1 printed note, 1 lead
  check (blind reader said 415, page prints 390), 3 unresolvable (55799 p32 averages, 3 vs 5 at 144 dpi).
  308 scanned tables: 306 pass, 2 flag (FOI 2122-026 p36 t5 source arithmetic; 55799 p32 the 3 averages).
  Clean 55799 table: 5,040 rows = 72 blocks x 70 rows; all 16 identities pass in all 432 block-columns.
- 8 October 2026: Internet Archive DSS batch (`data/extract/vision/scanned_wayback/`). Triage of 6,886 scanned
  pages on 431 packed contact sheets by Haiku 5.5 (pilot: 69/70 table pages, 1 false positive; Sonnet 67/70, 1;
  Haiku 4.5 66/70, 81), then the batch-1 pipeline on 324 pages: 556 tables, ~6.3M Sonnet tokens (~20k/page).
  Blind second reading: 0 misreadings in a random 60 of the 278 cells only one reader had seen; 86 of 87
  checkable cells in tables whose totals do not add up agreed, so those gaps are in the sources.
  Lessons, each learned the expensive way:
  - Run OCR to completion BEFORE cutting strips. `sideways()` reads the OCR; run early it says "upright" and
    the page is cut across its columns (8 pages). `ocr_pages.py strips` now refuses pages without OCR.
  - Agents will fit a cell to make a total add up (one did: neither reading, just the balancing value, which
    then passed every check). The brief now forbids it; the fix was to revert and leave the sum flagged.
    Also forbidden after the run: copying a value from another document's copy of the same table.
  - Agents set loose tolerances (0.3 for a one-cent gap). Tighten to the smallest passing value by script.
  - A blind re-read item must name the row by ALL its text cells (numbers masked) and give every page the
    table spans. With only the first column (often a section name like "expenses") or one page, readers
    answered a different row and the sample looked like 22 disagreements; after fixing the locator: none.
    Never paste checker "detail" text into an item: it carries other cells' values.
  - Many 12/13-044 slide PDFs carry an embedded text layer without the table's numbers: "not in text layer"
    there is a false alarm when OCR passes (`sort_flags.py` groups these).
  - 12/13-037 family payment tables print totals that omit the Family Supplement row: a source quirk
    across ~28 tables, not a misreading.
