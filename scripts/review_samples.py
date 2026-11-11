"""Fresh random samples for the Haiku check squad (.claude/workflows/haiku-checks.js).

  python -P scripts/review_samples.py <seed>
Writes data/reviews/sample_checked_facts_<seed>.json (20 vision facts with their page images) and
data/reviews/sample_labelled_facts_<seed>.json (40 text-layer facts with their PDF page: ids 1-20 `labelled`, 21-40
`inferred`, the naming pass's guessed measures, so every run checks those too), from
data/catalogue/catalogue.duckdb. Run build_catalogue.py and build_facts.py first.
"""
import glob, json, random, sys

import duckdb

ROOT = "C:/dev/foicommons"
seed = int(sys.argv[1])
c = duckdb.connect(f"{ROOT}/data/catalogue/catalogue.duckdb", read_only=True)
random.seed(seed)

# page images for vision tables: every batch file lists each page's strips
strips = {}
for f in glob.glob(f"{ROOT}/data/extract/vision/*/batches/*.json") + glob.glob(f"{ROOT}/data/extract/vision/scanned/batch_*.json"):
    for e in json.load(open(f)):
        if "/vision/" in e.get("out_prefix", ""):
            strips["data/extract/vision/" + e["out_prefix"].split("/vision/")[1]] = e["strips"]

rows = c.execute("""SELECT t.csv_path, f.csv_line, f."column", f.value_raw, f.measure, f.period, f.category, f.category_type,
       f.geography, f.other_dims, t.title, t.units, d.example_path, t.pages
FROM facts f JOIN tables t USING (table_id) JOIN documents d USING (doc_id)
WHERE f.layout = 'checked' AND f.period_from IS DISTINCT FROM 'clean table' AND f.value <> ''""").fetchall()
prefix = lambda p: p.rsplit(".csv", 1)[0].rsplit("_t", 1)[0]
# every checked fact is in the pool: the 21 hand-transcribed tables (t01_<name>.csv) have no strips, so their
# item names the PDF page instead (squad seed 15: they were never sampled)
a = random.sample(rows, min(20, len(rows)))   # 20: one Haiku agent opening page images ran out of budget at 15 of 40
json.dump([{"id": i + 1, "images": strips.get(prefix(r[0]), []),
            **({} if prefix(r[0]) in strips else {"pdf": f"{ROOT}/{r[12]}", "page": int(str(r[13]).split(";")[0])}),
            "table_csv": r[0], "csv_line": r[1], "column": r[2],
            "value_as_recorded": r[3], "measure": r[4], "period": r[5], "category": r[6], "category_type": r[7],
            "geography": r[8], "other_dims": r[9], "table_title": r[10], "units": r[11]} for i, r in enumerate(a)],
          open(f"{ROOT}/data/reviews/sample_checked_facts_{seed}.json", "w"), indent=1)

q = """SELECT t.csv_path, f.csv_line, f."column", f.value_raw, f.measure, f.category, d.example_path, t.pages, f.layout, f.named_by
FROM facts f JOIN tables t USING (table_id) JOIN documents d USING (doc_id)
WHERE f.layout = ? AND f.value <> ''"""
pools = {k: c.execute(q, [k]).fetchall() for k in ("labelled", "inferred")}
b = [r for k in ("labelled", "inferred") for r in random.sample(pools[k], min(20, len(pools[k])))]
json.dump([{"id": i + 1, "pdf": f"{ROOT}/{r[6]}", "page": int(str(r[7]).split(";")[0]), "table_csv": r[0], "csv_line": r[1],
            "column": r[2], "value_as_recorded": r[3], "measure": r[4], "row_label": r[5], "layout": r[8],
            "named_by": r[9] or "column name"} for i, r in enumerate(b)],
          open(f"{ROOT}/data/reviews/sample_labelled_facts_{seed}.json", "w"), indent=1)
print(f"seed {seed}: {len(a)} checked facts (of {len(rows)}; {sum(prefix(r[0]) not in strips for r in rows)} from PDF pages), {len(b)} text-layer facts "
      f"(labelled of {len(pools['labelled'])}, inferred of {len(pools['inferred'])})")
