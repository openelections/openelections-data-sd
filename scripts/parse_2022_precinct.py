#!/usr/bin/env python3
"""Parse the SD 2022 general precinct canvass (clean digital PDF, one contest per page,
contests may span consecutive pages). Candidate identity per column is recovered by
matching the page's column totals to the already-parsed county-level totals -- this both
labels the columns and reconciles precinct<->county automatically. Local races not present
in the county file are collected separately for a header-parse fallback."""
import os, re, csv, sys
from pathlib import Path
from collections import defaultdict
from natural_pdf import PDF

# Repo root (this file lives in <repo>/scripts/). The source-PDF repo is expected as a
# sibling checkout; override with SD_SOURCES if it lives elsewhere.
REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO.parent / "openelections-sources-sd"))

PREC_PDF = str(SOURCES / "2022/general/2022PrecintCanvass.pdf")
COUNTY_CSV = str(REPO / "2022/20221108__sd__general__county.csv")
# Output goes to a staging dir, NOT the committed 2022/counties: re-running this digital
# parse would otherwise clobber Yankton (absent here) and the 8 Minnehaha legislative
# contests that were filled in from the scanned regional PDF (see parse_2022_mz.py).
OUTDIR = os.environ.get("SD_PRECINCT_OUT", "/tmp/sd_2022_precinct_staging")

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

INT_RE = re.compile(r'^[\d,]+$')
ORD = {"First":"1","Second":"2","Third":"3","Fourth":"4","Fifth":"5","Sixth":"6",
       "Seventh":"7","Eighth":"8","Ninth":"9"}

def split_row(line):
    toks=line.split(); nums=[]; i=len(toks)
    while i>0 and INT_RE.match(toks[i-1]):
        nums.append(int(toks[i-1].replace(",",""))); i-=1
    if not nums: return None
    nums.reverse(); return " ".join(toks[:i]), nums

def normalize_office(text):
    t=re.sub(r'\s+',' ',text).strip()
    if re.search(r'United States Senator',t): return "U.S. Senate",""
    if re.search(r'United States Representative',t): return "U.S. House","1"
    if re.search(r'Governor and Lieutenant Governor',t): return "Governor",""
    if re.search(r'Secretary of State',t): return "Secretary of State",""
    if re.search(r'Attorney General',t): return "Attorney General",""
    if re.search(r'State Auditor',t): return "State Auditor",""
    if re.search(r'State Treasurer',t): return "State Treasurer",""
    if re.search(r'Commissioner of School and Public Lands',t):
        return "Commissioner of School and Public Lands",""
    if re.search(r'Public Utilities Commissioner',t): return "Public Utilities Commissioner",""
    m=re.search(r'State Senator District (\w+)',t)
    if m: return "State Senate",m.group(1)
    m=re.search(r'State Representative District (\w+)',t)
    if m: return "State House",m.group(1)
    m=re.search(r'Judge of the Circuit Court,\s*(Position \w+ \w+ Circuit)',t)
    if m: return "Judge of the Circuit Court",m.group(1)
    if re.search(r'Supreme Court Justice Retention',t):
        dm=re.search(r'the (\w+) Supreme Court District',t)
        return "Supreme Court Retention",(ORD.get(dm.group(1),"") if dm else "")
    m=re.search(r'Constitutional Amendment ([A-Z])\b',t)
    if m: return f"Constitutional Amendment {m.group(1)}",""
    m=re.search(r'Initiated Measure (\d+)\b',t)
    if m: return f"Initiated Measure {m.group(1)}",""
    m=re.search(r'Referred Law (\d+)\b',t)
    if m: return f"Referred Law {m.group(1)}",""
    if re.search(r'James River Water Development District',t):
        return "James River Water Development District",""
    # tolerant fallback for headers wrapped mid-word ('State Representati ve District 26B')
    flat=re.sub(r'\s+','',t)
    m=re.search(r'StateSenatorDistrict(\d+[AB]?)', flat)
    if m: return "State Senate", m.group(1)
    m=re.search(r'StateRepresentativeDistrict(\d+[AB]?)', flat)
    if m: return "State House", m.group(1)
    return None  # unknown / local

def normalize_precinct(p):
    p=re.sub(r'^Precinct[\s\-_]+','',p,flags=re.I).strip()
    return p or "?"

# ---- load county totals: (office,district,county) -> [(candidate,party,total)] ----
cf=defaultdict(list)
with open(COUNTY_CSV) as f:
    for r in csv.DictReader(f):
        cf[(r['office'],r['district'],r['county'])].append(
            (r['candidate'],r['party'],int(r['votes'])))

def trailing_int_count(line):
    return len(split_row(line)[1]) if split_row(line) else 0

def split_row_n(line, ncol):
    """Take exactly ncol trailing integer tokens as votes; the rest is the precinct name."""
    toks=line.split()
    if len(toks)<ncol: return None
    vt=toks[-ncol:]
    if not all(INT_RE.match(t) for t in vt): return None
    name=" ".join(toks[:-ncol]).strip()
    return name, [int(t.replace(",","")) for t in vt]

def cluster(values, gap=8):
    """Cluster sorted scalar values; return list of cluster center floats."""
    vs=sorted(values); clusters=[]; cur=[vs[0]]
    for v in vs[1:]:
        if v-cur[-1]<=gap: cur.append(v)
        else: clusters.append(cur); cur=[v]
    clusters.append(cur)
    return [sum(c)/len(c) for c in clusters]

def extract_matrix(page):
    """Return (dlabels, rows). dlabels=[(x0,x1,district)] from header band.
    rows=[(name, [(x_center,value)])] with wrapped-name fragments merged by proximity."""
    words=list(page.words)
    dlabels=[]
    for w in words:
        if w.top<112:
            m=re.search(r'District (\d+\w?)', w.text)
            if m: dlabels.append((w.x0,w.x1,m.group(1))); continue
            # lettered districts (26A/26B/28A/28B) often split from their 'District' word
            m2=re.fullmatch(r'(\d+[AB])', w.text.strip())
            if m2: dlabels.append((w.x0,w.x1,m2.group(1)))
    pname_top=min((w.top for w in words if w.text.startswith('Precinct Name')), default=112)
    byrow={}
    for w in words:
        if w.top>pname_top: byrow.setdefault(round(w.top), []).append(w)
    valrows=[]; labrows=[]
    for top in sorted(byrow):
        ws=sorted(byrow[top], key=lambda w:w.x0)
        vals=[((w.x0+w.x1)/2,int(w.text.replace(',',''))) for w in ws if INT_RE.match(w.text)]
        lab=" ".join(w.text for w in ws if not INT_RE.match(w.text)).strip()
        if lab.lower()=='total': continue
        if vals: valrows.append([top,lab,vals])
        elif lab: labrows.append((top,lab))
    if not valrows: return dlabels, []
    # attach each orphan label row to the nearest value row (handles names above & below)
    name_frags={id(vr):[(vr[0],vr[1])] for vr in valrows}
    for ltop,lab in labrows:
        vr=min(valrows, key=lambda v:abs(v[0]-ltop))
        name_frags[id(vr)].append((ltop,lab))
    rows=[]
    for vr in valrows:
        frags=sorted(name_frags[id(vr)])
        nm=" ".join(f for _,f in frags if f).strip()
        rows.append((nm, vr[2]))
    return dlabels, rows

def resolve_matrix_page(county, office_base, dlabels, rows):
    """Order districts left-to-right by header label, then consume value columns
    left-to-right, giving each district its county-file candidate count. Returns (out, ok)."""
    if not rows or not dlabels: return [],False
    all_xc=[xc for _,vals in rows for xc,_ in vals]
    centers=sorted(cluster(all_xc, gap=10))
    # district order = label x0 (dedup, keep leftmost occurrence)
    seen={}
    for x0,x1,d in sorted(dlabels):
        if d not in seen: seen[d]=x0
    dorder=sorted(seen, key=lambda d:seen[d])
    colmap={}; idx=0
    for d in dorder:
        cands=cf.get((office_base,d,county))
        if not cands: return [],False
        for (cn,cp,ct) in cands:
            if idx>=len(centers): return [],False
            colmap[centers[idx]]=(cn,cp,d); idx+=1
    if idx!=len(centers): return [],False   # column count must match total candidates
    col_of=lambda xc: min(centers,key=lambda c:abs(c-xc))
    out=[]
    for prec,vals in rows:
        for xc,v in vals:
            cn,cp,d=colmap[col_of(xc)]
            out.append((normalize_precinct(prec),office_base,d,cn,cp,v))
    return out,True

pdf=PDF(PREC_PDF)
# ---- parse each page (defer int splitting until ncol is known) ----
pages=[]
matrix_pages=[]
for i,p in enumerate(pdf.pages):
    lines=[l.strip() for l in (p.extract_text() or '').splitlines() if l.strip()]
    county=None; office_text_lines=[]; rawrows=[]; total=None
    for l in lines:
        if l.endswith(' County'):
            cand=l[:-len(' County')].strip()
            if cand.lower() in COUNTIES: county=COUNTIES[cand.lower()]
            break
    seen_county=False
    for l in lines:
        if l.startswith('General Election'): continue
        if l.endswith(' County') and not seen_county: seen_county=True; continue
        if not seen_county: continue
        if l.startswith('Precinct Name'): continue
        if re.match(r'\d+ of \d+$', l): continue            # page footer
        r=split_row(l)
        if r:
            name,nums=r
            # office headers can end in a number ('State Senator District 21'); don't
            # mistake them for precinct data rows.
            if name.strip().lower()=='total': total=nums    # Total row -> reliable ncol
            elif re.search(r'District$', name.strip()): office_text_lines.append(l)
            else: rawrows.append(l)                          # candidate data row (split later)
        else:
            office_text_lines.append(l)
    office_join=' '.join(office_text_lines)
    # detect district labels from header geometry (top<112) -- robust to text-flow quirks
    hdr=" ".join(w.text for w in p.words if w.top<112)
    districts_here=set(re.findall(r'District (\d+\w?)', hdr))
    office_base=None
    if 'State Senator' in hdr: office_base='State Senate'
    elif 'State Representative' in hdr: office_base='State House'
    # matrix page: legislative with 2+ districts side by side -> resolve per page (geometry)
    if county and office_base and len(districts_here)>=2:
        dlabels,mrows=extract_matrix(p)
        matrix_pages.append({'i':i,'county':county,'office_base':office_base,
                             'districts':sorted(districts_here),'dlabels':dlabels,'rows':mrows})
        continue
    office=normalize_office(office_join) if office_text_lines else None
    pages.append({'i':i,'county':county,'office':office,
                  'raw_office':office_join,'rawrows':rawrows,'total':total})

# ---- merge consecutive pages with same (county, office) ----
merged={}  # (county,office,district) -> {'rawrows':[...], 'total':...}
order=[]
for pg in pages:
    if pg['county'] is None or pg['office'] is None:
        continue
    office,district=pg['office']
    key=(pg['county'],office,district)
    if key not in merged:
        merged[key]={'rawrows':[], 'total':None}; order.append(key)
    merged[key]['rawrows'].extend(pg['rawrows'])
    if pg['total'] is not None: merged[key]['total']=pg['total']

# ---- assign candidates via county-total matching, build output ----
out_by_county=defaultdict(list)
unmatched=[]; recon_fail=[]; rowparse_fail=[]
for key in order:
    county,office,district=key
    m=merged[key]; total=m['total']
    cands=cf.get((office,district,county))
    # determine column count: prefer Total row, else county-file candidate count
    if total is not None: ncol=len(total)
    elif cands: ncol=len(cands)
    else:
        from collections import Counter as _C
        ncol=_C(trailing_int_count(l) for l in m['rawrows']).most_common(1)[0][0]
    rows=[]
    for l in m['rawrows']:
        rn=split_row_n(l,ncol)
        if rn is None: rowparse_fail.append((key,l)); continue
        rows.append(rn)
    if not rows: continue
    if not cands or len(cands)!=ncol:
        unmatched.append((key,ncol,len(cands) if cands else 0)); continue
    # match columns to candidates by total value
    colsum=[0]*ncol
    okcols=True
    for prec,nums in rows:
        if len(nums)!=ncol: okcols=False; continue
        for k in range(ncol): colsum[k]+=nums[k]
    # map each column index -> candidate by matching colsum to cand total (greedy unique)
    used=[False]*len(cands); mapping=[None]*ncol
    for k in range(ncol):
        for ci,(cn,cp,ct) in enumerate(cands):
            if not used[ci] and ct==colsum[k]:
                mapping[k]=(cn,cp); used[ci]=True; break
    if any(mp is None for mp in mapping):
        # fallback: assign by order
        mapping=[(c[0],c[1]) for c in cands]
        recon_fail.append((key,colsum,[c[2] for c in cands]))
    for prec,nums in rows:
        if len(nums)!=ncol: continue
        for k,(cn,cp) in enumerate(mapping):
            out_by_county[county].append([county,normalize_precinct(prec),office,district,cn,cp,nums[k]])

# ---- resolve matrix pages per page (geometry); emit every resolved page ----
matrix_ok=0; matrix_pagefail=[]
for mp in matrix_pages:
    res,ok=resolve_matrix_page(mp['county'],mp['office_base'],mp['dlabels'],mp['rows'])
    if ok:
        matrix_ok+=1
        for prec,office,district,cn,cp,v in res:
            out_by_county[mp['county']].append([mp['county'],prec,office,district,cn,cp,v])
    else:
        matrix_pagefail.append((mp['i'],mp['county'],mp['office_base'],mp['districts']))

# ---- final validation: drop any (county,office,district) whose precinct sums don't match
# the county totals (keeps output 100% reconciled; partially-parsed matrix contests removed)
psum=defaultdict(int)
for county,rows in out_by_county.items():
    for r in rows:
        psum[(r[0],r[2],r[3],r[4],r[5])]+=r[6]   # county,office,district,candidate,party
drop=set()  # (county,office,district)
contests_seen=set((r[0],r[2],r[3]) for rows in out_by_county.values() for r in rows)
for (county,office,district) in contests_seen:
    expected=cf.get((office,district,county))
    if not expected: continue
    ok=all(psum.get((county,office,district,cn,cp))==ct for cn,cp,ct in expected)
    if not ok: drop.add((county,office,district))
dropped_rows=0
for county in list(out_by_county):
    kept=[r for r in out_by_county[county] if (r[0],r[2],r[3]) not in drop]
    dropped_rows+=len(out_by_county[county])-len(kept)
    out_by_county[county]=kept

# ---- write per-county CSVs ----
import os
os.makedirs(OUTDIR,exist_ok=True)
def slug(c): return c.lower().replace(' ','_')
for county,rows in out_by_county.items():
    with open(f"{OUTDIR}/20221108__sd__general__{slug(county)}__precinct.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow(["county","precinct","office","district","candidate","party","votes"]); w.writerows(rows)

print(f"pages: {len(pages)}   merged contests: {len(merged)}   counties out: {len(out_by_county)}")
print(f"output rows: {sum(len(v) for v in out_by_county.values())}")
print(f"matrix pages OK: {matrix_ok}   page-fail: {len(matrix_pagefail)}   dropped (unreconciled) contests: {len(drop)} ({dropped_rows} rows)")
for x in sorted(drop)[:30]: print("   DROP",x)
print(f"\nUNMATCHED (not in county file / col mismatch): {len(unmatched)}")
from collections import Counter
uc=Counter()
for (key,nc,have) in unmatched:
    uc[key[1]]+=1
for o,n in uc.most_common(): print(f"   {n:4d}  {o}")
print(f"\nRECON FAIL (col totals != county cand totals): {len(recon_fail)}")
for key,colsum,ctot in recon_fail[:20]: print("  ",key,"colsum",colsum,"cand",ctot)
