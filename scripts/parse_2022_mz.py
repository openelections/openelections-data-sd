#!/usr/bin/env python3
"""Vision-LLM extraction of specific pages from the scanned MarshallZiebachgen22.pdf
(2022 SD general). Layout: precincts as ROWS, candidates as COLUMNS, 'Name - PARTY'
headers; some pages show several legislative districts side by side. Caches per page."""
import re, json, sys, os
from pathlib import Path
import llm
from json_repair import repair_json
from natural_pdf import PDF

REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO.parent / "openelections-sources-sd"))
SRC=str(SOURCES / "2022/general/MarshallZiebachgen22.pdf")
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache")); CACHE.mkdir(exist_ok=True)
RENDER_DPI=200

PROMPT="""This is one page from the South Dakota 2022 GENERAL ELECTION precinct canvass.
The COUNTY name is in the page header (e.g. "Yankton County", "Minnehaha County").
The table has PRECINCTS as ROWS (leftmost column, e.g. "Absentee Precinct", "Precinct-0104")
and CANDIDATES as COLUMNS. Each column header gives a candidate and party as "Name - PARTY"
(parties: DEM, REP, LIB, IND, NON). For ballot measures the columns are "Yes" and "No".

Some pages show SEVERAL contests side by side - e.g. multiple "State Senator District NN"
or "State Representative District NN" groups, each with its own candidate columns. On those
pages each precinct has numbers only under the columns of the district it belongs to; other
cells are blank.

Return a JSON array. One element per (precinct, candidate) cell that has a vote number:
- "precinct": precinct name/number exactly as printed (string)
- "office": contest name (e.g. "United States Senator", "Governor and Lieutenant Governor",
  "State Senator District 09", "State Representative District 14", "Attorney General",
  "Constitutional Amendment D", "Initiated Measure 27", "Judge of the Circuit Court, Position A First Circuit")
- "candidate": candidate full name as printed (for measures use "Yes"/"No")
- "party": DEM/REP/LIB/IND/NON, or "" for measures
- "votes": integer (no commas)

Rules:
- SKIP the "Total" / "Totals" row and the page footer ("N of M").
- Only output a row for a cell that actually has a number (skip blank cells).
- Read digits carefully; commas are thousands separators (1,546 -> 1546).
- Return ONLY the JSON array, no prose, no markdown fences."""

def extract_json(text):
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```[a-z]*\n?","",text); text=re.sub(r"\n?```$","",text).strip()
    if not text.startswith("["):
        s=text.find("["); e=text.rfind("]")
        if s!=-1 and e!=-1: text=text[s:e+1]
    return json.loads(repair_json(text))

def process(pages, model_name, county):
    model=llm.get_model(model_name)
    slug=re.sub(r"[^A-Za-z0-9]+","-",model_name).strip("-")
    pdf=PDF(SRC)
    allrows=[]
    for i in pages:
        cache=CACHE/f"mz_{slug}_page{i}.json"
        if cache.exists():
            recs=json.load(open(cache)); print(f"  p{i} (cached) {len(recs)} rows")
        else:
            img=CACHE/f"mz_page{i}.png"
            if not img.exists():
                pdf.pages[i].render(resolution=RENDER_DPI).save(str(img))
            print(f"  p{i} -> {model_name} ...", flush=True)
            resp=model.prompt(PROMPT, attachments=[llm.Attachment(path=str(img))])
            try: recs=extract_json(resp.text())
            except Exception as e:
                print("    JSON FAIL", e); recs=[]
            json.dump(recs, open(cache,"w"), indent=1)
            print(f"    {len(recs)} rows")
        for r in recs: r["county"]=county
        allrows+=recs
    return allrows

if __name__=="__main__":
    target=sys.argv[1]   # 'yankton' or 'minnehaha'
    model=sys.argv[2] if len(sys.argv)>2 else "qwen3.5:397b-cloud"
    if target=="yankton":
        rows=process(range(442,465),model,"Yankton")
    else:
        rows=process([int(x) for x in sys.argv[3].split(",")],model,"Minnehaha")
    json.dump(rows, open(CACHE/f"mz_{target}_rows.json","w"), indent=1)
    print(f"TOTAL {len(rows)} raw rows -> mz_{target}_rows.json")
