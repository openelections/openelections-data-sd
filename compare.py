'''
Sums the results of elections by precinct,
and returns any discrepancies with the
reported county-level results.

If there are two differing entries,
returns both. If an entry is not in
one file, it is returned as a NaN row.

If there are no discrepancies, returns
True.
'''

import warnings
warnings.filterwarnings('ignore')
import pandas as pd

def from_precinct(county_name, precinct_file):
    '''
    Sums results across precincts for all elections
    in the given county. Returns DF in same schema
    as standard county file.
    '''

    # data matching county from precinct file
    prec = precinct_file.groupby('county').get_group(county_name)
    offices = prec.office.unique()
    rows = []

    # results for each office
    for office_name in offices:
        office = prec.groupby('office').get_group(office_name)
        candidates = office.candidate.unique()

        # each candidate within each office
        for candidate_name in candidates:
            candidate = office.groupby('candidate').get_group(candidate_name)
            party = candidate.party[0]
            district = candidate.district[0]
            # counting invalid vote entries as 0
            votes = pd.to_numeric(candidate.votes, errors='coerce').fillna(0)
            votes = votes.astype('int64').sum()

            # final row
            result = pd.DataFrame({
                'office': office_name,
                'district': district,
                'party': party,
                'candidate': candidate_name,
                'votes': votes
            }, index = [county_name])
            rows.append(result)

    return pd.DataFrame(pd.concat(rows))

def from_county(county_name, county_file):
    '''
    Returns data from county sheet for
    the given county.
    '''

    data = county_file.xs(county_name)

    # cleaning off extra characters
    data.candidate = data.candidate.str.replace('.', '')

    return data

def compare(county, precinct):
    '''
    Compares data from county and precinct
    sheets, returning a DF with all unmatched
    rows between the two.
    '''

    county.sort_values(by=['office','district','candidate'], inplace = True)
    precinct.sort_values(by=['office','district','candidate'], inplace = True)
    diff = pd.merge(county, precinct, how = 'outer', indicator = 'there')
    diff = diff.loc[diff['there'] != 'both']

    return diff


def main(county_file, precinct_file):
    '''
    Finds discrepancies between two files.
    '''

    # files read and formatted
    c_raw = pd.read_csv(county_file).set_index('county').sort_values(by=['county', 'office'])
    p_raw = pd.read_csv(precinct_file)
    p_raw = p_raw.set_index(['county']).sort_values(
        by=['county', 'office', 'district', 'candidate']
        )[['office','district','candidate','party','precinct','votes']]

    # counties to check, catching inconsistent entries
    c_names = pd.Series(c_raw.index.drop_duplicates())
    p_names = pd.Series(p_raw.index.drop_duplicates())
    overlap_names = pd.merge(c_names, p_names, how = 'outer', indicator = 'there')
    missing_names = overlap_names[overlap_names.there != 'both']

    # checking file with list
    diffs = {}
    for name in overlap_names.county:

        # catches name in one file but not other
        if name in missing_names.county.tolist():
            return pd.DataFrame(data=[],
                                columns = [
                                    'office',
                                    'district',
                                    'party',
                                    'candidate',
                                    'votes'
                                ],
                                index = [name])

        county = from_county(name, c_raw)
        precinct = from_precinct(name, p_raw)
        diff = compare(county, precinct)
        if not diff.empty:
            diffs[name] = diff
        diff.index.name = 'county'

    return True if not diffs else diffs

# example runtime for testing
if __name__ == "__main__":
    county_file = '2024/20241105__sd__general__county.csv'
    precinct_file = '2020/20201103__sd__general__precinct.csv'
    print(main(county_file, precinct_file))
