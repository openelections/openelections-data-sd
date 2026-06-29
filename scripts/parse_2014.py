#!/usr/bin/env python3
"""Vision-LLM extraction of the SD 2014 Official Election Returns book (county-level).
Landscape pages, each holding up to two book-pages, each with one or more contest tables
(counties as rows, candidates as columns, Total row). Caches per page."""
import re, json, sys, os
from pathlib import Path
import llm
from json_repair import repair_json
from natural_pdf import PDF

REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO.parent / "openelections-sources-sd"))
SRC=str(SOURCES / "2014/2014ElectionReturn.pdf")
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache")); CACHE.mkdir(exist_ok=True)
DPI=260

PROMPT="""This is one LANDSCAPE page from the South Dakota 2014 Official Election Returns book.
It may show TWO book-pages side by side; each holds ONE or MORE contest result tables.

Each contest table has:
- a header naming the OFFICE. Examples: "Republican United States Senator", "Democratic Governor",
  "United States Senate", "Governor and Lieutenant Governor", "Attorney General",
  "Public Utilities Commission", "State Senate District 12", "State Representative District 19",
  "Supreme Court Retention" (a justice name with Yes/No), "Judge of the Circuit Court" (Yes/No),
  "Constitutional Amendment Q", "Initiated Measure 17".
- COUNTIES as rows (leftmost column) and CANDIDATES as columns; ballot measures / retention use
  "Yes" and "No" columns.
- a final "Total" row.

Legislative (State Senate / State Representative) and judicial pages contain a GRID of several
small district tables - extract EVERY table, reading the district/position from each header.

Return a JSON array, one element per (county, candidate) cell that has a number:
- "county": county name (standard SD spelling; "Shannon" was a 2014 county). Use "Total" for the total row.
- "office": office text as printed (include party word for primaries, e.g. "Republican Governor";
  include district, e.g. "State Senate District 12")
- "district": district number/identifier as a string, or "" if none
- "candidate": candidate name as printed (for measures/retention use "Yes" or "No")
- "party": party of the candidate if shown (REP, DEM, LIB, IND, CON, ...), else ""
- "votes": integer (no thousands separators)

Rules:
- INCLUDE each contest's "Total" row (county="Total") so totals can be verified.
- IGNORE anything that is not a vote-results table: cover pages, the Secretary's letter, sample
  ballots, voter-registration / precinct-count tables, ballot-measure text descriptions, recount
  narratives. Return [] if the page has no results table.
- Read digits carefully.
- Return ONLY the JSON array, no prose, no markdown fences."""

def extract_json(text):
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```[a-z]*\n?","",text); text=re.sub(r"\n?```$","",text).strip()
    if not text.startswith("["):
        s=text.find("["); e=text.rfind("]")
        if s!=-1 and e!=-1: text=text[s:e+1]
    return json.loads(repair_json(text))

import signal
from PIL import Image
HALF_PAGES={9,10}   # dense pages with several full-county contests -> split L/R to shrink output
TIMEOUT=300

class _TO(Exception): pass
def _alarm(s,f): raise _TO()

def render(pdf,i):
    img=CACHE/f"y2014_page{i}.png"
    if not img.exists(): pdf.pages[i].render(resolution=DPI).save(str(img))
    return img

def render_half(pdf,i,side):
    out=CACHE/f"y2014_page{i}_{side}.png"
    if out.exists(): return out
    full=Image.open(render(pdf,i)); W,H=full.size; m=int(W*0.03)
    box=(0,0,W//2+m,H) if side=="L" else (W//2-m,0,W,H)
    full.crop(box).save(str(out)); return out

def _ask(model,img_path):
    try:
        signal.signal(signal.SIGALRM,_alarm); signal.alarm(TIMEOUT); can=True
    except ValueError: can=False
    try:
        for attempt in range(1,4):
            try:
                resp=model.prompt(PROMPT, attachments=[llm.Attachment(path=str(img_path))])
                return extract_json(resp.text())
            except Exception as e:
                if attempt==3: print("    FAIL after retries:",e); return []
                print(f"    retry {attempt} ({e})", flush=True)
    finally:
        if can: signal.alarm(0)

def process(pages, model_name):
    model=llm.get_model(model_name)
    slug=re.sub(r"[^A-Za-z0-9]+","-",model_name).strip("-")
    pdf=PDF(SRC)
    allrows=[]
    for i in pages:
        cache=CACHE/f"y2014_{slug}_page{i}.json"
        if cache.exists():
            recs=json.load(open(cache)); print(f"  p{i} (cached) {len(recs)} rows")
        else:
            recs=[]
            if i in HALF_PAGES:
                for side in ("L","R"):
                    print(f"  p{i}-{side} -> {model_name} ...", flush=True)
                    part=_ask(model, render_half(pdf,i,side)); print(f"    {len(part)} rows")
                    recs+=part
            else:
                print(f"  p{i} -> {model_name} ...", flush=True)
                recs=_ask(model, render(pdf,i)); print(f"    {len(recs)} rows")
            for r in recs: r["_page"]=i
            json.dump(recs, open(cache,"w"), indent=1)
        allrows+=recs
    return allrows

if __name__=="__main__":
    model=sys.argv[1] if len(sys.argv)>1 else "qwen3.5:397b-cloud"
    tag=sys.argv[2] if len(sys.argv)>2 else "test"
    pages=[int(x) for x in sys.argv[3].split(",")] if len(sys.argv)>3 else [4]
    rows=process(pages,model)
    json.dump(rows, open(CACHE/f"y2014_{tag}_rows.json","w"), indent=1)
    print(f"TOTAL {len(rows)} raw rows -> y2014_{tag}_rows.json")
