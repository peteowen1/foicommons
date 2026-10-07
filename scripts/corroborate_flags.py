"""Second look at cells whose number the OCR cross-check could not find.

A cell is corroborated by arithmetic only when it takes part in arithmetic that holds EXACTLY: a printed
row sum in its own table (meta row_sums), or a group identity in the FOI LEX 55799 clean table
(clean_55799.py writes the vouched cells). DSS rounds every count to 5, so an identity that holds only
within rounding tolerance can hide a misread of 5 or 10; those cells go to a blind second reading instead.

  python -P scripts/clean_55799.py && python -P scripts/vision_tools.py verify > /dev/null
  python -P scripts/corroborate_flags.py
Writes data/extract/vision/flag_review.csv (one row per OCR-missed cell, including cells already confirmed).
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_tools import VISION, ocr_missing, read_csv, to_float

VOUCHED = "C:/dev/foicommons/data/extract/clean/foi_lex_55799_student_recipients_vouched_cells.csv"
FIELDS = ["table", "line", "row_label", "column", "value", "corroborated", "by"]


def exact_row_sums(row, meta, col):
    out = []
    for rule in meta.get("row_sums", []):
        if col not in rule["parts"] + [rule["total"]]:
            continue
        if rule.get("skip") and re.match(rule["skip"], next(iter(row.values()), "")):
            continue
        parts = [to_float(row.get(c, "")) for c in rule["parts"]]
        tot = to_float(row.get(rule["total"], ""))
        if tot is not None and all(p is not None for p in parts) and abs(sum(parts) - tot) < 1e-9:
            out.append(f"row sum {rule['total']} (exact)")
    return out


def main():
    exact = {}
    if os.path.exists(VOUCHED):
        for r in csv.DictReader(open(VOUCHED, encoding="utf-8")):
            if r["exact_identities"]:
                exact[(r["raw_table"], int(r["raw_line"]), r["column"])] = r["exact_identities"]
    else:
        print(f"WARNING: {VOUCHED} not found; run clean_55799.py first. No identity support will be found.")
    out = []
    for dirpath, _, files in os.walk(VISION):
        if "/pilot" in dirpath.replace("\\", "/"):
            continue
        for f in sorted(files):
            if not f.endswith(".meta.json"):
                continue
            base = os.path.join(dirpath, f[: -len(".meta.json")]).replace("\\", "/")
            meta = json.load(open(base + ".meta.json", encoding="utf-8"))
            if not meta.get("ocr") or not all(os.path.exists(p) for p in meta["ocr"]) or not os.path.exists(base + ".csv"):
                continue
            rows = read_csv(base + ".csv")
            for line, col, v in ocr_missing(meta, rows)[0]:
                row = rows[line - 2]
                support = exact_row_sums(row, meta, col)
                if (base, line, col) in exact:
                    support.append(exact[(base, line, col)] + " (exact)")
                out.append({"table": base.split("vision/")[1], "line": line, "row_label": next(iter(row.values())),
                            "column": col, "value": v, "corroborated": "yes" if support else "no", "by": "; ".join(support)})
    with open(f"{VISION}/flag_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    yes = sum(o["corroborated"] == "yes" for o in out)
    print(f"{len(out)} OCR-missed cells: {yes} corroborated by exact arithmetic, {len(out) - yes} need a second reading")


if __name__ == "__main__":
    main()
