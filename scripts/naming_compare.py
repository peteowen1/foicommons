"""Blind comparison of two naming-pass runs (Sonnet pilot against the Haiku full pass, 11 November 2026).

  python -P scripts/naming_compare.py prep <journal A> <journal B> <seed>
      one random value column per table both runs named -> data/reviews/naming_compare/judge_items.json
      (candidates shuffled to "X"/"Y" per item) and key.json (which run is X); the judge never sees the key
  python -P scripts/naming_compare.py score <judge journal>
      tallies right / vague / wrong per run from the judge's answers (labels "judge NN")
"""
import json, os, random, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from naming_load import answers

ROOT = "C:/dev/foicommons/data"
OUT = f"{ROOT}/reviews/naming_compare"


def named(journal):
    best = {}
    for x, model in answers(journal):
        try:
            i = int(x.get("id"))
        except (TypeError, ValueError):
            continue
        best.setdefault(i, (x, model))
    return best


def measure(x, col):
    m = x.get("m") if isinstance(x.get("m"), dict) else {}
    return m.get(col) or m.get("*", "")


def prep(ja, jb, seed):
    tables = {t["id"]: t for t in json.load(open(f"{ROOT}/naming/tables.json", encoding="utf-8"))}
    a, b = named(ja), named(jb)
    random.seed(seed)
    items, key = [], {}
    for i in sorted(set(a) & set(b)):
        t = tables[i]
        col = random.choice(t["value_columns"])
        cand = {"A": a[i], "B": b[i]}
        order = ["A", "B"] if random.random() < 0.5 else ["B", "A"]
        n = len(items) + 1
        key[n] = {"X": order[0], "Y": order[1], "item": i, "table_id": t["table_id"], "column": col,
                  "A_model": a[i][1], "B_model": b[i][1]}
        items.append({"n": n, "item": i, "bundle": f"{ROOT}/naming/bundles/bundle_{(i - 1) // 10 + 1:04d}.txt",
                      "column": col, **{lab: {"is_statistics": cand[r][0].get("s"), "title": cand[r][0].get("t", ""),
                                              "measure": measure(cand[r][0], col), "units": cand[r][0].get("u", "")}
                                        for lab, r in zip(["X", "Y"], order)}})
    os.makedirs(OUT, exist_ok=True)
    json.dump(items, open(f"{OUT}/judge_items.json", "w", encoding="utf-8"), indent=1)
    json.dump(key, open(f"{OUT}/key.json", "w", encoding="utf-8"), indent=1)
    print(f"{len(items)} items -> {OUT}/judge_items.json (A = {ja}, B = {jb})")


def score(journal):
    key = {int(k): v for k, v in json.load(open(f"{OUT}/key.json", encoding="utf-8")).items()}
    lines = [json.loads(l) for l in open(journal, encoding="utf-8") if l.strip()]
    from collections import Counter
    tally, seen = {"A": Counter(), "B": Counter()}, set()
    for o in lines:
        r = o.get("result")
        if o.get("type") != "result" or not isinstance(r, dict):
            continue
        try:
            verdicts = json.loads(r.get("verdicts_json") or "[]")
        except json.JSONDecodeError:
            continue
        for v in verdicts if isinstance(verdicts, list) else []:
            n = v.get("n") if isinstance(v, dict) else None
            if n not in key or n in seen:
                continue
            seen.add(n)
            for lab in ("X", "Y"):
                g = str(v.get(lab, "")).lower()
                tally[key[n][lab]][g if g in ("right", "vague", "wrong", "not statistics") else "unjudged"] += 1
    for run in ("A", "B"):
        m = next((k[f"{run}_model"] for k in key.values()), "")
        print(f"{run} ({m}): {dict(tally[run])} of {len(seen)} judged")
    print(f"{len(key) - len(seen)} items unjudged")


if __name__ == "__main__":
    if sys.argv[1] == "prep":
        prep(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        score(sys.argv[2])
