"""Write a haiku-checks run's reports to data/reviews/haiku_<check>_<part>_<seed>.md and print each one's totals.

The agents are read-only and return their report as text; this script is the only writer. Paths come from the
agent's label (set by the workflow script), never from the report text, which quotes untrusted PDF pages.

  python -P scripts/save_check_reports.py <run journal.jsonl> <seed>
"""
import json, re, sys

journal, seed = sys.argv[1], int(sys.argv[2])
lines = [json.loads(l) for l in open(journal, encoding="utf-8") if l.strip()]
label = {o["key"]: o.get("label", "") for o in lines if o.get("type") == "started"}
n = 0
for o in lines:
    r = o.get("result")
    if o.get("type") != "result" or not isinstance(r, dict) or "report_md" not in r:
        continue
    m = re.fullmatch(r"(checked_facts|labelled_facts|scripts|catalogue) (\d+-\d+|all)", label.get(o["key"], ""))
    if not m:
        print(f"  skipped result with label {label.get(o['key'])!r}")
        continue
    path = f"C:/dev/foicommons/data/reviews/haiku_{m[1]}_{m[2]}_{seed}.md"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(r["report_md"])
    n += 1
    print(f"{m[1]} {m[2]} | {str(r.get('totals', ''))[:300]}")
print(f"{n} reports written")
