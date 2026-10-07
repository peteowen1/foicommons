"""Phase 2 prototype: extract tables from archived FOI PDFs with pdfplumber.

Input:  data/survey/survey_docs.csv by default, or --survey <csv> (scripts/survey.py writes one), filtered by --classes.
Output: data/extract/<source>/<reference>/<pdf-stem>/p<page>_t<n>.csv  (one CSV per table)
        data/extract/tables_index.csv  (one row per table, appended after each document)
        data/extract/docs_done.csv     (one row per finished document, for resuming)

Resumable: documents already in docs_done.csv are skipped.
Usage: python scripts/extract_tables.py [--limit N] [--max-pages N] [--classes "pdf: has numeric tables"]
"""
import argparse, csv, os, re, sys, time

import pdfplumber

ROOT = "C:/dev/foicommons/data"
OUT = f"{ROOT}/extract"
NUM = re.compile(r"^\(?-?\$?\d[\d,]*(\.\d+)?%?\)?$")
INDEX_FIELDS = ["source", "reference", "title", "file", "page", "table_n", "n_rows", "n_cols",
                "cells", "empty_share", "numeric_share", "header", "csv_path"]
DONE_FIELDS = ["source", "reference", "file", "pages_total", "pages_read", "tables", "seconds", "status", "error"]


def slug(s, n=60):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")[:n] or "x"


def append(path, fields, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def table_stats(t):
    cells = [c for row in t for c in row]
    filled = [str(c).strip() for c in cells if c is not None and str(c).strip() != ""]
    numeric = [c for c in filled if NUM.match(c.replace(" ", ""))]
    return {
        "n_rows": len(t),
        "n_cols": max((len(r) for r in t), default=0),
        "cells": len(cells),
        "empty_share": round(1 - len(filled) / len(cells), 3) if cells else 1,
        "numeric_share": round(len(numeric) / len(filled), 3) if filled else 0,
        "header": " | ".join(str(c or "").strip().replace("\n", " ") for c in t[0])[:200] if t else "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    ap.add_argument("--classes", default="pdf: has numeric tables")
    ap.add_argument("--only", default="", help="substring of file path to run on one document")
    ap.add_argument("--survey", default=f"{ROOT}/survey/survey_docs.csv", help="survey CSV to read documents from")
    a = ap.parse_args()

    classes = {c.strip() for c in a.classes.split(",")}
    with open(a.survey, encoding="utf-8") as fh:
        docs = [r for r in csv.DictReader(fh) if r["class"] in classes and (not a.only or a.only in r["file"])]
    done = set()
    if os.path.exists(f"{OUT}/docs_done.csv"):
        with open(f"{OUT}/docs_done.csv", encoding="utf-8") as fh:
            done = {r["file"] for r in csv.DictReader(fh) if r["status"] == "ok"}
    todo = [d for d in docs if d["file"] not in done]
    print(f"{len(docs)} documents in scope, {len(done & {d['file'] for d in docs})} done, {len(todo)} to do", flush=True)
    if a.limit:
        todo = todo[: a.limit]

    for i, d in enumerate(todo, 1):
        t0 = time.time()
        out_dir = f"{OUT}/{d['source']}/{slug(d['reference'])}/{slug(os.path.splitext(os.path.basename(d['file']))[0])}"
        os.makedirs(out_dir, exist_ok=True)
        rows, n_tables, pages_read, pages_total, status, err = [], 0, 0, 0, "ok", ""
        try:
            with pdfplumber.open(d["file"]) as pdf:
                pages_total = len(pdf.pages)
                limit = min(pages_total, a.max_pages) if a.max_pages else pages_total
                for pno in range(limit):
                    page = pdf.pages[pno]
                    for tn, t in enumerate(page.extract_tables(), 1):
                        if not t or len(t) < 2:
                            continue
                        p = f"{out_dir}/p{pno + 1:04d}_t{tn}.csv"
                        with open(p, "w", newline="", encoding="utf-8") as fh:
                            csv.writer(fh).writerows([[("" if c is None else str(c)) for c in r] for r in t])
                        rows.append({"source": d["source"], "reference": d["reference"], "title": d["title"][:200],
                                     "file": d["file"], "page": pno + 1, "table_n": tn, "csv_path": p, **table_stats(t)})
                        n_tables += 1
                    page.close()  # free per-page cache (memory)
                    pages_read += 1
                if a.max_pages and pages_total > a.max_pages:
                    status = "partial"
        except Exception as e:  # record and carry on; one bad PDF shouldn't stop the run
            status, err = "error", repr(e)[:300]
        append(f"{OUT}/tables_index.csv", INDEX_FIELDS, rows)
        secs = round(time.time() - t0, 1)
        append(f"{OUT}/docs_done.csv", DONE_FIELDS, [{"source": d["source"], "reference": d["reference"], "file": d["file"],
                                                    "pages_total": pages_total, "pages_read": pages_read, "tables": n_tables,
                                                    "seconds": secs, "status": status, "error": err}])
        print(f"[{i}/{len(todo)}] {status} {d['reference'][:24]:24} pages={pages_read}/{pages_total} tables={n_tables} {secs}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
