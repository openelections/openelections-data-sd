#!/usr/bin/env python3
"""
Build the SD 2026 GENERAL county-level results file from vision-LLM hand
transcriptions of the state canvass PDF.

The source PDF (State Canvass and Certificate, 22 pages) is a scanned image
with no usable text layer, so each page was transcribed by reading the
rendered page image. Transcriptions live in
~/sd_cache/p2026_general/page{N}.json (one JSON dict per PDF page; districts
pages carry a "contests" list, statewide pages a single contest).

Every contest's sum of per-county votes is validated against the printed
"Total" row before writing.

Usage:
    uv run scripts/build_2026_general_county.py

Output:
    2026/20261103__sd__general__county.csv
"""
import csv
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("SD_CACHE", Path.home() / "sd_cache")) / "p2026_general"
OUT_CSV = REPO / "2026/20261103__sd__general__county.csv"

COUNTIES = {
    "Aurora", "Beadle", "Bennett", "Bon Homme", "Brookings", "Brown", "Brule", "Buffalo",
    "Butte", "Campbell", "Charles Mix", "Clark", "Clay", "Codington", "Corson", "Custer",
    "Davison", "Day", "Deuel", "Dewey", "Douglas", "Edmunds", "Fall River", "Faulk",
    "Grant", "Gregory", "Haakon", "Hamlin", "Hand", "Hanson", "Harding", "Hughes",
    "Hutchinson", "Hyde", "Jackson", "Jerauld", "Jones", "Kingsbury", "Lake", "Lawrence",
    "Lincoln", "Lyman", "Marshall", "McCook", "McPherson", "Meade", "Mellette", "Miner",
    "Minnehaha", "Moody", "Oglala Lakota", "Pennington", "Perkins", "Potter", "Roberts",
    "Sanborn", "Spink", "Stanley", "Sully", "Todd", "Tripp", "Turner", "Union",
    "Walworth", "Yankton", "Ziebach",
}

OFFICES_OUT = {
    "U.S. Senate": ("U.S. Senate", ""),
    "U.S. House": ("U.S. House", "1"),
    "Governor": ("Governor", ""),
    "Secretary of State": ("Secretary of State", ""),
    "Attorney General": ("Attorney General", ""),
    "State Auditor": ("State Auditor", ""),
    "State Treasurer": ("State Treasurer", ""),
    "Commissioner of School and Public Lands": ("Commissioner of School and Public Lands", ""),
    "Public Utilities Commissioner": ("Public Utilities Commissioner", ""),
}


def county_name(name):
    return "Oglala Lakota" if name == "Oglala" else name


def load_pages():
    pages = []
    for p in sorted(CACHE.glob("page*.json")):
        if p.stem == "page0":
            continue  # certificate page
        pg = json.loads(p.read_text())
        if pg.get("office", "").startswith("Constitutional Amendment"):
            pg["office"] = pg["office"].replace(" (I,J,K,L)", "")
            pg["candidates"] = [c.replace("Amendment", "") for c in pg["candidates"]]
        pg["rows"] = [[county_name(r[0])] + list(r[1:]) for r in pg.get("rows", [])]
        for c in pg.get("contests", []):
            c["rows"] = [[county_name(r[0])] + list(r[1:]) for r in c["rows"]]
        pages.append(pg)
    return pages


def expand(pages):
    """Yield normalized contest dicts: {office, district, party/candidates, rows, total}."""
    for pg in pages:
        if "contests" in pg:
            for c in pg["contests"]:
                cands = []
                for cand in c["candidates"]:
                    name, party = cand.rsplit("|", 1)
                    cands.append((name, party))
                yield {
                    "page": pg["page"],
                    "office": pg["office"],
                    "district": c["district"].zfill(2),
                    "candidates": cands,
                    "rows": [(r[0], list(r[1:])) for r in c["rows"]],
                    "total": c.get("total"),
                }
        else:
            cands = []
            for cand in pg["candidates"]:
                if "|" in cand:
                    name, party = cand.rsplit("|", 1)
                else:  # amendments page: "Amendment I Yes" etc., party filled in later
                    name, party = cand, ""
                cands.append((name, party))
            office, district = OFFICES_OUT.get(pg["office"], (pg["office"], pg.get("district", "")))
            yield {
                "page": pg["page"],
                "office": office,
                "district": district,
                "candidates": cands,
                "rows": [(r[0], list(r[1:])) for r in pg["rows"]],
                "total": pg.get("total"),
            }


def amendment_contests(contest):
    """Split the amendments page into one Yes/No contest per amendment."""
    out = []
    cand_list = contest["candidates"]
    for k in range(0, len(cand_list) // 2):
        label = cand_list[2 * k][0]  # "Amendment I Yes"
        amendment = label.replace(" Yes", "")
        a, b = 2 * k, 2 * k + 1
        out.append({
            "page": contest["page"],
            "office": f"Constitutional Amendment {amendment.split()[-1]}",
            "district": "",
            "candidates": [("Yes", ""), ("No", "")],
            "rows": [(name, [row[a], row[b]]) for name, row in contest["rows"]],
            "total": contest["total"][a:b + 1],
        })
    return out


def main():
    rows = []
    warnings = []
    n_contests = 0
    for contest in expand(load_pages()):
        if contest["office"].startswith("Constitutional Amendment"):
            for c in amendment_contests(contest):
                rows.extend(contest_rows(c, warnings))
                n_contests += 1
        else:
            rows.extend(contest_rows(contest, warnings))
            n_contests += 1

    rows.sort(key=lambda r: (r[1], r[2], r[3], r[0], r[4]))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["county", "office", "district", "party", "candidate", "votes"])
        w.writerows(rows)

    # Summary
    offices = {}
    for r in rows:
        offices.setdefault((r[1], r[2], r[3]), set()).add(r[0])
    missing = [
        cnty for cnty in COUNTIES
        if not any(r[0] == cnty for r in rows)
    ]
    print(f"contests: {n_contests}")
    print(f"rows: {len(rows)}")
    print(f"distinct offices/districts: {len(offices)}")
    if missing:
        print(f"counties MISSING from output: {missing}")
    print(f"warnings: {len(warnings)}")
    for wtext in warnings:
        print(f"  ! {wtext}")


def contest_rows(contest, warnings):
    """Validate one contest's county sums against its printed Total row and emit rows."""
    page, office, district = contest["page"], contest["office"], contest["district"]
    cands = contest["candidates"]
    n = len(cands)
    county_map = {}
    for name, vals in contest["rows"]:
        if name not in COUNTIES:
            warnings.append(f"p{page} {office} {district}: unknown county {name!r}")
            continue
        if name in county_map:
            warnings.append(f"p{page} {office} {district}: duplicate county row {name}")
            continue
        if len(vals) != n:
            warnings.append(f"p{page} {office} {district} {name}: {len(vals)} values vs {n} candidates")
        county_map[name] = vals
    absent = COUNTIES - set(county_map)
    if absent and office not in ("State Senate", "State House"):
        warnings.append(f"p{page} {office} {district}: counties absent: {sorted(absent)}")

    total = contest["total"]
    if total is not None:
        for i, (cand_name, _party) in enumerate(cands):
            s = sum(vals[i] for vals in county_map.values() if i < len(vals))
            t = total[i] if i < len(total) else None
            if t is None:
                warnings.append(f"p{page} {office} {district} {cand_name}: no printed Total")
            elif s != t:
                warnings.append(
                    f"TOTAL MISMATCH p{page} {office} {district} {cand_name}: sum={s} total={t}")
    else:
        warnings.append(f"p{page} {office} {district}: no printed Total row")

    out = []
    for county in sorted(county_map):
        vals = county_map[county]
        for i, (cand_name, party) in enumerate(cands):
            out.append([county, office, district, party, cand_name, vals[i] if i < len(vals) else 0])
    return out


if __name__ == "__main__":
    main()
