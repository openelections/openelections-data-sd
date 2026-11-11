#!/usr/bin/env python
"""Extract SD 2012 general legislature-by-precinct results (State Senate,
State House) and merge into the statewide precinct CSV.
Usage: leg_extract.py [out.csv [statewide_csv]]"""
import re, sys, csv, collections

PDF = '/Users/dwillis/code/openelections-sources-sd/2012/2012generalelectionslegislaturebyprecinct.pdf'
STATE_CSV = sys.argv[2] if len(sys.argv) > 2 else '/Users/dwillis/code/openelections-data-sd/2012/20121106__sd__general__precinct.csv'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/sd2012_staging/20121106__sd__general__precinct.csv'

COUNTY_FIX = {'Marchall': 'Marshall', 'Shannon': 'Oglala Lakota'}
COUNTIES = set()
with open('/Users/dwillis/code/openelections-data-sd/2022/20221108__sd__general__county.csv') as f:
    for r in csv.reader(f):
        if r and r[0] != 'county':
            COUNTIES.add(r[0])
ISSUES = []


def note(msg):
    ISSUES.append(msg)


INT_RE = re.compile(r'^(?:\d{1,3}(?:,\d{3})+|\d+)$')


def lines_of(page):
    ws = sorted(page.extract_words(), key=lambda w: (round(w['top']), w['x0']))
    raw, cur, curtop = [], [], None
    for w in ws:
        if curtop is None or w['top'] - curtop <= 3.5:
            cur.append(w)
            if curtop is None:
                curtop = w['top']
        else:
            raw.append(cur)
            cur, curtop = [w], w['top']
    if cur:
        raw.append(cur)
    return [dict(text=' '.join(w['text'] for w in ln), words=sorted(ln, key=lambda w: w['x0']),
                 top=min(w['top'] for w in ln)) for ln in raw if ln]


def is_int(w):
    return bool(INT_RE.match(w['text']))


def clean_label(txt):
    txt = re.sub(r'\s+', ' ', re.sub(r'\s*\(.*$', '', txt)).strip()
    return re.sub(r'^#+', '', txt).strip()


def main():
    import pdfplumber
    pdf = pdfplumber.open(PDF)
    page_data = []
    for pi, page in enumerate(pdf.pages):
        lines = lines_of(page)
        title = county_name = header = None
        for i, l in enumerate(lines):
            t = l['text']
            if title is None:
                m = re.match(r'State (Senator|Representative) - (\S+) \(South Dakota\)$', t)
                if m:
                    title = (m.group(1), m.group(2))
                    continue
            if title and county_name is None:
                m = re.match(r'^([A-Z][a-zA-Z .]+?) County$', t)
                if m:
                    nm = COUNTY_FIX.get(m.group(1), m.group(1))
                    if nm in COUNTIES:
                        county_name = nm
                        continue
                    note(f"p{pi+1}: unknown county '{m.group(1)}'")
                    continue
                plain = re.match(r'^([A-Z][a-z]+(?: [A-Z][a-zA-Z ]+)?)$', t)
                nm = COUNTY_FIX.get(plain.group(1), plain.group(1)) if plain else None
                if nm and nm in COUNTIES:
                    county_name = nm
                    continue
            if title and l['words'][0]['text'] == 'Precinct' and len(l['words']) > 2 \
                    and any(w['text'] == 'TOTALS' for w in l['words']):
                header = i
                break
        ch, dist = title
        page_data.append(dict(pi=pi, ch=ch, dist=dist, county=county_name, header=header,
                              lines=lines))

    def labels_of(pd):
        out = []
        for l in pd['lines'][pd['header'] + 1:]:
            w0 = l['words'][0]
            if w0['x0'] > 65 or l['text'].startswith(('TOTAL', 'Results')):
                continue
            words = l['words']
            li = len(words) - 1
            while li >= 1 and is_int(words[li]) and words[li]['x0'] > 90:
                li -= 1
            lab = clean_label(' '.join(w['text'] for w in words[:li + 1]))
            if lab:
                out.append(lab)
        return set(out) - {''}

    for pd in page_data:
        if pd['county']:
            continue
        labs = labels_of(pd)
        best = None
        for other in page_data:
            if other['county'] and other is not pd:
                ol = labels_of(other)
                if ol and labs:
                    inter = len(ol & labs)
                    score = inter / max(1, len(ol | labs))
                    if score > 0.5 and (best is None or inter > best[0]):
                        best = (inter, other['county'])
        if best:
            note(f"p{pd['pi']+1} {pd['ch']} {pd['dist']}: county inferred as {best[1]}")
            pd['county'] = best[1]
        else:
            note(f"p{pd['pi']+1} {pd['ch']} {pd['dist']}: county UNKNOWN")

    outrows = []
    for pd in page_data:
        pi, ch, dist = pd['pi'], pd['ch'], pd['dist']
        county_name = pd['county']
        lines = pd['lines']
        header = pd['header']
        # value columns
        prow = []
        total_row = None
        footer = len(lines)
        for k, l in enumerate(lines[header + 1:], header + 1):
            t = l['text']
            if t.startswith('Results provided'):
                footer = k
                break
            w0 = l['words'][0]
            if w0['x0'] > 65:
                continue
            if t.startswith('TOTAL'):
                total_row = [int(w['text'].replace(',', '')) for w in l['words'][1:] if is_int(w)]
                continue
            words = l['words']
            li = len(words) - 1
            while li >= 1 and is_int(words[li]) and words[li]['x0'] > 90:
                li -= 1
            labwords = words[:li + 1]
            prow.append(dict(pi=pi, top=l['top'],
                             label=clean_label(' '.join(w['text'] for w in labwords)),
                             lastword=labwords[-1] if labwords else None,
                             labwords=labwords, nums_w=words[li + 1:], strays=[]))
        xs = sorted(w['x0'] for r in prow for w in r['nums_w'])
        cl = []
        for x in xs:
            if cl and x - cl[-1][-1] <= 10:
                cl[-1].append(x)
            else:
                cl.append([x])
        colx = [sum(v) / len(v) for v in cl]
        # candidate names: header always lists `Total column` last; split header
        # words into (number of value columns - 1) groups at the largest word gaps
        ws = [w for w in lines[header]['words'][1:] if w['text'] != 'TOTALS']
        gaps = []
        for k in range(1, len(ws)):
            gaps.append((ws[k]['x0'] - ws[k - 1]['x1'], k))
        if not any(w['text'] == 'TOTALS' for w in lines[header]['words']):
            note(f"p{pi+1} {ch} {dist} ({county_name}): header lacks TOTALS")
        has_tot = True
        nc = max(1, len(colx) - 1)
        separators = sorted(k for g, k in sorted(gaps, reverse=True)[:max(0, nc - 1)])
        names, start = [], 0
        for sep in separators + [len(ws)]:
            nm = ' '.join(w['text'] for w in ws[start:sep]).strip()
            names.append(re.sub(r'(?<=[A-Za-z])\"(?=[A-Za-z])', "'", nm))
            start = sep
        if len(names) != nc:
            note(f"p{pi+1} {ch} {dist} ({county_name}): split into {len(names)} names "
                 f"{names} vs nc={nc}")
        sums, grand = [0] * nc, 0
        for r in prow:
            r['vals'] = [None] * (nc + 1)
            vals = {}
            for w in r['nums_w']:
                if w['x0'] < min(colx) - 16:
                    r['strays'].append(int(w['text'].replace(',', '')))
                    continue
                best = min(range(len(colx)), key=lambda i: abs(colx[i] - w['x0']))
                if abs(colx[best] - w['x0']) <= 14 and best not in vals:
                    vals[best] = int(w['text'].replace(',', ''))
                else:
                    r['strays'].append(int(w['text'].replace(',', '')))
            if len(vals) < len(colx) and r['lastword'] is not None:
                m = re.search(r'^(.+?\D)(\d+)$', r['lastword']['text'])
                if m:
                    miss = sorted(set(range(len(colx))) - set(vals))
                    vals[miss[0]] = int(m.group(2))
                    lw = r['lastword']
                    r['labwords'] = r['labwords'][:-1] + [dict(text=m.group(1), x0=lw['x0'], x1=lw['x1'], top=lw['top'])]
                    r['label'] = clean_label(' '.join(w['text'] for w in r['labwords']))
                    note(f"p{pi+1} {ch} {dist} '{r['label']}': glued value {m.group(2)}")
            for i in range(len(colx)):
                r['vals'][i] = vals.get(i)
        for i, r in enumerate(prow):
            for sv in list(r['strays']):
                for j in (i + 1, i - 1):
                    if not (0 <= j < len(prow)):
                        continue
                    o = prow[j]
                    if o['vals'][nc] is not None and all(v is not None for v in o['vals'][:nc]) \
                            and sum(o['vals'][:nc]) == sv:
                        o['vals'][nc] = sv
                        r['strays'].remove(sv)
                        note(f"p{pi+1} {ch} {dist} '{o['label']}': repaired stray total {sv}")
                        break
        for r in prow:
            cs = r['vals'][:nc]
            if any(v is None for v in cs):
                note(f"p{pi+1} {ch} {dist} ({county_name}) '{r['label']}': missing values {r['vals']}")
            if has_tot and r['vals'][nc] is not None and all(v is not None for v in cs):
                if sum(cs) != r['vals'][nc]:
                    note(f"p{pi+1} {ch} {dist} ({county_name}) '{r['label']}': row sum {sum(cs)} != total {r['vals'][nc]}")
            for i, v in enumerate(cs):
                if v is not None:
                    sums[i] += v
            if r['vals'][nc] is not None:
                grand += r['vals'][nc]
        if total_row:
            if has_tot and len(total_row) == nc + 1:
                if total_row[:nc] != sums:
                    note(f"p{pi+1} {ch} {dist} ({county_name}): TOTAL cands mismatch: {total_row[:nc]} != {sums}")
                if total_row[nc] != grand:
                    note(f"p{pi+1} {ch} {dist} ({county_name}): TOTAL grand {total_row[nc]} != {grand}")
            elif len(total_row) == nc:
                if total_row != sums:
                    note(f"p{pi+1} {ch} {dist} ({county_name}): TOTAL {total_row} != sums {sums}")
            else:
                note(f"p{pi+1} {ch} {dist}: TOTAL row shape {total_row} cands={nc}")
        else:
            note(f"p{pi+1} {ch} {dist} ({county_name}): no TOTAL row ({len(prow)} rows)")
        dist2 = dist.zfill(2) if dist.isdigit() else dist
        office = 'State Senate' if ch == 'Senator' else 'State House'
        for r in prow:
            for i, n in enumerate(names):
                v = r['vals'][i]
                if v is not None:
                    outrows.append((county_name, dist2, office, r['label'], i, n, v))

    # ---- merge with statewide csv
    with open(STATE_CSV) as f:
        base = list(csv.reader(f))
    hdr = base[0]
    leg_rows = []
    for county, dist2, office, lab, i, n, v in outrows:
        party = party_for(office, dist2, n)
        if not party:
            note(f"no party for {office}/{dist2}/{n}")
        leg_rows.append([county, lab, office, dist2, n, party, v])
    by_county = collections.defaultdict(list)
    for r in leg_rows:
        by_county[r[0]].append(r)
    merged = [hdr]
    seen = set()
    for r in base[1:]:
        merged.append(r)
        if r[0] not in seen:
            seen.add(r[0])
            merged.extend(by_county.pop(r[0], []))
    for c, rows in sorted(by_county.items()):
        note(f"county {c} not present in statewide csv: {len(rows)} rows appended at end")
        merged.extend(rows)
    with open(OUT, 'w', newline='') as f:
        csv.writer(f).writerows(merged)
    print(f'{len(outrows)} legislature data rows; merged file: {len(merged)-1} rows -> {OUT}')
    print(f'{len(ISSUES)} issues:')
    for i in ISSUES:
        print(' -', i)


# from SD SOS "2012 Statewide Candidate List" (sdsos.gov, 2012SDGeneralCandidates.pdf)
SOS_CANDS = {
    ('State House', '01'): [('D', 'Susan Wismer'), ('D', 'Dennis A. Feickert')],
    ('State House', '02'): [('D', 'Dennis E. Nemmers'), ('D', 'Danny Miles'), ('R', 'Brock L. Greenfield'), ('R', 'Burt E. Tulson')],
    ('State House', '03'): [('D', 'Zachary Anderson'), ('D', 'Bill Antonides'), ('R', 'David Novstrup'), ('R', 'Dan Kaiser')],
    ('State House', '04'): [('D', 'Kathy Tyler'), ('D', 'Jim Peterson'), ('R', 'Fred Deutsch'), ('R', 'James E. Gilkerson')],
    ('State House', '05'): [('D', 'Dorothy Kellogg'), ('R', 'Melissa Magstadt'), ('R', 'Roger Solum')],
    ('State House', '06'): [('D', 'Michael Christopher Jauron'), ('D', 'Joseph Weis'), ('R', 'Herman Otten'), ('R', 'Isaac Latterell')],
    ('State House', '07'): [('D', 'Spencer Hawley'), ('D', 'Linda A. Brandt'), ('R', 'Brian Roehrich'), ('R', 'Scott Munsterman')],
    ('State House', '08'): [('D', 'Scott Parsley'), ('D', 'Roy J. Lindsay'), ('R', 'Gene E. Kroger'), ('R', 'Leslie J. Heinemann')],
    ('State House', '09'): [('D', 'Paula Hawks'), ('D', 'Mark Anderson'), ('R', 'Steve Hickey'), ('R', 'Bob Deelstra')],
    ('State House', '10'): [('D', 'Jo Hausman'), ('D', 'Brian Parsons'), ('R', 'Jenna Haggar'), ('R', 'Don Haggar')],
    ('State House', '11'): [('D', 'Darrell D. Solberg'), ('D', 'Jim Larson'), ('R', 'Jim Stalzer'), ('R', 'Christine M. Erickson')],
    ('State House', '12'): [('D', 'Susan M. Randall'), ('D', 'Mike Knudson'), ('R', 'Manny Steele'), ('R', 'Hal Wick')],
    ('State House', '13'): [('R', 'G. Mark Mickelson'), ('R', 'Steve Westra')],
    ('State House', '14'): [('D', 'Marc S. Feinstein'), ('D', 'Jeff Winters'), ('R', 'Anne C. Hajek'), ('R', 'Larry P. Zikmund')],
    ('State House', '15'): [('D', 'Karen L. Soli'), ('D', 'Patrick A. Kirschman')],
    ('State House', '16'): [('D', 'Ann Tornberg'), ('D', 'Stanley Jacobson'), ('R', 'Jim Bolin'), ('R', 'Patty Miller')],
    ('State House', '17'): [('D', 'Marion Sorlien'), ('D', 'Ray Ring'), ('R', 'Nancy Rasmussen')],
    ('State House', '18'): [('D', 'Charlie Gross'), ('D', 'Bernie Hunhoff'), ('R', 'Mike Stevens'), ('R', 'Thomas D. Stotz')],
    ('State House', '19'): [('D', 'Alan Fenner'), ('R', 'Kyle Schoenfish'), ('R', 'Stace Nelson')],
    ('State House', '20'): [('D', 'Dave Mitchell'), ('D', 'James V. Schorzmann'), ('R', 'Lance Carson'), ('R', 'Tona Rozum')],
    ('State House', '21'): [('D', 'Julie Bartling'), ('D', 'Gary W. Coleman'), ('R', 'Dave Scott'), ('R', 'Lee Qualm')],
    ('State House', '22'): [('D', 'Dale Hargens'), ('D', 'Peggy Gibson'), ('R', 'Dick Werner'), ('R', 'Jay B.K. Slater')],
    ('State House', '23'): [('R', 'Justin R. Cronin'), ('R', 'Charles B. Hoffman')],
    ('State House', '24'): [('R', 'Tim Rounds'), ('R', 'Mary Duvall')],
    ('State House', '25'): [('D', 'Bill Laird'), ('D', 'Janelle Smedsrud'), ('R', 'Jon Hansen'), ('R', 'Scott W. Ecklund')],
    ('State House', '26A'): [('D', 'Troy Heinert')],
    ('State House', '26B'): [('D', 'Maynard J. Konechne'), ('R', 'James Schaefer')],
    ('State House', '27'): [('D', 'Kevin Killer'), ('I', 'Kathleen Ann'), ('R', 'Elizabeth May')],
    ('State House', '28A'): [('D', 'Dean Schrempp')],
    ('State House', '28B'): [('R', 'Betty Olson')],
    ('State House', '29'): [('R', 'Gary L. Cammack'), ('R', 'Dean Wink')],
    ('State House', '30'): [('R', 'Mike Verchio'), ('R', 'Lance Russell')],
    ('State House', '31'): [('R', 'Timothy R. Johns'), ('R', 'Fred W. Romkema')],
    ('State House', '32'): [('D', 'Jackie Swanson'), ('R', 'Kristin Conzet'), ('R', 'Brian Gosch')],
    ('State House', '33'): [('D', 'Robin A. Page'), ('R', 'Jacqueline Sly'), ('R', 'Scott W. Craig')],
    ('State House', '34'): [('D', 'John C. Willman'), ('I', 'Mike Reardon'), ('R', 'Dan Dryden'), ('R', 'David Lust')],
    ('State House', '35'): [('D', 'Jay Pond'), ('D', 'Shane Liebig'), ('R', 'Don Kopp'), ('R', 'Blaine "Chip" Campbell')],
    ('State Senate', '01'): [('D', 'Jason Frerichs')],
    ('State Senate', '02'): [('D', 'Chuck Welke'), ('R', 'Art Fryslie')],
    ('State Senate', '03'): [('D', 'H. Paul Dennert'), ('R', 'Al Novstrup')],
    ('State Senate', '04'): [('D', 'Steven Street'), ('R', 'Tim Begalka')],
    ('State Senate', '05'): [('D', 'Jeff Dunn'), ('R', 'Ried Holien')],
    ('State Senate', '06'): [('D', 'Richard Schriever'), ('R', 'Ernie Otten Jr.')],
    ('State Senate', '07'): [('D', 'Pamela Merchant'), ('R', 'Larry Tidemann')],
    ('State Senate', '08'): [('D', 'Charles J. Johnson'), ('R', 'Russell Olson')],
    ('State Senate', '09'): [('R', 'Deb Peters')],
    ('State Senate', '10'): [('D', 'Paul A. Thompson'), ('R', 'Shantel Krebs')],
    ('State Senate', '11'): [('D', 'Tom Cool'), ('R', 'David M. Omdahl')],
    ('State Senate', '12'): [('D', 'Kent Alberty'), ('R', 'Mark Johnston')],
    ('State Senate', '13'): [('D', 'Sam Khoroosi'), ('R', 'Phyllis M. Heineman')],
    ('State Senate', '14'): [('D', 'Brian Kaatz'), ('R', 'Deb Soholt')],
    ('State Senate', '15'): [('D', 'Angie Buhl'), ('I', 'Kathy Miles')],
    ('State Senate', '16'): [('D', "Michael O'Connor"), ('R', 'Dan Lederman')],
    ('State Senate', '17'): [('D', 'Tom Jones'), ('R', 'John S. Chicoine')],
    ('State Senate', '18'): [('D', 'David L. Allen'), ('R', 'Jean M. Hunhoff')],
    ('State Senate', '19'): [('D', 'Frank J. Kloucek'), ('R', 'Bill Van Gerpen')],
    ('State Senate', '20'): [('D', 'Quinten L. Burg'), ('R', 'Mike Vehle')],
    ('State Senate', '21'): [('D', 'Billie H. Sutton'), ('R', 'John S Meyer')],
    ('State Senate', '22'): [('D', 'Chris Studer'), ('R', 'Jim White')],
    ('State Senate', '23'): [('R', 'Corey Brown')],
    ('State Senate', '24'): [('R', 'Jeff Monroe')],
    ('State Senate', '25'): [('D', 'Dan Ahlers'), ('R', 'Tim Rave')],
    ('State Senate', '26'): [('D', 'Larry J. Lucas'), ('R', 'Kent Juhnke')],
    ('State Senate', '27'): [('D', 'Jim Bradford')],
    ('State Senate', '28'): [('R', 'Ryan M. Maher')],
    ('State Senate', '29'): [('R', 'Larry Rhoden')],
    ('State Senate', '30'): [('R', 'Bruce Rampelberg')],
    ('State Senate', '31'): [('R', 'Bob Ewing')],
    ('State Senate', '32'): [('R', 'Stan Adelstein')],
    ('State Senate', '33'): [('I', 'Matt McGrath'), ('R', 'Phil Jensen')],
    ('State Senate', '34'): [('R', 'Craig Tieszen')],
    ('State Senate', '35'): [('R', 'Mark Kirkeby')],
}
CODE = {'DEM': 'DEM', 'D': 'DEM', 'Republican': 'REP', 'R': 'REP', 'Independent': 'IND', 'I': 'IND',
        'Constitution': 'CON', 'Libertarian': 'LIB'}


def normalize_name(s):
    s = s.replace('“', '"').replace('”', '"').replace('O"', "O'")
    s = ' '.join(t for t in s.strip().split() if t not in ('Jr.', 'Sr.', 'JR', 'SR'))
    return s


def party_for(office, dist, display):
    dt = normalize_name(display).split()
    matches = [e for e in SOS_CANDS.get((office, dist), [])
               if normalize_name(e[1]).split()[-1] == dt[-1]]
    if len(matches) > 1:
        first = [e for e in matches if normalize_name(e[1]).split()[0] == dt[0]]
        if len(first) == 1:
            matches = first
    if len(matches) == 1:
        return CODE[matches[0][0]]
    return None


PARTY_MAP_STATIC = True

if __name__ == '__main__':
    main()
