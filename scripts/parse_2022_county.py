#!/usr/bin/env python3
"""Parse the SD 2022 general election statewide canvass (clean digital PDF text layer)
into an OpenElections county-level CSV."""
import os, re, csv, sys
from pathlib import Path
from natural_pdf import PDF

# Repo root (this file lives in <repo>/scripts/). The source-PDF repo is expected as a
# sibling checkout; override with SD_SOURCES if it lives elsewhere.
REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO.parent / "openelections-sources-sd"))

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else \
    str(SOURCES / "2022/general/2022Generalcanvassreport.pdf")
OUT = sys.argv[2] if len(sys.argv) > 2 else \
    str(REPO / "2022/20221108__sd__general__county.csv")

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

PARTY = r'(DEM|REP|LIB|IND|NON|CON|NPA|UNF)'
PARTY_SPLIT = re.compile(r'\s-\s' + PARTY + r'\b')
HAS_PARTY = re.compile(r'\s-\s' + PARTY + r'\b')
INT_RE = re.compile(r'^[\d,]+$')
ORD = {"First":"1","Second":"2","Third":"3","Fourth":"4","Fifth":"5","Sixth":"6",
       "Seventh":"7","Eighth":"8","Ninth":"9"}

def split_row(line):
    toks = line.split()
    nums=[]; i=len(toks)
    while i>0 and INT_RE.match(toks[i-1]):
        nums.append(int(toks[i-1].replace(",",""))); i-=1
    if not nums: return None
    nums.reverse()
    return " ".join(toks[:i]), nums

def parse_candidates(line):
    toks = PARTY_SPLIT.split(line)
    cands=[]
    for j in range(0,len(toks)-1,2):
        name=toks[j].strip(); party=toks[j+1]
        if name: cands.append((name,party))
    return cands

def normalize_office(text):
    """Return (office, district, justice_or_None)."""
    t = re.sub(r'\s+',' ',text).strip()
    if t.startswith("United States Senator"): return "U.S. Senate","",None
    if t.startswith("United States Representative"): return "U.S. House","1",None
    if t.startswith("Governor"): return "Governor","",None
    if t.startswith("Secretary of State"): return "Secretary of State","",None
    if t.startswith("Attorney General"): return "Attorney General","",None
    if t.startswith("State Auditor"): return "State Auditor","",None
    if t.startswith("State Treasurer"): return "State Treasurer","",None
    if t.startswith("Commissioner of School and Public Lands"):
        return "Commissioner of School and Public Lands","",None
    if t.startswith("Public Utilities Commissioner"): return "Public Utilities Commissioner","",None
    m=re.match(r'State Senator District (\w+)',t)
    if m: return "State Senate",m.group(1),None
    m=re.match(r'State Representative District (\w+)',t)
    if m: return "State House",m.group(1),None
    m=re.match(r'Judge of the Circuit Court,\s*(.+)',t)
    if m: return "Judge of the Circuit Court",m.group(1).strip(),None
    if t.startswith("Supreme Court Justice Retention"):
        jm=re.search(r'Shall Justice (.+?) representing',t)
        dm=re.search(r'the (\w+) Supreme Court District',t)
        justice=jm.group(1).strip() if jm else ""
        dist=ORD.get(dm.group(1),"") if dm else ""
        return "Supreme Court Retention",dist,justice
    m=re.match(r'(Constitutional Amendment [A-Z]\b)',t)
    if m: return m.group(1),"",None
    m=re.match(r'(Initiated Measure \d+)\b',t)
    if m: return m.group(1),"",None
    m=re.match(r'(Referred Law \d+)\b',t)
    if m: return m.group(1),"",None
    if "James River Water Development District" in t:
        return "James River Water Development District","",None
    return t,"",None  # fallback (flag later)

pdf = PDF(PDF_PATH)
contests=[]  # dict office,district,justice,cands,rows,total
cur=None
office_buf=[]

def finalize_header(cands, is_yesno=False):
    global cur, office_buf
    office_text=" ".join(office_buf).strip()
    office,district,justice = normalize_office(office_text)
    cur={"office":office,"district":district,"justice":justice,
         "cands":cands,"rows":{}, "total":None,"raw":office_text}
    contests.append(cur)
    office_buf=[]

for pi in range(1,len(pdf.pages)):
    for raw in (pdf.pages[pi].extract_text() or "").splitlines():
        line=raw.strip()
        if not line: continue
        if line=="County": continue
        # measure/retention header
        if line in ("County Yes No","Yes No"):
            finalize_header([("Yes",""),("No","")], is_yesno=True); continue
        # candidate header (Name - PARTY ...)
        if HAS_PARTY.search(line) and not line.startswith("County "):
            finalize_header(parse_candidates(line)); continue
        # 'County <office>' continuation OR 'County <office>' that is candidate header
        if line.startswith("County "):
            rest=line[len("County "):].strip()
            if HAS_PARTY.search(rest):
                # e.g. 'County James River...': actually office; but if it parses as cands? keep as office
                office_buf=[rest]; continue
            office_buf=[rest]; continue
        # data / total row
        row=split_row(line)
        if row:
            name,nums=row
            low=name.strip().lower()
            if low=="total" and cur is not None:
                cur["total"]=nums; continue
            if low in COUNTIES and cur is not None:
                cur["rows"][COUNTIES[low]]=nums; continue
            # unknown leading text w/ trailing ints -> office description (rare); fall through
        office_buf.append(line)

# ---- Merge contest fragments that share the same (office, district, justice, candidate set) ----
merged={}
for c in contests:
    key=(c["office"],c["district"],c["justice"],tuple(n for n,_ in c["cands"]))
    if key not in merged:
        merged[key]={"office":c["office"],"district":c["district"],"justice":c["justice"],
                     "cands":c["cands"],"rows":{}, "total":None}
    m=merged[key]
    m["rows"].update(c["rows"])
    if c["total"] is not None: m["total"]=c["total"]  # grand total appears on last fragment

# ---- Build output rows + validate merged ----
out=[]
problems=[]
for c in merged.values():
    office,district,justice,cands=c["office"],c["district"],c["justice"],c["cands"]
    ncol=len(cands)
    colsum=[0]*ncol
    for cty,nums in c["rows"].items():
        if len(nums)!=ncol:
            problems.append(f"COLCOUNT {office} d{district} {cty}: {len(nums)} vs {ncol}"); continue
        for k in range(ncol): colsum[k]+=nums[k]
    if c["total"] and colsum!=c["total"]:
        problems.append(f"TOTAL {office} d{district}: sum {colsum} != pdf {c['total']}")
    if c["total"] is None:
        problems.append(f"NOTOTAL {office} d{district}: no Total row found ({len(c['rows'])} counties)")
    for cty,nums in c["rows"].items():
        if len(nums)!=ncol: continue
        for (name,party),v in zip(cands,nums):
            cand=name
            if office=="Supreme Court Retention" and justice:
                cand=f"{justice} - {name}"
            out.append([cty,office,district,party,cand,v])

with open(OUT,"w",newline="") as f:
    w=csv.writer(f); w.writerow(["county","office","district","party","candidate","votes"]); w.writerows(out)

# summary
from collections import Counter
print(f"contests parsed: {len(contests)}   output rows: {len(out)}")
oc=Counter((r[1],r[2]) for r in out)
print("offices:")
for (o,d),n in sorted(oc.items()):
    print(f"   {n:5d}  {o}{' d'+d if d else ''}")
print(f"\nVALIDATION problems: {len(problems)}")
for p in problems[:40]: print("  ",p)
