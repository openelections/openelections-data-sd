#!/usr/bin/env python3
"""
Parse South Dakota 2024 general election canvass PDFs (scanned images) into
OpenElections precinct CSV format using a vision LLM.

Usage:
    uv run scripts/parse_2024_canvass.py <path/to/file.pdf> [--model gpt-4o] [--cache-dir /tmp/sd_cache]

Outputs per-county CSVs to 2024/counties/
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

import llm
from json_repair import repair_json
from pdf2image import convert_from_path

GITHUB_RAW_BASE = (
    "https://github.com/openelections/openelections-sources-sd/raw/master/2024/general"
)
COUNTY_TOTALS_PDF = "2024GeneralElectionCanvassWithCert.pdf"
COUNTY_TOTALS_OUTPUT = "2024/20241105__sd__general__county.csv"
ELECTION_DATE = "20241105"
ELECTION_TYPE = "general"

# All PDFs in the 2024/general directory of openelections-sources-sd
KNOWN_PDFS = [
    "Aurora-Clark.pdf",
    "Clay-Faulk.pdf",
    "Grant-Lyman.pdf",
    "Marshall-Ziebach.pdf",
]

# 2024 primary equivalents
PRIMARY_COUNTY_TOTALS_PDF = "2024PrimaryStateCanvass&Cert.pdf"
PRIMARY_COUNTY_TOTALS_OUTPUT = "2024/20240604__sd__primary__county.csv"
PRIMARY_ELECTION_DATE = "20240604"
PRIMARY_ELECTION_TYPE = "primary"
PRIMARY_PDFS = [
    "2024Aurora-ClarkPrimaryCanvass.pdf",
    "2024Clay-FaulkPrimaryCanvassReports.pdf",
    "2024Grant-LymanPrimaryCanvassReports.pdf",
    "2024Marshall-ZiebachPrimaryCanvassReports.pdf",
]

# Valid counties for each precinct PDF (lowercase, for repair logic)
_AURORA_CLARK_COUNTIES = {
    "aurora", "beadle", "bennett", "bon homme", "brookings", "brown",
    "brule", "buffalo", "butte", "campbell", "charles mix", "clark",
}
_CLAY_FAULK_COUNTIES = {
    "clay", "codington", "corson", "custer", "davison", "day", "deuel",
    "dewey", "douglas", "edmunds", "fall river", "faulk",
}
_GRANT_LYMAN_COUNTIES = {
    "grant", "gregory", "haakon", "hamlin", "hand", "hanson", "harding",
    "hughes", "hutchinson", "hyde", "jackson", "jerauld", "jones",
    "kingsbury", "lake", "lawrence", "lincoln", "lyman",
}
_MARSHALL_ZIEBACH_COUNTIES = {
    "marshall", "mccook", "mcpherson", "meade", "mellette", "miner",
    "minnehaha", "moody", "oglala lakota", "pennington", "perkins",
    "potter", "roberts", "sanborn", "spink", "stanley", "sully",
    "todd", "tripp", "turner", "union", "walworth", "yankton", "ziebach",
}

VALID_COUNTIES = {
    # General election PDFs
    "Aurora-Clark": _AURORA_CLARK_COUNTIES,
    "Clay-Faulk": _CLAY_FAULK_COUNTIES,
    "Grant-Lyman": _GRANT_LYMAN_COUNTIES,
    "Marshall-Ziebach": _MARSHALL_ZIEBACH_COUNTIES,
    # Primary election PDFs (same county groupings, different filenames)
    "2024Aurora-ClarkPrimaryCanvass": _AURORA_CLARK_COUNTIES,
    "2024Clay-FaulkPrimaryCanvassReports": _CLAY_FAULK_COUNTIES,
    "2024Grant-LymanPrimaryCanvassReports": _GRANT_LYMAN_COUNTIES,
    "2024Marshall-ZiebachPrimaryCanvassReports": _MARSHALL_ZIEBACH_COUNTIES,
}


def download_pdf(filename: str, dest_dir: Path, subdir: str = "general") -> Path:
    """Download a PDF from the GitHub repo if not already cached locally."""
    dest = dest_dir / filename
    if dest.exists():
        print(f"  PDF cached: {dest}")
        return dest
    base = GITHUB_RAW_BASE.rsplit("/", 1)[0]  # strip "general" suffix
    url = f"{base}/{subdir}/{urllib.request.quote(filename)}"
    print(f"  Downloading {filename} from GitHub...")
    urllib.request.urlretrieve(url, dest)
    print(f"  Saved to {dest}")
    return dest

PROMPT = """This is a page (or pair of pages) from a South Dakota 2024 general election official canvass document.
The table has precincts as columns and candidates as rows, grouped by office/contest.
The county name appears in the page header.

If TWO images are provided, the FIRST image is the PREVIOUS page. Use it only for county name
context if the current page does not show a county name in its header.
If ONE image is provided, it is the current page.

Extract all election results and return a JSON array. Each element must have:
- "county": the county name from the page header (title case, e.g. "Aurora", "Clark").
  If the current page has no county name header, use the county name from the previous page.
- "precinct": the precinct name or number as a string (e.g. "1", "2", "Huron 1")
- "office": contest name normalized to title case (e.g. "President", "U.S. Senate",
  "U.S. House", "Governor", "State Senate", "State House", "Attorney General",
  "Secretary of State", "State Auditor", "State Treasurer",
  "Commissioner of School and Public Lands", "Public Utilities Commissioner")
- "district": district number as a string, or "" if not applicable
- "candidate": candidate full name as printed
- "party": party abbreviation (REP, DEM, LIB, IND, CON, NPA, etc.), or "" if not shown
- "votes": integer vote count

Rules:
- The county name MUST come from the page header - do not guess from context.
  If a page covers multiple counties (e.g. a new county starts mid-page), use the
  correct county for each row.
- Skip any "Totals", "Total Votes", "Ballots Cast", or summary/aggregate rows.
- Skip blank rows and page headers with no vote data.
- Each precinct column produces one row per candidate.
- Extract district numbers from office names
  (e.g. "State Senate District 20" -> office="State Senate", district="20").
- If a page has no table data (cover page, blank page), return [].
- Return ONLY valid JSON - no explanation, no markdown fences.

Example output:
[
  {"county": "Aurora", "precinct": "1", "office": "President", "district": "",
   "candidate": "Donald Trump", "party": "REP", "votes": 230},
  {"county": "Clark", "precinct": "1", "office": "State Senate", "district": "5",
   "candidate": "Jane Smith", "party": "DEM", "votes": 45}
]"""

OFFICE_MAP = {
    "PRESIDENTIAL ELECTORS": "President",
    "PRESIDENT AND VICE PRESIDENT": "President",
    "PRESIDENT & VICE PRESIDENT": "President",
    "PRESIDENT": "President",
    "UNITED STATES SENATOR": "U.S. Senate",
    "UNITED STATES SENATE": "U.S. Senate",
    "U.S. SENATOR": "U.S. Senate",
    "U.S. SENATE": "U.S. Senate",
    "UNITED STATES REPRESENTATIVE": "U.S. House",
    "U.S. REPRESENTATIVE": "U.S. House",
    "U.S. HOUSE": "U.S. House",
    "REPRESENTATIVE IN CONGRESS": "U.S. House",
    "UNITED STATES": "U.S. House",
    "GOVERNOR": "Governor",
    "GOVERNOR AND LIEUTENANT GOVERNOR": "Governor",
    "ATTORNEY GENERAL": "Attorney General",
    "SECRETARY OF STATE": "Secretary of State",
    "STATE AUDITOR": "State Auditor",
    "STATE TREASURER": "State Treasurer",
    "COMMISSIONER OF SCHOOL AND PUBLIC LANDS": "Commissioner of School and Public Lands",
    "PUBLIC UTILITIES COMMISSIONER": "Public Utilities Commissioner",
    "STATE SENATOR": "State Senate",
    "STATE SENATE": "State Senate",
    "STATE REPRESENTATIVE": "State House",
    "STATE HOUSE": "State House",
}


def normalize_office(office: str, district: str) -> tuple:
    """Normalize office name and pull any embedded district number."""
    if not district:
        m = re.search(r"district\s+(\w+)", office, re.IGNORECASE)
        if m:
            district = m.group(1)

    clean = re.sub(r"\s*district\s+\w+", "", office, flags=re.IGNORECASE).strip()
    upper = clean.upper().strip()

    for key, normalized in OFFICE_MAP.items():
        # Use word-boundary matching so "PRESIDENT" does not match "PRESIDENTIAL ELECTORS"
        if re.search(r'\b' + re.escape(key) + r'\b', upper):
            # South Dakota has a single at-large congressional district
            if normalized == "U.S. House":
                district = "1"
            # 2024 SD has one Supreme Court retention vote: Justice Seat 5
            if normalized == "Supreme Court Retention" and not district:
                district = "5"
            return normalized, district

    return clean.strip(), district


def normalize_precinct(precinct: str) -> str:
    """Strip 'Precinct-' or 'Precinct ' prefix so page-to-page naming variants collapse."""
    p = re.sub(r'^Precinct[\s\-_]+', '', precinct, flags=re.IGNORECASE).strip()
    return p if p else precinct



def county_slug(county: str) -> str:
    return county.lower().replace(" ", "_")



def output_filename(county: str, election_date: str = ELECTION_DATE, election_type: str = ELECTION_TYPE) -> str:
    return f"{election_date}__sd__{election_type}__{county_slug(county)}__precinct.csv"


def parse_votes(value) -> int:
    """Convert a vote value to int, handling commas, whitespace, and nulls."""
    if value is None:
        return 0
    return int(str(value).replace(",", "").replace(" ", "").strip() or 0)


def extract_json(text: str) -> list:
    """Extract a JSON array from text, tolerating surrounding prose, fences, or malformed JSON."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    # Find first '[' and last ']' to isolate the array
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start:end + 1]
    # Use json-repair to fix trailing commas, truncation, unquoted keys, etc.
    repaired = repair_json(text)
    return json.loads(repaired)


def extract_page_records(model, page_img_path: Path, cache_file: Path, prev_img_path: Path = None) -> list:
    """Return parsed records for one page, using cache if available."""
    if cache_file.exists():
        print(f"    (cached)")
        with open(cache_file) as f:
            return json.load(f)

    attachments = []
    if prev_img_path is not None:
        attachments.append(llm.Attachment(path=str(prev_img_path)))
    attachments.append(llm.Attachment(path=str(page_img_path)))

    response = model.prompt(PROMPT, attachments=attachments)
    text = response.text().strip()

    # Save raw response alongside cache for debugging
    raw_file = cache_file.with_suffix(".raw.txt")
    raw_file.write_text(text)

    records = extract_json(text)

    with open(cache_file, "w") as f:
        json.dump(records, f, indent=2)

    return records


def parse_page_range(spec: str, total: int) -> range:
    """Parse a page range string like '1', '1-3', or '2-' into a range."""
    spec = spec.strip()
    if "-" in spec:
        start_s, _, end_s = spec.partition("-")
        start = int(start_s) - 1 if start_s else 0
        end = int(end_s) if end_s else total
    else:
        start = int(spec) - 1
        end = start + 1
    return range(max(0, start), min(total, end))


def process_pdf(pdf_path: str, model_name: str, cache_dir: str, output_dir: str, page_range: str = None,
                election_date: str = ELECTION_DATE, election_type: str = ELECTION_TYPE):
    pdf_stem = Path(pdf_path).stem
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    model = llm.get_model(model_name)

    print(f"Rendering pages from {pdf_path}...")
    pages = convert_from_path(pdf_path, dpi=200)
    print(f"  {len(pages)} page(s) found")

    indices = parse_page_range(page_range, len(pages)) if page_range else range(len(pages))
    print(f"  Processing pages: {indices.start + 1}-{indices.stop}")

    valid_counties = VALID_COUNTIES.get(pdf_stem, set())
    all_records = []
    prev_img_path = None
    last_valid_county = None
    for i, page in [(i, pages[i]) for i in indices]:
        img_path = cache_path / f"{pdf_stem}_page{i}.png"
        cache_file = cache_path / f"{pdf_stem}_page{i}.json"

        if not img_path.exists():
            page.save(str(img_path))

        print(f"  Page {i + 1}/{len(pages)}: calling {model_name}...")
        try:
            records = extract_page_records(model, img_path, cache_file, prev_img_path)
        except (json.JSONDecodeError, Exception) as e:
            raw_file = cache_file.with_suffix(".raw.txt")
            snippet = raw_file.read_text()[:200] if raw_file.exists() else "(no raw output)"
            print(f"    WARNING: failed to parse page {i + 1}: {e}")
            print(f"    Raw response snippet: {snippet}")
            records = []

        # County repair: if this page has no valid county, propagate last known good one
        if valid_counties and records:
            page_counties = {r.get("county", "").strip().lower() for r in records}
            valid_on_page = [r.get("county", "").strip() for r in records
                             if r.get("county", "").strip().lower() in valid_counties]
            if valid_on_page:
                last_valid_county = valid_on_page[0]
            elif last_valid_county:
                bad = page_counties - valid_counties
                if bad:
                    print(f"    REPAIR page {i + 1}: {bad} -> '{last_valid_county}'")
                    for r in records:
                        r["county"] = last_valid_county

        print(f"    -> {len(records)} rows")
        all_records.extend(records)
        prev_img_path = img_path

    # Normalize and group by county
    by_county: dict = {}
    for rec in all_records:
        office, district = normalize_office(
            rec.get("office", "").strip(),
            str(rec.get("district", "")).strip(),
        )
        county = rec.get("county", "Unknown").strip().title()
        row = {
            "county": county,
            "precinct": normalize_precinct(str(rec.get("precinct", "")).strip()),
            "office": office,
            "district": district,
            "candidate": rec.get("candidate", "").strip(),
            "party": rec.get("party", "").strip().upper(),
            "votes": parse_votes(rec.get("votes", 0)),
        }
        by_county.setdefault(county, []).append(row)

    # Write one CSV per county
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    fieldnames = ["county", "precinct", "office", "district", "candidate", "party", "votes"]
    for county, rows in sorted(by_county.items()):
        # Deduplicate: same (county, precinct, office, district, candidate, party) may appear
        # on multiple pages with identical data (e.g. continuation pages)
        seen: dict = {}
        deduped = []
        for row in rows:
            key = (row["county"], row["precinct"], row["office"],
                   row["district"], row["candidate"], row["party"])
            if key not in seen:
                seen[key] = row
                deduped.append(row)
            elif seen[key]["votes"] != row["votes"]:
                print(f"    WARN dedup conflict {county}/{row['precinct']}/{row['office']}/{row['candidate']}: "
                      f"{seen[key]['votes']} vs {row['votes']}")
        rows = deduped

        filepath = out_path / output_filename(county, election_date, election_type)
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Wrote {len(rows)} rows -> {filepath}")


COUNTY_PROMPT = """This is a page (or pair of pages) from the South Dakota 2024 general election official statewide canvass.
It contains county-level vote totals (one row per county, not broken out by precinct).
Counties are listed as rows; candidates are laid out as columns.

If TWO images are provided, the FIRST image is the PREVIOUS page (use it only for column
header / candidate name context). The SECOND image is the CURRENT page to extract data from.
If ONE image is provided, it is the current page.

The office/contest name appears at the top of the table or in a header row.
Some pages are continuations of a table from a previous page and may not repeat
the office name at the top - in that case, use any visible header or, if two images
are provided, read the office name from the first (previous) image.
Candidate names appear as column headers; use the previous page's headers if the
current page does not show them.

County names appear as the leftmost column in each data row (e.g. "Aurora", "Beadle",
"Charles Mix"). Each county row has vote totals for each candidate column.

Extract all county-level results from the CURRENT page and return a JSON array.
Each element must have:
- "county": county name in title case (e.g. "Aurora", "Beadle", "Charles Mix")
- "office": normalized contest name (e.g. "President", "U.S. Senate", "U.S. House",
  "Governor", "State Senate", "State House", "Attorney General", "Secretary of State",
  "State Auditor", "State Treasurer", "Commissioner of School and Public Lands",
  "Public Utilities Commissioner")
- "district": district number as a string, or "" if not applicable
- "candidate": candidate full name as printed
- "party": party abbreviation (REP, DEM, LIB, IND, CON, NPA, etc.), or "" if not shown
- "votes": integer vote count

Rules:
- Each county row produces one record per candidate column.
- Skip header rows, blank rows, certification text, and any statewide totals rows.
- Extract district numbers from office names (e.g. "State Senate District 8" ->
  office="State Senate", district="8").
- If the current page truly has no table data at all (e.g. a cover or signature page), return [].
- Return ONLY valid JSON - no explanation, no markdown fences."""


def process_county_totals_pdf(
    pdf_path: str, model_name: str, cache_dir: str, output_path: str, page_range: str = None,
    election_type: str = ELECTION_TYPE
):
    """Parse the statewide county-totals canvass PDF into a single county-level CSV."""
    pdf_stem = Path(pdf_path).stem
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    model = llm.get_model(model_name)

    print(f"Rendering pages from {pdf_path}...")
    pages = convert_from_path(pdf_path, dpi=200)
    print(f"  {len(pages)} page(s) found")

    indices = parse_page_range(page_range, len(pages)) if page_range else range(len(pages))
    print(f"  Processing pages: {indices.start + 1}-{indices.stop}")

    all_records = []
    prev_img_path = None
    for i in indices:
        page = pages[i]
        img_path = cache_path / f"{pdf_stem}_page{i}.png"
        cache_file = cache_path / f"{pdf_stem}_page{i}.json"

        if not img_path.exists():
            page.save(str(img_path))

        print(f"  Page {i + 1}/{len(pages)}: calling {model_name}...")
        try:
            if cache_file.exists():
                print(f"    (cached)")
                with open(cache_file) as f:
                    records = json.load(f)
            else:
                attachments = []
                if prev_img_path is not None:
                    attachments.append(llm.Attachment(path=str(prev_img_path)))
                attachments.append(llm.Attachment(path=str(img_path)))
                response = model.prompt(
                    COUNTY_PROMPT,
                    attachments=attachments,
                )
                text = response.text().strip()
                raw_file = cache_file.with_suffix(".raw.txt")
                raw_file.write_text(text)
                records = extract_json(text)
                with open(cache_file, "w") as f:
                    json.dump(records, f, indent=2)
        except (json.JSONDecodeError, Exception) as e:
            raw_file = cache_file.with_suffix(".raw.txt")
            snippet = raw_file.read_text()[:200] if raw_file.exists() else "(no raw output)"
            print(f"    WARNING: failed to parse page {i + 1}: {e}")
            print(f"    Raw response snippet: {snippet}")
            records = []

        print(f"    -> {len(records)} rows")
        all_records.extend(records)
        prev_img_path = img_path

    # Normalize records
    rows = []
    for rec in all_records:
        office, district = normalize_office(
            rec.get("office", "").strip(),
            str(rec.get("district", "")).strip(),
        )
        rows.append({
            "county": rec.get("county", "Unknown").strip().title(),
            "office": office,
            "district": district,
            "party": rec.get("party", "").strip().upper(),
            "candidate": rec.get("candidate", "").strip(),
            "votes": parse_votes(rec.get("votes", 0)),
        })

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["county", "office", "district", "party", "candidate", "votes"]
    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows -> {out_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse SD 2024 canvass PDFs to OpenElections precinct CSV"
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        help="Path to a local canvass PDF (omit to use --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download and process all known PDFs from the GitHub repo",
    )
    parser.add_argument(
        "--county-totals",
        action="store_true",
        help="Download and parse the statewide county-totals canvass PDF",
    )
    parser.add_argument(
        "--primary",
        action="store_true",
        help="Process the 2024 primary election PDFs instead of the general election",
    )
    parser.add_argument(
        "--model", default="gpt-4o", help="llm model name (default: gpt-4o)"
    )
    parser.add_argument(
        "--cache-dir",
        default="/tmp/sd_canvass_cache",
        help="Directory for cached page images and JSON responses",
    )
    parser.add_argument(
        "--output-dir",
        default="2024/counties",
        help="Output directory for per-county CSVs (default: 2024/counties)",
    )
    parser.add_argument(
        "--pages",
        default=None,
        metavar="RANGE",
        help="Page range to process, 1-based (e.g. '1', '1-3', '2-'). Useful for testing.",
    )
    args = parser.parse_args()

    if not args.pdf and not args.all and not args.county_totals:
        parser.error("Provide a PDF path, --all, or --county-totals")

    cache_path = Path(args.cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    # Select election-specific constants
    if args.primary:
        known_pdfs = PRIMARY_PDFS
        county_totals_pdf = PRIMARY_COUNTY_TOTALS_PDF
        county_totals_output = PRIMARY_COUNTY_TOTALS_OUTPUT
        election_date = PRIMARY_ELECTION_DATE
        election_type = PRIMARY_ELECTION_TYPE
        github_subdir = "primary"
    else:
        known_pdfs = KNOWN_PDFS
        county_totals_pdf = COUNTY_TOTALS_PDF
        county_totals_output = COUNTY_TOTALS_OUTPUT
        election_date = ELECTION_DATE
        election_type = ELECTION_TYPE
        github_subdir = "general"

    print(f"Model: {args.model}")
    print(f"Election: 2024 {election_type}")

    if args.county_totals:
        pdf_path = download_pdf(county_totals_pdf, cache_path, github_subdir)
        process_county_totals_pdf(
            str(pdf_path), args.model, args.cache_dir, county_totals_output, args.pages,
            election_type=election_type,
        )

    if args.all:
        pdfs = [download_pdf(name, cache_path, github_subdir) for name in known_pdfs]
    elif args.pdf:
        local = Path(args.pdf)
        if not local.exists():
            pdfs = [download_pdf(local.name, cache_path, github_subdir)]
        else:
            pdfs = [local]
    else:
        pdfs = []

    for pdf_path in pdfs:
        process_pdf(
            str(pdf_path), args.model, args.cache_dir, args.output_dir, args.pages,
            election_date=election_date, election_type=election_type,
        )
    print("Done.")


if __name__ == "__main__":
    main()
