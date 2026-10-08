"""Captions for text-layer tables: the text just above each table on its page.

pdfplumber's grid rarely includes a table's title ("Table 3: Payment purposes by program") or the line saying
what the numbers are; those sit above the grid. find_tables() returns tables in the same order as the
extract_tables() call extract_tables.py used, so table_n lines up, and each comes with its bounding box.

  python -P scripts/table_captions.py            # every kept pdfplumber table in data/catalogue/facts.csv
Writes data/extract/table_captions.csv (resumable: tables already there are skipped).
"""
import csv, os, re, sys, time
from collections import defaultdict

import pdfplumber

csv.field_size_limit(sys.maxsize)
ROOT = "C:/dev/foicommons"
OUT = f"{ROOT}/data/extract/table_captions.csv"
FIELDS = ["csv_path", "file", "page", "table_n", "caption", "above_text", "bbox_top", "status"]
ABOVE = 90      # points above the table to look in (about 6 lines of body text)


def rel(p):
    p = (p or "").replace("\\", "/")
    return p.split("foicommons/", 1)[1] if "foicommons/" in p else p


def lines_in(page, x0, top, x1, bottom):
    """Text lines in a region, top to bottom (words grouped by their top coordinate)."""
    if bottom <= top:
        return []
    # strict=False: some PDFs offset their page box, so a region computed from page.width/height can fall a
    # point outside it, which raised ValueError and failed the whole document (201 tables, 8 October)
    b0, b1 = page.bbox[1], page.bbox[3]
    region = (page.bbox[0] + max(0, x0), max(b0, top), min(page.bbox[2], page.bbox[0] + x1), min(b1, bottom))
    if region[3] <= region[1]:
        return []
    words = page.crop(region, strict=False).extract_words()
    rows = defaultdict(list)
    for w in words:
        rows[round(w["top"] / 3)].append(w)
    return [" ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"])) for _, ws in sorted(rows.items())]


def caption_from(lines):
    """Prefer a 'Table N' / 'Figure N' line; otherwise the last one or two lines just above the table."""
    for ln in reversed(lines):
        if re.match(r"^\s*(table|figure|chart|attachment)\s*[a-z]?\d", ln, re.I):
            return ln.strip()
    tail = [l for l in lines if len(l.strip()) > 3][-2:]
    return " ".join(tail).strip()


def main():
    kept = set()
    with open(f"{ROOT}/data/catalogue/facts.csv", encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            if f["layout"] in ("labelled", "context needed"):
                kept.add(f["table_id"])
    want = defaultdict(list)
    with open(f"{ROOT}/data/catalogue/tables.csv", encoding="utf-8") as fh:
        paths = {t["table_id"]: t["csv_path"] for t in csv.DictReader(fh) if t["table_id"] in kept}
    pset = set(paths.values())
    with open(f"{ROOT}/data/extract/tables_index.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if rel(r["csv_path"]) in pset:
                want[rel(r["file"])].append((int(r["page"]), int(r["table_n"]), rel(r["csv_path"])))
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            done = {r["csv_path"] for r in csv.DictReader(fh)}
    todo = {f: [x for x in ts if x[2] not in done] for f, ts in want.items()}
    todo = {f: ts for f, ts in todo.items() if ts}
    print(f"{len(pset)} tables in {len(want)} documents; {sum(len(v) for v in todo.values())} still to caption", flush=True)
    new = not os.path.exists(OUT)
    t0, n = time.time(), 0
    with open(OUT, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for k, (f, ts) in enumerate(sorted(todo.items()), 1):
            try:
                with pdfplumber.open(f"{ROOT}/{f}") as pdf:
                    by_page = defaultdict(list)
                    for pg, tn, cp in ts:
                        by_page[pg].append((tn, cp))
                    for pg, items in sorted(by_page.items()):
                        page = pdf.pages[pg - 1]
                        tables = page.find_tables()
                        for tn, cp in items:
                            if tn > len(tables):
                                w.writerow({"csv_path": cp, "file": f, "page": pg, "table_n": tn, "status": "table not found"})
                                continue
                            x0, top, x1, _ = tables[tn - 1].bbox
                            try:
                                lines = lines_in(page, 0, top - ABOVE, page.width, top - 1)
                            except Exception as e:
                                w.writerow({"csv_path": cp, "file": f, "page": pg, "table_n": tn, "status": f"error: {repr(e)[:120]}"})
                                continue
                            w.writerow({"csv_path": cp, "file": f, "page": pg, "table_n": tn, "caption": caption_from(lines)[:300],
                                        "above_text": " | ".join(lines)[-500:], "bbox_top": round(top, 1), "status": "ok"})
                            n += 1
                        page.close()
            except Exception as e:   # one bad PDF must not stop the run
                for pg, tn, cp in ts:
                    w.writerow({"csv_path": cp, "file": f, "page": pg, "table_n": tn, "status": f"error: {repr(e)[:120]}"})
            fh.flush()
            if k % 20 == 0:
                print(f"  {k}/{len(todo)} documents, {n} captions, {time.time() - t0:.0f}s", flush=True)
    print(f"done: {n} captions in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
