"""Clean table for FOI LEX 55799: DSS monthly reports of current and suspended student payment
recipients, January to December 2025, by sector and indicator.

The raw CSVs (data/extract/vision/dss/FOI_LEX_55799__*/) copy the pages as printed. The source
spreadsheet export puts each group's first category on the group heading's line: "Age" carries the
Under 18 numbers and the "Under 18" row is blank. This script moves those numbers onto their category,
gives every row a group and category, tags each row with its report date and sector, and checks the
result against identities that only hold if the move is right.

  python -P scripts/clean_55799.py
Writes data/extract/clean/foi_lex_55799_student_recipients.csv and prints every check.
"""
import csv, glob, json, os, re, sys
from collections import defaultdict

ROOT = "C:/dev/foicommons/data"
RAW = f"{ROOT}/extract/vision/dss"
OCR = f"{ROOT}/extract/vision/scanned/ocr/dss"
OUT = f"{ROOT}/extract/clean/foi_lex_55799_student_recipients.csv"
COLS = ["abstudy_non_living", "abstudy_living", "abstudy_total", "aic", "austudy", "youth_allowance"]
STD = ["row_label"] + COLS
HEADINGS = ["Age", "Gender", "Marital Status", "State", "Indigenous Indicator", "Course", "Independence",
            "Earnings", "AUS/YAL Rate", "ISP Rate Category", "Rent Assistance"]
TOP = {"Total", "Ave ISP Duration (WKS)", "Ave FN Earnings"}
SECTORS = ["Higher Education", "School", "VET", "Apprentice", "Not Specified"]
PARTS = ["part-1", "part-2"]   # part-2 continues part-1's August report


def report_dates():
    """(part, page) -> report date, from the 'as at dd/mm/yyyy' printed on each report's first pages."""
    found = []
    for i, part in enumerate(PARTS):
        for f in sorted(glob.glob(f"{OCR}/FOI_LEX_55799__foi-lex-55799-{part}/p0*.json")):
            if "_tiles" in f:
                continue
            txt = " ".join(s for _, s, _ in json.load(open(f, encoding="utf-8")))
            a = re.findall(r"[Aa][Ss]\s*[Aa][Tt][^0-9]{0,5}(\d{1,2}/\d{1,2}/\d{4})", txt)
            if a:
                d, m, y = a[0].split("/")
                found.append(((i, int(os.path.basename(f)[1:5])), f"{y}-{int(m):02d}-{int(d):02d}"))
    return sorted(found)


def date_for(order, dates):
    last = None
    for o, d in dates:
        if o <= order:
            last = d
    return last


def sector_of(title, previous):
    m = re.search(r"Sector:\s*(" + "|".join(SECTORS) + ")", title)
    if m:
        return m.group(1)
    if "All Sectors" in title or title.startswith("Table 1"):
        return "All sectors"
    return previous


def num(v):
    v = v.strip()
    return float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else None


def main():
    dates = report_dates()
    tables = []
    for i, part in enumerate(PARTS):
        for f in glob.glob(f"{RAW}/FOI_LEX_55799__foi-lex-55799-{part}/p*_t*.csv"):
            rows = list(csv.reader(open(f, encoding="utf-8")))
            if rows[0] != STD:
                continue
            b = os.path.basename(f)[:-4]
            tables.append(((i, int(b[1:5]), int(b.split("_t")[1])), f, rows[1:]))
    tables.sort()
    print(f"{len(tables)} standard tables; report dates: {[d for _, d in dates]}")

    out, anomalies = [], []
    sector, group, pending, block = None, None, None, None
    for (pi, page, t), f, rows in tables:
        title = json.load(open(f[:-4] + ".meta.json", encoding="utf-8"))["title"]
        rdate = date_for((pi, page), dates)
        # A sector's table always opens with its Total row; anything else continues the previous sector,
        # whatever its title says (an agent titled April's All-sectors continuation "Higher Education")
        first = rows[0][0].split(" / ")[-1].strip() if rows else ""
        sector = sector_of(title, sector) if first == "Total" or sector is None else sector
        if (rdate, sector) != block:
            if pending:
                anomalies.append(f"{block}: heading {pending[0]} numbers never placed")
            block, group, pending = (rdate, sector), None, None
        src = f"{PARTS[pi]} p{page} t{t}"
        base = f[:-4].replace("\\", "/")
        for k, r in enumerate(rows):
            line = k + 2   # CSV line number (header is line 1)
            label = r[0].split(" / ")[-1].strip()
            if re.match(r"n/a", label):
                label = "n/a"
            vals = r[1:7]
            blank = not any(v.strip() for v in vals)
            if label in HEADINGS:
                if blank and label == group and pending:
                    continue   # heading repeated, blank, at the top of the next page: keep its numbers waiting
                group = label
                pending = (label, vals, src, base, line) if not blank else None
                continue
            if label in TOP:
                group = None
            if pending and blank:
                out.append([rdate, sector, group, label, *pending[1], pending[2] + " (printed on heading line)", pending[3], pending[4]])
                pending = None
                continue
            if pending:
                anomalies.append(f"{src}: heading {pending[0]} has numbers but next row {label!r} is not blank")
                pending = None
            if blank:
                anomalies.append(f"{src}: blank row {label!r} not under a heading")
                continue
            out.append([rdate, sector, group or "", label, *vals, src, base, line])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["report_date", "sector", "group", "category"] + COLS + ["source", "raw_table", "raw_line"])
        w.writerows(out)

    # ---- checks ----------------------------------------------------------------------
    # Every cell is rounded to the nearest 5 by DSS (1-7 become 5), so a sum of n rounded parts can miss its
    # rounded total by about 2.5 per term. A misread that changes a digit in the tens or above shows up.
    blocks = defaultdict(dict)
    for r in out:
        blocks[(r[0], r[1])][(r[2], r[3])] = ([num(v) for v in r[4:10]], r[11], r[12])
    print(f"{len(out)} rows, {len(blocks)} report x sector blocks "
          f"({len({b[0] for b in blocks})} reports x {len({b[1] for b in blocks})} sectors)")
    print(f"anomalies: {len(anomalies)}")
    for a in anomalies[:15]:
        print("  ", a)

    vouched = defaultdict(set)   # (raw_table, raw_line, column) -> identities that pass through this cell

    def check(name, group, parts, total):
        total = total if isinstance(total, tuple) else (group, total)
        parts = [(group, p) for p in parts]
        ok = bad = 0
        fails = []
        for bk, rows in blocks.items():
            if total not in rows or not all(p in rows for p in parts):
                continue
            for c in range(6):
                vals = [rows[p][0][c] for p in parts]
                tv = rows[total][0][c]
                if tv is None or any(v is None for v in vals):
                    continue
                if abs(sum(vals) - tv) <= 2.5 * (len(parts) + 1):
                    ok += 1
                    for cell in parts + [total]:
                        vouched[(rows[cell][1], rows[cell][2], COLS[c])].add(name)
                else:
                    bad += 1
                    fails.append(f"{bk} {COLS[c]}: {sum(vals):g} vs {tv:g}")
        print(f"  {name}: {ok} pass, {bad} fail {fails[:3]}")

    T = ("", "Total")
    print("identities that depend on the heading-line move:")
    check("age under 25", "Age", ["Under 18", "18-20", "21-24"], "Under 25")
    check("dependent total", "Independence", ["Dependent - At Home", "Dependent - Away From Home", "Dependent - Assistance for Isolated Children"], "Dependent - Total")
    check("earnings split", "Earnings", ["No Earnings - Total", "With Earnings - Total"], T)
    print("group totals:")
    check("age 25+", "Age", ["25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65+"], "25+")
    check("age total", "Age", ["Under 25", "25+"], T)
    check("gender", "Gender", ["Female", "Male", "Non-binary"], T)
    check("marital status", "Marital Status", ["DeFacto", "Married", "Registered", "Not Partnered"], T)
    check("state", "State", ["New South Wales", "Victoria", "Queensland", "South Australia", "Western Australia", "Tasmania", "Northern Territory", "A.C.T", "Unknown"], T)
    check("indigenous", "Indigenous Indicator", ["Indigenous", "Non-indigenous"], T)
    check("course", "Course", ["Masters", "Other"], T)
    check("independent total", "Independence", ["Independent - Workforce", "Independent - Unable to live at Home", "Independent - Age", "Independent - Marital Status", "Independent - Other", "Independent - Austudy"], "Independent - Total")
    check("independence total", "Independence", ["Dependent - Total", "Independent - Total", "n/a"], T)
    check("earnings bands", "Earnings", ["With Earnings >$0 - $62", "With Earnings >$62 - $236", "With Earnings $236"], "With Earnings - Total")
    check("aus/yal rate", "AUS/YAL Rate", ["Single, At Home", "Single, Away from Home", "Partnered, no children", "Partnered, with children", "Single, with children", "Suspended", "Unknown"], T)
    check("isp rate", "ISP Rate Category", ["Not Coded", "Full Rate", "Part Rate", "Undetermined", "Zero Rate", "Suspended"], T)
    check("rent assistance", "Rent Assistance", ["No", "Yes", "n/a"], T)

    with open(OUT.replace(".csv", "_vouched_cells.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_table", "raw_line", "column", "identities"])
        for (t, ln, c), names in sorted(vouched.items()):
            w.writerow([t, ln, c, ";".join(sorted(names))])
    print(f"{len(vouched)} raw cells vouched for by at least one passing identity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
