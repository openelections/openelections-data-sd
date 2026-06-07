"""
Validate that precinct-level totals for a county match the county-level file.
Usage:
    uv run scripts/validate_county_totals.py            # all counties with precinct files
    uv run scripts/validate_county_totals.py aurora     # single county
    uv run scripts/validate_county_totals.py --csv discrepancies.csv  # write CSV of all mismatches
"""
import sys
import pandas as pd
from pathlib import Path

def county_slug(name: str) -> str:
    return name.lower().replace(" ", "_")

def validate_county(slug: str, county_df: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    """Validate one county. Returns (ok, mismatches_df)."""
    display = slug.replace("_", " ").title()
    precinct_path = Path(f"2024/counties/20241105__sd__general__{slug}__precinct.csv")
    county_path = Path("2024/20241105__sd__general__county.csv")

    if not precinct_path.exists():
        print(f"ERROR: precinct file not found: {precinct_path}")
        return False, pd.DataFrame()
    if not county_path.exists():
        print(f"ERROR: county file not found: {county_path}")
        return False, pd.DataFrame()

    precinct_df = pd.read_csv(precinct_path, dtype=str)

    # Normalise county name for matching (case-insensitive)
    aurora_county = county_df[county_df["county"].str.lower() == display.lower()].copy()
    if aurora_county.empty:
        # Try slug-style match
        aurora_county = county_df[
            county_df["county"].str.lower().str.replace(" ", "_") == slug
        ].copy()
    if aurora_county.empty:
        print(f"ERROR: no rows for '{display}' in {county_path}")
        return False, pd.DataFrame()

    aurora_county["votes"] = pd.to_numeric(aurora_county["votes"], errors="coerce").fillna(0).astype(int)

    precinct_df["votes"] = pd.to_numeric(precinct_df["votes"], errors="coerce").fillna(0).astype(int)

    # Sum precinct votes by office / district / candidate / party
    group_cols = ["office", "district", "candidate", "party"]
    precinct_totals = (
        precinct_df.groupby(group_cols, dropna=False)["votes"]
        .sum()
        .reset_index()
        .rename(columns={"votes": "precinct_votes"})
    )

    # county file uses same columns but may have NaN district
    county_totals = aurora_county[group_cols + ["votes"]].copy()
    county_totals = county_totals.rename(columns={"votes": "county_votes"})

    # Fill NaN district with "" for consistent merging
    for df in (precinct_totals, county_totals):
        df["district"] = df["district"].fillna("").astype(str).str.strip()
        # Normalize district: strip leading zeros from purely numeric values ("04" -> "4")
        df["district"] = df["district"].apply(
            lambda d: str(int(d)) if d.isdigit() else d
        )
        # 2024 SD has one Supreme Court retention (Seat 5); fill missing district
        sc_mask = df["office"].str.contains("Supreme Court Retention", na=False)
        df.loc[sc_mask & (df["district"] == ""), "district"] = "5"
        # Normalize Supreme Court Retention candidates: "Scott P. Myren - Yes" -> "Yes"
        df.loc[sc_mask, "candidate"] = df.loc[sc_mask, "candidate"].apply(
            lambda c: c.split(" - ")[-1].strip() if " - " in str(c) else c
        )

    merged = pd.merge(county_totals, precinct_totals, on=group_cols, how="outer")
    merged["county_votes"] = merged["county_votes"].fillna(0).astype(int)
    merged["precinct_votes"] = merged["precinct_votes"].fillna(0).astype(int)
    merged["diff"] = merged["county_votes"] - merged["precinct_votes"]

    mismatches = merged[merged["diff"] != 0]
    only_county = merged[merged["precinct_votes"] == 0]
    only_precinct = merged[merged["county_votes"] == 0]

    if mismatches.empty:
        print(f"OK: all {len(merged)} rows match for {display}")
        return True, pd.DataFrame()
    else:
        print(f"MISMATCHES ({len(mismatches)} rows) for {display}:")
        print(mismatches[group_cols + ["county_votes", "precinct_votes", "diff"]].to_string(index=False))

    if not only_county.empty:
        print(f"\n  In county file only ({len(only_county)} rows):")
        print(only_county[group_cols + ["county_votes"]].to_string(index=False))

    if not only_precinct.empty:
        print(f"\n  In precinct file only ({len(only_precinct)} rows):")
        print(only_precinct[group_cols + ["precinct_votes"]].to_string(index=False))

    mismatches = mismatches.copy()
    mismatches.insert(0, "county", display)
    return False, mismatches[["county"] + group_cols + ["county_votes", "precinct_votes", "diff"]]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("county", nargs="?", help="Single county slug to validate")
    parser.add_argument("--csv", metavar="FILE", help="Write all mismatches to this CSV file")
    args = parser.parse_args()

    county_path = Path("2024/20241105__sd__general__county.csv")
    if not county_path.exists():
        print(f"ERROR: county file not found: {county_path}")
        sys.exit(1)
    county_df = pd.read_csv(county_path, dtype=str)

    if args.county:
        slugs = [county_slug(args.county)]
    else:
        precinct_files = sorted(Path("2024/counties").glob("20241105__sd__general__*__precinct.csv"))
        slugs = [p.stem.split("__")[3] for p in precinct_files]
        print(f"Validating {len(slugs)} counties...\n")

    ok = 0
    fail = 0
    all_mismatches = []
    for slug in slugs:
        matched, mdf = validate_county(slug, county_df)
        if matched:
            ok += 1
        else:
            fail += 1
            if not mdf.empty:
                all_mismatches.append(mdf)

    if len(slugs) > 1:
        print(f"\nSummary: {ok} OK, {fail} with mismatches")

    if args.csv and all_mismatches:
        out = pd.concat(all_mismatches, ignore_index=True)
        out.to_csv(args.csv, index=False)
        print(f"Wrote {len(out)} mismatch rows -> {args.csv}")
    elif args.csv:
        print("No mismatches to write.")


if __name__ == "__main__":
    main()
