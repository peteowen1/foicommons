"""Scanned-page queue and free local OCR (RapidOCR), so vision transcriptions can be checked
against an independent reading of the page instead of a second model transcription.

  python -P scripts/ocr_pages.py queue   # merge triage_out_*.json into scanned/queue.json, render pages
  python -P scripts/ocr_pages.py ocr     # OCR every queued page; resumable, one JSON written per page
  python -P scripts/ocr_pages.py strips  # zoomed strips per page (run after ocr: sideways pages are found from it)
An optional last argument names another batch folder (e.g. data/extract/vision/scanned_wayback),
whose to_transcribe.json (scripts/merge_triage.py) replaces the triage_out_*.json files.

Per page:
  data/pages/<source>/<key>/p0001.png                   144 dpi (native scan resolution) for transcription
  data/pages/<source>/<key>/p0001_288.png               288 dpi grey, OCR input only
  data/extract/vision/scanned/ocr/<source>/<key>/p0001.json   [[box, text, confidence], ...]
<key> is the reference slug, plus the PDF name when a reference holds several PDFs (as in vision_tools sheets).
"""
import json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_tools import ROOT, VISION

SCANNED = sys.argv[2].replace("\\", "/").rstrip("/") if len(sys.argv) > 2 else f"{VISION}/scanned"
# Triage results set aside after review (7 October 2026): charts without data labels, contract
# pricing and rule lookup tables are not statistics.
EXCLUDE = {("17/18-079", 2), ("17/18-079", 3), ("17/18-131", 10), ("17/18-131", 25), ("17/18-131", 36),
           ("17/18-131", 63), ("LEX 85224", 6), ("LEX 85224", 7), ("LEX 90604", 35)}


def doc_keys():
    """file -> key, read back from the sheet names vision_tools sheets wrote."""
    out = {}
    for e in json.load(open(f"{SCANNED}/sheets_index.json", encoding="utf-8")):
        name = os.path.basename(e["sheet"])[: -len(".png")]
        out[e["file"]] = name.split("__", 1)[1].rsplit("__", 1)[0]
    return out


def cmd_queue():
    keys = doc_keys()
    pages = []
    if os.path.exists(f"{SCANNED}/to_transcribe.json"):
        pages = json.load(open(f"{SCANNED}/to_transcribe.json", encoding="utf-8"))
    else:
        for i in (1, 2, 3):
            pages += json.load(open(f"{SCANNED}/triage_out_{i}.json", encoding="utf-8"))
    q = []
    for p in pages:
        if p["kind"] == "chart" or (p["reference"], p["page"]) in EXCLUDE:
            continue
        key = keys[p["file"].replace("\\", "/")]
        d = f"{ROOT}/pages/{p['source']}/{key}"
        os.makedirs(d, exist_ok=True)
        for dpi, suffix in ((144, ""), (288, "_288")):
            target = f"{d}/p{p['page']:04d}{suffix}.png"
            if not os.path.exists(target):
                r = subprocess.run(["pdftoppm", "-f", str(p["page"]), "-l", str(p["page"]), "-r", str(dpi), "-gray", "-png",
                                    "-singlefile", p["file"], target[:-4]], capture_output=True)
                if r.returncode:
                    print(f"pdftoppm failed ({r.returncode}) on {p['file']} p{p['page']}: {r.stderr.decode(errors='ignore')[:200]}")
        q.append({**p, "key": key, "image": f"{d}/p{p['page']:04d}.png",
                  "ocr": f"{SCANNED}/ocr/{p['source']}/{key}/p{p['page']:04d}.json"})
    q.sort(key=lambda e: (e["source"], e["key"], e["page"]))
    json.dump(q, open(f"{SCANNED}/queue.json", "w", encoding="utf-8"), indent=1)
    missing = [x for e in q for x in (e["image"], e["image"][:-4] + "_288.png") if not os.path.exists(x)]
    print(f"{len(q)} pages queued from {len(pages)} triaged; {len(missing)} failed to render {missing[:3]}")


def cmd_ocr():
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    q = json.load(open(f"{SCANNED}/queue.json", encoding="utf-8"))
    todo = [e for e in q if not os.path.exists(e["ocr"])]
    print(f"{len(q)} pages, {len(todo)} still to OCR", flush=True)
    t0 = time.time()
    for n, e in enumerate(todo, 1):
        src = e["image"][:-4] + "_288.png"
        if not os.path.exists(src):
            print(f"missing {src}; skipped (run queue first)")
            continue
        res, _ = eng(src)
        if not res:
            print(f"WARNING: OCR found no text on {src}; saved as empty, so every number in its tables will flag")
        os.makedirs(os.path.dirname(e["ocr"]), exist_ok=True)
        tmp = e["ocr"] + ".part"
        json.dump([[b, s, float(c)] for b, s, c in (res or [])], open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, e["ocr"])   # a killed run never leaves a half-written page that looks done
        print(f"{n}/{len(todo)} {e['reference']} p{e['page']}: {len(res or [])} boxes, {time.time() - t0:.0f}s", flush=True)


def sideways(ocr_json):
    """True when most OCR text boxes are taller than wide: the page's text runs sideways, so
    horizontal strips would cut the table across its columns. For triage files with no rotated flag."""
    boxes = json.load(open(ocr_json, encoding="utf-8")) if os.path.exists(ocr_json) else []
    long = [b for b, s, c in boxes if len(s) >= 4]
    if len(long) < 5:
        return False
    tall = sum((max(y for _, y in b) - min(y for _, y in b)) > (max(x for x, _ in b) - min(x for x, _ in b)) for b in long)
    return tall > len(long) / 2


def cmd_strips():
    """Zoomed table strips for every queued page (vision_tools strips). Pages whose table is turned
    sideways are left whole: horizontal strips would slice the table across its columns."""
    from vision_tools import cmd_strips as strips
    q = json.load(open(f"{SCANNED}/queue.json", encoding="utf-8"))
    for e in q:
        if "rotated" not in e and not os.path.exists(e["ocr"]):
            # sideways() reads the OCR: run before it, it silently says "upright" and the page is cut across
            # its columns (8 pages of the 8 October batch). Leave the page for a later run instead.
            e["strips"] = []
            continue
        if "rotated" not in e:   # batch 1 flagged landscape pages by hand: sent whole, never stripped
            from PIL import Image
            w, h = Image.open(e["image"]).size
            e["rotated"] = w > h or sideways(e["ocr"])
        if e["rotated"] and e["reference"] != "FOI LEX 55799":   # 55799 "rotated" means landscape, table upright
            e["strips"] = [e["image"]]
            continue
        out = os.path.dirname(e["image"]) + "/strips"
        stem = os.path.basename(e["image"])[:-4]
        done = sorted(f"{out}/{f}" for f in os.listdir(out) if f.startswith(stem + "_s")) if os.path.isdir(out) else []
        # 55799 pages carry a running header above the table; other documents start at the top
        e["strips"] = done or strips(e["image"][:-4] + "_288.png", out, top_skip=200 if e["reference"] == "FOI LEX 55799" else 0)
    json.dump(q, open(f"{SCANNED}/queue.json", "w", encoding="utf-8"), indent=1)
    print(f"{len(q)} pages, {sum(len(e['strips']) for e in q)} strips")


if __name__ == "__main__":
    {"queue": cmd_queue, "ocr": cmd_ocr, "strips": cmd_strips}[sys.argv[1]]()
