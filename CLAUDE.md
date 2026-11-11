# CLAUDE.md

## Purpose
**Start here: `docs/NEXT-STEPS.md`** (live queue). Phase 2 plan: `docs/plan-phase2-extraction.md`. Rights: `docs/rights.md`.

Archive, then build a searchable database of, statistics released under the Commonwealth FOI Act. See README.md.

## Layout
- `R/helpers.R` shared polite-HTTP, robots.txt and manifest code; `R/scrape_<source>.R` one scraper per source.
- `docs/sources.md` per-source findings (robots.txt, terms, structure, counts, oddities). Update it when a source changes.
- `data/` raw downloads, manifests, logs. NOT in git.

## Politeness rules (hard)
- Read robots.txt and terms of use before crawling a site; record findings in docs/sources.md.
- At most one request per 3 seconds per host (more if robots.txt sets a Crawl-delay; Services Australia = 10s).
- User-Agent `foicommons-archiver/0.1 (personal research archive)`. No email address in requests.
- Never bypass a block, login, CAPTCHA or paywall. On 403/429, record it and stop that source.
- Site house rules/terms that ban automation override robots.txt. Right to Know is paused for this reason.

## Data out of git
Raw data, PDFs and manifests stay under `data/` (gitignored). CSV only, no RDS, no arrow (segfaults under Git Bash R).

## Phases
1. Archive raw documents and manifests (done for all agencies, 8 October 2026).
2. Extract tables from the PDFs (pdfplumber + checked vision transcription; in progress).
3. Publish (searchable database).

## Analyses
`analyses/<name>/`: one folder per piece of analysis, with a `rebuild.py` (or `.R`) that reproduces every published number and asserts the headline figures. First: `analyses/jobseeker-deaths/`.

## Gotchas
- `pdftotext -layout` shifts rows in sparse tables; use pdfplumber or vision for tables.
- Writing Windows paths through `sed`/Python strings mangled `\f` and `\a` into control characters
  three times. Use forward slashes in paths written by scripts.
- Haiku check squad: after each chunk of work, once `build_catalogue.py` and `build_facts.py` have been rerun,
  `Workflow({name: "haiku-checks", args: {seed: <new integer>}})` (~0.5M Haiku tokens, ~5 min, read-only; agents return report text; write it with `python -P scripts/save_check_reports.py <run>/journal.jsonl <seed>`;
  reports in `data/reviews/haiku_*_<seed>.md`). Verify a finding before fixing it: reports have overstated twice.
- Long runs: launch detached (`Invoke-CimMethod Win32_Process Create`), since `nohup` dies with the Claude
  session; check with `tasklist | grep Rscript`. `extract_tables.py --workers 8` max (12 ran out of memory).
