"""Phase 2 vision extraction helpers: find table pages, render them, verify transcriptions.

Transcription itself is done by a vision model (Claude) reading the rendered page images.
This script does everything around it, so every transcribed number is checked by code.

Layout (all under data/, gitignored):
  data/pages/<source>/<ref>/p0001.png                       rendered pages
  data/extract/vision/<source>/<ref>/<table_id>.csv         final table (text-layer docs)
  data/extract/vision/<source>/<ref>/<table_id>.A.csv/.B.csv two independent passes (scanned docs)
  data/extract/vision/<source>/<ref>/<table_id>.meta.json   provenance + optional sum rules
  data/extract/vision/verify_report.csv                     one row per table: checks and status

meta.json fields:
  source_pdf (path), pages (list of ints), title, units, transcriber (model), notes,
  row_sums: [{"parts": [col, ...], "total": col, "tol": 0}]            each row: sum(parts) == total
  col_totals: [{"col": col, "group_by": col or null, "totals": {group: value}, "tol": 0.006}]
              sum of col within each group == printed total (tol covers source rounding)

Usage:
  python scripts/vision_tools.py pages  <pdf>                  # list pages likely holding tables
  python scripts/vision_tools.py render <pdf> <source> <ref> [pages, e.g. 1,2,5-9] [--dpi 110]
  python scripts/vision_tools.py verify                        # check every vision table, write report
"""
import csv, json, os, re, subprocess, sys

ROOT = "C:/dev/foicommons/data"
VISION = f"{ROOT}/extract/vision"
NUM_TOKEN = re.compile(r"\d[\d,]*\.?\d*")
NUM_CELL = re.compile(r"^\(?-?\$?\d[\d,]*(\.\d+)?%?\)?$")


def slug(s, n=60):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")[:n] or "x"


def page_text(pdf, page):
    out = subprocess.run(["pdftotext", "-raw", "-f", str(page), "-l", str(page), pdf, "-"], capture_output=True)
    return out.stdout.decode("utf-8", "ignore")


def n_pages(pdf):
    info = subprocess.run(["pdfinfo", pdf], capture_output=True).stdout.decode("utf-8", "ignore")
    m = re.search(r"Pages:\s+(\d+)", info)
    return int(m.group(1)) if m else 0


def cmd_pages(pdf):
    """Pages with 3+ lines holding 2+ numeric cells; scanned pages (no text) listed separately."""
    table_pages, scanned = [], []
    for p in range(1, n_pages(pdf) + 1):
        t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"], capture_output=True).stdout.decode("utf-8", "ignore")
        if len(t.strip()) < 100:
            scanned.append(p)
            continue
        lines = sum(1 for ln in t.splitlines()
                    if sum(1 for c in re.split(r"\s{2,}", ln.strip()) if NUM_CELL.match(c.replace(" ", ""))) >= 2)
        if lines >= 3:
            table_pages.append(p)
    print(json.dumps({"pdf": pdf, "table_pages": table_pages, "scanned_pages": scanned}))


def parse_pages(spec, total):
    if not spec:
        return list(range(1, total + 1))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def cmd_render(pdf, source, ref, spec="", dpi=110):
    out_dir = f"{ROOT}/pages/{source}/{slug(ref)}"
    os.makedirs(out_dir, exist_ok=True)
    for p in parse_pages(spec, n_pages(pdf)):
        target = f"{out_dir}/p{p:04d}.png"
        if os.path.exists(target):
            continue
        subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", str(dpi), "-png", "-singlefile", pdf, target[:-4]],
                       capture_output=True)
        print(target)


def norm(v):
    return v.strip().replace(",", "").replace("$", "").replace("%", "")


def to_float(v):
    try:
        return float(norm(v).strip("()"))
    except ValueError:
        return None


def read_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def check_table(base, meta):
    """Returns dict of check results for one table (base = path without extension)."""
    res = {"table": base, "text_layer": "", "ab_agree": "", "row_sums": "", "col_totals": "", "status": "", "detail": ""}
    detail = []
    a, b, final = f"{base}.A.csv", f"{base}.B.csv", f"{base}.csv"

    # Check: two independent passes agree cell by cell (scanned documents)
    if os.path.exists(a) and os.path.exists(b):
        ra, rb = read_csv(a), read_csv(b)
        diffs = []
        if len(ra) != len(rb) or (ra and list(ra[0]) != list(rb[0])):
            diffs.append(f"shape/header differ A={len(ra)} rows B={len(rb)} rows")
        else:
            for i, (x, y) in enumerate(zip(ra, rb)):
                for k in x:
                    if norm(x[k]) != norm(y.get(k, "")):
                        diffs.append(f"row {i + 1} {k}: A={x[k]!r} B={y.get(k)!r}")
        res["ab_agree"] = "pass" if not diffs else f"fail ({len(diffs)})"
        detail += diffs[:10]
        if not diffs and not os.path.exists(final):
            with open(a, encoding="utf-8") as src, open(final, "w", encoding="utf-8", newline="") as dst:
                dst.write(src.read())
    if not os.path.exists(final):
        res["status"] = "flag"
        res["detail"] = "; ".join(detail or ["no final CSV"])
        return res
    rows = read_csv(final)

    # Check: every number appears in the PDF text layer of the cited pages (text-layer documents)
    text = "".join(page_text(meta["source_pdf"], p) for p in meta.get("pages", []))
    if len(text.strip()) >= 100:
        layer = {t.replace(",", "") for t in NUM_TOKEN.findall(text)}
        nums = [norm(v).strip("()").lstrip("-") for r in rows for v in r.values() if NUM_CELL.match(v.strip().replace(" ", ""))]
        missing = [v for v in nums if v not in layer]
        res["text_layer"] = "pass" if not missing else f"fail ({len(missing)}/{len(nums)})"
        detail += [f"not in text layer: {m}" for m in missing[:10]]
    else:
        res["text_layer"] = "n/a (scanned)"

    # Check: declared row sums
    rs_fail = []
    for rule in meta.get("row_sums", []):
        for i, r in enumerate(rows):
            parts = [to_float(r.get(c, "")) for c in rule["parts"]]
            tot = to_float(r.get(rule["total"], ""))
            if tot is None or any(p is None for p in parts):
                continue
            if abs(sum(parts) - tot) > rule.get("tol", 0) + 1e-9:
                rs_fail.append(f"row {i + 1}: {rule['parts']} sum {sum(parts)} != {rule['total']} {tot}")
    if meta.get("row_sums"):
        res["row_sums"] = "pass" if not rs_fail else f"fail ({len(rs_fail)})"
        detail += rs_fail[:10]

    # Check: declared column totals (per group)
    ct_fail = []
    for rule in meta.get("col_totals", []):
        for grp, printed in rule["totals"].items():
            sel = [r for r in rows if rule.get("group_by") is None or r.get(rule["group_by"]) == grp]
            s = sum(v for v in (to_float(r.get(rule["col"], "")) for r in sel) if v is not None)
            if abs(s - float(printed)) > rule.get("tol", 0) + 1e-9:
                ct_fail.append(f"{rule['col']} {grp}: sum {round(s, 6)} != printed {printed}")
    if meta.get("col_totals"):
        res["col_totals"] = "pass" if not ct_fail else f"fail ({len(ct_fail)})"
        detail += ct_fail[:10]

    checks = [res[k] for k in ("text_layer", "ab_agree", "row_sums", "col_totals")]
    ran = [c for c in checks if c and not c.startswith("n/a")]
    res["status"] = "pass" if ran and all(c == "pass" for c in ran) else ("flag" if ran else "unchecked")
    res["detail"] = "; ".join(detail)
    return res


def cmd_verify():
    out = []
    for dirpath, _, files in os.walk(VISION):
        for f in sorted(files):
            if f.endswith(".meta.json"):
                base = os.path.join(dirpath, f[: -len(".meta.json")]).replace("\\", "/")
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    meta = json.load(fh)
                out.append(check_table(base, meta))
    os.makedirs(VISION, exist_ok=True)
    with open(f"{VISION}/verify_report.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]) if out else ["table"])
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(f"{r['status']:9} text={r['text_layer']:14} ab={r['ab_agree']:10} rows={r['row_sums']:10} cols={r['col_totals']:10} {r['table'][-70:]}")
    print(f"{len(out)} tables: {sum(r['status'] == 'pass' for r in out)} pass, "
          f"{sum(r['status'] == 'flag' for r in out)} flag, {sum(r['status'] == 'unchecked' for r in out)} unchecked")


if __name__ == "__main__":
    args = sys.argv[1:]
    dpi = 110
    if "--dpi" in args:
        i = args.index("--dpi"); dpi = int(args[i + 1]); del args[i:i + 2]
    if not args:
        print(__doc__); sys.exit(1)
    if args[0] == "pages":
        cmd_pages(args[1])
    elif args[0] == "render":
        cmd_render(args[1], args[2], args[3], args[4] if len(args) > 4 else "", dpi)
    elif args[0] == "verify":
        cmd_verify()
