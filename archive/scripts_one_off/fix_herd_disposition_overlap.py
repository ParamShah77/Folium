"""
scripts/fix_herd_disposition_overlap.py

Tightens the 200 borderline herd samples that were added by
fix_herd_diversity.py to eliminate their overlap with the
disposition class.

Constraints applied:
  1. unrealized_gain_loss clipped to [-0.10, +0.20]
     (herd investors should NOT have deep losses > 10%)
  2. crowd_action_ratio >= 3x |unrealized_gain_loss|, min 0.45, max 1.0
     (crowd signal must dominate P&L signal for clear herd classification)
  3. market_volatility clipped to <= 0.28
     (extreme panic volatility pushes samples into loss_aversion territory)

Run ONCE before re-running data_preparation.py.
"""
import numpy as np
import pandas as pd
import os

ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISIONS_PATH = os.path.join(ROOT, 'synthetic_decisions.csv')
N_BORDERLINE   = 200  # the last N herd rows are the borderline additions

df = pd.read_csv(DECISIONS_PATH)
print(f'Loaded {DECISIONS_PATH}: {df.shape}')
print(f'Herd rows before fix: {(df["bias_type"] == "herd").sum()}')

herd_idx = df.index[df['bias_type'] == 'herd'].tolist()

if len(herd_idx) < N_BORDERLINE:
    raise ValueError(f'Expected >= {N_BORDERLINE} herd rows, found {len(herd_idx)}')

# The borderline additions are the LAST N_BORDERLINE herd rows
borderline_idx = herd_idx[-N_BORDERLINE:]
bh = df.loc[borderline_idx].copy()

print(f'\nBefore constraints:')
print(f'  unrealized_gain_loss: min={bh["unrealized_gain_loss"].min():.4f}, '
      f'max={bh["unrealized_gain_loss"].max():.4f}')
print(f'  crowd_action_ratio  : min={bh["crowd_action_ratio"].min():.4f}, '
      f'max={bh["crowd_action_ratio"].max():.4f}')
if 'market_volatility' in bh.columns:
    print(f'  market_volatility   : min={bh["market_volatility"].min():.4f}, '
          f'max={bh["market_volatility"].max():.4f}')

# ── Constraint 1: cap unrealized_gain_loss to realistic herd range ──────
# Herd investors follow crowd; deep losses (> 10%) shift a sample into
# loss_aversion territory. Gains capped at 20% to stay realistic.
bh['unrealized_gain_loss'] = bh['unrealized_gain_loss'].clip(lower=-0.10, upper=0.20)

# ── Constraint 2: crowd signal must dominate personal P&L ───────────────
# crowd_influence_ratio = crowd / |P&L| should be >= 3.0 for clear herd.
# Equivalently: crowd_action_ratio >= 3 x |unrealized_gain_loss|, min 0.45.
loss_abs  = bh['unrealized_gain_loss'].abs().clip(lower=0.02)
min_crowd = (loss_abs * 3.0).clip(lower=0.45, upper=0.90)
# hard cap at 1.0: crowd_action_ratio is a proportion [0, 1]
bh['crowd_action_ratio'] = np.maximum(
    bh['crowd_action_ratio'], min_crowd
).clip(upper=1.0)

# ── Constraint 3: market_volatility must not be in extreme-panic range ───
# market_volatility > 0.30 pushes context toward loss_aversion territory.
if 'market_volatility' in bh.columns:
    bh['market_volatility'] = bh['market_volatility'].clip(upper=0.28)

# ── Verify constraints are satisfied ────────────────────────────────────
crowd_ok = (bh['crowd_action_ratio'] >= 0.45).all()
loss_ok  = (bh['unrealized_gain_loss'] >= -0.10).all()
prop_ok  = (bh['crowd_action_ratio'] <= 1.00).all()

print(f'\nAfter constraints:')
print(f'  crowd_action_ratio >= 0.45 for all: {crowd_ok}')
print(f'  crowd_action_ratio <= 1.00 for all: {prop_ok}')
print(f'  unrealized_gain_loss >= -0.10 for all: {loss_ok}')
print(f'  unrealized_gain_loss: min={bh["unrealized_gain_loss"].min():.4f}, '
      f'max={bh["unrealized_gain_loss"].max():.4f}')
print(f'  crowd_action_ratio  : min={bh["crowd_action_ratio"].min():.4f}, '
      f'max={bh["crowd_action_ratio"].max():.4f}')
if 'market_volatility' in bh.columns:
    print(f'  market_volatility   : min={bh["market_volatility"].min():.4f}, '
          f'max={bh["market_volatility"].max():.4f}')

if not (crowd_ok and loss_ok and prop_ok):
    raise AssertionError('One or more constraints NOT satisfied — check data.')

# ── Write back only the modified rows ───────────────────────────────────
df.loc[borderline_idx] = bh
df.to_csv(DECISIONS_PATH, index=False)

total_herd = (df['bias_type'] == 'herd').sum()
print(f'\nSaved {DECISIONS_PATH}')
print(f'Total herd rows: {total_herd}  (expected 600)')
print(f'Borderline herd rows tightened: {N_BORDERLINE}')
print('Done.')
