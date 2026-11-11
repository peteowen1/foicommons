# JobSeeker deaths: response to Greg Jericho (Guardian, 17 September 2026)

Checks the claim that thousands of extra JobSeeker deaths a year are caused by the payment rate,
using the AIHW PHE 354 mortality data, DSS payment demographics, and FOI releases from the archive.

- `FINDINGS.md`: what we found, with every table and its source.
- `rebuild.py`: rebuilds every number from source files into `data/outputs/jobseeker-deaths/`.
  Each headline figure is asserted, so a changed input fails loudly. `python analyses/jobseeker-deaths/rebuild.py`
- `foi-request-draft.md`: DSS FOI request for deaths by partial capacity to work (not yet lodged).
- Draft post (stats, tables, bullets only; Pete writes the prose):
  `C:\dev\inthegame-blog\blog\2026-10-07-jobseeker-deaths\index.qmd`.

Inputs live in `data/inputs/jobseeker-deaths/` (gitignored). Sources and download links are in FINDINGS.md.

## Corrections made during the first session (so they aren't repeated)

- The straight-line estimate of 52 deaths per 100,000 for full-capacity recipients was first called a
  failed sense check; its 95% range (6-98) includes the non-welfare 67, and dropping 2020 gives 68.
- The "at most 18% double counting" bound was superseded by DSS FOI 2122-068: only about half of
  AIHW's JobSeeker deaths were on the payment at death.
