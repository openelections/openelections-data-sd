import os
import glob
import pandas as pd
from tickets import Tickets

'''
Navigates through available general precinct files 
to parse tickets with tickets.py
'''

os.chdir('../')
files = glob.glob('**/*.csv')
precinct_files = [f for f in files if 'precinct' in f]

for filename in precinct_files:
    tickets = Tickets(state_name='south_dakota', filename=filename,
                      fuzzy_iterations=2)
    break