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
  row_sums: [{"parts": [col, ...], "total": col, "tol": 0, "skip": "^Ave"}]   each row: sum(parts) == total
              (optional skip: regex on the first column for rows the rule does not cover)
  col_totals: [{"col": col, "group_by": col or null, "totals": {group: value}, "tol": 0.006}]
              sum of col within each group == printed total (tol covers source rounding)

Usage:
  python scripts/vision_tools.py pages  <pdf>                  # list pages likely holding tables
  python scripts/vision_tools.py render <pdf> <source> <ref> [pages, e.g. 1,2,5-9] [--dpi 110]
  python scripts/vision_tools.py strips <page_288.png> <out_dir>  # table area cut into zoomed strips
  python scripts/vision_tools.py sheets [survey] [out folder]  # contact sheets of every scanned page (triage)
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


def cmd_sheets(survey=f"{ROOT}/survey/survey_docs.csv", dpi=36, per=16, cols=4, out_root=None):
    """Contact sheets for scanned documents: every page rendered small and tiled 4x4 with its page
    number, so a vision pass can pick out the table pages without opening 1,900 images.
    Writes data/extract/vision/scanned/sheets/*.png and scanned/sheets_index.json."""
    from PIL import Image, ImageDraw
    out_root = out_root or f"{VISION}/scanned"   # a second batch gets its own folder so it never overwrites the first
    out_dir = f"{out_root}/sheets"
    os.makedirs(out_dir, exist_ok=True)
    with open(survey, encoding="utf-8") as fh:
        docs = [d for d in csv.DictReader(fh) if d["class"] == "pdf: scanned/image only"]
    index = []
    per_ref = {}
    for d in docs:
        per_ref[(d["source"], d["reference"])] = per_ref.get((d["source"], d["reference"]), 0) + 1
    for d in docs:
        pdf = d["file"].replace("\\", "/")
        # A reference can hold several PDFs (part-1, part-2): key those by file name too, or they share one folder
        key = slug(d["reference"])
        if per_ref[(d["source"], d["reference"])] > 1:
            key += "__" + slug(os.path.splitext(os.path.basename(pdf))[0])
        thumb_dir = f"{ROOT}/pages/{d['source']}/{key}/thumb{dpi}"
        if not os.path.isdir(thumb_dir) or not os.listdir(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
            r = subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", pdf, f"{thumb_dir}/t"], capture_output=True)
            if r.returncode:
                print(f"pdftoppm failed ({r.returncode}) on {pdf}: {r.stderr.decode(errors='ignore')[:200]}")
        # pdftoppm pads page numbers to the width of the page count: t-1.png or t-001.png
        thumbs = sorted(((int(re.search(r"-(\d+)\.png$", f).group(1)), f"{thumb_dir}/{f}") for f in os.listdir(thumb_dir)))
        if not thumbs:
            print(f"no pages rendered: {pdf}")
            continue
        if len(thumbs) != n_pages(pdf):   # a killed or failed render leaves a partial folder that looks done
            print(f"WARNING: {len(thumbs)} of {n_pages(pdf)} pages rendered for {pdf}; delete {thumb_dir} and rerun")
        for s in range(0, len(thumbs), per):
            chunk = thumbs[s:s + per]
            ims = [Image.open(p) for _, p in chunk]
            w, h = max(i.width for i in ims), max(i.height for i in ims)
            rows = (len(ims) + cols - 1) // cols
            sheet = Image.new("L", (cols * (w + 8), rows * (h + 26)), 255)
            draw = ImageDraw.Draw(sheet)
            for k, ((pg, _), im) in enumerate(zip(chunk, ims)):
                x, y = (k % cols) * (w + 8), (k // cols) * (h + 26)
                draw.text((x + 4, y + 4), f"p{pg}", fill=0, font_size=18)
                sheet.paste(im, (x, y + 24))
                draw.rectangle([x, y + 24, x + im.width - 1, y + 24 + im.height - 1], outline=0)
            name = f"{d['source']}__{key}__{s // per + 1:02d}.png"
            sheet.save(f"{out_dir}/{name}")
            index.append({"sheet": f"{out_dir}/{name}", "source": d["source"], "reference": d["reference"],
                          "file": pdf, "pages": [pg for pg, _ in chunk], "title": d["title"]})
    with open(f"{out_root}/sheets_index.json", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
    print(f"{len(docs)} documents, {sum(len(i['pages']) for i in index)} pages, {len(index)} sheets")


def cmd_packed(index_json, out_root, per=16, cols=4):
    """Repack contact sheets so pages from several documents share a sheet: one sheet per document wastes
    most of each image on short files (808 sheets for 6,886 pages). Tiles are labelled "D017 p3"; the
    packed index maps every tile back to its file and page. Reads the thumbnails cmd_sheets rendered."""
    from PIL import Image, ImageDraw
    entries = json.load(open(index_json, encoding="utf-8"))
    docs, tiles = {}, []
    for e in entries:
        key = os.path.basename(e["sheet"])[: -len(".png")].split("__", 1)[1].rsplit("__", 1)[0]
        thumb_dir = f"{ROOT}/pages/{e['source']}/{key}/thumb36"
        thumbs = {int(re.search(r"-(\d+)\.png$", f).group(1)): f"{thumb_dir}/{f}" for f in os.listdir(thumb_dir) if f.endswith(".png")}
        d = docs.setdefault(e["file"], f"D{len(docs) + 1:03d}")
        tiles += [{"doc": d, "file": e["file"], "reference": e["reference"], "page": p, "thumb": thumbs[p]} for p in e["pages"]]
    out_dir = f"{out_root}/packed"
    os.makedirs(out_dir, exist_ok=True)
    index = []
    for s in range(0, len(tiles), per):
        chunk = tiles[s:s + per]
        ims = [Image.open(t["thumb"]) for t in chunk]
        w, h = max(i.width for i in ims), max(i.height for i in ims)
        sheet = Image.new("L", (cols * (w + 8), ((len(ims) + cols - 1) // cols) * (h + 26)), 255)
        draw = ImageDraw.Draw(sheet)
        for k, (t, im) in enumerate(zip(chunk, ims)):
            x, y = (k % cols) * (w + 8), (k // cols) * (h + 26)
            draw.text((x + 4, y + 4), f"{t['doc']} p{t['page']}", fill=0, font_size=18)
            sheet.paste(im, (x, y + 24))
            draw.rectangle([x, y + 24, x + im.width - 1, y + 24 + im.height - 1], outline=0)
        path = f"{out_dir}/packed_{s // per + 1:04d}.png"
        sheet.save(path)
        index.append({"sheet": path, "tiles": [{k: t[k] for k in ("doc", "file", "reference", "page")} for t in chunk]})
    with open(f"{out_root}/packed_index.json", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
    print(f"{len(docs)} documents, {len(tiles)} pages, {len(index)} packed sheets")


def cmd_strips(png, out_dir, target=900, top_skip=200):
    """Crop a page (288 dpi render) to its table area and cut it into horizontal strips at gridlines.
    Dense scanned tables have ~8 px digits at page size; a vision model reads them far better when
    the image it is given is only as wide as the table. Strips are cut on ruled lines, never mid-row."""
    from PIL import Image
    im = Image.open(png).convert("L")
    w, h = im.size
    px = im.load()
    dark = lambda x, y: px[x, y] < 128
    # Table area: dark pixels below the running header (top_skip px), with a small margin
    ys = [y for y in range(top_skip, h, 2) if any(dark(x, y) for x in range(0, w, 4))]
    xs = [x for x in range(0, w, 2) if any(dark(x, y) for y in range(top_skip, h, 4))]
    x0, x1, y0, y1 = max(min(xs) - 10, 0), min(max(xs) + 10, w), max(min(ys) - 10, 0), min(max(ys) + 10, h)
    # Gridlines: rows where most of the table width is dark
    lines = [y for y in range(y0, y1) if sum(dark(x, y) for x in range(x0, x1, 6)) > 0.6 * (x1 - x0) / 6]
    cuts, last = [y0], y0
    while y1 - last > target * 1.3:
        near = [y for y in lines if last + target * 0.7 < y < last + target * 1.3]
        if not near:
            print(f"WARNING: no ruled line near y={last + target} in {png}; cutting there may split a row")
        cut = min(near, key=lambda y: abs(y - last - target)) if near else last + target
        cuts.append(cut)
        last = cut
    cuts.append(y1)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.basename(png).replace("_288", "")[:-4]
    paths = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:]), 1):
        p = f"{out_dir}/{stem}_s{i}.png"
        im.crop((x0, a, x1, b + 2)).save(p)
        paths.append(p)
    print(json.dumps({"page": png, "table_box": [x0, y0, x1, y1], "strips": paths}))
    return paths


def cmd_tiles(strip, out_dir, target=1600):
    """Cut a very wide table strip into vertical tiles at column gridlines, each with the row-label
    column pasted on its left. A 4,600 px strip is shrunk to ~1,568 px by the vision model, making
    digits a third of their size; tiles keep them legible and keep every row's label beside its numbers."""
    from PIL import Image
    im = Image.open(strip).convert("L")
    w, h = im.size
    px = im.load()
    # Column gridlines: x where most of the strip's height is dark
    # A strip can hold headings and several short tables, so few lines run its full height: take lines dark
    # over 45% of the height (the label column and left-hand columns) or 20% (shorter right-hand columns).
    # 30% picks up text in the label column; tested on 55799 part-2 p48.
    dark = [sum(px[x, y] < 128 for y in range(0, h, 4)) / (h / 4) for x in range(w)]
    vlines = [x for x in range(w) if dark[x] > 0.45 or (dark[x] > 0.2 and x > 0.3 * w)]
    gaps = [x for i, x in enumerate(vlines) if i == 0 or x - vlines[i - 1] > 3]   # one x per line
    # The label column's right edge: the first gridline well clear of the table's left border. (A fixed
    # 5%-of-width threshold landed past the first data columns on 4,600 px tables, repeating them on every tile.)
    left = gaps[0] if gaps else 0
    label_end = next((x for x in gaps if x - left > 100), None)
    if label_end is None:
        label_end = int(0.15 * w)
        print(f"WARNING: no label-column gridline found in {strip}; assuming 15% of the width")
    label = im.crop((0, 0, label_end + 2, h))
    cuts, last = [label_end], label_end
    while w - last > target * 1.2:
        near = [x for x in gaps if last + target * 0.6 < x < last + target * 1.2]
        if not near:
            print(f"WARNING: no column gridline near x={last + target} in {strip}; cutting there may split a column")
        cut = min(near, key=lambda x: abs(x - last - target)) if near else last + target
        cuts.append(cut)
        last = cut
    cuts.append(w)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.basename(strip)[:-4]
    paths = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:]), 1):
        tile = Image.new("L", (label.width + (b - a) + 2, h), 255)
        tile.paste(label, (0, 0))
        tile.paste(im.crop((a, 0, b + 2, h)), (label.width, 0))
        p = f"{out_dir}/{stem}_c{i}.png"
        tile.save(p)
        paths.append(p)
    return paths


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


def cells_agree(a, b):
    """Do transcriptions A and B of one cell count as the same reading?

    Numbers: must match exactly once separators are dropped (a scanned 8 read as 3 must fail).
    Labels (years, payment names, regions): this decides whether harmless differences like
    "JobSeeker Payment" vs "Jobseeker payment", "2019-20" vs "2019–20" (en dash), or a stray
    double space count as agreement. Too strict floods the report with flags nobody needs to
    look at; too loose lets a misread label ("NSW" vs "NT") through.
    """
    # TODO(Pete): decide the label rule. Return True when a and b are the same reading.
    return norm(a) == norm(b)


def to_float(v):
    try:
        return float(norm(v).strip("()"))
    except ValueError:
        return None


def read_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


_CONFIRMED = None


def confirmed():
    """(table relative to the vision folder, CSV line, column) -> (value, unsure) for numbers confirmed
    despite an OCR miss. Keyed by cell: confirming a 20 in one cell says nothing about another 20."""
    global _CONFIRMED
    if _CONFIRMED is None:
        _CONFIRMED = {}
        path = f"{VISION}/confirmations.csv"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    _CONFIRMED[(r["table"], int(r["line"]), r["column"])] = (r["value"], "unsure" in r["evidence"])
    return _CONFIRMED


def ocr_missing(meta, rows):
    """Cells whose number an independent OCR reading of the page does not contain.
    Returns ([(csv line, column, value), ...], numbers checked). Shared by verify and corroborate_flags.py."""
    tokens, runs = set(), set()
    for path in meta["ocr"]:
        with open(path, encoding="utf-8") as fh:
            for _, s, _ in json.load(fh):
                for run in re.findall(r"\d[\d,.]*\d|\d", s):
                    tail = len(re.split(r"[,.]", run)[-1]) if re.search(r"[,.]", run) else 0
                    runs.add((re.sub(r"\D", "", run), tail))
                for t in NUM_TOKEN.findall(s.replace(" ", "").replace(",.", ".")):
                    t = t.replace(",", "").rstrip(".")
                    tokens.add(t)
                    if re.fullmatch(r"\d{1,3}\.\d{3}", t):   # OCR reads a thousands comma as a full stop
                        tokens.add(t.replace(".", ""))

    def seen(v):
        if v in tokens:
            return True
        # OCR swaps separators (22,356.73 -> "22.356.73"): accept the same digits only where the decimal point
        # can sit in the same place, so 67.2 never matches "672" or "6.72"
        d = re.sub(r"\D", "", v)
        dec = len(v.split(".")[1]) if "." in v else 0
        return any((d, t) in runs for t in ((dec,) if dec else (0, 3)))

    cells, n = [], 0
    for i, r in enumerate(rows):
        for k, v in r.items():
            if not NUM_CELL.match(v.strip().replace(" ", "")):
                continue
            v = norm(v).strip("()").lstrip("-")
            if re.fullmatch(r"\d", v):
                continue   # lone digits (0, 5): OCR drops most of them; sums cover them
            n += 1
            if not seen(v):
                cells.append((i + 2, k, v))
    return cells, n


def check_table(base, meta):
    """Returns dict of check results for one table (base = path without extension)."""
    res = {"table": base, "text_layer": "", "ocr": "", "ab_agree": "", "row_sums": "", "col_totals": "", "status": "", "detail": ""}
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
                    if not cells_agree(x[k], y.get(k, "")):
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

    # Check: scanned pages have no text layer, so every number must appear in an independent OCR
    # reading of the page instead (meta "ocr": RapidOCR JSON per page, from ocr_pages.py).
    # OCR drops most lone zeros, so "0" is not checked; sums catch a zero misread.
    if meta.get("ocr") and not all(os.path.exists(p) for p in meta["ocr"]):
        res["ocr"] = "pending"
        detail.append("OCR not run yet for: " + ", ".join(p for p in meta["ocr"] if not os.path.exists(p)))
    elif meta.get("ocr"):
        missing, n = ocr_missing(meta, rows)
        # Cells OCR missed but confirmed another way (exact arithmetic, or a blind second reading that agrees):
        # data/extract/vision/confirmations.csv, written by the flag review (corroborate_flags.py + blind re-read)
        table, conf = base.split("vision/")[1], confirmed()
        ok = [c for c in missing if conf.get((table, c[0], c[1]), (None,))[0] == c[2]]
        unsure = sum(conf[(table, c[0], c[1])][1] for c in ok)
        left = [c for c in missing if c not in ok]
        if left:
            res["ocr"] = f"fail ({len(left)}/{n})"
        elif ok:
            res["ocr"] = f"pass (confirmed {len(ok)}" + (f", {unsure} by an unsure second reader)" if unsure else ")")
        else:
            res["ocr"] = "pass"
        detail += [f"not in OCR: line {ln} {col} = {v}" for ln, col, v in left[:10]]

    # Check: declared row sums
    rs_fail, rs_done = [], 0
    for rule in meta.get("row_sums", []):
        for i, r in enumerate(rows):
            if rule.get("skip") and re.match(rule["skip"], next(iter(r.values()), "")):
                continue   # e.g. "^Ave" rows: averages, not counts, so parts don't add up
            parts = [to_float(r.get(c, "")) for c in rule["parts"]]
            tot = to_float(r.get(rule["total"], ""))
            if tot is None or any(p is None for p in parts):
                continue
            rs_done += 1
            if abs(sum(parts) - tot) > rule.get("tol", 0) + 1e-9:
                rs_fail.append(f"row {i + 1}: {rule['parts']} sum {sum(parts)} != {rule['total']} {tot}")
    if meta.get("row_sums"):
        # a rule that no row could be tested against (non-numeric cells) is not a pass
        res["row_sums"] = ("pass" if rs_done else "n/a (0 rows testable)") if not rs_fail else f"fail ({len(rs_fail)})"
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

    checks = [res[k] for k in ("text_layer", "ocr", "ab_agree", "row_sums", "col_totals")]
    ran = [c for c in checks if c and not c.startswith("n/a")]
    if "pending" in ran:
        res["status"], res["detail"] = "pending", "; ".join(detail)
        return res
    res["status"] = "pass" if ran and all(c.startswith("pass") for c in ran) else ("flag" if ran else "unchecked")
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
        print(f"{r['status']:9} text={r['text_layer']:14} ocr={r['ocr']:10} ab={r['ab_agree']:10} rows={r['row_sums']:10} cols={r['col_totals']:10} {r['table'][-70:]}")
    print(f"{len(out)} tables: {sum(r['status'] == 'pass' for r in out)} pass, "
          f"{sum(r['status'] == 'flag' for r in out)} flag, {sum(r['status'] == 'pending' for r in out)} pending, "
          f"{sum(r['status'] == 'unchecked' for r in out)} unchecked")


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
    elif args[0] == "strips":
        cmd_strips(args[1], args[2], top_skip=int(args[3]) if len(args) > 3 else 200)
    elif args[0] == "packed":   # packed <sheets_index.json> <output folder>
        cmd_packed(args[1], args[2])
    elif args[0] == "sheets":   # sheets [survey csv] [output folder]
        cmd_sheets(*(args[1:2] or [f"{ROOT}/survey/survey_docs.csv"]), out_root=args[2] if len(args) > 2 else None)
    elif args[0] == "verify":
        cmd_verify()
