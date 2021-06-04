#!/usr/bin/env python3

'''
Returns every "ticket", a unique office-candidate pair,
from a given state-wide precinct file. Saves as CSV
to same directory.

!! THIS IS THE SOUTH DAKOTA VERSION OF THIS GENERAL SCRIPT !!
'''

from os import lseek
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz, process
from curtsies.fmtfuncs import red, bold, green, on_blue, yellow

class Tickets():
    # tokens representing e.g. void ballots or total vote counts
    PROCEDURALS = {
        'VOIDS': 'VOID',
        'BLANKS': 'BLANK',
        'TOTALS': 'BALLOTS',
        'TOTAL': 'BALLOTS',
        'TOTAL VOTES': 'BALLOTS',
        'BALLOTS CAST': 'BALLOTS',
        'OVER VOTES': 'OVER',
        'UNDER VOTES': 'UNDER',
        'SCATTERING': 'SCATTER'
    }
    PROCEDURALS_LIST = list(PROCEDURALS.keys()) + list(PROCEDURALS.values()) + [
        'UNCOMMITTED'
    ]
    # unwanted characters and their replacements
    BAD_CHARS = {
        '.': '',
        ',': '',
        ':': '',
        '"': '', # only for hanging quote marks
        '-': ' ',# since all quote sections cut first
        "'": ' ',
        '&': 'AND',
        '“': '',
        '”': ''
    }
    # delimiter characters
    DELIMS = ['/', '\\', ' AND ']
    
    # affixes to cut out of names
    # - parties, nicknames
    AFFIX = [r'^REP', r'^DEM', r'^IND', r'\".*\"', r'\(.*\)']

    def __init__(self, state_name, filename, fuzzy_iterations=1):
        self.state = state_name
        self.state_name = ' '.join(self.state.split('_')).title()
        self.filename = filename
        self.fuzzy_iterations = fuzzy_iterations
        self.df = pd.read_csv(filename, usecols=['office','candidate']).sort_values(by=['candidate'])
        self.df = self.df[self.df.candidate.isna() == False]
        
        # Getting tickets
        print('-----------------------------')
        print(f'Getting tickets for {on_blue(self.state_name)} in {on_blue(self.filename[:4])} ...')
        print('-----------------------------')
        print('STARTING UNIQUES:', red(str(len(self.df.candidate.unique()))))
        self.tickets = self.get_tickets(self.df, self.filename, 
                                        self.fuzzy_iterations)
    
        
    def clean_names(self, df):
        '''
        Standardizes formatting of candidate names.
        '''
        s = df['candidate']
        print('\nCLEANING CANDIDATE NAMES ...')
        
        s = s.str.strip()
        s = s.str.upper()
        
        # bad characters
        for char, replacement in self.BAD_CHARS.items():
            s = s.str.replace(char, replacement, regex=False)
        
        # procedural tokens
        s = s.replace(self.PROCEDURALS)

        # splitting on delimiters
        col_split = lambda s, c: s.str.split(c, expand = True)[0]
        for c in self.DELIMS:
            s = col_split(s,c)
        
        # standardizing write-ins
        s = s.str.replace('WRITE IN ', 'WRITE INS ')
        
        # whitespace
        s = s.str.replace('\s+', ' ', regex=True)
        s = s.str.strip()
        
        df['candidate'] = s
        
        print('Done.')
        print('UNIQUES:', green(str(len(s.unique()))))
        return df
    
    def clean_offices(self, df):
        '''
        Standardizes office names.
        '''
        s = df['office']
        print('\nCLEANING OFFICE NAMES ...')
        print(f'Number of offices: {red(str(len(s.unique())))}')
        
        s = s.str.strip()
        s = s.str.upper()
        
        for char, replacement in self.BAD_CHARS.items():
            s = s.str.replace(char, replacement, regex=False)
            
        s = s.str.replace('\s+', ' ', regex=False)
        s = s.str.strip()
        
        print(f'New number of offices: {green(str(len(s.unique())))}')
        df['office'] = s
        return df
    
    def tags(self, df):
        '''
        Standardizes prefixes/suffixes often
        added to candidate names.
        '''
        print('\nREMOVING COMMON AFFIXES...')
        
        # WRITE INS first, as they may include the others
        wr = df['candidate'][df['candidate'].str.contains('WRITE INS')]
        changes = {}
        for ind, name in wr.iteritems():
            w = name.partition('WRITE INS')
            if w[0] != '' and w[0] != 'UNQUALIFIED ':
                new_name = w[0].strip()
            elif w[2] != '':
                new_name = w[2].strip()
            # just 'write ins'
            elif name == 'WRITE INS':
                new_name = 'WRITE INS'            
            # collapsing "Unqualified write ins"
            elif w[0] == 'UNQUALIFIED ':
                new_name = 'WRITE INS'
            changes[name] = new_name
        df['candidate'] = df['candidate'].replace(changes)
        
        # cutting out unwanted affixes
        s = df['candidate']
        for a in self.AFFIX:
            s = s.str.replace(a, '', regex=True)
        df['candidate'] = s
        
        print('Done.')
        print('UNIQUES:', green(str(len(s.unique()))))
        return df
        
    def match(self, df, iteration):
        '''
        Fuzzy matches similar candidate names.
        '''
        print(f'\nFUZZY MATCHING | Iteration {iteration}')
        print('-----------------------------')
        s = df['candidate']
        candidate_names = s.value_counts().index.tolist()
        
        # CHECK THAT MATCH PAIR IS VALID:
        # - score is at least 85
        # - not a self-match
        # - not a reverse match: re-matching an already changed token
        unique = lambda n,s: s >= 85 and n != name and n not in changes.values()
        
        changes = {}
        change_df = []
        for name in candidate_names:
            # checking if name not already matched as incorrect
            if name not in changes.keys():
                # fuzzy matches 
                scores = process.extract(name, candidate_names, scorer=fuzz.token_set_ratio)
                matches = [(n,s) for (n,s) in scores if unique(n,s)]
                if matches:
                    for match_pair in matches:
                        # if match_pair[0] not in changes.values():
                        match = match_pair[0]
                        name_office = df.office[df.candidate == name].tolist()[0]
                        match_office = df.office[df.candidate == match].tolist()[0]
                        if name_office == match_office:
                            print(f'{red(match)} -- to --> {green(name)}')
                            changes[match] = name
                            change_df.append((match, name, name_office))
                            
        # making changes to column
        s = s.replace(changes)
        df['candidate'] = s
        
        print('-----------------------------')
        print(f'MADE {yellow(str(len(changes.keys())))} CHANGES |','UNIQUES:', green(str(len((s.unique())))))
        
        return df, change_df
    
    def get_tickets(self, df, path, fuzzy_iterations=1):
        '''
        Returns and saves DF of tickets.
        '''
        
        # cleaning df
        df = self.clean_names(df)
        df = self.tags(df)
        df = self.clean_offices(df)
        
        # matching for the given number of iterations
        changes_list = []
        for i in range(fuzzy_iterations):
            df, changes = self.match(df, i+1)
            changes_list.append(changes)
        
        # assembling tickets
        offices = df.office.drop_duplicates()
        d = {}
        for office in offices:
            odf = df.groupby('office').get_group(office)
            candidates = odf.candidate.drop_duplicates().tolist()
            d[office] = candidates
            
        # compiling into DF
        fdf = pd.concat([pd.DataFrame(k) for k in d.values()], keys=d.keys())
        fdf.reset_index(inplace=True)
        fdf.columns = ['office','x','candidate']
        fdf.drop('x', axis=1, inplace=True)
        
        # changes from match()
        change_df = pd.concat([pd.DataFrame(c, columns=['old', 'new', 'office']) for c in changes_list], 
                              keys=list(range(fuzzy_iterations)))
        change_df.index.names = ['iteration','ind']
        
        # saving both DFs to file
        year = path[:4]
        filename = f'{year}/{self.state}__{year}__tickets.csv'
        fdf.to_csv(filename)
        change_df.to_csv(f'{year}/{self.state}__{year}__ticket__changes.csv')
        
        print(f'\nFinished and saved to file at {filename}')
        return fdf