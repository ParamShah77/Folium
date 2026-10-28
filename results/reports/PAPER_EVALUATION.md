# Evaluations for the journal paper

2026-10-27. Target: *Applications of Modelling and Simulation* (ARQII). Script: `scripts/evaluate_for_paper.py`, which writes every number below to `results/reports/paper_evaluation.json` (about 4 minutes). It uses the deployed bias model v4, simulator v2 (`src/simulator_v2.py`) and the template explainer, with nothing changed. The only simulator change was adding two evaluation hooks, `paths=` and `return_gaps=`, and making the block length readable from `assumptions`. The app's results are identical.

Monthly history: NIFTY 50 (+1.25% dividend yield) and gold in rupees, Oct 2007 – Sep 2026, 228 months.

## 1. Behavioural classifier against baselines

The test set is 4,000 synthetic cases, re-weighted to how often each market regime really occurred (2008–2026). Every learner gets the same 22 features and the same definitions guard.

**Five split seeds (7, 11, 23, 42, 101), mean ± SD**

| Model | Accuracy | Macro-F1 | ECE | Log-loss |
|---|---|---|---|---|
| Always "rational" | 57.4% ± 0.0 | 0.182 | 0.426 | — |
| Rules only (label definitions) | 84.4% ± 0.6 | 0.818 ± 0.006 | 0.156 | — |
| Logistic regression | 84.9% ± 0.4 | 0.816 ± 0.003 | 0.018 ± 0.003 | 0.321 ± 0.022 |
| Random forest (500 trees) | 87.0% ± 0.5 | **0.833** ± 0.005 | **0.014** ± 0.003 | 0.282 ± 0.021 |
| XGBoost (deployed settings) | **87.2%** ± 0.6 | 0.831 ± 0.009 | 0.015 ± 0.004 | **0.267** ± 0.014 |

**The paper's split (seed 7), with 2,000 bootstrap resamples and McNemar tests**

| Model | Accuracy [95% CI] | XGBoost minus this [95% CI] | McNemar p |
|---|---|---|---|
| Rules only | 85.2% [83.9, 86.4] | +2.7 pp [+1.6, +3.8] | 2.4e-7 |
| Logistic regression | 85.5% [84.2, 86.6] | +2.4 pp [+1.4, +3.4] | 1.0e-5 |
| Random forest | 87.6% [86.5, 88.7] | +0.2 pp [−0.4, +0.9] | 0.096 |
| XGBoost | 87.8% [86.7, 89.0] | — | — |
| XGBoost as shipped (with calibration curve) | 87.9% [86.8, 89.1] | −0.1 pp [−0.5, +0.3] | 1.0 |

**For the paper:**
- XGBoost clearly beats the rules and logistic regression, but it is **statistically tied with a random forest**. Say so, and don't claim XGBoost is the better learner.
- The real gain over the label definitions is about 2.7 points.
- Calibration does not change accuracy. On this split it moved ECE from 0.012 to 0.014, so the calibration curve adds nothing measurable here.
- The paper's sentence "This current analysis does not provide any baseline" must go.

## 2. Is the market generator realistic?

There are 10,000 ten-year paths per generator. All generators use the same historical mean, so only the shape and the dependence differ. The real figures come from rolling windows, which overlap, so KS distances are descriptive only.

| | 1-yr p10 | 1-yr median | 1-yr p90 | Years < −20% | ACF of squared returns, lag 1 / 3 / 6 | KS distance, 1-yr |
|---|---|---|---|---|---|---|
| **Real NIFTY** (217 windows) | −7.5% | 11.3% | 33.3% | 4.6% | 0.136 / 0.051 / 0.093 | — |
| Lognormal (GBM) | −16.2% | 9.5% | 42.1% | 6.4% | −0.01 / −0.01 / −0.01 | 0.132 |
| Independent months | −15.9% | 10.6% | 41.2% | 6.7% | −0.01 / −0.01 / −0.01 | 0.108 |
| Block 3 months | −14.3% | 10.6% | 37.8% | 6.3% | 0.077 / −0.01 / −0.01 | 0.083 |
| Block 6 months | −13.7% | 10.5% | 35.9% | 6.3% | 0.100 / 0.029 / −0.01 | 0.072 |
| **Block 12 months (used)** | **−8.1%** | **10.3%** | **33.1%** | **4.7%** | **0.101 / 0.035 / 0.025** | **0.027** |
| Block 24 months | −8.1% | 10.3% | 33.0% | 4.9% | 0.105 / 0.023 / 0.033 | 0.030 |

**For the paper:**
- The 12-month block bootstrap is the only generator here that reproduces both the spread of real one-year returns and the volatility clustering.
  - Its KS distance is a quarter of the iid bootstrap's (0.027 vs 0.108) and a fifth of GBM's (0.132).
  - GBM and independent months have no clustering at all and make bad years about twice as bad.
- Going to 24-month blocks changes almost nothing, so 12 months is a reasonable choice.
- **Ten-year comparisons are not meaningful.** The record holds only one independent decade. The 10-year KS distance is about 0.34 for every generator, so leave it out or report it only as a limitation.

## 3. Monte Carlo convergence (base case, 20 repeats per size)

| Futures | P(hold wins) mean ± SD | Median gap mean ± SD |
|---|---|---|
| 250 | 0.637 ± 0.030 | ₹1,60,784 ± 36,940 |
| 500 | 0.634 ± 0.024 | ₹1,70,247 ± 32,938 |
| **1,000 (app)** | 0.633 ± 0.017 | ₹1,68,549 ± 24,140 |
| 2,000 | 0.628 ± 0.010 | ₹1,63,326 ± 14,347 |
| 5,000 | 0.632 ± 0.008 | ₹1,67,786 ± 11,317 |
| 10,000 | 0.632 ± 0.006 | ₹1,67,712 ± 7,700 |

**For the paper:** at the app's 1,000 futures, P(hold) is stable to about ±1.7 points, close to the binomial ±1.5. The median ₹ gap still moves by about ±14% between runs. Either report it with that error, or recommend 5,000 futures when the ₹ figure matters.

## 4. The paired simulation over 1,000 investors

Each investor and position comes from the v4 dataset:
- **Position:** the investor's position share of liquid money.
- **Asset type:** a fund or a stock, in proportion to their fund and stock holdings. 40% of positions are funds.
- **Stock risk:** each stock gets the beta and own swings of one of 24 measured NIFTY 50 stocks.
- **Horizon:** the investor's own horizon, median 23 years.
- **Futures:** 1,000 per investor.

Verdict bands follow the app: HOLD above 60%, a toss-up from 40% to 60%, SELL below 40%.

| | Long-run assumptions (app) | History replayed exactly |
|---|---|---|
| Mean P(hold wins) | 0.635 | 0.380 |
| HOLD / toss-up / SELL | 58.1% / 40.8% / 1.1% | 5.6% / 37.8% / 56.6% |

| Group (long-run assumptions) | n | Mean P(hold) | HOLD share |
|---|---|---|---|
| Horizon 1–3 years | 52 | 0.571 | 29% (rest toss-up) |
| Horizon 4–10 years | 100 | 0.598 | 43% |
| Horizon 11–20 years | 275 | 0.624 | 57% |
| Horizon 21–30 years | 573 | 0.652 | 64% |
| Single stock | 596 | 0.562 | 31% |
| Equity fund | 404 | 0.742 | 99% |
| Position at a gain / at a loss | 543 / 457 | 0.635 / 0.635 | 59% / 57% |

**The flip, which must be disclosed.** When history is replayed exactly, gold compounds at its 2007–2026 rate of about 15% a year instead of the assumed 9%.
- **86% of verdicts change.**
- 52.5% of HOLD verdicts become a toss-up or SELL.
- The sign of the median gap reverses for 67% of investors.

The model's answer depends heavily on the stated long-run growth rates, which the next section shows directly.

## 5. Sensitivity

The table changes one thing at a time. "Base" is the stock down 17% over 20 years (1,000 futures). "Sub-population" is 300 investors from §4 (500 futures each).

| Change | Base: P(hold), median gap | Sub-population: mean P(hold) | Verdicts that change |
|---|---|---|---|
| None (base) | 0.642, ₹1,88,632 | 0.639 | — |
| Shares grow 9% (not 11%) | 0.536, ₹42,336 | 0.543 | **41.7%** |
| Shares grow 13% | 0.740, ₹4,13,079 | 0.720 | 19.7% |
| Gold grows 6% (not 9%) | 0.698, ₹2,63,194 | 0.718 | 21.7% |
| FD rate 5.5% (not 6.75%) | 0.664, ₹2,14,851 | 0.651 | 7.3% |
| FD rate 8% | 0.620, ₹1,57,287 | 0.625 | 5.3% |
| Stock's own swings 15% | 0.722, ₹3,01,085 | 0.680 | 19.3% |
| Stock's own swings 35% | 0.438, −₹70,082 | 0.545 | **41.0%** |
| Sale costs 0.5% or 1% (not 0.15%) | 0.642, ~₹1,87,000 | 0.639 | 0% |
| Independent months (block 1) | 0.636, ₹1,60,619 | 0.635 | 10.3% |
| Block 6 months | 0.626, ₹1,62,702 | 0.637 | 6.7% |
| Block 24 months | 0.648, ₹1,97,782 | 0.643 | 7.0% |
| Tax rules before 23 July 2024 (STCG 15%, LTCG 10% above ₹1 L) | 0.644, ₹2,03,626 | 0.641 | 1.0% |
| Future starts in a bad year (worst 10% of real years) | 0.518, ₹9,626 | 0.481 | **62.0%** |
| Future starts in a good year (best 10%) | 0.756, ₹4,66,968 | 0.757 | 26.7% |
| History replayed exactly | 0.430, −₹1,32,747 | 0.381 | **86.3%** |

**For the paper:**
- **Most sensitive:** the growth assumptions (shares and gold), how risky the particular stock is, and the kind of year the future starts in.
- **Barely matters:** the block length, the 2024 tax change, and sale costs. The cost is charged on cashing out in both futures, so it cancels in the ratio. This makes a useful tornado chart.

## 6. Walk-forward replay of real windows

A diversified fund, up 30%, is run through the same tax and cost accounting over every real 5- and 10-year window, with history's own growth rates. Each real outcome is then placed in the simulated distribution for the same case.

| | Real windows (independent) | Hold won, real | Hold won, simulated | Real median gap | Simulated median gap | Real inside simulated 10–90% |
|---|---|---|---|---|---|---|
| 5 years | 169 (3) | 88.8% | 61.0% | ₹56,378 | ₹23,133 | 99.4% |
| 10 years | 109 (1) | 100% | 60.7% | ₹1,25,114 | ₹44,327 | 100% |

**For the paper:**
- Every real outcome falls inside the simulated band. The band is wider than the real record, as intended: the simulator allows for decades better and worse than 2007–2026.
- Real outcomes sit in the upper-middle of the band, with a median percentile of 0.66–0.67. 2007–2026 was a good period for holding equity against this mix.
- With 1–3 independent windows this is a **consistency check, not validation**. State it that way.

## 7. Replacement for Table III: Eq. (8) done properly

This uses the base-case investor over 14 years with 1,000 futures. "Difference of medians" is what the paper's Table III showed. **"Median paired gap" is what Eq. (8) actually defines.**

**Stock down 17%**

| Year | HOLD median | SELL median | Difference of medians | Median paired gap [p10, p90] | Hold wins |
|---|---|---|---|---|---|
| 0 | ₹1,00,000 | ₹99,850 | ₹150 | ₹150 | — |
| 5 | ₹1,51,619 | ₹1,29,647 | ₹21,972 | ₹21,787 [−75,796, 2,13,706] | 57.6% |
| 10 | ₹2,33,490 | ₹1,69,700 | ₹63,790 | ₹51,717 [−1,19,371, 5,12,349] | 61.2% |
| 14 | ₹3,10,324 | ₹2,16,030 | ₹94,294 | ₹85,272 [−1,65,144, 9,17,770] | 61.6% |

**Equity fund up 30%**

| Year | HOLD median | SELL median | Difference of medians | Median paired gap [p10, p90] | Hold wins |
|---|---|---|---|---|---|
| 5 | ₹1,71,639 | ₹1,29,647 | ₹41,992 | ₹41,253 [−46,522, 1,66,486] | 67.7% |
| 10 | ₹2,78,091 | ₹1,69,700 | ₹1,08,392 | ₹1,05,471 [−69,364, 4,16,558] | 76.3% |
| 14 | ₹4,11,636 | ₹2,16,030 | ₹1,95,606 | ₹1,82,568 [−97,397, 7,38,846] | 76.2% |

The two definitions differ by up to 19% at year 10. Use the paired gap with its p10–p90 range, so the table also shows that HOLD loses in a large share of futures.

## 8. Explanations on the current pipeline

This replaces the old `explanation_quality.json`, which ran simulator v1 and the v3 `integration` pipeline.
- **Cases:** 166 sell/hold decisions from §4's investors.
- **Explanations:** 332 in total, one in English and one in Hindi per case.
- **Pipeline:** bias v4, simulator v2 and the template explainer, with no LLM.
- **Patterns:**

| Pattern | Cases |
|---|---|
| Rational | 78 |
| Disposition | 38 |
| Herd | 27 |
| Loss aversion | 23 |

| | Complete | Readable | Actionable | Personalised | Jargon | Readability |
|---|---|---|---|---|---|---|
| English (166) | 100% | 100% | 100% | 100% | 0 | Flesch mean 76.4, worst 73.5 (target ≥ 60) |
| Hindi (166) | 100% | 100% | 100% | 100% | 0 | 12.8 words a sentence (target ≤ 20) |

**For the paper:**
- Replace "Flesch 78.3, 64-case check" with **Flesch 76.4 (min 73.5) over 166 cases, plus Hindi at 12.8 words per sentence**.
- These are structural checks on the explanation text. They do not measure user comprehension.

Note on running: NLTK, which textstat uses for Flesch, refuses to read its data from a redirected AppData folder. If the English Flesch comes out empty, set `NLTK_DATA` to the real `nltk_data` folder and run again.
