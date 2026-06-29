#!/usr/bin/env python3
"""Normalize 2026 primary county rows, validate each contest against its Total row, write CSV."""
import os, re, json, csv
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache"))
OUT=str(REPO / "2026/20260602__sd__primary__county.csv")

COUNTIES={c.lower():c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

def norm_office(t):
    t=re.sub(r'\s+',' ',t).strip()
    if re.search(r'United States Senator|U\.?S\.? Senate',t,re.I): return "U.S. Senate",""
    if re.search(r'United States Represent|U\.?S\.? House|Representative in Congress',t,re.I): return "U.S. House","1"
    if re.search(r'Governor',t,re.I): return "Governor",""
    m=re.search(r'Senat\w*\D*(\d+\w?)',t,re.I)
    if m and re.search(r'senat',t,re.I): return "State Senate",m.group(1)
    m=re.search(r'Represent\w*\D*(\d+\w?)',t,re.I)
    if m: return "State House",m.group(1)
    return t,""

def to_int(v):
    s=re.sub(r'[^\d]','',str(v))
    return int(s) if s else 0

def cty(name):
    n=str(name).strip()
    if n.lower()=='total': return 'Total'
    return COUNTIES.get(n.lower(), n)  # keep as-is if unknown (flagged later)

rows=json.load(open(CACHE/"p2026_rows.json"))
# normalize + dedupe
seen=set(); data=[]
for r in rows:
    office,district=norm_office(r.get('office',''))
    c=cty(r.get('county',''))
    cand=str(r.get('candidate','')).strip()
    party=str(r.get('party','REP')).strip().upper() or 'REP'
    v=to_int(r.get('votes',0))
    key=(office,district,c,cand)
    if key in seen: continue
    seen.add(key)
    data.append([c,office,district,party,cand,v])

# validate: county-sum vs Total row per (office,district,candidate)
csum=defaultdict(int); totrow={}
for c,o,d,p,cand,v in data:
    if c=='Total': totrow[(o,d,cand)]=v
    else: csum[(o,d,cand)]+=v
contests=defaultdict(set)
for (o,d,cand) in set(list(csum)+list(totrow)): contests[(o,d)].add(cand)
print(f"contests: {len(contests)}")
ok=0; bad=[]; notot=[]
for (o,d),cands in sorted(contests.items()):
    allok=True
    for cand in cands:
        cs=csum.get((o,d,cand),0); tr=totrow.get((o,d,cand))
        if tr is None: notot.append((o,d,cand)); allok=False
        elif cs!=tr: bad.append((o,d,cand,tr,cs)); allok=False
    if allok: ok+=1
print(f"contests reconciled (county-sum == Total): {ok}/{len(contests)}")
for o,d,cand,tr,cs in bad[:40]: print(f"  MISMATCH {o} d{d} {cand}: Total {tr} vs sum {cs} (Δ{cs-tr:+d})")
for o,d,cand in notot[:40]: print(f"  NO-TOTAL {o} d{d} {cand}")
# unknown counties
unk=sorted(set(c for c,*_ in data if c not in COUNTIES.values() and c!='Total'))
if unk: print("UNKNOWN COUNTY NAMES:", unk)

# write (drop Total rows)
out=[r for r in data if r[0]!='Total']
out.sort(key=lambda r:(r[1],r[2],r[0],r[4]))
Path(OUT).parent.mkdir(parents=True,exist_ok=True)
with open(OUT,'w',newline='') as f:
    w=csv.writer(f); w.writerow(['county','office','district','party','candidate','votes']); w.writerows(out)
print(f"wrote {len(out)} rows -> {OUT}")
print("offices:", sorted(set((r[1],r[2]) for r in out)))
