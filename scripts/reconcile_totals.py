#!/usr/bin/env python3
"""
Reconcile precinct-level results against the statewide county-totals canvass.

This is the independent accuracy check for a full parse: the sum of every precinct's
votes in a county must equal that county's figure in the separately-parsed county-totals
canvass (a different PDF). Because the two are parsed independently, candidate names can
differ slightly, so the comparison is done at two naming-robust levels:

  - Contest totals: votes summed per (county, office, district). Catches any net
    discrepancy regardless of candidate labels.
  - Party totals: votes summed per (county, office, district, party). Catches issues
    within a contest (e.g. a candidate's votes attributed to the wrong row) without
    depending on exact candidate spelling. Ballot measures carry no party, so for those
    only the contest-total level applies.

A county whose contest and party totals all agree is strong evidence the precinct parse
is both complete and accurate for that county. Disagreements point precisely at the
county/office to re-check.

Usage:
    uv run scripts/reconcile_totals.py \
        --precinct-dir /tmp/sd_2024_staging \
        --county-totals /tmp/sd_2024_staging/20241105__sd__general__county.csv
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def to_int(value) -> int:
    return int(str(value).replace(",", "").strip() or 0)


def load(path: Path) -> list:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def sum_by(rows: list, keyfn) -> dict:
    out: dict = defaultdict(int)
    for r in rows:
        out[keyfn(r)] += to_int(r["votes"])
    return out


def _contest(r: dict) -> tuple:
    return (r["county"].strip(), r["office"].strip(), r["district"].strip())


def _party(r: dict) -> tuple:
    return (*_contest(r), r["party"].strip().upper())


def compare(precinct_sums: dict, total_sums: dict, tolerance: int):
    """Return (agree, discrepancies, missing) over keys present in the totals side."""
    agree, discrepancies, missing = [], [], []
    for key, tv in total_sums.items():
        if key not in precinct_sums:
            missing.append((key, tv))
        elif abs(precinct_sums[key] - tv) > tolerance:
            discrepancies.append((key, tv, precinct_sums[key]))
        else:
            agree.append(key)
    return agree, discrepancies, missing


def main():
    ap = argparse.ArgumentParser(description="Reconcile precinct sums vs county totals")
    ap.add_argument("--precinct-dir", required=True,
                    help="Directory of per-county *__precinct.csv files")
    ap.add_argument("--county-totals", required=True,
                    help="The statewide county-level CSV")
    ap.add_argument("--show", type=int, default=12,
                    help="Max discrepancies to print per section (default: 12)")
    ap.add_argument("--tolerance", type=int, default=0,
                    help="Allowed absolute vote difference before flagging (default: 0)")
    args = ap.parse_args()

    prec_rows = []
    for p in sorted(Path(args.precinct_dir).glob("*__precinct.csv")):
        prec_rows.extend(load(p))
    if not prec_rows:
        ap.error(f"No *__precinct.csv files in {args.precinct_dir}")
    total_rows = load(Path(args.county_totals))

    p_contest = sum_by(prec_rows, _contest)
    t_contest = sum_by(total_rows, _contest)
    p_party = sum_by(prec_rows, _party)
    t_party = sum_by(total_rows, _party)

    c_agree, c_bad, c_missing = compare(p_contest, t_contest, args.tolerance)
    p_agree, p_bad, _ = compare(p_party, t_party, args.tolerance)

    # Counties the totals cover but the precinct parse hasn't produced at all.
    total_counties = {k[0] for k in t_contest}
    prec_counties = {k[0] for k in p_contest}
    uncovered = sorted(total_counties - prec_counties)

    def pct(n, d):
        return 100.0 * n / d if d else 0.0

    print(f"Precinct files: {len(list(Path(args.precinct_dir).glob('*__precinct.csv')))}"
          f"   counties in totals: {len(total_counties)}")
    if uncovered:
        print(f"\nNOT YET PARSED ({len(uncovered)} counties with no precinct data): "
              f"{', '.join(uncovered)}")

    print(f"\nContest totals:  {len(c_agree)}/{len(t_contest)} agree "
          f"({pct(len(c_agree), len(t_contest)):.1f}%)   "
          f"{len(c_bad)} mismatched, {len(c_missing)} missing on precinct side")
    for (county, office, dist), tv, pv in sorted(c_bad)[:args.show]:
        d = f" d{dist}" if dist else ""
        print(f"    {county} / {office}{d}: county-total {tv} != precinct-sum {pv} "
              f"(Δ{pv - tv:+d})")
    if c_missing:
        print(f"  missing contests (in totals, absent from precincts):")
        for (county, office, dist), tv in sorted(c_missing)[:args.show]:
            d = f" d{dist}" if dist else ""
            print(f"    {county} / {office}{d}: county-total {tv}, no precinct rows")

    print(f"\nParty totals:    {len(p_agree)}/{len(t_party)} agree "
          f"({pct(len(p_agree), len(t_party)):.1f}%)   {len(p_bad)} mismatched")
    for (county, office, dist, party), tv, pv in sorted(p_bad)[:args.show]:
        d = f" d{dist}" if dist else ""
        print(f"    {county} / {office}{d} [{party or '-'}]: "
              f"county-total {tv} != precinct-sum {pv} (Δ{pv - tv:+d})")

    clean = sorted(c for c in prec_counties
                   if not any(b[0][0] == c for b in c_bad)
                   and not any(b[0][0] == c for b in p_bad)
                   and not any(m[0][0] == c for m in c_missing))
    print(f"\nFully reconciled counties: {len(clean)}/{len(prec_counties)} parsed")


if __name__ == "__main__":
    main()
