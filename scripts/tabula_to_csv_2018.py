import csv
import os
import sys


def parse_precinct_name(name):
    if name.startswith('Precinct-'):
        return str(int(name[9:]))
    return name.replace(' Precinct', '')


candidates = []
current_name = ''
reference_file = '20181106__sd__general__custer__precinct.csv'
reference_path = os.path.join(
    os.path.dirname(__file__),
    '..',
    '2018',
    reference_file
)
offices_to_ignore = ['State Senate', 'State House']
headers = None

with open(reference_path) as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        if headers is None:
            headers = row.keys()
        if row['candidate'] != current_name:
            current_name = row['candidate']
            if row['office'] not in offices_to_ignore:
                candidates.append({
                    'name': row['candidate'],
                    'party': row['party'],
                    'office': row['office'],
                    'district': row['district'],
                    'votes': [],
                })


county = sys.argv[1]
tabula_file = 'tabula-{0}.csv'.format(county)

precinct_names = []
race_index = -1
num_candidates_in_previous_races = 0
num_candidates_in_this_race = 0
unknown_candidate_number = 0


with open(tabula_file) as csvfile:
    csvreader = csv.reader(csvfile)
    for row in csvreader:
        if row[0].startswith('Precinct Name'):
            race_index += 1
            num_candidates_in_previous_races += num_candidates_in_this_race
        else:
            num_candidates_in_this_race = len(row) - 1
            if race_index == 0:
                precinct_names.append(parse_precinct_name(row[0]))
            for i in range(len(row) - 1):
                cand_index = num_candidates_in_previous_races + i
                if cand_index >= len(candidates):
                    unknown_candidate_number += 1
                    n = unknown_candidate_number
                    candidates.append({
                        'name': 'Unknown Candidate #{0}'.format(n),
                        'party': 'PARTY{0}'.format(n),
                        'office': 'Uknown Office #{0}'.format(n),
                        'district': 'DIST{0}'.format(n),
                        'votes': [],
                    })
                candidates[cand_index]['votes'].append(row[i + 1])


out_file = '20181106__sd__general__{0}__precinct.csv'.format(county.lower())
out_path = os.path.join(
    os.path.dirname(__file__),
    '..',
    '2018',
    out_file
)

with open(out_path, 'w') as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    for cand in candidates:
        for i in range(len(cand['votes'])):
            writer.writerow([
                county,
                precinct_names[i],
                cand['office'],
                cand['district'],
                cand['party'],
                cand['name'],
                cand['votes'][i],
            ])
