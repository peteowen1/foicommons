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
