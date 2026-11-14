#!/usr/bin/env python3
"""Build the SD 2018 general county-level file from the vision-transcribed
state canvass (scripts/2018_canvass_data.py).

Validations:
  1. Every contest's per-candidate county sum must equal the printed Total row.
  2. Statewide offices (and any matching legislature rows) are cross-checked
     per county against the independent partial build in
     2018/counties/20181106__sd__general__county.csv.

Writes 2018/20181106__sd__general__county.csv (CRLF, repo convention).
"""
import csv
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "canvass_data_2018", Path(__file__).resolve().parent / "2018_canvass_data.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ALL_CONTESTS = _mod.ALL_CONTESTS

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "2018" / "20181106__sd__general__county.csv"
CROSS = REPO / "2018" / "counties" / "20181106__sd__general__county.csv"


def col_sums(rows, ncand):
    sums = [0] * ncand
    for _, vals in rows:
        for i, v in enumerate(vals):
            sums[i] += v
    return sums


def main():
    failures = []

    # --- validation 1: county sums vs printed totals ---
    for office, dist, cands, rows, totals in ALL_CONTESTS:
        sums = col_sums(rows, len(cands))
        for i, (s, t) in enumerate(zip(sums, totals)):
            if s != t:
                failures.append(
                    f"TOTAL {office} d{dist} {cands[i][0]}: sum={s} printed={t} "
                    f"(diff {s - t})")
        if len(rows) != len({c for c, _ in rows}):
            failures.append(f"DUPLICATE COUNTY rows in {office} d{dist}")
        if len(sum((vals for _, vals in rows), start=[])) and any(
                len(vals) != len(cands) for _, vals in rows):
            failures.append(f"ROW LEN mismatch in {office} d{dist}")

    # --- validation 2: cross-check against the independent partial build ---
    cross = defaultdict(dict)  # (county, office, dist, cand) -> votes sum
    with open(CROSS, newline="") as f:
        for r in csv.DictReader(f):
            key = (r["county"], r["office"], r["district"], r["candidate"])
            cross[key][r["party"]] = cross[key].get(r["party"], 0) + int(r["votes"])
    cross_diffs = []
    for office, dist, cands, rows, _ in ALL_CONTESTS:
        county_map = dict(rows)
        for i, (cand, party) in enumerate(cands):
            if office in ("U.S. House",):
                variants = {cand: 1, 'Dustin "Dusty" Johnson': 1} \
                    if cand.startswith('Dustin') else {cand: 1}
            else:
                variants = {cand: 1}
            for (xcounty, xoffice, xdist, xcand), parties in cross.items():
                if xoffice != office or xdist != dist:
                    continue
                if district_differs(dist, xdist):
                    continue
                if xcand not in variants:
                    continue
                if xcounty not in county_map:
                    continue
                xv = parties.get(party, sum(parties.values()))
                mv = county_map[xcounty][i]
                if xv != mv:
                    cross_diffs.append(
                        f"CELL {office} d{dist} {cand}: {xcounty} canvass={mv} county-file={xv}")

    print(f"Contests: {len(ALL_CONTESTS)}")
    print(f"Total-mismatch failures: {len(failures)}")
    for x in failures:
        print("  !", x)
    print(f"Cell cross-check diffs: {len(cross_diffs)}")
    for x in cross_diffs:
        print("  -", x)

    if failures:
        print("\nNOT writing CSV until totals reconcile.")
        return 1

    # --- write CSV ---
    rows_out = []
    for office, dist, cands, rows, _ in ALL_CONTESTS:
        for county, vals in rows:
            for (cand, party), v in zip(cands, vals):
                rows_out.append([county, office, dist, party, cand, v])
    rows_out.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["county", "office", "district", "party", "candidate", "votes"])
        w.writerows(rows_out)
    counties = {r[0] for r in rows_out}
    print(f"\nWrote {OUT}: {len(rows_out)} rows, {len(counties)} counties")


def district_differs(a, b):
    """District strings only need to match loosely (statewide = '')."""
    if not a or not b:
        return False
    return str(a).upper() != str(b).upper()


if __name__ == "__main__":
    sys.exit(main())
