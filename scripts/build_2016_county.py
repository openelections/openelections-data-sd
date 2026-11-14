#!/usr/bin/env python3
"""Build the SD 2016 general county-level file from the vision-transcribed
state canvass (scripts/2016_canvass_data.py).

Validations:
  1. Every contest's per-candidate county sum must equal the printed Total row.
  2. Cells cross-checked against the independent partial precinct build
     2016/20161108__sd__general__precinct.csv (where offices overlap), using
     normalized candidate names.

Writes 2016/20161108__sd__general__county.csv (CRLF, repo convention).
"""
import csv
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "canvass_data_2016", Path(__file__).resolve().parent / "2016_canvass_data.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ALL_CONTESTS = _mod.ALL_CONTESTS
TOTAL_EXCEPTIONS = _mod.TOTAL_EXCEPTIONS

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "2016" / "20161108__sd__general__county.csv"
PRECINCT = REPO / "2016" / "20161108__sd__general__precinct.csv"

# precinct-file office string -> my office
PREC_OFFICE = {
    "u.s. house": "U.S. House", "u.s house": "U.S. House",
    "u.s. senate": "U.S. Senate", "u.s senate": "U.S. Senate",
    "president": "President",
    "state senate": "State Senate", "state house": "State House",
    "public utilities commissioner": "Public Utilities Commissioner",
}


def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


# known spelling variants in the precinct file
ALIASES = {
    norm("Donald Trump"): norm("Donald J. Trump"),
    norm("Hillary Clinton"): norm("Hillary Clinton"),
}


def main():
    failures = []
    for office, dist, cands, rows, totals in ALL_CONTESTS:
        sums = [0] * len(cands)
        for _, vals in rows:
            for i, v in enumerate(vals):
                sums[i] += v
        for i, (s, t) in enumerate(zip(sums, totals)):
            if s != t and (office, dist, cands[i][0]) not in TOTAL_EXCEPTIONS:
                failures.append(
                    f"TOTAL {office} d{dist} {cands[i][0]}: sum={s} printed={t} (diff {s - t})")
        if any(len(vals) != len(cands) for _, vals in rows):
            failures.append(f"ROW LEN mismatch in {office} d{dist}")
        if len(rows) != len({c for c, _ in rows}):
            failures.append(f"DUPLICATE COUNTY rows in {office} d{dist}")

    # --- cross-check against precinct file ---
    pfs = defaultdict(int)  # (office, dist, candnorm, county, party) -> sum
    with open(PRECINCT, newline="") as f:
        for r in csv.DictReader(f):
            if r["precinct"].strip().lower() in ("total", "totals"):
                continue  # county total rows duplicate the precinct rows
            off = PREC_OFFICE.get(r["office"].strip().lower())
            if not off:
                continue
            cand = ALIASES.get(norm(r["candidate"]), norm(r["candidate"]))
            try:
                v = int(r["votes"])
            except (ValueError, TypeError):
                continue
            key = (off, (r["district"] or "").strip(), cand, r["county"], r["party"].upper())
            pfs[key] = pfs.get(key, 0) + v

    cross_diffs = []
    for office, dist, cands, rows, _ in ALL_CONTESTS:
        county_map = dict(rows)
        for i, (cand, party) in enumerate(cands):
            key = (office, str(dist), norm(cand))
            for (xoff, xdist, xcand, xcounty, xparty), xv in sorted(pfs.items()):
                if xoff != office or norm(xdist) != norm(str(dist)) or xcand != key[2]:
                    continue
                if xcounty not in county_map:
                    continue
                if xparty != party and not xparty.startswith(party):  # 'Rep' vs 'REP'
                    continue
                if xv != county_map[xcounty][i]:
                    cross_diffs.append(
                        f"CELL {office} d{dist} {cand}[{party}]: {xcounty} canvass={county_map[xcounty][i]} precinct={xv}")
    seen = set()
    cross_diffs = [d for d in cross_diffs if not (d in seen or seen.add(d))]

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
