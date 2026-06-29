#!/usr/bin/env python3
"""Per-contest diagnostic for the 2014 contests that did NOT auto-reconcile to the printed
Total. For each, shows each candidate's printed Total vs each model read's county-sum (and the
gap), and lists the counties where the reads disagree (the likely misread sites) so the values
can be verified quickly against the page images."""
import os, re, json
from collections import defaultdict
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("b2014", HERE/"build_2014.py")
B=importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
CACHE=B.CACHE

def reads_for(page, is_primary):
    out=[]
    for f in sorted(CACHE.glob(f"y2014_*_page{page}.json")):
        try: out.append((f.name.split('_page')[0], B.normalize(json.load(open(f)), page, is_primary)))
        except Exception: pass
    return out

def report(pages, is_primary, label):
    print(f"\n########## {label} ##########")
    for page in pages:
        reads=reads_for(page, is_primary)
        # contests on this page
        contests=defaultdict(lambda: defaultdict(list))  # (o,d) -> model -> rows
        for model,rd in reads:
            for r in rd: contests[(r[1],r[2])][model].append(r)
        for (o,d),bymodel in sorted(contests.items()):
            versions=list(bymodel.values())
            if any(B.reconciles(v) for v in versions): continue       # ok
            if B.merge_reconcile(versions) is not None: continue       # recovered by unique cell-merge
            agreed = B.cross_read_agree(versions) is not None
            tag = "CROSS-READ AGREES (off printed total)" if agreed else "NEEDS REVIEW"
            print(f"\n  [{tag}] p{page}  {o} {('d'+d) if d else ''}")
            # per candidate: printed total + each read's sum
            cands=sorted({(r[4],r[3]) for v in versions for r in v if r[0]!='Total'})
            for cand,party in cands:
                tots=[r[5] for v in versions for r in v if r[0]=='Total' and (r[4],r[3])==(cand,party)]
                printed = max(set(tots), key=tots.count) if tots else None
                sums=[sum(r[5] for r in v if r[0]!='Total' and (r[4],r[3])==(cand,party)) for v in bymodel.values()]
                deltas=", ".join(f"{m}:{s}({s-printed:+d})" if printed is not None else f"{m}:{s}"
                                 for m,s in zip(bymodel,sums))
                print(f"      {cand} [{party or '-'}]  printed_total={printed}  read_sums: {deltas}")
            # disagreeing counties
            if len(versions)>=2:
                cellmaps=[{(r[4],r[3],r[0]):r[5] for r in v if r[0]!='Total'} for v in versions]
                allkeys=set().union(*cellmaps)
                diffs=[(k,[cm.get(k) for cm in cellmaps]) for k in sorted(allkeys)
                       if len({cm.get(k) for cm in cellmaps})>1]
                if diffs:
                    print(f"      disagreeing cells (candidate/party/county -> reads): {len(diffs)}")
                    for (cand,party,county),vals in diffs[:8]:
                        print(f"         {county} {cand}[{party or '-'}]: {vals}")

report([4,5,6], True, "PRIMARY (20140603)")
report([9,10,11,12,13,14,15,16,17,18,19,20,21,23,24], False, "GENERAL (20141104)")
