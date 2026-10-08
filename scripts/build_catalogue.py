"""Build data/catalogue/: one linked set of tables describing everything archived and extracted.

  agencies -> logs -> requests -> document_sources -> documents -> tables -> columns
                                                                     tables -> series (same table across releases)

Every layer is rebuilt from the files the pipeline already writes (registry, manifests, surveys, the pdfplumber
index, vision meta.json + verify report), so the catalogue never drifts from the data. Documents are keyed by
sha256, so a file downloaded twice (two logs, phase 1 and the all-agency run) is one document with two sources.
Column meanings: docs/data-model.md.

  python -P scripts/build_catalogue.py              # everything
  python -P scripts/build_catalogue.py --log dss-main   # one log and the agency above it (for review)
"""
import argparse, csv, glob, hashlib, json, os, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(sys.maxsize)
ROOT = "C:/dev/foicommons"
DATA = f"{ROOT}/data"
OUT = f"{DATA}/catalogue"

# Phase 1 scrapers wrote their own manifests before the registry existed: say which log each one belongs to.
OLD_SOURCES = {"dss": "dss-main", "dss_detail": "dss-main", "dss_wayback": "dss-wayback",
               "servicesaustralia": "servicesaustralia-log"}
EXTRA_LOGS = {"dss-wayback": ("department-of-social-services", "Internet Archive copies of the old DSS disclosure log "
                              "(2010-11 to 2024), recovered by R/wayback.R")}


def iso_date(raw):
    """release_date as written by each log ("6 July 2022", "27/07/11", "2019-08-15") -> YYYY-MM-DD, or ""."""
    from datetime import datetime
    t = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", (raw or "").strip())
    four = bool(re.search(r"(19|20)\d\d", t))   # %Y also accepts "02" as year 2: only try it when 4 digits are there
    fmts = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%B %Y", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%SZ") if four else ("%d/%m/%y",)
    for f in fmts:
        try:
            d = datetime.strptime(t, f)
        except ValueError:
            continue
        # the FOI Act began in 1982; anything outside 1982..today is a misparse, not a date
        return d.strftime("%Y-%m-%d") if 1982 <= d.year and d <= datetime.now() else ""
    return ""


def bare_host(u):
    u = (u or "").strip()
    if not u:
        return ""
    h = re.sub(r"^https?://", "", u if "://" in u else "http://" + u).split("/")[0].lower()
    return h[4:] if h.startswith("www.") else h


def rel(p):
    """Repo-relative forward-slash path, whatever form the writer used."""
    p = (p or "").replace("\\", "/")
    return p.split("foicommons/", 1)[1] if "foicommons/" in p else p.lstrip("/")


def short_id(*parts):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def write(name, rows, fields):
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")


# ---- column meaning: which shared breakdown a column carries, so tables can be joined on it ----
STATES = {"nsw", "vic", "qld", "wa", "sa", "tas", "act", "nt", "australia", "total", "new south wales", "victoria",
          "queensland", "western australia", "south australia", "tasmania", "australian capital territory",
          "northern territory", "other", "unknown", "overseas"}
PAYMENTS = re.compile(r"jobseeker|newstart|youth allowance|austudy|abstudy|age pension|disability support|\bdsp\b|"
                      r"carer (payment|allowance)|parenting payment|family tax|\bftb\b|rent assistance|special benefit|"
                      r"sickness allowance|widow|partner allowance|mobility allowance|pension|allowance|supplement|"
                      r"paid parental|dad and partner|income management|baby bonus|schoolkids|energy supplement", re.I)
PLACE_LGA = re.compile(r"\((c|s|m|t|rc|dc|ac|b|r|rcc)\)$|shire|city of|council|regional|municipal", re.I)
FY = re.compile(r"(19|20)\d\d ?[-/–] ?(\d\d|(19|20)\d\d)")
# Breakdowns are judged on the column's VALUES; the name only decides between look-alikes (a year column
# vs a count, an electorate vs any list of places). Column names alone mis-tag: "division" was an AAT division.
DIMENSIONS = [
    ("state", lambda n, vs: share(vs, lambda v: v.lower().strip(" *") in STATES) > 0.6 and len(vs) >= 3),
    ("financial_year", lambda n, vs: share(vs, lambda v: FY.fullmatch(v.strip())) > 0.6),
    ("year", lambda n, vs: "year" in n and share(vs, lambda v: re.fullmatch(r"(19|20)\d\d", v.strip())) > 0.6),
    ("month", lambda n, vs: share(vs, lambda v: re.fullmatch(r"(\d{1,2}[\s/-]+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?([\s,/-]+\d{2,4})?", v.strip(), re.I)) > 0.6),
    ("lga", lambda n, vs: share(vs, lambda v: PLACE_LGA.search(v)) > 0.4 and len(vs) >= 5),
    ("electorate", lambda n, vs: "electorate" in n and len(vs) >= 5),
    ("payment_type", lambda n, vs: share(vs, lambda v: PAYMENTS.search(v)) > 0.5),
    ("age_group", lambda n, vs: share(vs, lambda v: re.search(r"\d+\s*(-|–|to)\s*\d+|\d+\s*(\+|and over|years)|under \d+", v, re.I)) > 0.6
                                and ("age" in n or share(vs, lambda v: "year" in v.lower() or "+" in v) > 0.3)),
    ("sex", lambda n, vs: share(vs, lambda v: v.lower().strip() in {"male", "female", "men", "women", "persons", "total", "m", "f"}) > 0.7),
]
# Pattern for wide tables whose year sits in the column NAME (lodged_2019_20): recorded, not reshaped here.
YEAR_IN_NAME = re.compile(r"(19|20)\d\d_?(\d\d)?")


def share(vals, test):
    vals = [v for v in vals if v.strip()]
    return sum(bool(test(v)) for v in vals) / len(vals) if vals else 0


NUM = re.compile(r"^\(?-?\$?\d[\d,]*(\.\d+)?%?\)?$")


def describe_column(name, vals):
    filled = [v for v in vals if v.strip() not in ("", "-", "n/a", "redacted")]
    num = share(filled, lambda v: NUM.match(v.replace(" ", "")))
    kind = "number" if num >= 0.8 else "label" if num <= 0.2 else "mixed"
    dim = ""
    lengths = sorted(len(v) for v in filled)
    short = bool(lengths) and lengths[len(lengths) // 2] <= 40   # prose "tables" (captions, paragraphs) carry no breakdown
    # a column of plain years (1998, 2000, ...) is numeric but is a breakdown, not a value: tag it so facts
    # use it as the row's period (Haiku doc check and re-check, 8 October 2026)
    if kind == "number" and len(filled) >= 2 and share(filled, lambda v: re.fullmatch(r"(19[89]\d|20[0-4]\d)", v.strip())) == 1 \
            and (re.search(r"year|^yr|period", name.lower()) or name.strip() == ""):
        kind, dim = "label", "year"
    elif kind != "number" and short:
        for d, test in DIMENSIONS:
            if test(name.lower(), filled):
                dim = d
                break
    return {"type": kind, "filled_share": round(len(filled) / len(vals), 3) if vals else 0,
            "numeric_share": round(num, 3), "example": (filled[0] if filled else "")[:60], "dimension": dim,
            "year_in_name": "yes" if kind != "label" and YEAR_IN_NAME.search(name) else ""}


MONTHS = r"january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"


def title_key(title):
    """Title with the parts that change between releases removed: dates, years, numbers, table labels."""
    t = title.lower()
    t = re.sub(r"\b(table|figure|attachment|appendix)\s*[a-z]?[\d.]*[a-z]?\b", " ", t)
    t = re.sub(r"\b(" + MONTHS + r")\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"\b(as at|at|to|from|of|the|and|for|by|in|on|continued|cont|untitled|table|previous|next|page|column|left|right|middle|first|second|third|fourth)\b", " ", t)
    words = re.findall(r"[a-z]{3,}", t)
    return " ".join(words) if len(words) >= 2 else ""


def norm_header(cols):
    return "|".join(sorted(re.sub(r"[^a-z]", "", c.lower()) for c in cols if c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", help="only this log (and its agency)")
    a = ap.parse_args()
    global OUT
    if a.log:   # a one-log review build must never overwrite the full catalogue (Haiku script scan, 8 October 2026)
        OUT = f"{DATA}/catalogue_review"

    # ---- agencies and logs ----
    reg = read(f"{DATA}/registry/agencies.csv")
    status = {r["log_slug"]: r for r in read(f"{DATA}/registry/harvest_status.csv")}
    agencies, logs = {}, {}
    for r in reg:
        agencies.setdefault(r["agency_slug"], {"agency_slug": r["agency_slug"], "agency": r["agency"],
            "portfolio": r["portfolio"], "website": r["website"], "type_of_body": r["agor_type_of_body"],
            "staff_asl": r["agor_asl"], "agor_id": r["agor_id"], "foi_page_url": r["foi_page_url"]})
        if r["disclosure_log_url"]:
            h = status.get(r["log_slug"], {})
            logs[r["log_slug"]] = {"log_slug": r["log_slug"], "agency_slug": r["agency_slug"], "log_url": r["disclosure_log_url"],
                "discovery_status": r["status"], "how_found": r["how_found"], "robots_ok": r["robots_ok"],
                "harvest_status": h.get("status", ""), "harvested_at": h.get("finished_at", ""), "note": r["notes"]}
    # Logs harvested under the wrong agency before R/build_registry.R learned to drop foreign links (ANAO got
    # the PMC, Treasury and Infrastructure logs; ARENA got DCCEEW's). Their documents are already on disk, so
    # credit each such log to the agency whose website hosts it. A log on no agency's site keeps its agency
    # and is marked, never silently counted.
    site = {}
    for ag in agencies.values():
        h = bare_host(ag["website"])
        if h:
            site.setdefault(h, ag["agency_slug"])
    ok_hosts = {"cer.gov.au", "nzea.gov.au", "publichospitalfunding.gov.au", "webarchive.nla.gov.au"}
    for l in logs.values():
        h, own = bare_host(l["log_url"]), bare_host(agencies[l["agency_slug"]]["website"])
        if not h or h in ok_hosts or h == own or h.endswith("." + own) or own.endswith("." + h):
            continue
        owner = site.get(h)
        l["note"] = (f"reattributed from {l['agency_slug']}: log is on {h}" if owner else
                     f"log host {h} is not {l['agency_slug']}'s site and matches no agency") + ("; " + l["note"] if l["note"] else "")
        if owner:
            l["agency_slug"] = owner
    for slug, (ag, note) in EXTRA_LOGS.items():
        logs[slug] = {"log_slug": slug, "agency_slug": ag, "log_url": "web.archive.org", "discovery_status": "wayback",
                      "harvest_status": "complete", "note": note}

    # ---- requests and document sources, from every manifest ----
    requests, sources = {}, []
    # phase 1 manifests first: their titles and dates are parsed fields, the harvest's are raw log text
    mans = sorted(glob.glob(f"{DATA}/manifest_*.csv"))
    for m in sorted(mans, key=lambda f: "log_slug" in open(f, encoding="utf-8").readline()):
        for r in read(m):
            if "log_slug" in r and r.get("link_type") != "document":
                continue          # listing pages, navigation pages, mailto links are not requests; agency logs
                                  # list a request only through its documents (phase 1 DSS also lists email-only ones)
            has_file = r.get("http_status") == "200" and r.get("local_path") and r.get("sha256")
            if "log_slug" in r:   # all-agency harvest layout
                log = OLD_SOURCES.get(r["log_slug"], r["log_slug"]); key = r["item_id"] or r["detail_url"] or r["title"]
                title = r["title"] or r["item_text"][:200]; release = r["date_detected"]; decision = r["decision"]
            else:                 # phase 1 layout
                log = OLD_SOURCES.get(r["source"], r["source"]); key = r["reference"] or r["title"]
                title = r["title"]; release = r["release_date"]; decision = r["decision"]
            # the same request reached through two manifests (phase 1 and the all-agency run) must be one
            # request: key on the FOI reference when there is one, normalised ("FOI_LEX_56712" = "FOI LEX 56712")
            ref = re.sub(r"[^A-Z0-9]", "", r.get("reference", "").upper())
            rid = short_id(log, ref) if ref else short_id(log, key)
            requests.setdefault(rid, {"request_id": rid, "log_slug": log, "foi_reference": r.get("reference", "").strip(),
                                      "title": title.strip()[:300], "release_date": release, "release_date_iso": iso_date(release), "decision": decision})
            if not has_file or ("log_slug" in r and r.get("link_type") != "document"):
                continue          # the request is kept even when its documents were not released online
            sources.append({"request_id": rid, "doc_id": r["sha256"], "log_slug": log, "local_path": rel(r["local_path"]),
                            "doc_url": r.get("doc_url", ""), "bytes": r.get("bytes", "")})

    # ---- documents: one per sha256, described by whichever survey saw a copy ----
    by_path = {s["local_path"]: s["doc_id"] for s in sources}
    surveyed = {}
    # survey_docs.csv is the first one-off survey: its `scanned` is a 0/1 flag, not a page count. It is
    # superseded by survey_phase1.csv (same files, current rules), so it is never read here.
    for f in sorted(glob.glob(f"{DATA}/survey/survey_*.csv")):
        if f.replace("\\", "/").endswith("/survey_docs.csv"):
            continue
        for r in read(f):
            d = by_path.get(rel(r["file"]))
            if d and d not in surveyed:
                surveyed[d] = r
    documents = {}
    for s in sources:
        if s["doc_id"] in documents:
            continue
        v = surveyed.get(s["doc_id"], {})
        documents[s["doc_id"]] = {"doc_id": s["doc_id"], "ext": os.path.splitext(s["local_path"])[1].lower(),
            "bytes": s["bytes"], "pages": v.get("pages", ""), "scanned_pages": v.get("scanned", ""),
            "text_table_lines": v.get("table_lines", ""), "class": v.get("class", "not surveyed"),
            "example_path": s["local_path"]}

    # ---- tables: pdfplumber index + vision meta files, one list ----
    verify = {rel(r["table"]): r for r in read(f"{DATA}/extract/vision/verify_report.csv")}
    # text above each text-layer table (scripts/table_captions.py); only "Table N: ..." style lines count as a
    # caption here, the rest is usually page furniture
    capf = f"{DATA}/extract/table_captions.csv"
    captions = {r["csv_path"]: r["caption"] for r in read(capf) if r["status"] == "ok"
                and re.match(r"^\s*(table|figure|chart)\s*[a-z]?\d", r["caption"], re.I)} if os.path.exists(capf) else {}
    tables = []
    for r in read(f"{DATA}/extract/tables_index.csv"):
        d = by_path.get(rel(r["file"]))
        tables.append({"table_id": short_id(rel(r["csv_path"])), "doc_id": d or "", "method": "pdfplumber",
            "pages": r["page"], "table_n": r["table_n"], "title": r["header"][:200], "units": "",
            "n_rows": r["n_rows"], "n_cols": r["n_cols"], "check_status": "text layer (no check)",
            "caption": captions.get(rel(r["csv_path"]), ""), "csv_path": rel(r["csv_path"])})
    for mfile in glob.glob(f"{DATA}/extract/vision/**/*.meta.json", recursive=True):
        meta = json.load(open(mfile, encoding="utf-8"))
        base = rel(mfile[: -len(".meta.json")])
        csvp = base + ".csv"
        if not os.path.exists(f"{ROOT}/{csvp}"):
            continue
        with open(f"{ROOT}/{csvp}", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        v = verify.get(base, {})
        tables.append({"table_id": short_id(csvp), "doc_id": by_path.get(rel(meta.get("source_pdf", "")), ""),
            "method": "vision", "pages": ";".join(str(p) for p in meta.get("pages", [])),
            "table_n": re.search(r"_t(\d+)$", base).group(1) if re.search(r"_t(\d+)$", base) else "",
            "title": meta.get("title", "")[:200], "units": meta.get("units", "")[:200],
            "n_rows": max(len(rows) - 1, 0), "n_cols": len(rows[0]) if rows else 0,
            "check_status": v.get("status", "not verified"), "csv_path": csvp})

    # ---- filter to one log for review ----
    if a.log:
        keep_req = {k for k, r in requests.items() if r["log_slug"] == a.log}
        sources = [s for s in sources if s["request_id"] in keep_req]
        keep_doc = {s["doc_id"] for s in sources}
        requests = {k: r for k, r in requests.items() if k in keep_req}
        documents = {k: d for k, d in documents.items() if k in keep_doc}
        tables = [t for t in tables if t["doc_id"] in keep_doc]
        ag = logs[a.log]["agency_slug"]
        logs = {k: l for k, l in logs.items() if l["agency_slug"] == ag}
        agencies = {ag: agencies[ag]}

    # ---- columns (data dictionary) and series ----
    columns, groups = [], defaultdict(list)
    doc_agency = {}
    for src in sources:
        doc_agency.setdefault(src["doc_id"], logs.get(src["log_slug"], {}).get("agency_slug", src["log_slug"]))
    for t in tables:
        with open(f"{ROOT}/{t['csv_path']}", encoding="utf-8", errors="replace") as fh:
            rows = list(csv.reader(fh))
        if not rows:
            continue
        head = rows[0]
        for i, c in enumerate(head):
            columns.append({"table_id": t["table_id"], "position": i + 1, "column": c,
                            **describe_column(c, [r[i] if i < len(r) else "" for r in rows[1:]])})
        # A series is the same table published again (another month, year, release). Agents name columns
        # differently each time, so match on the TITLE with dates and numbers removed, within one agency.
        # pdfplumber "titles" are usually the first data row, so only vision tables are grouped for now.
        if t["method"] == "vision":
            k = title_key(t["title"])
            if k:
                groups[(doc_agency.get(t["doc_id"], ""), k)].append((t, norm_header(head)))
    series = []
    for (ag, k), ts in groups.items():
        docs = {t["doc_id"] for t, _ in ts}
        if len(docs) < 2:
            continue   # repeats inside one document are copies, not a series
        sid = short_id(ag, k)
        same_cols = len({h for _, h in ts}) == 1
        for t, h in ts:
            series.append({"series_id": sid, "agency_slug": ag, "title_key": k, "table_id": t["table_id"],
                           "doc_id": t["doc_id"], "title": t["title"], "n_tables": len(ts), "n_documents": len(docs),
                           "confidence": "high (same title and columns)" if same_cols else "medium (same title, columns differ)"})

    # ---- counts up the chain ----
    n_docs = Counter(s["request_id"] for s in {(s["request_id"], s["doc_id"]): s for s in sources}.values())
    n_tab = Counter(t["doc_id"] for t in tables)
    n_src = Counter(s["doc_id"] for s in sources)
    for r in requests.values():
        r["n_documents"] = n_docs.get(r["request_id"], 0)
    for d in documents.values():
        d["n_tables"] = n_tab.get(d["doc_id"], 0)
        d["n_sources"] = n_src.get(d["doc_id"], 0)
    req_per_log = Counter(r["log_slug"] for r in requests.values())
    for l in logs.values():
        l["n_requests"] = req_per_log.get(l["log_slug"], 0)

    print(f"catalogue -> {OUT}" + (f" (log {a.log} only)" if a.log else ""))
    write("agencies", list(agencies.values()), ["agency_slug", "agency", "portfolio", "website", "type_of_body", "staff_asl", "agor_id", "foi_page_url"])
    write("logs", list(logs.values()), ["log_slug", "agency_slug", "log_url", "discovery_status", "how_found", "robots_ok", "harvest_status", "harvested_at", "n_requests", "note"])
    write("requests", list(requests.values()), ["request_id", "log_slug", "foi_reference", "title", "release_date", "release_date_iso", "decision", "n_documents"])
    write("document_sources", sources, ["request_id", "doc_id", "log_slug", "local_path", "doc_url", "bytes"])
    write("documents", list(documents.values()), ["doc_id", "ext", "bytes", "pages", "scanned_pages", "text_table_lines", "class", "n_tables", "n_sources", "example_path"])
    write("tables", tables, ["table_id", "doc_id", "method", "pages", "table_n", "title", "caption", "units", "n_rows", "n_cols", "check_status", "csv_path"])
    write("columns", columns, ["table_id", "position", "column", "type", "filled_share", "numeric_share", "example", "dimension", "year_in_name"])
    write("series", series, ["series_id", "agency_slug", "title_key", "table_id", "doc_id", "title", "n_tables", "n_documents", "confidence"])


LINEAGE = """
CREATE OR REPLACE VIEW table_lineage AS
SELECT t.table_id, t.method, t.title AS table_title, t.units, t.pages, t.n_rows, t.n_cols, t.check_status, t.csv_path,
       d.doc_id, d.class AS doc_class, d.pages AS doc_pages,
       r.request_id, r.foi_reference, r.title AS request_title, r.release_date, r.release_date_iso,
       l.log_slug, a.agency_slug, a.agency, a.portfolio
FROM tables t
JOIN documents d USING (doc_id)
JOIN (SELECT DISTINCT doc_id, request_id FROM document_sources) s USING (doc_id)
JOIN requests r USING (request_id)
JOIN logs l ON l.log_slug = r.log_slug
JOIN agencies a ON a.agency_slug = l.agency_slug
"""


def build_duckdb():
    """catalogue.duckdb: every catalogue CSV as a table, plus the table_lineage view. The CSVs stay the
    master copy; this file is rebuilt from them and is only for querying."""
    try:
        import duckdb
    except ImportError:
        print("  duckdb not installed: CSVs only")
        return
    path = f"{OUT}/catalogue.duckdb"
    if os.path.exists(path):
        os.remove(path)
    con = duckdb.connect(path)
    for name in ("agencies", "logs", "requests", "document_sources", "documents", "tables", "columns", "series"):
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_csv('{OUT}/{name}.csv', all_varchar = true, header = true)")
    con.execute(LINEAGE)
    n = con.execute("SELECT count(*), count(DISTINCT table_id) FROM table_lineage").fetchone()
    con.close()
    print(f"  catalogue.duckdb: table_lineage {n[0]} rows for {n[1]} tables")


if __name__ == "__main__":
    main()
    build_duckdb()
