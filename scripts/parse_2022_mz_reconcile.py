#!/usr/bin/env python3
"""Normalize MZ vision-LLM rows, reconcile against county totals, write/merge precinct CSV."""
import os, re, json, csv, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache"))
COUNTY_CSV=str(REPO / "2022/20221108__sd__general__county.csv")
ORD={"First":"1","Second":"2","Third":"3","Fourth":"4","Fifth":"5","Sixth":"6",
     "Seventh":"7","Eighth":"8","Ninth":"9"}

def normalize_office(text):
    t=re.sub(r'\s+',' ',text).strip()
    if re.search(r'United States Senator|U\.?S\.? Senate',t,re.I): return "U.S. Senate",""
    if re.search(r'United States Representative|U\.?S\.? House',t,re.I): return "U.S. House","1"
    if re.search(r'Governor',t,re.I): return "Governor",""
    if re.search(r'Secretary of State',t,re.I): return "Secretary of State",""
    if re.search(r'Attorney General',t,re.I): return "Attorney General",""
    if re.search(r'State Auditor',t,re.I): return "State Auditor",""
    if re.search(r'State Treasurer',t,re.I): return "State Treasurer",""
    if re.search(r'Commissioner of School',t,re.I): return "Commissioner of School and Public Lands",""
    if re.search(r'Public Utilities',t,re.I): return "Public Utilities Commissioner",""
    m=re.search(r'Senator.*?District (\d+\w?)',t,re.I) or re.search(r'State Senate.*?(\d+\w?)',t,re.I)
    if m and re.search(r'senat',t,re.I): return "State Senate",m.group(1)
    m=re.search(r'Represent\w*.*?District (\d+\w?)',t,re.I)
    if m: return "State House",m.group(1)
    m=re.search(r'Judge of the Circuit Court,?\s*(Position \w+ \w+ Circuit)',t,re.I)
    if m: return "Judge of the Circuit Court",m.group(1)
    if re.search(r'Supreme Court.*Retention|Retention.*Justice',t,re.I):
        dm=re.search(r'(\w+) Supreme Court District',t)
        return "Supreme Court Retention",(ORD.get(dm.group(1),"") if dm else "")
    m=re.search(r'Constitutional Amendment ([A-Z])\b',t,re.I)
    if m: return f"Constitutional Amendment {m.group(1).upper()}",""
    m=re.search(r'Initiated Measure (\d+)',t,re.I)
    if m: return f"Initiated Measure {m.group(1)}",""
    if re.search(r'James River Water',t,re.I): return "James River Water Development District",""
    return t,""

def nprec(p):
    p=re.sub(r'^Precinct[\s\-_]+','',str(p),flags=re.I).strip()
    return p or "?"

# county totals
cf=defaultdict(list)
for r in csv.DictReader(open(COUNTY_CSV)):
    cf[(r['county'],r['office'],r['district'])].append((r['candidate'],r['party'],int(r['votes'])))

target=sys.argv[1]
county=target.capitalize()
rows=json.load(open(CACHE/f"mz_{target}_rows.json"))
# normalize + dedupe
norm=[]
seen=set()
for r in rows:
    office,district=normalize_office(r.get('office',''))
    key=(county,nprec(r.get('precinct','')),office,district,
         str(r.get('candidate','')).strip(),str(r.get('party','')).strip().upper())
    if key in seen: continue
    seen.add(key)
    try: v=int(str(r.get('votes',0)).replace(',','').strip() or 0)
    except: v=0
    norm.append([county,nprec(r.get('precinct','')),office,district,
                 str(r.get('candidate','')).strip(),str(r.get('party','')).strip().upper(),v])

# reconcile by contest-total (county,office,district)
psum=defaultdict(int)
for c,p,o,d,cand,pty,v in norm: psum[(c,o,d)]+=v
print(f"{target}: {len(norm)} rows, {len(set((o,d) for _,_,o,d,_,_,_ in norm))} contests")
ok=0; bad=[]
contests=set((o,d) for _,_,o,d,_,_,_ in norm)
for (o,d) in sorted(contests):
    ct=sum(t for _,_,t in cf.get((county,o,d),[]))
    ps=psum[(county,o,d)]
    if cf.get((county,o,d)) and ct==ps: ok+=1
    else: bad.append((o,d,ct,ps))
print(f"  contest-total reconciled: {ok}/{len(contests)}")
for o,d,ct,ps in bad[:40]:
    print(f"   MISMATCH {o} d{d}: county {ct} vs precinct {ps} (Δ{ps-ct:+d})")
# save normalized
json.dump(norm, open(CACHE/f"mz_{target}_norm.json","w"))
