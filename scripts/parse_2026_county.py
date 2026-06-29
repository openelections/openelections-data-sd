#!/usr/bin/env python3
"""Vision-LLM extraction of the SD 2026 PRIMARY state canvass (scanned, garbled OCR).
County-level: counties as rows, candidates as columns, one or more contest tables per page
(legislative pages hold a grid of small per-district tables). Caches per page."""
import re, json, sys, os
from pathlib import Path
import llm
from json_repair import repair_json
from natural_pdf import PDF

REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO.parent / "openelections-sources-sd"))
SRC=str(SOURCES / "2026/primary/State Canvass and Certificate.pdf")
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache")); CACHE.mkdir(exist_ok=True)
DPI=240

PROMPT="""This is one page from the South Dakota 2026 PRIMARY ELECTION official COUNTY canvass.
The page holds one or MORE contest tables. Each table has:
- a header giving the OFFICE (e.g. "United States Senator", "United States Representative",
  "Governor", "State Senator District 32", "State Representative District 19") and party "Republican";
- COUNTIES as rows (leftmost column) and CANDIDATES as columns;
- a final "Total" row.

The State Senate / State House pages contain SEVERAL small district tables (stacked and side by
side) - extract EVERY table, reading the district number from each table's own header.

If TWO images are provided, they are CONSECUTIVE pages of the SAME contest(s): the second image
continues the county list from the first and carries the "Total" row. The candidate column
headers appear on the FIRST image - reuse those exact candidate names for the second image's rows.

Return a JSON array, one element per (county, candidate) cell that has a number:
- "county": county name (standard SD spelling: Aurora, Bon Homme, Charles Mix, Fall River,
  McCook, McPherson, Oglala Lakota, ...). Use "Total" for the total row.
- "office": office text as printed (e.g. "United States Senator", "Governor",
  "State Senator District 32", "State Representative District 19")
- "district": district number as a string, or "" if none
- "candidate": candidate full name as printed
- "party": "REP"
- "votes": integer. Thousands may be printed with a comma OR a period (both "1,608" and
  "1.608" mean 1608). Output a plain integer with no separators.

Rules:
- INCLUDE the "Total" row of each contest (county="Total") so totals can be verified.
- Read digits carefully; this is a slightly noisy scan.
- Return ONLY the JSON array, no prose, no markdown fences."""

def extract_json(text):
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```[a-z]*\n?","",text); text=re.sub(r"\n?```$","",text).strip()
    if not text.startswith("["):
        s=text.find("["); e=text.rfind("]")
        if s!=-1 and e!=-1: text=text[s:e+1]
    return json.loads(repair_json(text))

# Statewide contests span two pages (header on first, Total on second) and must be sent as a
# unit so the candidate columns are always in view; legislative grid pages are self-contained.
UNITS=[[0,1],[2,3],[4,5],[6],[7],[8],[9]]

def render(pdf,i):
    img=CACHE/f"p2026_page{i}.png"
    if not img.exists(): pdf.pages[i].render(resolution=DPI).save(str(img))
    return img

def process(units, model_name):
    model=llm.get_model(model_name)
    slug=re.sub(r"[^A-Za-z0-9]+","-",model_name).strip("-")
    pdf=PDF(SRC)
    allrows=[]
    for unit in units:
        tag="-".join(map(str,unit))
        cache=CACHE/f"p2026_{slug}_unit{tag}.json"
        if cache.exists():
            recs=json.load(open(cache)); print(f"  unit {tag} (cached) {len(recs)} rows")
        else:
            atts=[llm.Attachment(path=str(render(pdf,i))) for i in unit]
            print(f"  unit {tag} -> {model_name} ...", flush=True)
            resp=model.prompt(PROMPT, attachments=atts)
            try: recs=extract_json(resp.text())
            except Exception as e:
                print("    JSON FAIL", e); recs=[]
            json.dump(recs, open(cache,"w"), indent=1)
            print(f"    {len(recs)} rows")
        allrows+=recs
    return allrows

if __name__=="__main__":
    model=sys.argv[1] if len(sys.argv)>1 else "qwen3.5:397b-cloud"
    if len(sys.argv)>2:
        units=[[int(x) for x in u.split(',')] for u in sys.argv[2].split(';')]
    else:
        units=UNITS
    rows=process(units,model)
    json.dump(rows, open(CACHE/"p2026_rows.json","w"), indent=1)
    print(f"TOTAL {len(rows)} raw rows -> p2026_rows.json")
