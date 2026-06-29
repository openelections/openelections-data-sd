#!/usr/bin/env python3
"""Build 2014 primary/general county CSVs from per-page vision-LLM caches.
Cross-read arbitration: each results page may have several model reads; for each contest
keep whichever read's county sums match the printed Total row. Drop contests no read
reconciles, so the output is 100% Total-validated. Reports included/dropped per file."""
import os, re, json, csv
from collections import defaultdict
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
CACHE=Path(os.environ.get("SD_CACHE", Path.home()/"sd_cache"))
PARTY_BY_PAGE={4:"REP",5:"DEM",6:"REP"}

COUNTIES={c.lower():c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Shannon","Spink","Stanley","Sully","Todd","Tripp","Turner",
 "Union","Walworth","Yankton","Ziebach"]}
ALIAS={"beadie":"Beadle","duel":"Deuel","oglala":"Oglala Lakota","shanon":"Shannon"}
PARTYMAP={"REPUBLICAN":"REP","DEMOCRAT":"DEM","DEMOCRATIC":"DEM","REP":"REP","DEM":"DEM",
          "LIBERTARIAN":"LIB","LIB":"LIB","INDEPENDENT":"IND","IND":"IND","CONSTITUTION":"CON",
          "CONSTITUTION PARTY":"CON","CON":"CON","NONPARTISAN":"","NPA":"NPA","":"",
          "GREEN":"GRN","GRN":"GRN",
          "R":"REP","D":"DEM","L":"LIB","I":"IND","C":"CON","G":"GRN"}

def gi(v):
    s=re.sub(r'[^0-9]','',str(v)); return int(s) if s else 0
def norm_party(p): return PARTYMAP.get(str(p).strip().upper(), str(p).strip().upper())
def cty(name):
    n=str(name).strip()
    if n.lower() in ('total','totals'): return 'Total'
    if n.lower() in ALIAS: return ALIAS[n.lower()]
    return COUNTIES.get(n.lower(), n)
def norm_district(d):
    d=str(d).strip().upper(); return d.zfill(2) if d.isdigit() else d
def norm_office(t):
    t=re.sub(r'\s+',' ',str(t)).strip(); tl=t.lower()
    if 'district' in tl and ('senat' in tl or 'repres' in tl or 'house' in tl) and 'united states' not in tl:
        m=re.search(r'district\s*(\d+[ab]?)',tl); d=norm_district(m.group(1)) if m else ""
        return ("State Senate" if 'senat' in tl else "State House"), d
    if re.search(r'united states senat',tl): return "U.S. Senate",""
    if re.search(r'united states (house|repres)|representative in congress|u\.?s\.? house|u\.?s\.? repres',tl): return "U.S. House","1"
    if 'lieutenant' in tl or re.search(r'\bgovernor\b',tl): return "Governor",""
    if 'attorney general' in tl: return "Attorney General",""
    if 'auditor' in tl: return "State Auditor",""
    if 'treasurer' in tl: return "State Treasurer",""
    if 'school and public lands' in tl: return "Commissioner of School and Public Lands",""
    if 'public utilities' in tl: return "Public Utilities Commissioner",""
    if 'supreme court' in tl: return "Supreme Court Retention",""
    if 'circuit court' in tl or 'circut court' in tl:
        d=t.split(',',1)[1].strip() if ',' in t else ""
        return "Judge of the Circuit Court", d
    m=re.search(r'constitutional amendment\s*([a-z])',tl)
    if m: return f"Constitutional Amendment {m.group(1).upper()}",""
    m=re.search(r'initiated measure\s*(\d+)',tl)
    if m: return f"Initiated Measure {m.group(1)}",""
    m=re.search(r'referred law\s*(\d+)',tl)
    if m: return f"Referred Law {m.group(1)}",""
    return t,""

def normalize(raw, page, is_primary):
    """raw cache rows -> normalized [county,office,district,party,candidate,votes] (Total kept)."""
    out=[]
    for r in raw:
        if 'change of county name' in str(r.get('office','')).lower(): continue
        office,district=norm_office(r.get('office',''))
        c=cty(r.get('county',''))
        cand=str(r.get('candidate','')).strip()
        party=PARTY_BY_PAGE.get(page,"") if is_primary else norm_party(r.get('party',''))
        if office.startswith(('Constitutional Amendment','Initiated Measure','Referred Law',
                              'Supreme Court Retention')) or cand.lower() in ('yes','no'):
            party=""
        out.append([c,office,district,party,cand,gi(r.get('votes',0))])
    return out

def reconciles(rows):
    """rows for one contest (incl Total). True iff every candidate's county-sum == its Total."""
    cs=defaultdict(int); tot={}
    for c,o,d,p,cand,v in rows:
        if c=='Total': tot[(cand,p)]=v
        else: cs[(cand,p)]+=v
    if not tot: return False
    keys=set(cs)|set(tot)
    return all(tot.get(k) is not None and cs.get(k,0)==tot.get(k) for k in keys)

def merge_reconcile(versions):
    """Cell-level arbitration across multiple reads of one contest. Where reads agree on a
    (candidate,county) value, trust it; at disagreeing cells pick values that make every
    candidate's county-sum equal its Total. Returns merged county rows, or None."""
    # collect Total per (cand,party) by majority; collect per-cell value sets
    tot_votes=defaultdict(list); cell=defaultdict(lambda: defaultdict(set)); meta={}
    counties=defaultdict(set)
    for v in versions:
        for c,o,d,p,cand,vv in v:
            meta[(cand,p)]=(o,d)
            if c=='Total': tot_votes[(cand,p)].append(vv)
            else: cell[(cand,p)][c].add(vv); counties[(cand,p)].add(c)
    if not tot_votes: return None
    tot={k: max(set(vs),key=vs.count) for k,vs in tot_votes.items()}
    out=[]
    for k in tot:
        cand,p=k; o,d=meta[k]
        fixed={}; ambig={}
        for c in sorted(counties[k]):           # sorted -> deterministic
            vals=cell[k][c]
            if len(vals)==1: fixed[c]=next(iter(vals))
            else: ambig[c]=sorted(vals)
        need=tot[k]-sum(fixed.values())
        if not ambig:
            if need!=0: return None
        else:
            # accept only a UNIQUE assignment of ambiguous cells that hits the total;
            # if zero or multiple combinations work, the merge is not determined -> reject.
            import itertools
            keys=sorted(ambig)
            if len(keys)>14: return None          # avoid 2^N blow-up; too ambiguous anyway
            sols=[combo for combo in itertools.product(*[ambig[c] for c in keys])
                  if sum(combo)==need]
            if len(sols)!=1: return None
            fixed.update(dict(zip(keys,sols[0])))
        for c,vv in fixed.items(): out.append([c,o,d,p,cand,vv])
    return out

def cross_read_agree(versions):
    """If >=2 reads agree on every county cell (same candidates, same per-county votes),
    return those county rows (Total-independent corroboration). Else None."""
    if len(versions)<2: return None
    def cellmap(v):
        m={}
        for c,o,d,p,cand,vv in v:
            if c!='Total': m[(cand,p,c)]=vv
        return m
    maps=[cellmap(v) for v in versions]
    for i in range(len(maps)):
        for j in range(i+1,len(maps)):
            if maps[i] and maps[i]==maps[j]:
                v=versions[i]
                return [[c,o,d,p,cand,vv] for c,o,d,p,cand,vv in v if c!='Total']
    return None

def build(pages, is_primary, date, etype):
    chosen=[]; dropped=[]; total_contests=set(); agreed=[]
    for page in pages:
        reads=[]
        for f in sorted(CACHE.glob(f"y2014_*_page{page}.json")):
            try: reads.append(normalize(json.load(open(f)), page, is_primary))
            except Exception: pass
        # group each read by contest
        versions=defaultdict(list)
        for rd in reads:
            bc=defaultdict(list)
            for row in rd: bc[(row[1],row[2])].append(row)
            for k,v in bc.items(): versions[k].append(v)
        for k,vlist in versions.items():
            total_contests.add(k)
            pick=next((v for v in vlist if reconciles(v)), None)
            if pick is not None:
                chosen+=[r for r in pick if r[0]!='Total']
            else:
                merged=merge_reconcile(vlist) if len(vlist)>1 else None
                if merged is not None:
                    chosen+=merged
                else:
                    # cross-read agreement is high-confidence but NOT total-validated;
                    # report it for manual review, keep it OUT of the committed file.
                    ag=cross_read_agree(vlist)
                    if ag is not None: agreed.append(k)
                    else: dropped.append(k)
    # dedupe and write
    seen=set(); out=[]
    for r in chosen:
        key=tuple(r[:5])
        if key in seen: continue
        seen.add(key); out.append(r)
    out.sort(key=lambda r:(r[1],r[2],r[0],r[4]))
    fn=REPO/f"2014/{date}__sd__{etype}__county.csv"
    fn.parent.mkdir(parents=True,exist_ok=True)
    with open(fn,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['county','office','district','party','candidate','votes']); w.writerows(out)
    nrec=len(total_contests)-len(dropped)-len(agreed)
    print(f"=== {etype} ({date}): {len(out)} rows | contests {len(total_contests)}: "
          f"Total-validated {nrec}, cross-read-agreed {len(agreed)}, dropped {len(dropped)} -> {fn.name}")
    for o,d in sorted(agreed): print(f"     AGREED(no total match) {o} {('d'+d) if d else ''}")
    for o,d in sorted(dropped): print(f"     DROP {o} {('d'+d) if d else ''}")
    unk=sorted(set(r[0] for r in out if r[0] not in COUNTIES.values()))
    if unk: print("   UNKNOWN COUNTIES:",unk)

build([4,5,6], True, "20140603", "primary")
build([9,10,11,12,13,14,15,16,17,18,19,20,21,23,24], False, "20141104", "general")
