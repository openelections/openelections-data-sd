#!/usr/bin/env python3
"""
Evaluate parsed canvass CSVs against committed ground-truth CSVs.

Compares a directory of freshly parsed per-county precinct CSVs (e.g. the output of
parse_2024_canvass.py for a candidate model) against a directory of trusted CSVs,
matching files by name. Two complementary scores are reported per county and overall:

  - Row match: exact (precinct, office, district, candidate, party, votes) agreement.
    Strict; sensitive to candidate-label formatting (e.g. "Yes" vs "Justice - Yes").
  - Contest reconciliation: votes summed per (precinct, office, district) compared to
    truth. Robust to candidate-label differences, so it isolates real number errors -
    the way election results are normally validated.

Use it to rank models on the same pages (the parser's model-aware cache lets several
models write side by side), or to sanity-check a pipeline change against known output.

Usage:
    uv run scripts/eval_canvass.py --pred-dir /tmp/sd_smoke/out
    uv run scripts/eval_canvass.py --pred-dir out --truth-dir 2024/counties --county aurora
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path) -> list:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_int(value) -> int:
    return int(str(value).replace(",", "").strip() or 0)


def row_key(r: dict) -> tuple:
    return (r["precinct"], r["office"], r["district"], r["candidate"], r["party"])


def contest_key(r: dict) -> tuple:
    return (r["precinct"], r["office"], r["district"])


def contest_totals(rows: list) -> dict:
    totals: dict = defaultdict(int)
    for r in rows:
        totals[contest_key(r)] += to_int(r["votes"])
    return totals


def eval_county(truth_rows: list, pred_rows: list) -> dict:
    """Return per-county metrics comparing predicted rows to truth rows."""
    truth_map = {row_key(r): to_int(r["votes"]) for r in truth_rows}
    pred_map = {row_key(r): to_int(r["votes"]) for r in pred_rows}

    shared = truth_map.keys() & pred_map.keys()
    matched = [k for k in shared if truth_map[k] == pred_map[k]]
    vote_mismatch = [(k, truth_map[k], pred_map[k]) for k in shared
                     if truth_map[k] != pred_map[k]]
    missing = truth_map.keys() - pred_map.keys()   # in truth, not predicted
    extra = pred_map.keys() - truth_map.keys()     # predicted, not in truth

    # Contest-total reconciliation (label-insensitive).
    t_tot, p_tot = contest_totals(truth_rows), contest_totals(pred_rows)
    contest_shared = t_tot.keys() & p_tot.keys()
    contest_ok = [k for k in contest_shared if t_tot[k] == p_tot[k]]
    contest_bad = [(k, t_tot[k], p_tot[k]) for k in contest_shared
                   if t_tot[k] != p_tot[k]]
    contest_missing = t_tot.keys() - p_tot.keys()

    return {
        "truth_rows": len(truth_map),
        "pred_rows": len(pred_map),
        "matched": len(matched),
        "vote_mismatch": vote_mismatch,
        "missing": missing,
        "extra": extra,
        "contests": len(t_tot),
        "contest_ok": len(contest_ok),
        "contest_bad": contest_bad,
        "contest_missing": contest_missing,
    }


def main():
    ap = argparse.ArgumentParser(description="Evaluate parsed canvass CSVs vs ground truth")
    ap.add_argument("--pred-dir", required=True, help="Directory of parsed CSVs to score")
    ap.add_argument("--truth-dir", default="2024/counties",
                    help="Directory of trusted CSVs (default: 2024/counties)")
    ap.add_argument("--county", help="Limit to a single county slug (e.g. 'aurora')")
    ap.add_argument("--show", type=int, default=10,
                    help="Max example discrepancies to print per county (default: 10)")
    args = ap.parse_args()

    truth_dir, pred_dir = Path(args.truth_dir), Path(args.pred_dir)
    pred_files = sorted(pred_dir.glob("*__precinct.csv"))
    if args.county:
        pred_files = [p for p in pred_files if f"__{args.county}__" in p.name]
    if not pred_files:
        ap.error(f"No predicted CSVs found in {pred_dir}")

    totals = defaultdict(int)
    print(f"{'county':<16}{'rows':>6}{'match':>7}{'mismVote':>9}{'miss':>6}{'extra':>6}"
          f"{'contests':>10}{'recon%':>8}")
    print("-" * 69)

    for pred_path in pred_files:
        truth_path = truth_dir / pred_path.name
        county = pred_path.name.split("__")[3]
        if not truth_path.exists():
            print(f"{county:<16}{'(no truth file)':>53}")
            continue

        m = eval_county(load_rows(truth_path), load_rows(pred_path))
        recon = 100.0 * m["contest_ok"] / m["contests"] if m["contests"] else 0.0
        print(f"{county:<16}{m['truth_rows']:>6}{m['matched']:>7}"
              f"{len(m['vote_mismatch']):>9}{len(m['missing']):>6}{len(m['extra']):>6}"
              f"{m['contests']:>10}{recon:>7.1f}")

        for label in ("truth_rows", "matched", "contests", "contest_ok"):
            totals[label] += m[label]
        totals["vote_mismatch"] += len(m["vote_mismatch"])
        totals["missing"] += len(m["missing"])
        totals["extra"] += len(m["extra"])

        # Detail: the number errors that matter most.
        for (key, tv, pv) in m["contest_bad"][:args.show]:
            prec, office, dist = key
            d = f" d{dist}" if dist else ""
            print(f"    RECON  {prec} / {office}{d}: truth total {tv} != pred {pv}")
        for (key, tv, pv) in m["vote_mismatch"][:args.show]:
            prec, office, dist, cand, party = key
            print(f"    VOTES  {prec} / {office} / {cand} ({party}): {tv} -> {pv}")

    print("-" * 69)
    trecon = 100.0 * totals["contest_ok"] / totals["contests"] if totals["contests"] else 0.0
    rowacc = 100.0 * totals["matched"] / totals["truth_rows"] if totals["truth_rows"] else 0.0
    print(f"{'TOTAL':<16}{totals['truth_rows']:>6}{totals['matched']:>7}"
          f"{totals['vote_mismatch']:>9}{totals['missing']:>6}{totals['extra']:>6}"
          f"{totals['contests']:>10}{trecon:>7.1f}")
    print(f"\nRow-level accuracy:        {rowacc:.1f}%  "
          f"({totals['matched']}/{totals['truth_rows']} rows exact)")
    print(f"Contest reconciliation:    {trecon:.1f}%  "
          f"({totals['contest_ok']}/{totals['contests']} contest totals agree)")


if __name__ == "__main__":
    main()
