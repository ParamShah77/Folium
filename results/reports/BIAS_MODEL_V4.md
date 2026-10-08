# Bias model v4.1: evaluation and comparison with v3

Model: `src/bias_model_v4.py`. Training and evaluation: `scripts/train_bias_v4.py` (about 90 seconds, fixed seeds), which writes every number below to `results/reports/bias_v4_evaluation.json`. Trained on dataset 4.1 (`data/v4/DATASET_CARD.md`). Tests: `tests/test_bias_model_v4.py` (26).

## Summary

| | v4.1 | v3 |
|---|---|---|
| Accuracy, real-frequency test set | **87.9%** | 53.4% |
| Macro-F1, real-frequency test set | **0.840** | 0.309 |
| Calibration error (ECE) | **0.014** | 0.254 |
| Answers a pattern the agreed definitions rule out | **0%** | 13.5% |
| Answer depends on the action (sell / hold / buy more) | **84% of cases** | never |
| Forced sales (the money was needed) read as rational | **72%** (91% when the need is stated) | — |
| "What weighed most" explains the pattern shown | **always** | 1.4% of cases |
| Sense checks passed | **21 / 21** | 5 / 13 scenarios |

The app uses v4.1 by default (`BIAS_MODEL_VERSION=v4`); v3 stays available as a rollback. The previous v4.0 model (`models/bias_detector_v4.0.*`, trained before stretched households and cash shocks) scores 87.1% on the same test cases and reads only 38% of forced sales as rational.

## What the model is

- **Inputs (22):**
  - the action (3 flags), gain or loss and holding period;
  - NIFTY's 1-month return, India VIX and 30-day volatility;
  - which patterns the agreed definitions permit here (`allows_*`, 3 flags from `src/dataset_v4.py`);
  - age, horizon and risk tolerance;
  - money left each month as a share of income, and the emergency fund;
  - position size, equity share, gold share, property and loans relative to assets;
  - **`cash_need_stated`**: the investor said they need the money, read from their comment.
- **Model:** XGBoost, 402 trees, depth 5; the tree count comes from 5-fold cross-validation with early stopping.
- **Guard:** a pattern the definitions rule out is set to zero. On the test set it never had to change an answer.
- **Calibration:** the chosen pattern's probability goes through a centred isotonic curve fitted on out-of-fold predictions, weighted to how often each market regime really occurs. It never shows more than 99%, except when the definitions leave only one possible reading, which is then certain by definition. It never changes which pattern is chosen.
- **Explanations:** exact TreeSHAP values (XGBoost `pred_contribs`) for the chosen pattern, summed into 18 plain drivers. They add up to the model's score to within 1e-5.
- **Stored as** `models/bias_detector_v4.json` (native XGBoost JSON, not a pickle) plus `.meta.json` (features, calibration curve, fill-in values).

Years of investing is deliberately not an input: the app doesn't collect it, and including it added only about 0.5 points.

## How it was tested

20,000 cases. 20% are held out as the test set, stratified by label × regime, and used once. Crashes are over-sampled in the data (24.5% of cases against 6.6% of real days), so the figures to quote are **re-weighted to real frequency**: normal 39.4%, bull 29.0%, correction 19.9%, crash 6.6%, euphoria 5.2%.

## Results

### Overall (test set, 4,000 cases)

| | As sampled | Real frequency |
|---|---|---|
| Accuracy | 86.0% | **87.9%** |
| Macro-F1 | 0.834 | **0.840** |
| Cross-validation accuracy | 84.9% | 86.3% |

| Pattern | Precision | Recall | F1 |
|---|---|---|---|
| Disposition effect | 0.84 | 0.92 | 0.88 |
| Herd behaviour | 0.82 | 0.84 | 0.83 |
| Loss aversion | 0.67 | 0.85 | 0.75 |
| Rational | 0.94 | 0.88 | 0.91 |

Real frequency. Loss aversion is the weakest pattern: in a falling, fearful market a loss-making sale can be panic or herd-following, and the data can't always tell which.

| Regime | Cases | Accuracy | | Action | Accuracy (real frequency) |
|---|---|---|---|---|---|
| Normal | 950 | 89.5% | | Sell | 84.9% |
| Bull | 713 | 87.8% | | Hold | 90.0% |
| Correction | 975 | 87.8% | | Buy more | 89.4% |
| Crash | 979 | 77.6% | | | |
| Euphoria | 383 | 90.3% | | | |

### Confidence means what it says

| Shown as | Share of analyses | Right |
|---|---|---|
| High (85%+) | 68.4% | **98.7%** |
| Medium (65–85%) | 7.1% | **74.4%** |
| Low (under 65%) | 24.5% | **61.7%** |

A "Low" reading usually means two patterns are close to even; the probability bars on the result page show which two.

In 44% of real-frequency cases the definitions allow only one reading (for example, holding a winner in a calm market can only be rational), which flatters overall figures. On the other 56%, the cases that need judgement, accuracy is **78.3%**, and High is right 96.3% of the time, Medium 74.4%, Low 61.7%.

On this test set calibration did not lower the error further (raw 0.012, calibrated 0.014). Both are small, and the calibrated curve keeps the bands honest where the raw model was overconfident in the middle.

### Forced sales

167 test cases are sales forced by money (an uncovered shock, or payments above income with no fund).

| | Read as rational |
|---|---|
| v4.1, need stated in the comment | **91%** |
| v4.1, need not stated | 39% |
| v4.1, all forced sales | 72% |
| v4.0 (no money pressure in its training data) | 38% |

The gap between stated and not stated is what reading the comment closes (`backend/core/comment_reader.py`): when the investor says "fees are due in March", the sale reads as the forced sale it is.

### New market periods

Trained only on 2008–2019 and tested on 2020–2026, which includes the COVID crash: 86.5% accuracy, 0.826 macro-F1 (real frequency).

### How good can a model get on this data?

| | Accuracy | Macro-F1 |
|---|---|---|
| Always "rational" | 57.5% | — |
| **Definitions only** (call a bias whenever one can apply; loss aversion > disposition > herd) | 85.2% | 0.825 |
| v4.1 without the `allows_*` inputs | 87.6% | 0.832 |
| **v4.1** | **87.9%** | **0.840** |
| Ceiling: v4.1 also shown each investor's hidden tendencies | 90.0% | 0.866 |

The agreed definitions do most of the work, by design. v4.1's value is judgement and calibrated confidence. It disagrees with the definitions-only answer in 9.6% of cases, and when it does it is right 64% of the time against 36% for the rules: it recognises rebalancing, a near goal, cutting a loss and a stated need for the money. Where two biases could both apply (5% of cases), neither does better than about 58%; that choice depends on tendencies the app can't observe.

## v3 compared on the same test cases

v3 was given the same mapping the app uses, plus each case's true years of investing, which the app never had.

**Calm markets, by action** (shares of each answer, real frequency):

| Action | Truth | v3 says | v4.1 says |
|---|---|---|---|
| Sell (648) | 69% disposition, 27% rational | 84% rational, 14% disposition | 72% disposition, 26% rational |
| Hold (808) | 79% rational, 17% disposition | 84% rational | 75% rational, 21% disposition |
| Buy more (207) | 66% rational, 34% herd | 86% rational, 0% herd | 60% rational, 40% herd |

v3 can't see the action. Across 600 test cases, changing only the action changed v4.1's answer in 84% of them and v3's in none.

**"What weighed most."** v3 ranked factors for whichever class had the largest total attribution; in 98.6% of cases that wasn't the pattern it showed (the class pushed down hardest is usually one that is ruled out). v4.1 explains the chosen pattern only, with each factor's direction.

## Sense checks (21 / 21)

Scenarios use a typical investor (dataset medians: age 38, ₹75,000 income, 12% position, emergency fund).

| | Scenario | Expected | v4.1 | v3 |
|---|---|---|---|---|
| S1 | Calm market: selling a winner up 35% | Disposition | ✓ Disposition (0.98) | Rational |
| S2 | Calm market: holding a loser down 15% | Disposition | ✓ Disposition (0.60) | Rational |
| S3 | Calm market: holding a deep loser down 40% | Loss aversion | ✓ Loss aversion (0.65) | Rational |
| S4 | Calm market: selling at a 20% loss | Rational | ✓ Rational (1.00) | Rational |
| S5 | Crash: panic-selling at a 35% loss | Loss aversion | ✓ Loss aversion (0.60) | Loss aversion |
| S6 | Crash: selling a winner up 25% into the fear | Herd | ✓ Herd (0.98) | Rational |
| S7 | Euphoric rally: buying more with little to spare | Herd | ✓ Herd (0.98) | Disposition |
| S8 | Fearful market: buying more with spare cash, long horizon | Rational | ✓ Rational (1.00) | Rational |
| S9 | Calm market: holding a winner up 10% | Rational | ✓ Rational (1.00) | Rational |
| S10 | Calm market: adding a little to a holding up 5% | Rational | ✓ Rational (1.00) | Rational |
| S11 | Today's market (5 Oct 2026: NIFTY −5.7% in a month, VIX 14.8): selling at a 12% loss | Loss aversion or herd | ✓ Loss aversion (0.64) | Rational |
| S12 | Calm market: selling a winner up 20%, paying out more than earned, no emergency fund | Rational | ✓ Rational (0.64) | Disposition |
| S13 | Calm market: selling a winner up 20%, says the money is needed | Rational | ✓ Rational (0.64) | Disposition |

| | Reasoning check (model probabilities) | v4.1 |
|---|---|---|
| C1 | Calm market, holding up 35%: the action changes the reading (sell → disposition, hold → rational, buy more → rational) | ✓ (v3 says rational for all three) |
| C2 | A calm-market winner sold from an oversized holding (45%) reads less like disposition than from a small one (8%) | ✓ 0.56 vs 0.96 |
| C3 | Crash sale: as the loss deepens (−8%, −20%, −40%), loss aversion gains on herd behaviour | ✓ 0.52 → 0.64 → 0.70 |
| C4 | Buying more: in every rally band, the herd reading is within 3 points of how often herd behaviour actually drove the purchase | ✓ largest gap 2.0 points |
| C5 | Selling a winner reads as more rational with the goal 2 years away than 20 | ✓ 0.49 vs 0.05 |
| C6 | Gold share alone (5% vs 35%) barely moves the reading | ✓ largest change 0.05 |
| C7 | Fearful market, selling at a 15% loss: saying the money is needed raises the rational reading | ✓ 0.09 → 0.49 |
| C8 | Calm market, selling a winner: paying out more than earned reads as more rational than money to spare | ✓ 0.71 vs 0.06 |

C3 is phrased as loss aversion's share of the two biased readings: loss aversion's raw share is flat with loss depth, because deeper losses also invite rational loss-cutting. C4 tracks the data rather than assuming herd buying rises steadily with the rally: herd's real share is 75%, 77%, 77%, 77% and then 73% for months above +14%, which are post-crash rebounds. A +12% month with low VIX almost never happened (1% of such days), so a single-scenario test there would ask the model about a market it has never seen.

## What drives v4.1's answers

Average share of the explanation, real frequency:

| Driver | Share | | Driver | Share |
|---|---|---|---|---|
| Fit with the disposition pattern | 24.7% | | Your age | 2.7% |
| Fit with the herd pattern | 16.1% | | Stated need for the money | 2.7% |
| Your action | 15.8% | | Asset mix (shares, funds, gold) | 2.4% |
| Fit with the loss-aversion pattern | 9.0% | | NIFTY's past month | 2.2% |
| Gain or loss | 7.9% | | Risk tolerance, market fear, market swings | 1.7–2.2% each |
| Position size | 3.1% | | Money left each month, holding period | 1.2% each |
| Horizon | 3.1% | | Property and loans; emergency fund | 1.1%; 0.8% |

Gold, property and loans reach the model but carry little weight: in the training data loans and rent act through the money left each month, and gold not at all.

## In the app

- `backend/core/bias_detector.py` assembles the inputs from the decision row, the profile and the portfolio snapshot (`build_v4_inputs`). Profile gaps are listed in `assumed_defaults` and portfolio gaps in `fixed_inputs`; the result page shows both.
- Missing profile fields use the training medians. Missing market data uses the median real trading day (NIFTY +1.0% in a month, VIX 16.9).
- `cash_need_stated` comes from the decision's `comment_facts` (the comment reader); without a comment it is "not stated".
- The result page's "What weighed most" shows each factor's direction (teal toward the reading, grey away from it), worded with the action, e.g. "Selling a winner in a calm market".

## Limitations

- **Synthetic investors, real markets.** The labels follow behavioural-finance definitions, not observed Indian investors.
- **Loss aversion vs herd in a fearful sell-off is close to a coin toss** (about 58% either way). The app shows both probabilities, and the confidence reads Low.
- **An unstated cash need is often missed** (39% of such forced sales read as rational). The model can only know what the investor tells it.
- **Years of investing** isn't an input; asking for it at sign-up would add about half a point of accuracy.
