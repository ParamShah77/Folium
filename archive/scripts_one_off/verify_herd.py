import json, pickle, numpy as np, pandas as pd

# Check exactly what nb07 reads from report JSON (look at what keys it uses)
# Also check how fix_herd_diversity.py generated herd samples
with open('scripts/fix_herd_diversity.py', 'r', encoding='utf-8') as f:
    src = f.read()
# Print disposition_strength generation line and constraints
for i, line in enumerate(src.split('\n')):
    if any(k in line for k in ['disposition_strength', 'crowd_action_ratio', 'unrealized_gain', 'loss_aversion', 'constraint', 'Constraint', 'herd_sensitivity']):
        print(f'L{i+1}: {line}')

print()
print('=== Current herd in synthetic_decisions.csv ===')
df = pd.read_csv('synthetic_decisions.csv')
herd = df[df['bias_type'] == 'herd']
print(f'Total herd rows: {len(herd)}')
print('Columns in decisions csv:', list(df.columns))
print()
# Check if disposition_strength is in the csv
if 'disposition_strength' in df.columns:
    print('disposition_strength stats (herd only):')
    print(herd['disposition_strength'].describe())
    print()
if 'herd_sensitivity' in df.columns:
    print('herd_sensitivity stats (herd only):')
    print(herd['herd_sensitivity'].describe())
if 'crowd_action_ratio' in df.columns:
    print('crowd_action_ratio stats (herd only):')
    print(herd['crowd_action_ratio'].describe())
if 'unrealized_gain_loss' in df.columns:
    print('unrealized_gain_loss stats (herd only):')
    print(herd['unrealized_gain_loss'].describe())
