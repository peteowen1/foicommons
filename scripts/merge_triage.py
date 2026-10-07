"""Merge per-batch triage outputs into one list of pages to transcribe.

Each batch agent read contact sheets listed in triage/in_NN.json and wrote
triage/out_NN.json ({doc, page, kind}). This checks every listed page was on
one of that batch's sheets (catches misread tile labels), attaches the source
file and FOI reference, and writes triage.json beside the triage folder.

Usage: python -I scripts/merge_triage.py data/extract/vision/scanned_wayback
"""
import collections
import glob
import json
import os
import sys

# Copies of a document already listed under another code, checked 8 October 2026 by perceptual
# hash of the page thumbnails plus matching document number and page count. Drafts of the same
# report (D095/D096, D388/D389/D391) are NOT here: their pages differ and the numbers may too.
DUPLICATE_OF = {
    "D071": "D030", "D047": "D019", "D062": "D026", "D064": "D028",  # 12/13-065 re-released 12/13-073 docs
    "D550": "D158",  # byte-identical file, 12/13-006
}

root = sys.argv[1]
tdir = os.path.join(root, "triage")
merged, problems = [], []
for inp in sorted(glob.glob(os.path.join(tdir, "in_*.json"))):
    n = os.path.basename(inp)[3:5]
    out = os.path.join(tdir, f"out_{n}.json")
    if not os.path.exists(out):
        problems.append(f"batch {n}: no output file")
        continue
    tiles = {(t["doc"], t["page"]): t for s in json.load(open(inp)) for t in s["tiles"]}
    for r in json.load(open(out)):
        t = tiles.get((r["doc"], int(r["page"])))
        if t is None:
            problems.append(f"batch {n}: {r['doc']} p{r['page']} not on its sheets")
            continue
        if r["kind"] not in ("stats", "chart", "maybe"):
            problems.append(f"batch {n}: {r['doc']} p{r['page']} unknown kind {r['kind']!r}")
        merged.append({**t, "kind": r["kind"], "batch": n})

keys = [(r["doc"], r["page"]) for r in merged]
dupes = [k for k, c in collections.Counter(keys).items() if c > 1]
merged.sort(key=lambda r: (r["doc"], r["page"]))
for r in merged:
    if r["doc"] in DUPLICATE_OF:
        r["duplicate_of"] = DUPLICATE_OF[r["doc"]]
json.dump(merged, open(os.path.join(root, "triage.json"), "w"), indent=1)
todo = [r for r in merged if r["kind"] == "stats" and "duplicate_of" not in r]
json.dump(todo, open(os.path.join(root, "to_transcribe.json"), "w"), indent=1)

print(f"pages listed: {len(merged)}  by kind: {dict(collections.Counter(r['kind'] for r in merged))}")
print(f"documents with a listed page: {len({r['doc'] for r in merged})}  duplicates: {len(dupes)}")
print(f"stats pages to transcribe: {len(todo)} in {len({r['doc'] for r in todo})} documents "
      f"({sum('duplicate_of' in r for r in merged if r['kind'] == 'stats')} stats pages dropped as copies)")
for p in problems:
    print("PROBLEM:", p)
