import pandas as pd
from src.simulator import get_simulator
from tqdm import tqdm
import numpy as np
import concurrent.futures
df = pd.read_csv('synthetic_counterfactuals.csv')
sim = get_simulator()

def process_row(index, row):
    if row['action'] == 'hold':
        res = sim.simulate_individual('mock_validation', 10000.0, 0, n_simulations=500, action='hold')
    else:
        res = sim.simulate_individual('mock_validation', 10000.0, 0, n_simulations=500, action='sell')
    return index, res['median_final_wealth']

with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [executor.submit(process_row, i, row) for i, row in df.iterrows()]
    for f in tqdm(concurrent.futures.as_completed(futures), total=len(df)):
        index, val = f.result()
        df.at[index, 'final_wealth_20y'] = val

df.to_csv('synthetic_counterfactuals.csv', index=False)
print('Done!')
