"""Build data/catalogue/facts.csv: one row per number in the checked (vision) tables, with its breakdowns.

Rules agreed with Pete, 8 October 2026 (docs/data-model.md, "facts"):
  1. a period not in any column is taken from the table title, and marked period_from=title
  2. derived numbers the agency printed (% of total, % change, differences) are kept, marked stat/derived
  3. suppressed or nil cells ("<1%", "<20", "-", "n.p.", "redacted") get a blank value, the printed text in
     value_raw, and a flag; never 0
  4. breakdowns use shared names where a column was tagged (state, electorate, lga, payment_type, ...), the
     table's own column name otherwise (category_type)
  5. modelled or illustrative numbers (worked examples, projections) are kept with kind=modelled
Run after build_catalogue.py:  python -P scripts/build_facts.py
"""
import csv, os, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(sys.maxsize)
ROOT = "C:/dev/foicommons"
CAT = f"{ROOT}/data/catalogue"

FY = r"(?:19|20)\d\d[-/–_ ]?\d\d(?!\d)"
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
MONTH_NUM = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
MODELLED = re.compile(r"projection|projected|hypothetical|illustrative|worked example|example famil|scenario|"
                      r"20\d\d system|modelled|modeled", re.I)
SHARED = {"state", "lga", "electorate", "payment_type", "age_group", "sex", "financial_year", "year", "month"}
GEO = {"state", "lga", "electorate"}
PERIOD = {"financial_year", "year", "month"}


# Cleaned tables (scripts/clean_*.py) that replace their raw page tables in facts.
CLEAN = {"data/extract/clean/foi_lex_55799_student_recipients.csv": {
    "values": ["abstudy_non_living", "abstudy_living", "abstudy_total", "aic", "austudy", "youth_allowance"],
    "derived": ["abstudy_total"], "period": "report_date", "dims": ["sector", "group", "category"],
    "measure": "current and suspended student payment recipients", "unit": "people (rounded to 5)"}}


def rel(p):
    p = (p or "").replace("\\", "/")
    return p.split("foicommons/", 1)[1] if "foicommons/" in p else p


def fy(s):
    m = re.search(r"((?:19|20)\d\d)[-/–_ ]?(\d\d)(?!\d)", s)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def period_in_name(name):
    """(period, period_type, name with the period removed) for a value column like lodged_2019_20 or sept09_1st."""
    n = name.lower()
    m = re.search(r"(?<!\d)((?:19|20)\d\d)_(\d\d)(?!\d)", n)
    if m:
        return f"{m.group(1)}-{m.group(2)}", "financial_year", n.replace(m.group(0), " ")
    m = re.search(rf"\b({MONTHS})[a-z]*_?(\d\d|(?:19|20)\d\d)(?!\d)", n)
    if m:
        y = m.group(2); y = y if len(y) == 4 else "20" + y
        return f"{y}-{MONTH_NUM[m.group(1)[:3]]:02d}", "month", n.replace(m.group(0), " ")
    m = re.search(r"(?<![a-z0-9])(?<!system_)((?:19|20)\d\d)(?!\d)", n)
    if m and not re.search(r"system", n):
        return m.group(1), "year", n.replace(m.group(0), " ")
    return "", "", n


def period_in_title(title):
    t = title.lower()
    m = re.search(rf"\b({MONTHS})[a-z]*\.?\s+((?:19|20)\d\d)\b", t)
    fys = {fy(x) for x in re.findall(FY, title)}
    if len(fys) == 1:   # the same year printed twice ("2020-21 ... Annual Report 2020-21") is still one period
        return fys.pop(), "financial_year"
    if m and len(re.findall(rf"\b({MONTHS})[a-z]*\.?\s+(?:19|20)\d\d", t)) == 1:
        return f"{m.group(2)}-{MONTH_NUM[m.group(1)[:3]]:02d}", "month"
    ys = re.findall(r"\b((?:19|20)\d\d)\b", t)
    if len(set(ys)) == 1 and not fys:
        return ys[0], "year"
    return "", ""   # none, or several (a range is the table's span, not one fact's period)


def stat_of(name):
    n = name.lower()
    if re.search(r"pct_change|percent_change|change_pct|pct_chg|growth", n):
        return "pct change", "%", True
    if re.search(r"pct_of_total|share|proportion|_pct$|^pct_|percent|_per_cent|rate_pct", n):
        return "percent", "%", re.search(r"of_total|share", n) is not None
    if re.search(r"(^|_)difference($|_)|(^|_)diff($|_)|variance", n):
        return "difference", "", True
    return "value", "", False


NIL = {"-", "–", "—", "nil", "n/a", "na", "", "..", "—"}


def parse_value(raw):
    """(value or '', flag)"""
    r = raw.strip()
    low = r.lower()
    if low in NIL:
        return "", "nil" if r else "blank"
    if low in ("redacted", "s22", "s47f", "s47g") or low.startswith("redacted"):
        return "", "redacted"
    if low in ("n.p.", "np", "n.p", "not published", "not available", "n.a."):
        return "", "not published"
    if re.match(r"^[<>≤≥]\s*\d", r):
        return "", "below threshold" if r[0] in "<≤" else "above threshold"
    v = r.replace(",", "").replace("$", "").replace("%", "").replace(" ", "")
    neg = v.startswith("(") and v.endswith(")")
    v = v.strip("()")
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return ("-" + v if neg and not v.startswith("-") else v), ""
    return "", "text"


def measure_of(rest):
    words = [w for w in re.split(r"[_\W]+", rest) if w and w not in
             {"no", "num", "number", "count", "pct", "of", "total", "change", "share", "percent", "value", "amount",
              "fy", "y", "yr", "and"}]
    return " ".join(words)


def main():
    tables = {t["table_id"]: t for t in csv.DictReader(open(f"{CAT}/tables.csv", encoding="utf-8")) if t["method"] == "vision"}
    cols = defaultdict(list)
    for c in csv.DictReader(open(f"{CAT}/columns.csv", encoding="utf-8")):
        if c["table_id"] in tables:
            cols[c["table_id"]].append(c)
    out = []
    # Tables that have a cleaned, identity-checked version: facts come from the clean table, not the raw pages.
    by_csv = {t["csv_path"]: tid for tid, t in tables.items()}
    replaced = set()
    for clean, spec in CLEAN.items():
        with open(f"{ROOT}/{clean}", encoding="utf-8") as fh:
            crows = list(csv.DictReader(fh))
        for i, r in enumerate(crows, start=2):
            src = by_csv.get(rel(r["raw_table"]) + ".csv", "")
            replaced.add(src)
            for col in spec["values"]:
                val, flag = parse_value(r[col])
                out.append({"fact_id": f"clean:{os.path.basename(clean)}:{i}:{col}", "table_id": src, "csv_line": i,
                    "column": col, "measure": spec["measure"], "stat": "value", "derived": "yes" if col in spec.get("derived", ()) else "",
                    "is_total": "yes" if "total" in (r["category"] + col).lower() else "",
                    "period": r[spec["period"]][:7], "period_type": "month", "period_from": "clean table",
                    "geography": "", "geography_type": "", "category": col, "category_type": "payment_type",
                    "other_dims": "; ".join(f"{k}={r[k]}" for k in spec["dims"] if r[k]),
                    "value": val, "value_raw": r[col], "flag": flag, "unit": spec["unit"], "kind": "reported",
                    "check_status": "pass (clean table identities)"})
    for tid, t in tables.items():
        if tid in replaced:
            continue
        cs = sorted(cols[tid], key=lambda c: int(c["position"]))
        if not cs:
            continue
        # a label column holds text; a column that is all nil ("-") is an empty VALUE column, not a label
        label = [c for c in cs if c["dimension"] or (c["type"] == "label" and float(c["filled_share"] or 0) > 0)]
        value = [c for c in cs if c not in label]
        if not label and value:          # no label column: the first column names the rows
            label, value = [value[0]], value[1:]
        tp, tpt = period_in_title(t["title"])
        modelled = bool(MODELLED.search(t["title"] + " " + t["units"]))
        with open(f"{ROOT}/{t['csv_path']}", encoding="utf-8", errors="replace") as fh:
            rows = list(csv.DictReader(fh))
        unit_default = t["units"].split(";")[0].split("(")[0].strip()[:60]
        for i, row in enumerate(rows, start=2):
            dims = {"geography": "", "geography_type": "", "category": "", "category_type": "", "other_dims": ""}
            row_period, row_ptype = "", ""
            other = []
            for c in label:
                v = (row.get(c["column"]) or "").strip()
                d = c["dimension"]
                if d in GEO and not dims["geography"]:
                    dims["geography"], dims["geography_type"] = v, d
                elif d in PERIOD and not row_period:
                    row_period, row_ptype = (fy(v) or v), d
                elif not dims["category"]:
                    dims["category"], dims["category_type"] = v, (d if d in SHARED else c["column"])
                elif v:
                    other.append(f"{d if d in SHARED else c['column']}={v}")
            dims["other_dims"] = "; ".join(other)
            row_label = " ".join((row.get(c["column"]) or "") for c in label).lower()
            for c in value:
                raw = row.get(c["column"]) or ""
                val, flag = parse_value(raw)
                p, pt, rest = period_in_name(c["column"])
                stat, unit, derived = stat_of(c["column"])
                if p:
                    period, ptype, pfrom = p, pt, "column name"
                elif row_period:
                    period, ptype, pfrom = row_period, row_ptype, "row label"
                elif tp:
                    period, ptype, pfrom = tp, tpt, "title"
                else:
                    period, ptype, pfrom = "", "", ""
                if stat == "pct change" and not p and re.findall(FY, t["title"]):
                    period, ptype, pfrom = " to ".join(fy(x) for x in re.findall(FY, t["title"])[:2]), "change", "title"
                scen = re.search(r"((?:19|20)\d\d)_?system|system_((?:19|20)\d\d)", c["column"].lower())
                cat, cat_type = dims["category"], dims["category_type"]
                if scen:   # 12/13-037 style: the column is a policy scenario, not a period
                    other_s = f"scenario={(scen.group(1) or scen.group(2))} system"
                else:
                    other_s = ""
                out.append({
                    "fact_id": f"{tid}:{i}:{c['position']}", "table_id": tid, "csv_line": i, "column": c["column"],
                    "measure": "amount" if scen else (measure_of(rest) or measure_of(c["column"])), "stat": stat,
                    "derived": "yes" if derived else "",
                    "is_total": "yes" if re.search(r"\btotal\b", row_label) or re.search(r"(^|_)total($|_)", c["column"].lower()) else "",
                    "period": period, "period_type": ptype, "period_from": pfrom,
                    "geography": dims["geography"], "geography_type": dims["geography_type"],
                    "category": cat, "category_type": cat_type,
                    "other_dims": "; ".join(x for x in (dims["other_dims"], other_s) if x),
                    "value": val, "value_raw": raw, "flag": flag, "unit": unit or unit_default,
                    "kind": "modelled" if modelled or scen else "reported", "check_status": t["check_status"],
                })
    fields = list(out[0])
    with open(f"{CAT}/facts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(f"facts.csv: {len(out)} facts from {len({f['table_id'] for f in out})} of {len(tables)} vision tables")
    print("  value parsed:", sum(bool(f["value"]) for f in out), " flags:", dict(Counter(f["flag"] for f in out if f["flag"])))
    print("  period from:", dict(Counter(f["period_from"] or "none" for f in out)))
    print("  kind:", dict(Counter(f["kind"] for f in out)), " derived:", sum(bool(f["derived"]) for f in out))
    try:
        import duckdb
        con = duckdb.connect(f"{CAT}/catalogue.duckdb")
        con.execute(f"CREATE OR REPLACE TABLE facts AS SELECT * FROM read_csv('{CAT}/facts.csv', all_varchar = true, header = true)")
        con.close()
        print("  loaded into catalogue.duckdb as facts")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
