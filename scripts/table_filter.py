"""Free pre-filter for scanned pages: does this page look like it holds a ruled table?

Vision triage costs tokens per page; most scanned FOI pages are letters, emails and forms. A ruled table
shows up on even a 36 dpi render as several long horizontal lines crossed by several vertical ones. This
measures those lines per page so only likely table pages go on to contact-sheet triage.

  python -P scripts/table_filter.py score            # measure recall against the first batch's triage
  python -P scripts/table_filter.py run <survey csv> # features for every page of the scanned files listed
Features per page: h_lines (dark runs >= 35% of the width), v_lines (dark runs >= 8% of the height),
written to data/extract/vision/scanned/page_features*.csv.
"""
import csv, glob, json, os, re, subprocess, sys

import numpy as np
from PIL import Image

ROOT = "C:/dev/foicommons/data"
SCANNED = f"{ROOT}/extract/vision/scanned"


def runs_over(mask, axis, min_len):
    """Number of distinct lines along an axis whose longest dark run is at least min_len pixels."""
    m = mask if axis == 0 else mask.T
    hit = []
    for row in m:
        d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        hit.append(bool(len(starts)) and (ends - starts).max() >= min_len)
    hit = np.array(hit)
    return int(np.sum(hit[1:] & ~hit[:-1]) + (1 if len(hit) and hit[0] else 0))   # count separate groups


def features(png):
    im = np.asarray(Image.open(png).convert("L"))
    mask = im < 160
    h, w = mask.shape
    return {"h_lines": runs_over(mask, 0, int(0.35 * w)), "v_lines": runs_over(mask, 1, int(0.08 * h))}


def thumbs_for(source, key):
    d = f"{ROOT}/pages/{source}/{key}/thumb36"
    out = {}
    for f in os.listdir(d) if os.path.isdir(d) else []:
        m = re.search(r"-(\d+)\.png$", f)
        if m:
            out[int(m.group(1))] = f"{d}/{f}"
    return out


def cmd_score():
    """First batch: positives are the pages triage listed (stats, maybe, chart)."""
    sheets = json.load(open(f"{SCANNED}/sheets_index.json", encoding="utf-8"))
    keys = {e["file"]: (e["source"], e["sheet"].split("/")[-1].split("__", 1)[1].rsplit("__", 1)[0]) for e in sheets}
    pos = {}
    for i in (1, 2, 3):
        for p in json.load(open(f"{SCANNED}/triage_out_{i}.json", encoding="utf-8")):
            pos[(p["file"].replace("\\", "/"), p["page"])] = p["kind"]
    rows = []
    for f, (src, key) in keys.items():
        for page, png in sorted(thumbs_for(src, key).items()):
            rows.append({"file": f, "page": page, "label": pos.get((f, page), "none"), **features(png)})
    out = f"{SCANNED}/page_features_batch1.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n_pos = sum(r["label"] != "none" for r in rows)
    print(f"{len(rows)} pages, {n_pos} triage positives; recall = positives kept, kept = pages sent on")
    for hmin in (2, 3, 4, 6):
        for vmin in (0, 2, 3):
            keep = [r for r in rows if r["h_lines"] >= hmin and r["v_lines"] >= vmin]
            kp = sum(r["label"] != "none" for r in keep)
            stats_missed = [(os.path.basename(r["file"])[:30], r["page"]) for r in rows
                            if r["label"] == "stats" and not (r["h_lines"] >= hmin and r["v_lines"] >= vmin)]
            print(f"  h>={hmin} v>={vmin}: kept {len(keep):5} ({len(keep) / len(rows):.0%}), positives kept {kp}/{n_pos}, "
                  f"stats missed {len(stats_missed)} {stats_missed[:3]}")


if __name__ == "__main__":
    {"score": cmd_score}[sys.argv[1]]()
