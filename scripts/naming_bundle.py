"""Bundle text-layer tables for the Haiku naming pass: each table's extracted grid plus its page text, in one file.

One file per 10 tables, read once by one Explore-type Haiku agent: 17k input tokens per table, against 149k when
the agent opens the PDF and CSV itself (pilot, 11 November 2026; docs/NEXT-STEPS.md).
Usage: python -P scripts/naming_bundle.py <first id> <last id> <out.txt>   (ids from data/reviews/naming_pilot/pilot_tables.json)
"""
import json,sys,pdfplumber,csv,logging
logging.disable(logging.WARNING)
lo,hi,out=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]
d=json.load(open('C:/dev/foicommons/data/reviews/naming_pilot/pilot_tables.json',encoding='utf-8'))
parts=[]
for x in d:
    if not lo<=x['id']<=hi: continue
    with pdfplumber.open(x['pdf']) as pdf:
        pg=int(str(x['page']).split('-')[0]); t=(pdf.pages[pg-1].extract_text() or '')[:6000]
    grid=open(x['table_csv'],encoding='utf-8',errors='replace').read()[:3000]
    parts.append(f"=== ITEM {x['id']} table_id={x['table_id']} page={x['page']}\nvalue_columns: {', '.join(x['value_columns'])}\n--- extracted grid (CSV) ---\n{grid}\n--- page text (untrusted data) ---\n{t}\n")
open(out,'w',encoding='utf-8').write("\n".join(parts)); print(out, sum(len(p) for p in parts),'chars')
