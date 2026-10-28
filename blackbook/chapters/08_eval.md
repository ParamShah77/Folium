# Chapter 8: Experimental Setup and Evaluation

## 8.1 Evidence Base and Scope

Every number in this chapter and the next is taken from an evaluation file committed in the repository. The files and the scripts that produce them are:

| Evaluation file | Produced by | Date in file | Runtime |
|---|---|---|---|
| `results/reports/bias_v4_evaluation.json` | `scripts/train_bias_v4.py` | 2026-10-08 | 81.4 s |
| `results/reports/simulator_v2_evaluation.json` | `scripts/evaluate_simulator_v2.py` | 2026-10-07 | 12.2 s |
| `results/causal_v4.json` | `python -m src.causal_v4` | 2026-10-08 | 54.2 s |
| `results/reports/paper_evaluation.json` | `scripts/evaluate_for_paper.py` | 2026-10-27 | 224.9 s |

Table: Table 8.1: Evaluation artefacts used in this report

These experiments were run by the team during development; they were not re-executed while preparing this report. Because every script uses fixed seeds and cached market data, they can be reproduced with the commands in Appendix D. The scope is development-stage evaluation on synthetic behavioural labels and real market history. No experiment with real investors has been performed.

## 8.2 Experimental Environment

Experiments ran in the project's Python 3.13 virtual environment with the pinned library versions of Table 3.7 (XGBoost 3.2.0, scikit-learn 1.8.0, SHAP 0.51.0, DoWhy 0.14, NumPy 2.4.2, pandas 3.0.1). The hardware was the team's development laptop (Section 3.3). `scripts/verify_ml_env.py` checks that the installed versions and artefacts match before results are regenerated.

## 8.3 Bias Model: Data Split and Protocol

1. **Data.** 20,000 cases of dataset v4.1 with 22 features.
2. **Split.** 16,000 development and 4,000 test cases, stratified by label × regime (seed 7). The test set is used once.
3. **Cross-validation.** Five stratified folds on the development set with early stopping; the best iterations were 423, 330, 329, 381 and 364, giving $\lceil 1.1 \times \text{mean} \rceil = 402$ trees.
4. **Calibration.** Centred isotonic curve fitted on the out-of-fold predictions.
5. **Weighting.** Because stress regimes are over-sampled, every metric is reported both "as sampled" and re-weighted to the real frequency of each regime (normal 39.4%, bull 29.0%, correction 19.9%, crash 6.6%, euphoria 5.2%). The real-frequency figures are the ones quoted in the abstract.
6. **Additional protocols.** Out-of-time (train 2008-06 to 2019-12, 13,601 rows; test 2020-01 to 2026-10, 6,399 rows, including the COVID crash); baselines (Section 8.6); comparison with v3 on the same test cases; forced-sale analysis; 21 scenario and relational sense checks.

| Hyper-parameter | Value |
|---|---|
| Objective | `multi:softprob` (4 classes) |
| Number of trees | 402 (from cross-validation) |
| Maximum depth | 5 |
| Learning rate | 0.03 |
| Row / column subsample | 0.85 / 0.85 |
| Minimum child weight | 3 |
| L2 regularisation (λ) | 2.0 |
| Tree method | `hist` |
| Random state / split seed | 42 / 7 |

Table: Table 8.2: Hyper-parameters of bias model v4.1 (`scripts/train_bias_v4.py`)

## 8.4 Evaluation Metrics

For true labels $y_i$, predictions $\hat{y}_i$ and weights $w_i$:

$$ \text{Accuracy} = \frac{\sum_i w_i \mathbf{1}[\hat{y}_i = y_i]}{\sum_i w_i}, \qquad \text{Precision}_k = \frac{TP_k}{TP_k + FP_k}, \qquad \text{Recall}_k = \frac{TP_k}{TP_k + FN_k}, $$

$$ F1_k = \frac{2\,\text{Precision}_k\,\text{Recall}_k}{\text{Precision}_k + \text{Recall}_k}, \qquad \text{Macro-F1} = \frac{1}{K}\sum_{k=1}^{K} F1_k , $$

where the counts $TP_k$, $FP_k$, $FN_k$ are weighted sums. Macro-F1 gives each class equal importance, which matters because loss aversion is only 10% of cases. Log-loss is $-\frac{1}{W}\sum_i w_i \ln \hat{p}_{y_i}(\mathbf{x}_i)$, and ECE is defined in Section 7.4. For the simulator, the metrics are percentiles of simulated 1-year and 10-year returns compared with rolling windows of the real index. For the causal module, the metric is mean absolute error in percentage points between estimated and true effects, plus sign agreement. For explanations, the metrics are completeness (all six sections present), actionability (a concrete action stated), personalisation (the investor's own figures used), jargon leaks, Flesch reading ease [49] for English and words per sentence for Hindi.

## 8.5 Bias Model Results

### 8.5.1 Overall performance

| Metric | As sampled | Real frequency |
|---|---|---|
| Accuracy (test) | 86.0% | **87.9%** |
| Macro-F1 (test) | 0.834 | **0.840** |
| Log-loss (test, calibrated) | — | 0.246 |
| ECE (test, calibrated) | — | **0.014** |
| Cross-validation accuracy | 84.9% | 86.3% |
| Cross-validation macro-F1 | 0.824 | 0.829 |
| Rule violations (pattern the definitions rule out) | — | 0% |

Table: Table 8.3: Overall test performance of bias model v4.1

The guard and the calibration step do not change any prediction on the test set: the model alone, the guarded model and the guarded-and-calibrated model all score 87.92% accuracy. Calibration lowered log-loss from 0.2482 to 0.2463 but did not lower ECE further on this test set (0.012 after the guard, 0.014 after calibration); the repository's report notes that both are small and that the calibrated curve keeps the confidence bands honest where the raw model was over-confident in the middle range.

### 8.5.2 Per-class results

![Figure 8.1: Confusion matrix of bias model v4.1 on the test set, rows normalised, real-frequency weighting (plotted from `bias_v4_evaluation.json`)](figures/fig8_1_confusion.png){width=62%}

![Figure 8.2: Per-class precision, recall and F1, real-frequency weighting (plotted from `bias_v4_evaluation.json`)](figures/fig8_2_per_class.png){width=85%}

| Pattern | Precision | Recall | F1 |
|---|---|---|---|
| Disposition effect | 0.844 | 0.918 | 0.879 |
| Herd behaviour | 0.819 | 0.838 | 0.828 |
| Loss aversion | 0.667 | 0.849 | 0.747 |
| Rational | 0.939 | 0.875 | 0.906 |

Table: Table 8.4: Per-class metrics (real frequency)

Figure 8.1 and Table 8.4 show that loss aversion is the weakest class, with the lowest precision. The confusion matrix explains why: 8.0% of true herd cases are predicted as loss aversion, and 12.2% of true loss-aversion cases are predicted as rational. In a falling, fearful market a loss-making sale is permitted under both loss aversion (panic) and herd behaviour (selling into fear), and the data cannot always tell which motive won. Rational decisions are recognised with the highest precision (0.939), which matters because wrongly labelling a sensible decision as biased is the more harmful error for a user.

### 8.5.3 Calibration and confidence bands

![Figure 8.3: Reliability diagram after calibration; each point is a confidence bin with its case count (plotted from `bias_v4_evaluation.json`)](figures/fig8_3_reliability.png){width=58%}

| Band shown to user | Threshold | Share of analyses | Share correct |
|---|---|---|---|
| High | ≥ 0.85 | 68.4% | **98.7%** |
| Medium | 0.65–0.85 | 7.1% | 74.4% |
| Low | < 0.65 | 24.5% | 61.7% |

Table: Table 8.5: Confidence bands and how often each is right (test set, real frequency)

Figure 8.3 shows the calibrated points lying close to the diagonal. Most cases (66% by weight) fall in the 0.95–1.00 bin, where the model is right 99.1% of the time against a mean stated confidence of 99.1%. The bands in Table 8.5 are what the user sees: a High reading is right about 99 times in 100, while a Low reading usually means that two patterns are close to even.

**Single-reading cases.** In 44.3% of real-frequency test cases the definitions allow only one label (for example, holding a winner in a calm market can only be rational), which flatters the overall figures. On the remaining 55.7%—the cases that need judgement—accuracy is **78.3%** and macro-F1 0.747.

### 8.5.4 Results by regime and action

| Regime | Test cases | Accuracy | Macro-F1 |
|---|---|---|---|
| Normal | 950 | 89.5% | 0.793 |
| Bull | 713 | 87.8% | 0.834 |
| Correction | 975 | 87.8% | 0.839 |
| Crash | 979 | 77.6% | 0.771 |
| Euphoria | 383 | 90.3% | 0.895 |

Table: Table 8.6: Accuracy by market regime

| Action | Test cases | Accuracy (real frequency) |
|---|---|---|
| Sell | 1,582 | 84.9% |
| Hold | 1,641 | 90.0% |
| Buy more | 777 | 89.4% |

Table: Table 8.7: Accuracy by action

Crashes are the hardest regime (77.6%) because they are where loss aversion and herd behaviour overlap most.

### 8.5.5 Out-of-time generalisation

Trained only on decisions dated 2008–2019 and tested on 2020–2026, the model reaches **86.5%** accuracy and 0.826 macro-F1 at real frequency—close to the random-split result. This suggests the model is not merely memorising particular market days. It does not test robustness to genuinely new market regimes or to real investors.

## 8.6 Baselines and Ablations

![Figure 8.4: Accuracy of v4.1 against baselines and an upper bound on the same test set (plotted from `bias_v4_evaluation.json`)](figures/fig8_4_baselines.png){width=92%}

| Model | Accuracy | Macro-F1 |
|---|---|---|
| Always "rational" | 57.5% | — |
| Previous model v3 (same test cases) | 53.4% | 0.309 |
| Definitions only (call a bias whenever one can apply; loss aversion > disposition > herd) | 85.2% | 0.825 |
| v4.1 without the `allows_*` inputs | 87.6% | 0.832 |
| **v4.1** | **87.9%** | **0.840** |
| Ceiling: v4.1 also given the hidden tendencies | 90.0% | 0.866 |

Table: Table 8.8: Baselines, ablation and ceiling (real-frequency test set)

Table 8.8 is the most important table for interpreting the model honestly. Because labels are generated from written definitions, a rules-only baseline already reaches 85.2%. The model's gain over that baseline is 2.7 percentage points of accuracy. Its value lies in two places: it disagrees with the rules in 9.6% of cases and, when it does, it is right 64% of the time against 36% for the rules—it recognises rebalancing, a near goal, cutting a loss and a stated cash need; and it provides calibrated confidence, which the rules cannot. Removing the `allows_*` inputs costs only 0.3 points but introduces rule violations (0.08% of cases), which the guard would then have to correct. The ceiling of 90.0% shows that about one case in ten cannot be resolved from what the app observes, because it depends on hidden tendencies. Where two biases could both apply (5.3% of cases), neither the model (58.2%) nor the rules (56.8%) do much better than chance.

### 8.6.1 Comparison with other learners

To test whether XGBoost is the right learner, `scripts/evaluate_for_paper.py` trains logistic regression and a 500-tree random forest on the same 22 features, with the same definitional guard and real-frequency weighting, over five different split seeds (7, 11, 23, 42 and 101). On the original split (seed 7), it adds 2,000 bootstrap resamples of the test set for confidence intervals and McNemar's test for paired differences in correctness.

| Model | Accuracy | Macro-F1 | ECE | Log-loss |
|---|---|---|---|---|
| Always "rational" | 57.4% ± 0.0 | 0.182 | 0.426 | — |
| Rules only (label definitions) | 84.4% ± 0.6 | 0.818 ± 0.006 | 0.156 | — |
| Logistic regression | 84.9% ± 0.4 | 0.816 ± 0.003 | 0.018 ± 0.003 | 0.321 ± 0.022 |
| Random forest (500 trees) | 87.0% ± 0.5 | **0.833** ± 0.005 | **0.014** ± 0.003 | 0.282 ± 0.021 |
| XGBoost (deployed settings) | **87.2%** ± 0.6 | 0.831 ± 0.009 | 0.015 ± 0.004 | **0.267** ± 0.014 |

Table: Table 8.9: Learners compared over five split seeds, mean ± standard deviation (`paper_evaluation.json`)

| Model | Accuracy [95% CI] | XGBoost minus model [95% CI] | McNemar *p* |
|---|---|---|---|
| Rules only | 85.2% [83.9, 86.4] | +2.7 pp [+1.6, +3.8] | $2.4 \times 10^{-7}$ |
| Logistic regression | 85.5% [84.2, 86.6] | +2.4 pp [+1.4, +3.4] | $1.0 \times 10^{-5}$ |
| Random forest | 87.6% [86.5, 88.7] | +0.2 pp [−0.4, +0.9] | 0.096 |
| XGBoost | 87.8% [86.7, 89.0] | — | — |
| XGBoost as shipped (with calibration curve) | 87.9% [86.8, 89.1] | −0.1 pp [−0.5, +0.3] | 1.0 |

Table: Table 8.10: Seed-7 test set with bootstrap confidence intervals and McNemar tests

![Figure 8.5: (a) Accuracy with 95% bootstrap confidence intervals on the seed-7 test set; (b) mean ± SD over five split seeds (plotted from `paper_evaluation.json`)](figures/fig8_5_baselines_ci.png){width=100%}

Figure 8.5 and Tables 8.9–8.10 lead to three conclusions. First, XGBoost's advantage over the label definitions (+2.7 points) and over logistic regression (+2.4 points) is statistically significant; the non-linear interactions in the data matter. Second, XGBoost is **statistically tied with a random forest** (difference +0.2 points, confidence interval spanning zero, $p = 0.096$). We therefore do not claim that XGBoost is the better learner. It was kept because it has the lowest log-loss, exact and fast TreeSHAP explanations, and a portable native JSON model format. Third, the calibration curve does not change accuracy, and on this split it moved ECE only from 0.012 to 0.014, so its measurable benefit here is in keeping the displayed bands honest (Table 8.5) rather than in any headline metric.

## 8.7 Forced Sales

Of the test cases, 167 are sales forced by money (an uncovered shock, or payments above income with no emergency fund).

| Model and condition | Read as rational |
|---|---|
| v4.1, need stated in the comment | **90.6%** |
| v4.1, need not stated | 39.3% |
| v4.1, all forced sales | 71.9% |
| v4.0 (trained without money pressure) | 37.7% |

Table: Table 8.11: Forced sales read as rational

The gap between stated and unstated needs is exactly what the comment reader is designed to close: when the investor writes "fees are due in March", the `cash_need_stated` input is set and the sale is read as the forced sale it is.

## 8.8 Comparison with the Previous Model (v3)

v3 was evaluated on the same test cases with the same label mapping and was even given each case's true years of investing, which the app never has. It scored 53.4% accuracy, 0.309 macro-F1 and an ECE of 0.254, and it output a pattern the definitions rule out in 13.5% of cases. Two structural defects explain this. First, v3 did not see the action: across 600 test cases, changing only the action changed v4.1's answer in 83.7% of them and v3's in none. Second, v3's "what weighed most" explained a different pattern from the one it displayed in 98.6% of cases. Of the 13 scenario checks, v3 passed 5.

## 8.9 Sense Checks

The training script also runs 13 scenarios and 8 relational checks against a typical investor (dataset medians: age 38, ₹75,000 income, 12% position, emergency fund). v4.1 passes **21 of 21**. Selected examples:

| ID | Scenario or check | Expected | v4.1 |
|---|---|---|---|
| S1 | Calm market: selling a winner up 35% | Disposition | Disposition (0.98) |
| S3 | Calm market: holding a deep loser down 40% | Loss aversion | Loss aversion (0.65) |
| S4 | Calm market: selling at a 20% loss | Rational | Rational (1.00) |
| S6 | Crash: selling a winner up 25% into the fear | Herd | Herd (0.98) |
| S7 | Euphoric rally: buying more with little to spare | Herd | Herd (0.98) |
| S12 | Calm market: selling a winner, paying out more than earned, no fund | Rational | Rational (0.64) |
| S13 | Calm market: selling a winner, says the money is needed | Rational | Rational (0.64) |
| C1 | Same holding up 35%: the action changes the reading | sell → disposition; hold, buy → rational | Passed |
| C2 | Oversized holding (45%) reads less like disposition than a small one (8%) | lower | 0.56 vs 0.96 |
| C5 | Selling a winner reads more rational with the goal 2 years away than 20 | higher | 0.49 vs 0.05 |
| C6 | Gold share alone (5% vs 35%) barely moves the reading | small change | largest change 0.05 |
| C7 | Fearful market, selling at a 15% loss: stated cash need raises "rational" | higher | 0.09 → 0.49 |

Table: Table 8.12: Selected sense checks (full list in `results/reports/BIAS_MODEL_V4.md`)

C6 doubles as a sanity check on spurious features: gold share has no role in the label definitions, and the model correctly gives it almost no influence.

## 8.10 Simulator Evaluation Protocol

The simulator was evaluated on four questions using `scripts/evaluate_simulator_v2.py`:

1. **Realism.** Do simulated 1-year and 10-year NIFTY returns match rolling windows of the real index (217 one-year and 109 ten-year windows)?
2. **Horizon effect.** For a base case—a ₹1 lakh position, an investor earning ₹18 lakh a year with ₹11 lakh liquid—how do $p$ and the typical gap change from 1 to 30 years, for a stock down 17% and a fund up 30%?
3. **Sensitivity.** How do the results change with each assumption?
4. **Stock-specific risk.** For 24 NIFTY 50 stocks, measured beta and own volatility from 10 years of monthly prices, how often does holding win over 20 years?

`scripts/evaluate_for_paper.py` extends this with five further experiments, using the deployed simulator through two evaluation-only hooks (`paths=` to supply given market paths and `return_gaps=` to return every paired gap) that the app never uses:

5. **Generator comparison.** 10,000 ten-year paths from each of six generators—a lognormal (GBM) model, independent months, and 3-, 6-, 12- and 24-month blocks, all with the same historical mean—compared with the real index on one-year quantiles, the Kolmogorov–Smirnov (KS) distance and the autocorrelation of squared returns.
6. **Monte Carlo convergence.** The base case repeated 20 times at 250 to 10,000 paths.
7. **Population study.** 1,000 investors and positions drawn from dataset v4.1, each with their own horizon (median 23 years), asset type (40% funds) and the measured risk of one of the 24 stocks, with 1,000 paths each, under both the long-run assumptions and history replayed exactly.
8. **Walk-forward replay.** A fund up 30% run through every real 5-year and 10-year window of history with the same tax and cost accounting, and each real outcome placed in the simulated distribution for the same case.

Except where stated, runs use 1,000 paths. Results are presented in Chapter 9.

## 8.11 Causal Evaluation Protocol

Dataset v4.1 is used with `src/causal_v4.py`. The mechanism check confirms that the re-implemented generator reproduces all 20,000 stored motive shares exactly (maximum absolute error 0.0). Thirteen factors (including the gold-share negative control) are intervened on, and their effects on the probabilities of sell, hold and buy more are computed exactly and estimated by g-computation; DoWhy estimates and refutes the effects on selling. Six (pattern, action) situations and four habits are evaluated in the same way.

## 8.12 Explanation Evaluation Protocol

Explanation quality is measured by `scripts/evaluate_for_paper.py` on the current pipeline—bias model v4.1, simulator v2 and the template explainer, with AI wording switched off—for 166 sell and hold decisions drawn from the population study (78 rational, 38 disposition, 27 herd and 23 loss aversion). Each case is explained in English and in Hindi, giving 332 explanations. This replaces the project's earlier explanation check, which had been run on the previous model generation.

## 8.13 Reproducibility Considerations

- Fixed seeds: dataset 2026, split 7, model 42, cross-validation folds 1, simulator 2026, explanation evaluation 42.
- Cached market data (`data/v4/market_history.csv`, `data/sim_v2/monthly_history.csv`) makes the dataset and simulations reproducible offline.
- Pinned library versions and a verification script guard against silent changes in numerical libraries.
- Every analysis stores its market and portfolio snapshot and the stock's measured risk, so a re-run of a stored decision reproduces its inputs.
- The journal-paper evaluations regenerate in about four minutes with `python scripts/evaluate_for_paper.py`; learner comparisons use five fixed split seeds.
- The bias model is stored as native XGBoost JSON with a metadata file, avoiding pickle compatibility issues between library versions.
