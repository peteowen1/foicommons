"""Collect the naming pass's answers (one Haiku agent per bundle) into data/naming/names.csv.

Reads each naming-pass Workflow run's journal.jsonl (one result per agent, labelled "bundle NNNN" or
"bundle NNNN retry"), maps item ids back to table_ids through data/naming/tables.json, and writes one row per
table and value column. Agent text quotes untrusted PDF pages: it is parsed as JSON data and never acted on.

Usage: python -P scripts/naming_load.py <journal.jsonl> [<journal.jsonl> ...]
"""
import csv, json, sys

ROOT = "C:/dev/foicommons/data/naming"
FIELDS = ["table_id", "item_id", "is_statistics", "title", "column", "measure", "units", "period", "source", "evidence", "model_id"]


def answers(journal):
    """(item dict, model_id) for every item every agent in this run returned."""
    label = {}
    with open(journal, encoding="utf-8") as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    for o in lines:
        if o.get("type") == "started":
            label[o["key"]] = o.get("label", "")
    for o in lines:
        r = o.get("result")
        if o.get("type") != "result" or not isinstance(r, dict) or not label.get(o["key"], "").startswith("bundle "):
            continue
        try:
            items = json.loads(r.get("items_json") or "[]")
        except json.JSONDecodeError:
            print(f"  unparseable answer from {label[o['key']]}", file=sys.stderr)
            continue
        for x in items if isinstance(items, list) else []:
            if isinstance(x, dict):
                yield x, r.get("model_id", "")


def main(journals):
    with open(f"{ROOT}/tables.json", encoding="utf-8") as fh:
        tables = {t["id"]: t for t in json.load(fh)}
    best = {}
    for j in journals:
        for x, model in answers(j):
            try:
                i = int(x.get("id"))
            except (TypeError, ValueError):
                continue
            if i in tables and i not in best:   # first answer wins; a retry only fills ids that were missing
                best[i] = (x, model)
    rows, bad_cols = [], 0
    for i, (x, model) in sorted(best.items()):
        t = tables[i]
        m = x.get("m") if isinstance(x.get("m"), dict) else {}
        pattern = m.get("*", "")
        for col in t["value_columns"]:
            measure = m.get(col) or pattern
            if not measure:
                bad_cols += 1
            rows.append({"table_id": t["table_id"], "item_id": i, "is_statistics": x.get("s"), "title": x.get("t", ""),
                         "column": col, "measure": measure, "units": x.get("u", ""), "period": x.get("p", ""),
                         "source": x.get("src", ""), "evidence": x.get("ev", ""), "model_id": model})
    with open(f"{ROOT}/names.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(rows)
    missing = sorted(set(tables) - set(best))
    print(f"{len(best)} of {len(tables)} tables named, {len(rows)} column rows -> {ROOT}/names.csv")
    print(f"  {bad_cols} value columns with no measure; {len(missing)} tables with no answer"
          + (f" (first: {missing[:10]})" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
