#!/usr/bin/env python3
"""Download and parse race-level exports from electionresults.sd.gov.

The site's Excel buttons are ASP.NET postbacks, not static file links. For each
export, this script GETs the results page, submits the current hidden form fields
and the race's export-button target, and saves the returned XLSX. It then writes
OpenElections-style county and precinct CSVs. Candidate parties, which are absent
from the workbooks, are read from the results page.

Usage (one race):
    uv run scripts/parse_electionresults.py \
        --race "United States Senator" \
        --county-out /tmp/sd_2026_senate_county.csv \
        --precinct-out /tmp/sd_2026_senate_precinct.csv \
        --download-dir /tmp/sd_2026_senate_exports

Repeat --race to select several races. Without --race, every race on --page-url
is exported. Use --list-races to see the available names. Existing output files
are not overwritten unless --force is supplied.

Only the Python standard library is required. Blank vote cells are interpreted
as zero, and duplicate county/precinct labels within a worksheet are summed.
Printed workbook totals are checked, and precinct sums are reconciled to the
county export before either CSV is written.
"""

import argparse
import csv
import re
import sys
import tempfile
from collections import defaultdict
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

DEFAULT_PAGE = "https://electionresults.sd.gov/resultsSW.aspx?type=SWR&map=CTY"
USER_AGENT = "OpenElections-SD-results-parser/1.0"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

PARTIES = {
    "": "",
    "democratic": "DEM",
    "democrat": "DEM",
    "republican": "REP",
    "libertarian": "LIB",
    "independent": "IND",
    "unaffiliated": "IND",
    "constitution": "CON",
    "nonpartisan": "",
    "no party affiliation": "NPA",
}


class ExportError(Exception):
    """An expected download or source-format error."""


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def name_key(value):
    return clean(value).casefold()


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:70].rstrip("-")


def normalize_office(title):
    """Return the OpenElections office and district for a statewide contest."""
    title = clean(title)
    if title.startswith("United States Senator"):
        return "U.S. Senate", ""
    if title.startswith("United States Representative"):
        return "U.S. House", "1"
    if title.startswith("Governor"):
        return "Governor", ""
    match = re.match(r"State Senator\s*-?\s*District\s+(\w+)", title)
    if match:
        return "State Senate", match.group(1)
    match = re.match(r"State Representative\s*-?\s*District\s+(\w+)", title)
    if match:
        return "State House", match.group(1)
    for pattern in (
        r"Constitutional Amendment [A-Z]+",
        r"Initiated Measure \d+",
        r"Referred Law \d+",
    ):
        match = re.match(pattern, title)
        if match:
            return match.group(0), ""
    return title, ""


def party_code(raw_party):
    party = name_key(raw_party)
    if party not in PARTIES:
        raise ExportError(f"Unrecognized candidate party: {raw_party!r}")
    return PARTIES[party]


class ResultsPageParser(HTMLParser):
    """Collect form state, race export targets, and candidate parties."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form_action = ""
        self.hidden = {}
        self.races = []
        self.race = None
        self.div_depth = 0
        self.candidate = None
        self.candidate_depth = None
        self.text_tag = None
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())

        if tag == "form" and attrs.get("id") == "form1":
            self.form_action = attrs.get("action", "")

        if tag == "input":
            if attrs.get("type", "").lower() == "hidden" and attrs.get("name"):
                self.hidden[attrs["name"]] = attrs.get("value", "")
            if self.race is not None and "export-button" in classes:
                level = {"county level": "county", "precinct level": "precinct"}.get(
                    name_key(attrs.get("value"))
                )
                onclick = attrs.get("onclick", "")
                match = re.search(r"__doPostBack\('([^']+)'", onclick)
                target = match.group(1) if match else attrs.get("name")
                if level and target:
                    self.race["exports"][level] = target
                    self.race["raceid"] = attrs.get("raceid", "")

        if tag == "div":
            if self.race is None:
                if {"wrapper-inside", "wrapper-border"}.issubset(classes):
                    self.race = {
                        "name": "",
                        "raceid": "",
                        "candidates": [],
                        "exports": {},
                    }
                    self.div_depth = 1
            else:
                self.div_depth += 1
                if "display-results-box-d" in classes:
                    self.candidate = {"name": "", "party": ""}
                    self.candidate_depth = self.div_depth

        if self.race is not None and tag in ("h1", "h2"):
            self.text_tag = tag
            self.text_parts = []

    def handle_data(self, data):
        if self.text_tag is not None:
            self.text_parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.text_tag:
            text = clean(" ".join(self.text_parts))
            if self.candidate is not None:
                if tag == "h1":
                    self.candidate["name"] = text
                elif tag == "h2":
                    self.candidate["party"] = text
            elif tag == "h1" and self.race is not None and not self.race["name"]:
                self.race["name"] = text
            self.text_tag = None
            self.text_parts = []

        if tag == "div" and self.race is not None:
            if self.candidate is not None and self.div_depth == self.candidate_depth:
                if self.candidate["name"]:
                    self.race["candidates"].append(self.candidate)
                self.candidate = None
                self.candidate_depth = None
            self.div_depth -= 1
            if self.div_depth == 0:
                if self.race["name"] and self.race["exports"]:
                    self.races.append(self.race)
                self.race = None
                self.candidate = None
                self.candidate_depth = None


def parse_results_page(html):
    parser = ResultsPageParser()
    parser.feed(html)
    if not parser.form_action:
        raise ExportError("Could not find the ASP.NET results form")
    return parser


def column_number(cell_reference):
    number = 0
    for char in cell_reference:
        if not char.isalpha():
            break
        number = number * 26 + ord(char.upper()) - ord("A") + 1
    if not number:
        raise ExportError(f"Invalid XLSX cell reference: {cell_reference!r}")
    return number


def workbook_sheets(path):
    """Yield (worksheet name, [(row number, {column number: value}), ...])."""
    with ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(node.itertext())
                for node in root.findall(f"{{{MAIN_NS}}}si")
            ]

        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))

        for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
            relationship_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
            target = targets[relationship_id]
            if target.startswith("/"):
                sheet_path = target.lstrip("/")
            else:
                sheet_path = str(PurePosixPath("xl") / target)
            root = ET.fromstring(archive.read(sheet_path))
            rows = []
            for row_number, row in enumerate(
                root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"), 1
            ):
                cells = {}
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    reference = cell.attrib.get("r", "")
                    column = column_number(reference)
                    kind = cell.attrib.get("t")
                    inline = cell.find(f"{{{MAIN_NS}}}is")
                    if inline is not None:
                        value = "".join(inline.itertext())
                    else:
                        node = cell.find(f"{{{MAIN_NS}}}v")
                        value = "" if node is None or node.text is None else node.text
                        if kind == "s" and value:
                            value = shared_strings[int(value)]
                    cells[column] = value
                rows.append((int(row.attrib.get("r", row_number)), cells))
            yield sheet.attrib["name"], rows


def parse_votes(value, context):
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        number = float(text)
    except ValueError as exc:
        raise ExportError(f"Non-numeric vote value at {context}: {value!r}") from exc
    if not number.is_integer() or number < 0:
        raise ExportError(f"Invalid vote value at {context}: {value!r}")
    return int(number)


def parse_table(rows, level, race, sheet_name):
    label = "County" if level == "county" else "Precinct"
    header_index = None
    label_column = None
    for index, (_, cells) in enumerate(rows):
        for column, value in cells.items():
            if name_key(value) == label.casefold():
                header_index = index
                label_column = column
                break
        if header_index is not None:
            break
    if header_index is None:
        raise ExportError(f"No {label!r} header in worksheet {sheet_name!r}")

    header = rows[header_index][1]
    office = clean(header.get(label_column - 1))
    if normalize_office(office) != normalize_office(race["name"]):
        raise ExportError(
            f"Wrong contest in worksheet {sheet_name!r}: {office!r} != {race['name']!r}"
        )

    party_lookup = {name_key(c["name"]): party_code(c["party"]) for c in race["candidates"]}
    candidates = []
    candidate_columns = []
    for column in sorted(header):
        if column <= label_column or not clean(header[column]):
            continue
        candidate = clean(header[column])
        key = name_key(candidate)
        if key not in party_lookup:
            raise ExportError(
                f"Candidate {candidate!r} in worksheet {sheet_name!r} is missing "
                f"from the {race['name']!r} results page"
            )
        if candidate in candidates:
            raise ExportError(f"Duplicate candidate {candidate!r} in {sheet_name!r}")
        candidates.append(candidate)
        candidate_columns.append(column)
    if not candidates:
        raise ExportError(f"No candidates found in worksheet {sheet_name!r}")

    records = {}
    sums = defaultdict(int)
    printed_totals = None
    for row_number, cells in rows[header_index + 1 :]:
        raw_label = clean(cells.get(label_column))
        if not raw_label:
            continue
        values = {
            candidate: parse_votes(
                cells.get(column), f"{sheet_name}!row {row_number}"
            )
            for candidate, column in zip(candidates, candidate_columns)
        }
        if raw_label.casefold() == "totals":
            printed_totals = values
            break
        output_label = clean_county(raw_label) if level == "county" else clean_precinct(raw_label)
        output_key = name_key(output_label)
        if output_key in records:
            print(
                f"  warning: summing duplicate {label.lower()} {output_label!r} "
                f"in worksheet {sheet_name!r}",
                file=sys.stderr,
            )
            for candidate, votes in values.items():
                records[output_key][1][candidate] += votes
        else:
            records[output_key] = (output_label, values)
        for candidate, votes in values.items():
            sums[candidate] += votes

    if printed_totals is None:
        raise ExportError(f"No TOTALS row in worksheet {sheet_name!r}")
    for candidate in candidates:
        if sums[candidate] != printed_totals[candidate]:
            raise ExportError(
                f"{sheet_name} / {candidate}: detail rows sum to {sums[candidate]}, "
                f"but TOTALS says {printed_totals[candidate]}"
            )

    return {
        "office": office,
        "candidates": [(candidate, party_lookup[name_key(candidate)]) for candidate in candidates],
        "records": list(records.values()),
    }


def clean_county(value):
    return clean(re.sub(r"\s*\(Vote Center\)\s*$", "", clean(value), flags=re.I))


def clean_precinct(value):
    value = re.sub(r"\bPrecinct[\s\-_]*(?=\d)", "", clean(value), flags=re.I)
    value = clean(value)
    return str(int(value)) if value.isdigit() else value


def parse_county_workbook(path, race):
    sheets = list(workbook_sheets(path))
    if len(sheets) != 1:
        raise ExportError(f"Expected one county worksheet in {path}, found {len(sheets)}")
    table = parse_table(sheets[0][1], "county", race, sheets[0][0])
    office, district = normalize_office(table["office"])
    output = []
    counts = {}
    for county, values in table["records"]:
        counts[county] = values
        for candidate, party in table["candidates"]:
            output.append({
                "county": county,
                "office": office,
                "district": district,
                "party": party,
                "candidate": candidate,
                "votes": values[candidate],
            })
    return output, counts


def parse_precinct_workbook(path, race):
    output = []
    counts = {}
    for sheet_name, sheet_rows in workbook_sheets(path):
        county = clean_county(sheet_name)
        if county in counts:
            raise ExportError(f"Duplicate county worksheet: {county}")
        table = parse_table(sheet_rows, "precinct", race, sheet_name)
        office, district = normalize_office(table["office"])
        county_counts = defaultdict(int)
        for precinct, values in table["records"]:
            for candidate, party in table["candidates"]:
                output.append({
                    "county": county,
                    "precinct": precinct,
                    "office": office,
                    "district": district,
                    "candidate": candidate,
                    "party": party,
                    "votes": values[candidate],
                })
                county_counts[candidate] += values[candidate]
        counts[county] = dict(county_counts)
    return output, counts


def reconcile_county_and_precinct(race_name, county_counts, precinct_counts):
    county_names = set(county_counts)
    precinct_county_names = set(precinct_counts)
    if county_names != precinct_county_names:
        raise ExportError(
            f"{race_name}: county/precinct county sets differ; "
            f"county-only={sorted(county_names - precinct_county_names)}, "
            f"precinct-only={sorted(precinct_county_names - county_names)}"
        )
    for county in sorted(county_names):
        county_values = county_counts[county]
        precinct_values = precinct_counts[county]
        candidates = set(county_values) | set(precinct_values)
        differences = [
            f"{candidate}: county={county_values.get(candidate, 0)}, "
            f"precinct={precinct_values.get(candidate, 0)}"
            for candidate in sorted(candidates)
            if county_values.get(candidate, 0) != precinct_values.get(candidate, 0)
        ]
        if differences:
            raise ExportError(f"{race_name} / {county}: " + "; ".join(differences))


def select_races(races, requested):
    if not requested:
        return races
    selected = []
    for requested_name in requested:
        matches = [race for race in races if name_key(race["name"]) == name_key(requested_name)]
        if len(matches) != 1:
            available = "\n  ".join(race["name"] for race in races)
            raise ExportError(
                f"Expected one race named {requested_name!r}, found {len(matches)}. "
                f"Available races:\n  {available}"
            )
        selected.append(matches[0])
    return selected


def download_export(opener, page_url, race, level, destination, timeout):
    """Use a fresh page/form for each export, then save the XLSX response."""
    request = Request(page_url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        html = response.read().decode(response.headers.get_content_charset() or "utf-8")
    page = parse_results_page(html)

    current_races = [
        item for item in page.races
        if race["raceid"] and item["raceid"] == race["raceid"]
    ]
    if len(current_races) != 1:
        current_races = [item for item in page.races if name_key(item["name"]) == name_key(race["name"])]
    if len(current_races) != 1 or level not in current_races[0]["exports"]:
        raise ExportError(f"Could not find the current {level} export button for {race['name']!r}")

    data = dict(page.hidden)
    data["__EVENTTARGET"] = current_races[0]["exports"][level]
    data["__EVENTARGUMENT"] = ""
    action = urljoin(page_url, page.form_action)
    request = Request(
        action,
        data=urlencode(data).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": page_url,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with opener.open(request, timeout=timeout) as response:
        content = response.read()
        content_type = response.headers.get_content_type()
    if not content.startswith(b"PK\x03\x04"):
        preview = content[:160].decode("utf-8", errors="replace")
        raise ExportError(
            f"{race['name']} {level} export was not XLSX "
            f"(Content-Type {content_type!r}): {preview!r}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def write_csv(path, fieldnames, rows, force):
    if path.exists() and not force:
        raise ExportError(f"Output exists: {path} (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--page-url", default=DEFAULT_PAGE, help="Statewide results page URL")
    parser.add_argument(
        "--race", action="append", default=[],
        help="Exact race name to export; repeat for multiple races (default: all)",
    )
    parser.add_argument("--county-out", type=Path, help="County CSV output path")
    parser.add_argument("--precinct-out", type=Path, help="Precinct CSV output path")
    parser.add_argument(
        "--download-dir", type=Path,
        help="Directory for source XLSX files (default: a new temporary directory)",
    )
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs/downloads")
    parser.add_argument("--list-races", action="store_true", help="List race names and exit")
    args = parser.parse_args()

    if not args.list_races and (not args.county_out or not args.precinct_out):
        parser.error("--county-out and --precinct-out are required unless --list-races is used")
    if args.county_out and args.precinct_out and args.county_out == args.precinct_out:
        parser.error("--county-out and --precinct-out must be different paths")
    if not args.force:
        for output_path in (args.county_out, args.precinct_out):
            if output_path is not None and output_path.exists():
                parser.error(f"output exists: {output_path} (use --force to overwrite)")

    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    try:
        request = Request(args.page_url, headers={"User-Agent": USER_AGENT})
        with opener.open(request, timeout=args.timeout) as response:
            html = response.read().decode(response.headers.get_content_charset() or "utf-8")
        page = parse_results_page(html)
        if args.list_races:
            for race in page.races:
                print(f"{race['raceid'] or '-':>8}  {race['name']}")
            return

        races = select_races(page.races, args.race)
        if not races:
            raise ExportError("No race export buttons found on the results page")
        download_root = args.download_dir or Path(tempfile.mkdtemp(prefix="sd_electionresults_"))
        print(f"Downloading {len(races)} race(s); XLSX directory: {download_root}")

        county_rows = []
        precinct_rows = []
        for race in races:
            slug = slugify(race["name"])
            if race["raceid"]:
                slug += "-" + slugify(race["raceid"])
            county_path = download_root / slug / "county" / "county.xlsx"
            precinct_path = download_root / slug / "precinct" / "precinct.xlsx"
            for path in (county_path, precinct_path):
                if path.exists() and not args.force:
                    raise ExportError(f"Download exists: {path} (use --force to overwrite)")

            print(f"  {race['name']}: downloading county export")
            download_export(opener, args.page_url, race, "county", county_path, args.timeout)
            print(f"  {race['name']}: downloading precinct export")
            download_export(opener, args.page_url, race, "precinct", precinct_path, args.timeout)

            current_county_rows, county_counts = parse_county_workbook(county_path, race)
            current_precinct_rows, precinct_counts = parse_precinct_workbook(precinct_path, race)
            reconcile_county_and_precinct(race["name"], county_counts, precinct_counts)
            county_rows.extend(current_county_rows)
            precinct_rows.extend(current_precinct_rows)
            print(
                f"  {race['name']}: validated {len(county_counts)} counties; "
                f"{len(current_county_rows)} county rows, "
                f"{len(current_precinct_rows)} precinct rows"
            )

        write_csv(
            args.county_out,
            ["county", "office", "district", "party", "candidate", "votes"],
            county_rows,
            args.force,
        )
        write_csv(
            args.precinct_out,
            ["county", "precinct", "office", "district", "candidate", "party", "votes"],
            precinct_rows,
            args.force,
        )
        print(f"Wrote {len(county_rows)} rows to {args.county_out}")
        print(f"Wrote {len(precinct_rows)} rows to {args.precinct_out}")
    except (ExportError, URLError, BadZipFile, ET.ParseError) as exc:
        sys.exit(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
