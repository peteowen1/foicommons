"""Document survey: what each archived file is, so extraction can pick its method.

Rebuilt 8 October 2026 from the original one-off survey's output (data/survey/survey_docs.csv), whose rules
it reproduces: a line is a "table line" when it has 2+ numeric cells in `pdftotext -layout` output;
10+ table lines = "has numeric tables", 3-9 = "some numbers", fewer = "text, no tables". One change: a PDF
is "scanned/image only" when at least half its pages have no text layer (< 100 characters), rather than
when any page does, so one image-only cover page no longer makes a report "scanned". `scanned` still
counts every image-only page.

  python -P scripts/survey.py <manifest csv> <out csv>
  e.g. python -P scripts/survey.py data/manifest_dss_wayback.csv data/survey/survey_dss_wayback.csv
Resumable: files already in <out csv> are skipped; one row is written per file.
"""
import csv, os, re, subprocess, sys

csv.field_size_limit(sys.maxsize)   # agency manifests carry whole detail-page text in one field

ROOT = "C:/dev/foicommons"
NUM_CELL = re.compile(r"^\(?-?\$?\d[\d,]*(\.\d+)?%?\)?$")
FIELDS = ["chars", "class", "ext", "file", "kind", "mb", "missing", "pages", "reference", "release_date",
          "scanned", "source", "table_lines", "title"]


def survey_pdf(path):
    t = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True)
    if t.returncode:
        return {"class": "pdf: unreadable", "kind": t.stderr.decode(errors="ignore")[:80]}
    pages = t.stdout.decode("utf-8", "ignore").split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]   # pdftotext ends with a form feed
    n = len(pages)
    scanned = sum(len(p.strip()) < 100 for p in pages)
    table_lines = sum(1 for p in pages for ln in p.splitlines()
                      if sum(1 for c in re.split(r"\s{2,}", ln.strip()) if NUM_CELL.match(c.replace(" ", ""))) >= 2)
    chars = sum(len(p.strip()) for p in pages)
    if n and scanned / n >= 0.5:
        cls = "pdf: scanned/image only"
    elif table_lines >= 10:
        cls = "pdf: has numeric tables"
    elif table_lines >= 3:
        cls = "pdf: some numbers"
    else:
        cls = "pdf: text, no tables"
    return {"class": cls, "pages": n, "scanned": scanned, "table_lines": table_lines, "chars": chars,
            "kind": "mixed" if 0 < scanned < n and cls != "pdf: scanned/image only" else ""}


def main(manifest, out):
    done = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            done = {r["file"] for r in csv.DictReader(fh)}
    with open(manifest, encoding="utf-8") as fh:
        # Agency manifests (R/scrape_*.R via run_all.R) also list log pages and links: keep downloaded
        # documents only, and read their log_slug / date_detected as source / release date.
        rows = [r for r in csv.DictReader(fh) if r["http_status"] == "200" and r["local_path"]
                and r.get("link_type", "document") == "document"]
    new = not os.path.exists(out)
    n = 0
    with open(out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            path = f"{ROOT}/{r['local_path']}".replace("\\", "/")
            if path in done:
                continue
            ext = os.path.splitext(path)[1].lower()
            rec = {"file": path, "ext": ext, "source": r.get("source") or r.get("log_slug", ""), "reference": r["reference"], "title": r["title"],
                   "release_date": r.get("release_date") or r.get("date_detected", ""), "missing": int(not os.path.exists(path)),
                   "mb": round(os.path.getsize(path) / 1e6, 2) if os.path.exists(path) else ""}
            if rec["missing"]:
                rec["class"] = "missing"
            elif ext == ".pdf":
                rec.update(survey_pdf(path))
            else:
                rec.update({"class": {".doc": "word", ".docx": "word", ".rtf": "word"}.get(ext, "other"), "kind": ext.strip(".")})
            w.writerow(rec)
            fh.flush()
            n += 1
    print(f"{n} files surveyed into {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
