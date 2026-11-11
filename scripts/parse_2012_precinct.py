#!/usr/bin/env python
"""Extract SD 2012 general election statewide-by-precinct results (President,
U.S. House, PUC 6-yr, PUC 4-yr) from the SOS PDF into long-form CSV.

Layout quirks handled:
- tables continue across pages without repeating titles/headers
- a section can start mid-page with no title/header (label list restarts)
- TOTALS columns sometimes printed as separate "spill" pages (aligned by y)
- a stray total value can land on the end of the previous data line
Validation: row totals, section TOTAL rows, spilled columns per row.
"""
import re, csv, collections, sys

PDF = '/Users/dwillis/code/openelections-sources-sd/2012/2012generalelectionsstatewidecandidatesbyprecint.pdf'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/sd2012_staging/20121106__sd__general__precinct.csv'
INT_RE = re.compile(r'^(?:\d{1,3}(?:,\d{3})+|\d+)$')

# office -> (title-matcher, [(candidate, party), ...])
CONTESTS = [
    ('President', lambda t: t.startswith('Presidential Electors'),
     [('Barack Obama and Joe Biden', 'DEM'), ('Mitt Romney and Paul Ryan', 'REP'),
      ('Gary Johnson and James P. Gray', 'LIB'), ('Virgil Goode and Jim Clymer', 'CON')]),
    ('U.S. House', lambda t: t.startswith('United States Representative'),
     [('Kristi Noem', 'REP'), ('Matt Varilek', 'DEM')]),
    ('Public Utilities Commissioner (6-year term)', lambda t: t.startswith('Public Utilities Commissioner') and '6' in t,
     [('Kristie Fiegen', 'REP'), ('Matt McGovern', 'DEM'), ('Russell Clarke', 'LIB')]),
    ('Public Utilities Commissioner (4-year term)', lambda t: t.startswith('Public Utilities Commissioner') and '4' in t,
     [('Nick Nemec', 'DEM'), ('Chris Nelson', 'REP')]),
]
OFFICES = [c[0] for c in CONTESTS]
ISSUES = []


def note(msg):
    ISSUES.append(msg)


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


class Section:
    def __init__(self, county, office, cands):
        self.county = county
        self.office = office
        self.cands = cands
        self.rows = []            # dict(precinct, page, top, values=list, strays=[])
        self.seen = set()
        self.tr = None            # dict(page, tvals=[ints], raw=text)
        self.has_t = False        # header TOTALS word seen for latest run
        self.done = False


class C:
    def __init__(self, name):
        self.name = name
        self.sections = []        # in office order
        self.spill = []


COUNTY_RENAME = {'Shannon': 'Oglala Lakota'}

def clean_label(words):
    txt = ' '.join(w['text'] for w in words).strip()
    txt = re.sub(r'\s*\(.*$', '', txt)      # drop location parens
    txt = re.sub(r'^#+', '', txt).strip()
    return txt


def parse():
    import pdfplumber
    pdf = pdfplumber.open(PDF)
    pages = [lines_of(p) for p in pdf.pages]

    counties, cur, sec, run = [], None, None, None

    def flush():
        nonlocal run
        if run is None:
            return
        s, page = run['sec'], run['page']
        rows = run['rows']
        run = None
        if not rows:
            return
        nc = len(s.cands)
        # infer columns from value x positions
        xs = sorted(w['x0'] for r in rows for w in r['nums'] if w['x0'] > 90)
        if not xs:
            for r in rows:
                s.rows.append(dict(precinct=r['label'], page=page, top=r['top'],
                                   values=[None] * (nc + 1), strays=[]))
            note(f"p{page} {s.county}/{s.office}: rows with no values")
            return
        cl = []
        for x in xs:
            if cl and x - cl[-1][-1] <= 10:
                cl[-1].append(x)
            else:
                cl.append([x])
        colx = [sum(v) / len(v) for v in cl]
        expect = {nc, nc + 1}
        if len(colx) not in expect:
            note(f"p{page} {s.county}/{s.office}: {len(colx)} value columns "
                 f"{[round(x) for x in colx]}, cands={nc}")
        has_tot = len(colx) == nc + 1
        mainx = colx[:nc + 1]           # values beyond the totals column are strays
        for r in rows:
            vals, strays = {}, []
            for w in r['nums']:
                if w['x0'] <= 90:
                    continue
                if mainx and w['x0'] < min(mainx) - 16:
                    strays.append(w)
                    continue
                best = min(range(len(mainx) or 1), key=lambda i: abs(mainx[i] - w['x0'])) if mainx else None
                if best is not None and abs(mainx[best] - w['x0']) <= 14 and best not in vals:
                    vals[best] = int(w['text'].replace(',', ''))
                else:
                    strays.append(w)
            if len(vals) < len(mainx) and r['lastword'] is not None:
                m = re.search(r'^(.+?\D)(\d+)$', r['lastword']['text'])
                if m:
                    miss = sorted(set(range(len(mainx))) - set(vals))
                    vals[miss[0]] = int(m.group(2))
                    lw = r['lastword']
                    r['labwords'] = r['labwords'][:-1] + [
                        dict(text=m.group(1), x0=lw['x0'], x1=lw['x1'], top=lw['top'])]
                    r['label'] = clean_label(r['labwords'])
                    note(f"p{page} {s.county}/{s.office} '{r['label']}': glued value {m.group(2)}")
            values = [vals.get(i) for i in range(nc + 1)]
            s.rows.append(dict(precinct=r['label'], page=page, top=r['top'],
                               values=values, strays=[int(w['text'].replace(',', '')) for w in strays]))

    def new_section(office):
        nonlocal sec
        cands = next(cl for o, m, cl in CONTESTS if o == office)
        sec = Section(cur.name, office, cands)
        cur.sections.append(sec)
        return sec

    for pi, lines in enumerate(pages):
        texts = [l['text'].strip() for l in lines]
        tidx = [i for i, t in enumerate(texts) if t.startswith('2012 General Election')]
        spilled = not tidx and all(
            all(is_int(w) or w['text'] == 'TOTALS' for w in l['words'])
            for l in lines if l['text'].strip())
        if tidx:
            flush()
            if cur:
                counties.append(cur)
            prev = texts[tidx[0] - 1] if tidx[0] > 0 else ''
            cur = C(COUNTY_RENAME.get(prev.replace(' County', '').strip(), prev.replace(' County', '').strip()))
            sec = None
            lines = lines[tidx[0] + 1:]
        elif spilled and cur is not None:
            flush()
            cur.spill.extend(dict(page=pi, top=l['top'], x=w['x0'],
                                  val=int(w['text'].replace(',', '')))
                             for l in lines for w in l['words'] if is_int(w))
            continue
        for l in lines:
            t = l['text'].strip()
            if not t or t.startswith('Results provided by'):
                flush()
                continue
            w0 = l['words'][0]
            off = next((o for o, m, _ in CONTESTS if m(t)), None)
            if off:
                flush()
                s = next((x for x in cur.sections if x.office == off and not x.done), None)
                sec = s if s else new_section(off)
                continue
            if w0['text'].startswith('Precinct') and len(l['words']) > 2:
                flush()
                if sec is None:
                    note(f"p{pi}: header before any section")
                    continue
                ws = l['words']
                if any(w['text'] == 'TOTALS' for w in ws):
                    tx = next(w['x0'] for w in ws if w['text'] == 'TOTALS')
                    sec.has_t = True
                    run = dict(page=pi, sec=sec, colx=None, totx=tx, rows=[])
                else:
                    sec.has_t = False
                    run = dict(page=pi, sec=sec, colx=None, totx=None, rows=[])
                continue
            if t.startswith('TOTAL'):
                flush()
                if sec is None:
                    note(f"p{pi}: TOTAL row with no section")
                    continue
                tv = [int(w['text'].replace(',', '')) for w in l['words'][1:] if is_int(w)]
                if sec.tr:
                    note(f"{sec.county}/{sec.office}: second TOTAL row {tv} p{pi}")
                else:
                    sec.tr = dict(page=pi, tvals=tv)
                continue
            if w0['x0'] < 65:
                words = l['words']
                li = len(words) - 1
                while li >= 1 and is_int(words[li]) and words[li]['x0'] > 90:
                    li -= 1
                numwords = words[li + 1:]
                labwords = words[:li + 1]
                if sec is None:
                    note(f"p{pi}: data row before any section: {t[:60]}")
                    continue
                label = clean_label(labwords)
                if label in sec.seen:
                    # precinct list restarted: this is the next contest's table
                    flush()
                    note(f"p{pi} restart: label '{label}' seen again in {sec.county}/{sec.office}")
                    nxt = None
                    for o in OFFICES:
                        if o in [x.office for x in cur.sections]:
                            continue
                        nxt = o
                        break
                    if nxt is None:
                        note(f"p{pi} {label}: duplicate label, no next office")
                        nxt = sec.office
                    sec = new_section(nxt)
                # run for this section/page
                if run is None or run['sec'] is not sec or run['page'] != pi:
                    flush()
                    run = dict(page=pi, sec=sec, colx=None, totx=None, rows=[])
                sec.seen.add(label)
                run['rows'].append(dict(labwords=labwords, lastword=labwords[-1] if labwords else None,
                                        top=l['top'], nums=numwords, label=label))
                continue
        flush()
    if cur:
        counties.append(cur)
    return counties


def total_of(vals):
    return sum(v for v in vals if v is not None)


def validate_and_repair(counties):
    # detect foreign table copies (the source PDF sometimes duplicates the
    # previous county's table for an office, replacing the county's own rows)
    for cx in counties:
        for s in cx.sections:
            s.labels = [r['precinct'] for r in s.rows]
        sets = [frozenset(s.labels) for s in cx.sections if s.labels]
        if len(sets) < 2:
            continue
        majority = max(sets, key=lambda fs: sum(len(fs & g) for g in sets))
        if not majority:
            continue
        for s in cx.sections:
            if frozenset(s.labels) & majority or not s.labels:
                continue
            donor = None
            for other in counties:
                if other is cx:
                    continue
                d = next((o for o in other.sections if o.office == s.office), None)
                if d and frozenset(d.labels) == frozenset(s.labels):
                    donor = d
                    break
            if donor:
                note(f"{cx.name}/{s.office}: source defect - table is a copy of {donor.county}'s "
                     f"({len(s.rows)} rows); county's own rows absent from PDF")
                s.rows = []
                s.tr = None
                s.sums = s.grand = s.rtotal = None
                s.foreign = True
            else:
                note(f"{cx.name}/{s.office}: labels differ from county norm "
                     f"({sorted(s.labels)[:5]}...) vs {sorted(majority)[:5]}...")

    # stray totals: a value printed at the end of the previous line
    for cx in counties:
        for s in cx.sections:
            for i, r in enumerate(s.rows):
                for sv in list(r['strays']):
                    for j in (i + 1, i - 1):
                        if not (0 <= j < len(s.rows)):
                            continue
                        o = s.rows[j]
                        cs = o['values'][:len(s.cands)]
                        if cs and all(v is not None for v in cs) and total_of(cs) == sv \
                                and (len(o['values']) <= len(s.cands) or o['values'][len(s.cands)] is None):
                            o['values'] = cs + [sv]
                            r['strays'].remove(sv)
                            note(f"{s.county}/{s.office} '{o['precinct']}': repaired stray total {sv}")
                            break

    for cx in counties:
        for s in cx.sections:
            nc = len(s.cands)
            sums, grand = [0] * nc, 0
            ntot = 0
            for r in s.rows:
                cs = r['values'][:nc]
                if any(v is None for v in cs):
                    if r['values'][nc] is None or any(v is None for v in cs):
                        note(f"{s.county}/{s.office} '{r['precinct']}': missing value(s) {r['values']}")
                tot = r['values'][nc]
                if tot is not None and all(v is not None for v in cs):
                    if sum(cs) != tot:
                        note(f"{s.county}/{s.office} '{r['precinct']}': row sum {sum(cs)} != total {tot}")
                    else:
                        ntot += 1
                for i, v in enumerate(cs):
                    if v is not None:
                        sums[i] += v
                        grand += v
            rtotal = None
            if s.tr:
                tv = s.tr['tvals']
                if len(tv) == nc + 1:
                    if tv[:nc] != sums:
                        bad = [i for i in range(nc) if tv[i] != sums[i]]
                        note(f"{s.county}/{s.office}: TOTAL row {[tv[i] for i in bad]} != col sums {[sums[i] for i in bad]}")
                    rtotal = tv[nc]
                    if rtotal != grand:
                        note(f"{s.county}/{s.office}: TOTAL grand {rtotal} != row sum {grand} "
                             f"(rows={len(s.rows)})")
                elif len(tv) == nc:
                    # candidate-sum TOTAL row (grand total spills to its own page)
                    if tv != sums:
                        note(f"{s.county}/{s.office}: TOTAL row {tv} != col sums {sums}")
                    rtotal = None
                elif len(tv) == 1:
                    rtotal = tv[0]
                    if rtotal != grand:
                        note(f"{s.county}/{s.office}: TOTAL {rtotal} != col sums {sums}/{grand}")
                else:
                    note(f"{s.county}/{s.office}: TOTAL row shape {tv} cands={nc}")
            s.sums, s.grand = sums, grand
            s.rtotal = rtotal

    # spilled TOTALS columns
    for cx in counties:
        if not cx.spill:
            continue
        cols = collections.defaultdict(list)
        for sp in cx.spill:
            cols[(round(sp['x'] / 12),)].append(sp)
        for key, col in cols.items():
            col.sort(key=lambda sp: sp['top'])
            best = None
            for s in cx.sections:
                if s.has_t and s.rtotal is not None:
                    continue
                rows = [r for r in s.rows if r['values'][len(s.cands)] is None
                        and all(v is not None for v in r['values'][:len(s.cands)])]
                if not rows:
                    continue
                pages = {r['page'] for r in rows}
                for pg in pages:
                    pgrows = [r for r in rows if r['page'] == pg]
                    hits = sum(1 for r in pgrows if any(abs(r['top'] - sp['top']) <= 2 for sp in col))
                    ok = sum(1 for r in pgrows if any(
                        abs(r['top'] - sp['top']) <= 2 and total_of(r['values'][:len(s.cands)]) == sp['val']
                        for sp in col))
                    if ok and best is None or ok and ok > best[0]:
                        best = (ok, s, pg, pgrows, col)
            if best is None:
                note(f"SPILL {cx.name}: unmatched column ({len(col)} values) "
                     f"{[sp['val'] for sp in col]}")
                continue
            _, s, pg, pgrows, col = best
            s.spill_matched = True
            match, left = 0, []
            for sp in col:
                r = next((r for r in pgrows if abs(r['top'] - sp['top']) <= 2), None)
                if r is None:
                    left.append(sp)
                    continue
                cs = r['values'][:len(s.cands)]
                if total_of(cs) != sp['val']:
                    note(f"SPILL {cx.name}/{s.office} '{r['precinct']}': {sp['val']} != sum {total_of(cs)}")
                else:
                    r['values'] = list(cs) + [sp['val']]
                    match += 1
            for sp in left:
                if s.rtotal is not None and s.rtotal == sp['val']:
                    s.spilled_grand = sp['val']
                    continue
                if sp['val'] == s.grand:
                    s.spilled_grand = sp['val']
                    continue
                note(f"SPILL {cx.name}/{s.office}: leftover {sp['val']} vs grand {s.rtotal} "
                     f"(row sums {s.grand})")

    # sections with rows but no TOTAL row and no spilled totals anywhere
    for cx in counties:
        for s in cx.sections:
            if s.rows and not s.tr and not getattr(s, 'spilled_grand', None) \
                    and not getattr(s, 'spill_matched', False):
                note(f"{cx.name}/{s.office}: no county TOTAL row found "
                     f"({len(s.rows)} rows; likely truncated table)")


def outrows(counties):
    rows = [('county', 'precinct', 'office', 'district', 'candidate', 'party', 'votes')]
    n = 0
    for cx in counties:
        for s in cx.sections:
            dist = '1' if s.office == 'U.S. House' else ''
            for r in s.rows:
                for j, (cand, party) in enumerate(s.cands):
                    v = r['values'][j]
                    if v is None:
                        continue
                    rows.append((s.county, r['precinct'], s.office, dist, cand, party, v))
                    n += 1
    return rows, n


def main():
    counties = parse()
    validate_and_repair(counties)
    for cx in counties:
        for s in cx.sections:
            nc = len(s.cands)
            inline = sum(1 for r in s.rows if r['values'][nc] is not None)
            print(f"{cx.name:12s} {s.office[:40]:42s} rows={len(s.rows):3d} "
                  f"tot_inline={inline:3d} TOTALrow={'Y' if s.tr else 'N'} "
                  f"sums={s.sums}/{s.grand}")
    print(f"\n{len(ISSUES)} issues (see report):")
    for i in ISSUES:
        print(' -', i)
    rows, n = outrows(counties)
    with open(OUT, 'w', newline='') as f:
        csv.writer(f).writerows(rows)
    print(f"\nwrote {n} data rows -> {OUT}")


if __name__ == '__main__':
    main()
