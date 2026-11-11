# DECISIONS

Decisions for foicommons, newest first. Queue: `docs/NEXT-STEPS.md`.

## November 2026

- **Director of National Parks folded into DCCEEW** (Pete, 11 November): it lists DCCEEW's log, which was
  harvested twice. `SHARED_LOGS` in `scripts/build_catalogue.py` counts it once; 855 duplicate requests gone
  (13,175 -> 12,320), documents unchanged at 14,312. A new shared log stops the build until it gets an owner.

## Deliberately not done

- **Right to Know scraping**: house rules ban unapproved automation; paused pending permission
  (`docs/righttoknow-permission-request.md`). Its JSON endpoints also returned Cloudflare challenges.
  4 requests were made before the pause.
- **Republishing full PDFs**: release under FOI gives no licence to republish; see `docs/rights.md`.
- **Tesseract OCR**: not installed; vision transcription with code checks replaced it.
- **Line-detection pre-filter** (`scripts/table_filter.py`): kept 162/170 table pages on DSS batch 1 but only
  ~14/22 on other documents, so not used (8 October).

## October 2026

- **Haiku 5.5 for page triage** (8 October): pilot of 70 known table pages, 69 caught with 1 false positive.
- **Research/regression tables out of scope for now** (Pete, 8 October): later sweep, queued.
- **Facts rules** agreed with Pete on real tables (8 October): `docs/data-model.md`, "facts".
- **Registry drops logs on another agency's host** (8 October, `d203ba5`). ANAO has no log of its own, so its
  `foreign_logs_only` row is correct.
- **`11_12-044__52 p17` Grants Unexpended**: (83,065) as printed (Pete); the total not reconciling is the source.
