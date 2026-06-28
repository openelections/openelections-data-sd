#!/usr/bin/env python3
"""
Extract official SD county-level totals directly from the Secretary of State canvass PDF.

Unlike the scanned precinct PDFs, the statewide "Canvass With Cert" document is a digitally
generated PDF with a clean text layer, so the county totals can be read deterministically -
no vision model, no OCR error. This produces an authoritative reconciliation baseline.

Each contest in the PDF looks like:
    <office title>
    <candidate names, wrapped over 1-3 lines>
    County DEM LIB REP ...        (party codes in column order; "Yes"/"No" for measures)
    Aurora      302 5 1,056 30    (county name + one integer per column)
    ...
    Total       146,859 ...       (statewide total - skipped)

Output columns match reconcile_totals.py / the LLM county CSV:
    county, office, district, party, candidate, votes

Usage:
    uv run scripts/extract_official_totals.py <canvass.pdf> -o out.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

from natural_pdf import PDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_2024_canvass import OFFICE_MAP, VALID_COUNTIES, _BALLOT_MEASURES, normalize_office

ALL_COUNTIES = set()
for _s in VALID_COUNTIES.values():
    ALL_COUNTIES |= _s  # lowercased SD county names

KNOWN_OFFICES = set(OFFICE_MAP.values())
PARTY_TOKENS = {"DEM", "REP", "LIB", "IND", "CON", "NPA", "IAP", "NLP", "GRN"}


def classify_office(line: str):
    """If a header line names a known office/measure, return (office, district); else (None, '')."""
    upper = line.upper()
    if "SUPREME COURT" in upper and "RETENTION" in upper:
        return "Supreme Court Retention", "5"
    for pattern, label in _BALLOT_MEASURES:
        m = pattern.search(line)
        if m:
            return f"{label} {m.group(1).upper()}", ""
    office, district = normalize_office(line, "")
    if office in KNOWN_OFFICES:
        return office, district
    return None, ""


def is_number(tok: str) -> bool:
    return bool(re.fullmatch(r"[\d,]+", tok))


def split_county_votes(line: str):
    """If line is 'CountyName n n n ...', return (county_lower, [ints]); else (None, None)."""
    toks = line.split()
    idx = next((i for i, t in enumerate(toks) if is_number(t)), None)
    if not idx:  # None or 0 (0 = no leading county name)
        return None, None
    name = " ".join(toks[:idx]).lower()
    if name not in ALL_COUNTIES:
        return None, None
    nums = toks[idx:]
    if not all(is_number(t) for t in nums):
        return None, None
    return name, [int(t.replace(",", "")) for t in nums]


def finalize_header(buf: list):
    """From accumulated header lines, derive (office, district, columns).

    The office is the last office-like line in the block (closest to the data, immune to
    leading certificate/preamble text). Party/Yes-No columns are read only from that line
    onward. columns is a list of (party, candidate) left-to-right; partisan races yield
    party codes (candidate blank), ballot measures yield ("", "Yes")/("", "No").
    """
    office = district = None
    office_idx = 0
    for i, line in enumerate(buf):
        off, dist = classify_office(line)
        if off:
            office, district, office_idx = off, dist, i
    if office is None:
        return None, "", []

    # Legislative races print the district on its own line ("State Senator" / "District 01").
    if not district:
        for line in buf[office_idx:]:
            m = re.search(r"\bDistrict\s+(\w+)", line)
            if m:
                district = m.group(1)
                break

    tokens = " ".join(buf[office_idx:]).split()
    parties = [t.strip(",").upper() for t in tokens if t.strip(",").upper() in PARTY_TOKENS]
    if parties:
        return office, district, [(p, "") for p in parties]
    cols = []
    for t in tokens:
        tl = t.strip(",").lower()
        if tl in ("yes", "no") and ("", tl.capitalize()) not in cols:
            cols.append(("", tl.capitalize()))
    return office, district, cols


MEASURE_RE = re.compile(
    r"(Constitutional Amendment [EFGH])|(Initiated Measure \d+)|(Referred Law \d+)")


def measure_office(text: str):
    """Canonical measure office for a header word, or None."""
    m = MEASURE_RE.search(text)
    if not m:
        return None
    office, _ = classify_office(m.group(0))
    return office


def _emit_measure_row(rows, county, measures, votes):
    for k, office in enumerate(measures):
        for candidate, v in (("Yes", votes[2 * k]), ("No", votes[2 * k + 1])):
            rows.append({
                "county": county, "office": office, "district": "",
                "party": "", "candidate": candidate, "votes": v,
            })


def extract_measures(pdf, county_order: list) -> list:
    """Parse the ballot-measure section, which lays measures out in side-by-side columns.

    Measure titles run left-to-right in the same order as their Yes/No column pairs, so the
    linear vote order maps positionally to measures. Continuation pages repeat no titles, so
    the ordering carries until a new set of titles appears. A single-measure page (Amendment
    H) prints no county labels at all - just bare Yes/No pairs in the canonical county order -
    so those rows are matched to county_order positionally.
    """
    rows = []
    measures = []       # current left-to-right measure offices
    bare_idx = 0        # position into county_order for unlabeled (Amendment H) rows
    for page in pdf.pages:
        text = page.extract_text() or ""
        titles = {}
        for w in page.find_all("text"):
            if w.top < 160:
                off = measure_office(w.extract_text())
                if off and off not in titles:
                    titles[off] = w.x0
        if titles:
            new = sorted(titles, key=titles.get)
            if new != measures:
                measures, bare_idx = new, 0  # new measure group -> restart county counter
        if not measures:
            continue
        ncol = 2 * len(measures)
        for line in text.split("\n"):
            county, votes = split_county_votes(line)
            if county is not None and len(votes) == ncol:
                _emit_measure_row(rows, county.title(), measures, votes)
                continue
            # Unlabeled bare number row (Amendment H): map to canonical county order.
            toks = line.split()
            if (len(toks) == ncol and all(is_number(t) for t in toks)
                    and bare_idx < len(county_order)):
                votes = [int(t.replace(",", "")) for t in toks]
                _emit_measure_row(rows, county_order[bare_idx], measures, votes)
                bare_idx += 1
    return rows


def extract(pdf_path: str) -> list:
    pdf = PDF(pdf_path)
    lines = []
    for page in pdf.pages:
        lines.extend((page.extract_text() or "").split("\n"))

    rows = []
    office = district = None
    columns = []
    header_buf = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        county, votes = split_county_votes(line)
        if county is not None:
            if header_buf:  # a header block preceded this row -> maybe a new contest
                new_office, new_district, new_columns = finalize_header(header_buf)
                header_buf = []
                if new_office:  # only switch if we actually recognized an office
                    office, district, columns = new_office, new_district, new_columns
            if office and columns and len(votes) == len(columns):
                for (party, candidate), v in zip(columns, votes):
                    rows.append({
                        "county": county.title(),
                        "office": office,
                        "district": district,
                        "party": party,
                        "candidate": candidate,
                        "votes": v,
                    })
            continue
        if line.startswith("Total"):  # statewide total row ends the contest's data
            # Reset contest state so the next page's header starts fresh and we
            # don't accidentally carry SC Retention columns into a local-district contest.
            office = district = None
            columns = []
            continue
        header_buf.append(line)  # office title / candidate names / party line

    # Canonical county order (for the unlabeled Amendment H rows), taken from President.
    county_order = []
    for r in rows:
        if r["office"] == "President" and r["county"] not in county_order:
            county_order.append(r["county"])

    rows.extend(extract_measures(pdf, county_order))  # measures need column geometry
    return rows


def main():
    ap = argparse.ArgumentParser(description="Extract official SD county totals from canvass PDF")
    ap.add_argument("pdf")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    rows = extract(args.pdf)
    fieldnames = ["county", "office", "district", "party", "candidate", "votes"]
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    counties = sorted({r["county"] for r in rows})
    offices = sorted({(r["office"], r["district"]) for r in rows})
    print(f"Wrote {len(rows)} rows -> {args.output}")
    print(f"  {len(counties)} counties, {len(offices)} office/district contests")


if __name__ == "__main__":
    main()
