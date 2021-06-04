import os
import glob
from tickets import Tickets

'''
Navigates through available general precinct files 
to parse tickets with tickets.py
'''

def get_files():
    '''
    Finds general precinct csv filenames from
    the parent dirrectory for parsing.
    '''
    os.chdir('../')
    files = glob.glob('**/*.csv')

    precinct_files = {}
    for f in files:
        year = f[:4]
        if 'general__precinct' in f:
            precinct_files[year] = f
        elif 'primary__precinct' in f:
            if year not in precinct_files.keys():
                precinct_files[year] = f

    return precinct_files

def parse_files(files):
    '''
    Parses each given file for tickets.
    '''
    tickets_list = []
    for filename in files:
        # main call
        parser = Tickets(state_name='south_dakota', filename=filename)
        tickets = parser.parse()
        tickets_list.append(tickets)

    return tickets_list

if __name__ == '__main__':
    files = get_files()
    tickets = parse_files(files.values())