"""Sort flagged vision tables by WHY they are flagged, so a paid re-read covers only the ones that need eyes.

Reads data/extract/vision/verify_report.csv (run `vision_tools.py verify` first) and writes
data/extract/vision/<batch folder>/flag_sort.csv with one row per flagged table and a `group`:

  rounding     only sum checks fail, and every gap is within 0.05 per part (source prints 1 dp):
               fixable by setting tol, no re-read needed
  text_layer   only the PDF's own text layer disagrees; OCR passes and no sum fails. The embedded
               text on these scanned slides does not hold the table's numbers: false alarm
  ocr_summed   only OCR misses, and the table's printed totals pass: the arithmetic confirms the
               cells OCR could not see
  ocr_only     only OCR misses and nothing printed to sum against: needs a blind re-read
  sum_gap      a sum fails by more than rounding: a misreading or a source error, needs eyes

Usage: python -P scripts/sort_flags.py dss_wayback
"""
import csv
import os
import re
import sys

VISION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "extract", "vision")
part = sys.argv[1]   # folder name under vision/ whose tables to sort, e.g. dss_wayback

rows = [r for r in csv.DictReader(open(os.path.join(VISION, "verify_report.csv"), encoding="utf-8"))
        if f"/{part}/" in r["table"].replace("\\", "/") and r["status"] == "flag"]


def failed(v):
    return v.startswith("fail")


def gaps(detail):
    """(gap, number of parts) for every failed sum named in the detail column."""
    out = []
    for m in re.finditer(r"\[([^\]]*)\] sum (-?[\d.]+) != total (-?[\d.]+)", detail):   # row sums
        out.append((abs(float(m.group(2)) - float(m.group(3))), m.group(1).count(",") + 1))
    for m in re.finditer(r": sum (-?[\d.]+) != printed (-?[\d.]+)", detail):   # column totals
        out.append((abs(float(m.group(1)) - float(m.group(2))), None))
    return out


sorted_rows = []
for r in rows:
    sums_fail = failed(r["row_sums"]) or failed(r["col_totals"])
    ocr_fail, text_fail = failed(r["ocr"]), failed(r["text_layer"])
    sums_pass = r["row_sums"] == "pass" or r["col_totals"] == "pass"
    if sums_fail:
        g = gaps(r["detail"])
        # column totals don't say how many parts: allow 0.05 each for up to 4 parts, which only
        # ever covers a 0.1-0.2 rounding gap, never a misread digit
        small = g and all(gap <= 0.05 * (n or 4) + 1e-9 for gap, n in g)
        group = "rounding" if small and not ocr_fail else "sum_gap"
    elif text_fail and not ocr_fail:
        group = "text_layer"
    elif ocr_fail:
        group = "ocr_summed" if sums_pass else "ocr_only"
    else:
        group = "other"
    sorted_rows.append({"group": group, "table": r["table"], "ocr": r["ocr"], "text_layer": r["text_layer"],
                        "row_sums": r["row_sums"], "col_totals": r["col_totals"], "detail": r["detail"]})

out = os.path.join(VISION, part, "flag_sort.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(sorted_rows[0]) if sorted_rows else ["group"])
    w.writeheader()
    w.writerows(sorted(sorted_rows, key=lambda x: (x["group"], x["table"])))
counts = {}
for r in sorted_rows:
    counts[r["group"]] = counts.get(r["group"], 0) + 1
print(f"{len(sorted_rows)} flagged tables in {part}: {counts}")
print(f"written {out}")
