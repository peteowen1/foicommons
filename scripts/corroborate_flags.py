"""Second look at numbers the OCR cross-check could not find ("not in OCR" flags in verify_report.csv).

A flagged number is corroborated when its cell takes part in arithmetic that holds: a printed row sum in
its own table (meta row_sums), or a group identity in the FOI LEX 55799 clean table (clean_55799.py writes
the vouched cells). A misread would have to be cancelled by a second, matching misread to survive that.
Numbers with no such support are listed for a look at the page.

  python -P scripts/clean_55799.py && python -P scripts/vision_tools.py verify > /dev/null
  python -P scripts/corroborate_flags.py
Writes data/extract/vision/flag_review.csv (one row per flagged number).
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_tools import VISION, norm, ocr_missing, read_csv, to_float

VOUCHED = "C:/dev/foicommons/data/extract/clean/foi_lex_55799_student_recipients_vouched_cells.csv"


def row_sum_ok(row, rule):
    if rule.get("skip") and re.match(rule["skip"], next(iter(row.values()), "")):
        return False
    parts = [to_float(row.get(c, "")) for c in rule["parts"]]
    tot = to_float(row.get(rule["total"], ""))
    if tot is None or any(p is None for p in parts):
        return False
    return abs(sum(parts) - tot) <= rule.get("tol", 0) + 1e-9


def main():
    vouched = {}
    if os.path.exists(VOUCHED):
        for r in csv.DictReader(open(VOUCHED, encoding="utf-8")):
            vouched[(r["raw_table"], int(r["raw_line"]), r["column"])] = r["identities"]
    out = []
    for r in csv.DictReader(open(f"{VISION}/verify_report.csv", encoding="utf-8")):
        if r["status"] != "flag" or "/pilot/" in r["table"]:
            continue
        meta = json.load(open(r["table"] + ".meta.json", encoding="utf-8"))
        rows = read_csv(r["table"] + ".csv")
        if not meta.get("ocr"):
            continue
        missing, _ = ocr_missing(meta, rows)
        for v in sorted(set(missing)):
            cells = [(i, k) for i, row in enumerate(rows) for k, x in row.items() if norm(x).strip("()").lstrip("-") == v]
            for i, k in cells:
                support = [f"row sum {rule['total']}" for rule in meta.get("row_sums", []) if k in rule["parts"] + [rule["total"]] and row_sum_ok(rows[i], rule)]
                ident = vouched.get((r["table"], i + 2, k))
                if ident:
                    support.append(ident)
                out.append({"table": r["table"].split("vision/")[1], "line": i + 2, "row_label": next(iter(rows[i].values())),
                            "column": k, "value": v, "corroborated": "yes" if support else "no", "by": "; ".join(support)})
    with open(f"{VISION}/flag_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    yes = [o for o in out if o["corroborated"] == "yes"]
    no = [o for o in out if o["corroborated"] == "no"]
    print(f"{len(out)} flagged cells: {len(yes)} corroborated by arithmetic, {len(no)} with no arithmetic support")
    for o in no:
        print(f"  {o['table'][-42:]} line {o['line']} {o['row_label'][:40]!r} {o['column']} = {o['value']}")


if __name__ == "__main__":
    main()
