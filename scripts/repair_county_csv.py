#!/usr/bin/env python3
"""
Repair the 2024 county-level CSV by:
1. Deduplicating PUC rows (keeping higher vote total per county+candidate+party)
2. Re-extracting Amendment H from pages 28 and 29 using explicit county name lists
3. Rewriting the CSV with corrected data

Usage: uv run scripts/repair_county_csv.py [--model gpt-4o]
"""
import argparse
import csv
import json
from pathlib import Path

import llm
from json_repair import repair_json

COUNTY_CSV = Path("2024/20241105__sd__general__county.csv")
CACHE_DIR = Path("/tmp/sd_canvass_cache")
PDF_STEM = "2024GeneralElectionCanvassWithCert"

# Standard SD county alphabetical order (66 counties)
SD_COUNTIES = [
    "Aurora", "Beadle", "Bennett", "Bon Homme", "Brookings", "Brown", "Brule",
    "Buffalo", "Butte", "Campbell", "Charles Mix", "Clark", "Clay", "Codington",
    "Corson", "Custer", "Davison", "Day", "Deuel", "Dewey", "Douglas", "Edmunds",
    "Fall River", "Faulk", "Grant", "Gregory", "Haakon", "Hamlin", "Hand",
    "Hanson", "Harding", "Hughes", "Hutchinson", "Hyde", "Jackson", "Jerauld",
    "Jones", "Kingsbury", "Lake", "Lawrence", "Lincoln", "Lyman", "Marshall",
    "McCook", "McPherson", "Meade", "Mellette", "Miner", "Minnehaha", "Moody",
    "Oglala Lakota", "Pennington", "Perkins", "Potter", "Roberts", "Sanborn",
    "Spink", "Stanley", "Sully", "Todd", "Tripp", "Turner", "Union", "Walworth",
    "Yankton", "Ziebach",
]

# Page 28: rows 1-45 = Aurora through McPherson
PAGE28_COUNTIES = SD_COUNTIES[0:45]   # indices 0-44
# Page 29: rows 1-21 = Meade through Ziebach
PAGE29_COUNTIES = SD_COUNTIES[45:66]  # indices 45-65

PUC_PAGE5_COUNTIES = [
    "Aurora", "Beadle", "Bennett", "Bon Homme", "Brookings", "Brown", "Brule",
    "Buffalo", "Butte", "Campbell", "Charles Mix", "Clark", "Clay", "Codington",
    "Corson", "Custer", "Davison", "Day", "Deuel", "Dewey", "Douglas", "Edmunds",
    "Fall River", "Faulk", "Grant", "Gregory", "Haakon", "Hamlin", "Hand",
    "Hanson", "Harding", "Hughes", "Hutchinson", "Hyde", "Jackson", "Jerauld",
    "Jones", "Kingsbury", "Lake", "Lawrence", "Lincoln", "Lyman", "Marshall",
    "McCook", "McPherson", "Meade", "Mellette", "Miner", "Minnehaha",
]

PUC_PROMPT = """This is a page from the South Dakota 2024 general election canvass.
It shows Public Utilities Commissioner vote totals by county.
The table has three candidate columns: Forrest Wilson (DEM), A. Gideon Oakes (LIB),
and Kristie Fiegen (REP). County names appear in the leftmost column.

Extract every county row and return a JSON array. Each element must have:
- "county": county name as printed
- "office": "Public Utilities Commissioner"
- "district": ""
- "candidate": candidate full name as printed in the column header
- "party": party abbreviation (DEM, LIB, or REP)
- "votes": integer vote count

Rules:
- Skip the Total row at the bottom.
- Return ONLY valid JSON — no explanation, no markdown fences.
"""

AMEND_H_PROMPT_TEMPLATE = """This is a page from the South Dakota 2024 general election canvass.
It shows Constitutional Amendment H (Top-Two Primary Elections) vote totals.
The table has two columns: Yes votes and No votes.
There are NO county name labels visible — the rows correspond to counties in
the following order (one county per row):

{county_list}

Extract the Yes and No vote totals for each county row in order and return a
JSON array. Each element must have:
- "county": the county name from the list above (in order, row by row)
- "office": "Constitutional Amendment H"
- "district": ""
- "candidate": "Yes" or "No"
- "party": ""
- "votes": integer vote count

Rules:
- Skip any bold "Total" row at the bottom.
- Return ONLY valid JSON — no explanation, no markdown fences.
- Every county in the list above must appear exactly twice (once for Yes, once for No).
"""


def extract_json(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        import re
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start:end + 1]
    return json.loads(repair_json(text))


def extract_amendment_h(model, img_path: Path, counties: list) -> list:
    county_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(counties))
    prompt = AMEND_H_PROMPT_TEMPLATE.format(county_list=county_list)
    response = model.prompt(prompt, attachments=[llm.Attachment(path=str(img_path))])
    text = response.text().strip()
    # Save raw for debugging
    raw_path = img_path.with_suffix(".amend_h.raw.txt")
    raw_path.write_text(text)
    records = extract_json(text)
    return records


def deduplicate_puc(rows: list) -> list:
    """For Public Utilities Commissioner, keep the row with the higher vote count
    when a county+candidate+party combination appears more than once."""
    puc_best: dict = {}
    other: list = []

    for row in rows:
        if row["office"] == "Public Utilities Commissioner":
            key = (row["county"], row["candidate"], row["party"])
            votes = int(row["votes"])
            if key not in puc_best or votes > int(puc_best[key]["votes"]):
                puc_best[key] = row
        else:
            other.append(row)

    return other + list(puc_best.values())


def fix_supreme_court(rows: list) -> list:
    """Normalize Supreme Court Retention rows: set district=5 and prepend justice name."""
    out = []
    for row in rows:
        if row["office"] == "Supreme Court Retention":
            cand = row["candidate"].strip()
            if cand in ("Yes", "No"):
                row = dict(row)
                row["candidate"] = f"Scott P. Myren - {cand}"
                row["district"] = "5"
        out.append(row)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM re-extraction (use cached amend_h files if present)")
    args = parser.parse_args()

    # 1. Load current CSV
    with open(COUNTY_CSV) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Loaded {len(rows)} rows from {COUNTY_CSV}")

    # 2. Remove any existing (wrong) Amendment H rows
    non_h = [r for r in rows if r["office"] != "Constitutional Amendment H"]
    removed = len(rows) - len(non_h)
    print(f"Removed {removed} existing Amendment H rows")

    # 3. Deduplicate PUC
    before_puc = len(non_h)
    non_h = deduplicate_puc(non_h)
    after_puc = len(non_h)
    print(f"Deduplicated PUC: {before_puc - after_puc} duplicate rows removed")

    # 4. Re-extract missing PUC rows from page 5 (Aurora–Minnehaha)
    puc_page5_cache = CACHE_DIR / f"{PDF_STEM}_page5.puc.json"
    new_puc_rows = []

    if not args.skip_llm:
        model = llm.get_model(args.model)

        img_path = CACHE_DIR / f"{PDF_STEM}_page5.png"
        if not img_path.exists():
            print(f"ERROR: image not found: {img_path}")
        elif puc_page5_cache.exists():
            print(f"Page 5 PUC: using cached extraction")
            with open(puc_page5_cache) as f:
                puc_records = json.load(f)
            new_puc_rows = puc_records
        else:
            print(f"Page 5 PUC: calling {args.model}...")
            response = model.prompt(PUC_PROMPT, attachments=[llm.Attachment(path=str(img_path))])
            text = response.text().strip()
            (CACHE_DIR / f"{PDF_STEM}_page5.puc.raw.txt").write_text(text)
            puc_records = extract_json(text)
            with open(puc_page5_cache, "w") as f:
                json.dump(puc_records, f, indent=2)
            print(f"  -> {len(puc_records)} records")
            new_puc_rows = puc_records
    else:
        if puc_page5_cache.exists():
            with open(puc_page5_cache) as f:
                new_puc_rows = json.load(f)
            print(f"Loaded {len(new_puc_rows)} cached PUC rows from {puc_page5_cache.name}")

    puc_csv_rows = []
    for rec in new_puc_rows:
        puc_csv_rows.append({
            "county": rec.get("county", "").strip(),
            "office": "Public Utilities Commissioner",
            "district": "",
            "party": rec.get("party", "").strip().upper(),
            "candidate": rec.get("candidate", "").strip(),
            "votes": str(rec.get("votes", 0)),
        })
    print(f"New PUC rows (page 5): {len(puc_csv_rows)}")

    # 5. Fix Supreme Court Retention candidate names and district
    before_sc = len(non_h)
    non_h = fix_supreme_court(non_h)
    print(f"Fixed Supreme Court Retention rows (candidate name + district=5)")

    # 6. Re-extract Amendment H from pages 28 and 29
    new_h_rows = []
    page28_cache = CACHE_DIR / f"{PDF_STEM}_page28.amend_h.json"
    page29_cache = CACHE_DIR / f"{PDF_STEM}_page29.amend_h.json"

    if not args.skip_llm:
        model = llm.get_model(args.model)

        for page_num, img_name, counties, cache_file in [
            (28, f"{PDF_STEM}_page28.png", PAGE28_COUNTIES, page28_cache),
            (29, f"{PDF_STEM}_page29.png", PAGE29_COUNTIES, page29_cache),
        ]:
            img_path = CACHE_DIR / img_name
            if not img_path.exists():
                print(f"ERROR: image not found: {img_path}")
                continue

            if cache_file.exists():
                print(f"Page {page_num}: using cached extraction ({cache_file.name})")
                with open(cache_file) as f:
                    records = json.load(f)
            else:
                print(f"Page {page_num}: calling {args.model} with {len(counties)} counties...")
                records = extract_amendment_h(model, img_path, counties)
                with open(cache_file, "w") as f:
                    json.dump(records, f, indent=2)
                print(f"  -> {len(records)} records")

            new_h_rows.extend(records)
    else:
        for cache_file in [page28_cache, page29_cache]:
            if cache_file.exists():
                with open(cache_file) as f:
                    records = json.load(f)
                new_h_rows.extend(records)
                print(f"Loaded {len(records)} cached Amendment H rows from {cache_file.name}")
            else:
                print(f"WARNING: cache not found: {cache_file}")

    # Convert new H rows to CSV dict format
    h_csv_rows = []
    for rec in new_h_rows:
        h_csv_rows.append({
            "county": rec.get("county", "").strip(),
            "office": "Constitutional Amendment H",
            "district": "",
            "party": "",
            "candidate": rec.get("candidate", "").strip(),
            "votes": str(rec.get("votes", 0)),
        })
    print(f"New Amendment H rows: {len(h_csv_rows)}")

    # 7. Combine and write
    all_rows = non_h + puc_csv_rows + h_csv_rows
    fieldnames = ["county", "office", "district", "party", "candidate", "votes"]
    with open(COUNTY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Wrote {len(all_rows)} rows to {COUNTY_CSV}")


if __name__ == "__main__":
    main()
