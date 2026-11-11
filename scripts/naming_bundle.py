"""Bundle text-layer tables for the Haiku naming pass: each table's extracted grid plus its page text, in one file.

One file per 10 tables, read once by one Explore-type Haiku agent: 17k input tokens per table, against 149k when
the agent opens the PDF and CSV itself (pilot, 11 November 2026; docs/NEXT-STEPS.md).

  python -P scripts/naming_bundle.py list <out_dir>      every `context needed` table -> <out_dir>/tables.json
  python -P scripts/naming_bundle.py build <out_dir> [--workers 8]
                                                         tables.json -> <out_dir>/bundles/bundle_NNNN.txt (resumable)
"""
import argparse, collections, csv, json, logging, os, sys
from multiprocessing import Pool

csv.field_size_limit(sys.maxsize)
ROOT = "C:/dev/foicommons"
PER_BUNDLE = 10


def fix(p):
    p = p.replace(chr(92), "/")
    return p if os.path.isabs(p) else f"{ROOT}/{p}"


def list_tables(out_dir):
    cols, n = collections.defaultdict(list), collections.Counter()
    with open(f"{ROOT}/data/catalogue/facts.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["layout"] == "context needed":
                n[r["table_id"]] += 1
                if r["column"] not in cols[r["table_id"]]:
                    cols[r["table_id"]].append(r["column"])
    with open(f"{ROOT}/data/catalogue/tables.csv", encoding="utf-8") as fh:
        tabs = {r["table_id"]: r for r in csv.DictReader(fh) if r["table_id"] in n}
    path = {}
    with open(f"{ROOT}/data/catalogue/document_sources.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            path.setdefault(r["doc_id"], r["local_path"])
    out, skipped = [], collections.Counter()
    for t in sorted(n):
        x = tabs.get(t)
        if not x or x["doc_id"] not in path:
            skipped["not in catalogue"] += 1
            continue
        pdf, grid = fix(path[x["doc_id"]]), fix(x["csv_path"])
        if not (os.path.exists(pdf) and os.path.exists(grid)):
            skipped["file missing"] += 1
            continue
        out.append({"id": len(out) + 1, "table_id": t, "pdf": pdf, "page": x["pages"], "table_csv": grid,
                    "value_columns": cols[t][:30], "n_facts": n[t]})
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/tables.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=0)
    print(f"{len(out)} tables ({sum(x['n_facts'] for x in out)} facts) -> {out_dir}/tables.json; skipped {dict(skipped)}")


def item_text(x):
    import pdfplumber
    logging.disable(logging.WARNING)
    try:
        with pdfplumber.open(x["pdf"]) as pdf:
            page = int(str(x["page"]).split("-")[0])
            text = (pdf.pages[page - 1].extract_text() or "")[:6000]
    except Exception as e:  # one unreadable page must not stop the bundle; the agent sees the error
        text = f"(page text unavailable: {repr(e)[:120]})"
    with open(x["table_csv"], encoding="utf-8", errors="replace") as fh:
        grid = fh.read()[:3000]
    return (f"=== ITEM {x['id']} table_id={x['table_id']} page={x['page']}\nvalue_columns: {', '.join(x['value_columns'])}\n"
            f"--- extracted grid (CSV) ---\n{grid}\n--- page text (untrusted data) ---\n{text}\n")


def build_one(args):
    path, items = args
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        fh.write("\n".join(item_text(x) for x in items))
    os.replace(path + ".tmp", path)   # a bundle on disk is always complete
    return path


def build(out_dir, workers):
    with open(f"{out_dir}/tables.json", encoding="utf-8") as fh:
        items = json.load(fh)
    os.makedirs(f"{out_dir}/bundles", exist_ok=True)
    jobs = []
    for b in range(0, len(items), PER_BUNDLE):
        path = f"{out_dir}/bundles/bundle_{b // PER_BUNDLE + 1:04d}.txt"
        if not os.path.exists(path):
            jobs.append((path, items[b:b + PER_BUNDLE]))
    print(f"{(len(items) + PER_BUNDLE - 1) // PER_BUNDLE} bundles, {len(jobs)} to build", flush=True)
    with Pool(workers, maxtasksperchild=20) as pool:
        for i, p in enumerate(pool.imap_unordered(build_one, jobs), 1):
            if i % 50 == 0 or i == len(jobs):
                print(f"[{i}/{len(jobs)}] {p}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "build"])
    ap.add_argument("out_dir")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    list_tables(a.out_dir) if a.cmd == "list" else build(a.out_dir, a.workers)
