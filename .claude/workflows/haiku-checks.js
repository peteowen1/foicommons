export const meta = {
  name: 'haiku-checks',
  description: 'Standing Haiku check squad: fresh fact spot-checks, script scan and catalogue anomaly scan (read-only)',
  whenToUse: 'After a chunk of foicommons work, once build_catalogue.py and build_facts.py have been rerun. Pass args {seed: <new integer>} so each run samples fresh facts.',
  phases: [
    { title: 'Sample', detail: 'draw fresh random facts with scripts/review_samples.py', model: 'haiku' },
    { title: 'Check', detail: 'four read-only Haiku checks, each writing data/reviews/haiku_*_<seed>.md', model: 'haiku' },
  ],
}

// Read-only by design: Haiku finds and reports; the main session verifies a finding before fixing it, and
// Haiku never fixes code or acts as the review gate (global CLAUDE.md). Each check stays near 150k tokens.
const seed = (args && args.seed) || 1
const R = 'C:/dev/foicommons/data/reviews'
const ID = 'First line of your final report must state your exact model ID as given in your system prompt.'
const RO = 'READ-ONLY CHECK. Do not edit, create or delete any file except your one report file.'
const SUMMARY = {
  type: 'object',
  properties: {
    model_id: { type: 'string' },
    report_path: { type: 'string' },
    totals: { type: 'string', description: 'one line with the counts per check' },
    top_problems: { type: 'array', items: { type: 'string' }, description: 'up to 5, most important first' },
  },
  required: ['model_id', 'report_path', 'totals', 'top_problems'],
}

phase('Sample')
const sampled = await agent(
  `${ID}\nRun exactly this command from C:/dev/foicommons and report its printed output, nothing else:\n` +
  `python -P scripts/review_samples.py ${seed}\nDo not edit any file.`,
  { label: 'sample facts', model: 'haiku', effort: 'low' })
log(`samples: ${sampled}`)

const CHECKS = [
  { key: 'checked_facts', prompt:
`${ID}\n${RO} Keep under 150k tokens: open each image once.

Input: ${R}/sample_checked_facts_${seed}.json, 20 facts transcribed from scanned government FOI tables. Each item has \`images\` (strips of the scanned page, top to bottom, or one whole page), \`table_csv\`, \`csv_line\` (line in that CSV, header = line 1), \`column\`, \`value_as_recorded\`, the breakdowns (\`measure\`, \`period\`, \`category\`, \`category_type\`, \`geography\`, \`other_dims\`), \`table_title\` and \`units\`.

For each item answer: value_ok (does the page print exactly value_as_recorded in that cell?); period_ok (Australian financial years run 1 July to 30 June: "year ended 30 June 2010" is 2009-10; a dd/mm/yyyy "as at" date is a date period; blank is fine only if the page gives no period); labels_ok (do category / geography / other_dims describe the cell's row and column?); measure_ok (yes / vague / wrong).

Write ${R}/haiku_checked_facts_${seed}.md: one row per item, totals per check, then the 5 most important problems. If you run short of budget, say exactly which items you did not check.` },
  { key: 'labelled_facts', prompt:
`${ID}\n${RO} Keep under 150k tokens.

Input: ${R}/sample_labelled_facts_${seed}.json, 40 numbers from the TEXT layer of government FOI PDFs. Each item has \`pdf\` and \`page\` (open with the Read tool, pages parameter), \`table_csv\` (the extracted grid, small, you may open it), \`csv_line\`, \`column\`, \`value_as_recorded\`, \`measure\`, \`row_label\`.

For each item answer: value_ok (printed in that row, under the heading \`column\` names?); shifted (if not, is it elsewhere in the same row?); column_ok (yes / partly / no); measure_ok (yes / vague / wrong). For any "no", say whether the CSV grid itself is wrong (extraction) or the CSV is right and the fact is wrong (fact-building).

Write ${R}/haiku_labelled_facts_${seed}.md: one row per item, totals per check, then the 5 most important problems.` },
  { key: 'scripts', prompt:
`${ID}\nREAD-ONLY REVIEW. Do not edit any file except your one report file.

Scan C:/dev/foicommons/scripts/*.py, scripts/*.sh and R/*.R for: the same helper written more than once (file:line for each copy, and whether they behave the same); functions or command modes nothing calls (search other files and docs/*.md first); hard-coded paths or constants repeated across files; dead branches; comments that describe behaviour the code no longer has. Also compare against the previous report if one exists in ${R} (haiku_simplify*.md) and mark each finding NEW or STILL OPEN; list previously reported findings that are now fixed.

Rank by how likely each is to cause a real bug. Skip style. Write ${R}/haiku_scripts_${seed}.md.` },
  { key: 'catalogue', prompt:
`${ID}\n${RO} Keep under 100k tokens: use python -P to scan CSVs, never read whole large files.

Scan C:/dev/foicommons/data/catalogue/ (requests.csv, documents.csv, document_sources.csv, logs.csv, tables.csv, facts.csv) for data problems: requests that are not FOI requests (navigation text, month headings like "Disclosure Log 2026 (July)", decision labels like "Partial disclosure"); release_date_iso that contradicts the title; logs where most documents are "not surveyed"; logs with 0 requests; facts with a value but no measure, or a period that is not a valid date or year; any column that is 100% empty. Give counts and up to 5 example rows per problem. Compare with the previous report if one exists (${R}/haiku_catalogue_anomalies*.md) and say which problems grew, shrank or are new.

Write ${R}/haiku_catalogue_${seed}.md, ranked by rows affected.` },
]

phase('Check')
const results = await parallel(CHECKS.map(c => () =>
  agent(c.prompt, { label: c.key, phase: 'Check', model: 'haiku', schema: SUMMARY })
    .then(r => r && { check: c.key, ...r })))
const done = results.filter(Boolean)
if (done.length < CHECKS.length) log(`${CHECKS.length - done.length} check(s) did not return; see /workflows`)
return { seed, sampled, results: done }
