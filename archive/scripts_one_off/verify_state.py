import json, pickle, numpy as np

# V1 JSON
with open('results/model_evaluation_report.json') as f:
    r1 = json.load(f)
print('=== V1 JSON EXACT VALUES ===')
print('macro_f1           :', r1.get('macro_f1'))
print('cv_macro_f1_mean   :', r1.get('cv_macro_f1_mean'))
print('cv_macro_f1_std    :', r1.get('cv_macro_f1_std'))
print('train_accuracy     :', r1.get('train_accuracy'))
print('test_accuracy      :', r1.get('test_accuracy'))
print('overfitting_gap    :', r1.get('overfitting_gap'))
cr = r1.get('classification_report', {})
for cls in ['disposition','herd','loss_aversion','rational']:
    d = cr.get(cls, {})
    print(f'  {cls}: p={d.get("precision",0):.4f}  r={d.get("recall",0):.4f}  f1={d.get("f1-score",0):.4f}  sup={int(d.get("support",0))}')

# V2 JSON  
with open('results/model_evaluation_report_v2.json') as f:
    r2 = json.load(f)
print()
print('=== V2 JSON KEYS ===')
print(list(r2.keys()))
cr2 = r2.get('classification_report', {})
for cls in ['disposition','herd','loss_aversion','rational']:
    d = cr2.get(cls, {})
    print(f'  {cls}: p={d.get("precision",0):.4f}  r={d.get("recall",0):.4f}  f1={d.get("f1-score",0):.4f}')

# V3 JSON
with open('results/model_evaluation_report_v3.json') as f:
    r3 = json.load(f)
print()
print('=== V3 JSON KEYS ===')
print(list(r3.keys()))
pf = r3.get('per_class_f1', {})
pr = r3.get('per_class_recall', {})
for cls in ['disposition','herd','loss_aversion','rational']:
    print(f'  {cls}: f1={pf.get(cls,0):.4f}  recall={pr.get(cls,0):.4f}')

# V3 pkl keys
with open('models/bias_detector_xgboost_v3.pkl','rb') as f:
    b3 = pickle.load(f)
print()
print('=== V3 PKL KEYS ===', list(b3.keys()))
print('v3 n_features:', b3.get('n_features'))
print('v3 feature_cols[:5]:', b3.get('feature_cols', [])[:5])

# V1 pkl keys
with open('models/bias_detector_xgboost.pkl','rb') as f:
    b1 = pickle.load(f)
print()
print('=== V1 PKL KEYS ===', list(b1.keys()))
print('v1 feature_cols[:5]:', b1.get('feature_cols', [])[:5])
print('v1 n_features:', len(b1.get('feature_cols', [])))
