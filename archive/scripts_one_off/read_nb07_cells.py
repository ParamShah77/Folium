import json, pickle, numpy as np, pandas as pd

# Check nb07 Cell 4 code to see how it reads v1/v2/v3 metrics
with open('notebooks/07_final_evaluation.ipynb', 'r', encoding='utf-8') as f:
    nb07 = json.load(f)

print('=== NB07 Cell 4 source (three-version comparison) ===')
cell4 = nb07['cells'][4]
print(''.join(cell4['source']))

print()
print('=== NB07 Cell 8 source (overfitting section) ===')
cell8 = nb07['cells'][8]
print(''.join(cell8['source']))

print()
print('=== NB07 Cell 13 source (summary card) ===')
cell13 = nb07['cells'][13]
print(''.join(cell13['source']))
