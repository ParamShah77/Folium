# Chapter 9: Results and Discussion

Chapter 8 reported the bias model in detail. This chapter presents the results of the simulator, the causal module and the explanation engine, discusses what all the results together demonstrate, and reserves space for screenshots of the running application.

## 9.1 Simulator Realism

![Figure 9.1: One-year NIFTY 50 return percentiles: real index (rolling windows) against simulator v2 and the earlier v1 (plotted from `simulator_v2_evaluation.json`)](figures/fig9_1_realism.png){width=88%}

| Statistic | Real NIFTY (217 windows) | Simulator v2 | v2 replaying history | v1 synthetic paths |
|---|---|---|---|---|
| Bad year (10th percentile) | −7.5% | −6.9% | −8.1% | −15.8% |
| Typical year (median) | +11.3% | +11.6% | +10.3% | +9.5% |
| Good year (90th percentile) | +33.3% | +34.7% | +33.0% | +35.1% |
| Years below −20% | 4.6% | 4.3% | 4.6% | 6.8% |

Table: Table 9.1: Realism of simulated one-year returns

Figure 9.1 and Table 9.1 show that simulator v2's one-year distribution lies within 1.4 percentage points of the real index at all three quantiles, whereas the earlier v1 paths produced bad years roughly twice as bad as reality. Over ten years, v2 is deliberately wider than the real record: the real 10-year annualised growth ranged from 8.8% to 14.8% (10th to 90th percentile), while v2's middle 80% spans 2.4% to 19.8%. The real record holds only about two independent decades, so the simulator allows for decades better and worse than 2008–2026. This is a matching of one-year marginal distributions, not evidence of forecasting ability.

## 9.2 Why a 12-Month Block Bootstrap

![Figure 9.2: (a) Kolmogorov–Smirnov distance between each generator's one-year returns and the real NIFTY 50; (b) autocorrelation of squared monthly returns, a measure of volatility clustering (plotted from `paper_evaluation.json`)](figures/fig9_2_generators.png){width=100%}

| Generator | 1-yr p10 | 1-yr median | 1-yr p90 | Years < −20% | ACF of squared returns, lag 1 / 3 / 6 | KS distance |
|---|---|---|---|---|---|---|
| **Real NIFTY** (217 windows) | −7.5% | 11.3% | 33.3% | 4.6% | 0.136 / 0.051 / 0.093 | — |
| Lognormal (GBM) | −16.2% | 9.5% | 42.1% | 6.4% | −0.01 / −0.01 / −0.01 | 0.132 |
| Independent months | −15.9% | 10.6% | 41.2% | 6.7% | −0.01 / −0.01 / −0.01 | 0.108 |
| Block 3 months | −14.3% | 10.6% | 37.8% | 6.3% | 0.077 / −0.01 / −0.01 | 0.083 |
| Block 6 months | −13.7% | 10.5% | 35.9% | 6.3% | 0.100 / 0.029 / −0.01 | 0.072 |
| **Block 12 months (used)** | **−8.1%** | **10.3%** | **33.1%** | **4.7%** | **0.101 / 0.035 / 0.025** | **0.027** |
| Block 24 months | −8.1% | 10.3% | 33.0% | 4.9% | 0.105 / 0.023 / 0.033 | 0.030 |

Table: Table 9.2: Six market-path generators against the real index (10,000 ten-year paths each, same historical mean)

Table 9.2 and Figure 9.2 justify the generator choice experimentally. All six generators share the same average growth, so only the shape and the dependence differ. The 12-month block bootstrap is the only one that reproduces both the spread of real one-year returns and volatility clustering: its KS distance (0.027) is a quarter of the independent-months bootstrap's (0.108) and a fifth of GBM's (0.132). GBM and independent months have no volatility clustering at all and make bad years about twice as bad as reality. Moving to 24-month blocks changes almost nothing, so 12 months is a reasonable choice. Because the 19-year record contains only one independent decade, ten-year KS distances (about 0.34 for every generator) carry no information and are not used to rank generators; the real windows also overlap, so KS distances are descriptive rather than formal tests.

## 9.3 The Horizon Matters, and How Stable the Numbers Are

![Figure 9.3: (a) Share of futures in which holding beats selling and (b) median paired gap, by horizon, for the base case (plotted from `simulator_v2_evaluation.json`)](figures/fig9_3_horizon.png){width=100%}

| Horizon | Stock down 17%: holding wins | Typical gap | Fund up 30%: holding wins | Typical gap |
|---|---|---|---|---|
| 1 year | 55% | ₹3,592 | 66% | ₹6,377 |
| 3 years | 60% | ₹13,950 | 70% | ₹22,244 |
| 5 years | 59% | ₹21,124 | 70% | ₹41,640 |
| 10 years | 62% | ₹59,925 | 75% | ₹1.09 L |
| 20 years | 64% | ₹1.81 L | 80% | ₹4.09 L |
| 30 years | 61% | ₹3.49 L | 81% | ₹13.9 L |

Table: Table 9.3: Effect of horizon (₹1 lakh position; investor on ₹18 lakh a year with ₹11 lakh liquid)

Figure 9.3(a) shows the central practical result of the simulator. For a single stock down 17%, the probability that holding beats selling stays between 55% and 64% at every horizon—mostly inside or near the 40–60% band that the recommendation rules treat as a toss-up. A diversified fund, which carries little company-specific risk, favours holding much more clearly, reaching 80% at 20 years. The previous simulator always used a 20-year horizon and therefore tilted every recommendation towards holding, even for someone who needs the money in three years. The typical gap grows with horizon even when the probability does not, because the size of outcomes grows with time.

![Figure 9.4: Monte Carlo convergence for the base case, 20 repeats per size: (a) probability that holding wins, mean ± SD; (b) run-to-run variation of the median rupee gap (plotted from `paper_evaluation.json`)](figures/fig9_4_convergence.png){width=100%}

| Futures | P(hold wins), mean ± SD | Median gap, mean ± SD |
|---|---|---|
| 250 | 0.637 ± 0.030 | ₹1,60,784 ± 36,940 |
| 500 | 0.634 ± 0.024 | ₹1,70,247 ± 32,938 |
| **1,000 (app)** | **0.633 ± 0.017** | **₹1,68,549 ± 24,140** |
| 2,000 | 0.628 ± 0.010 | ₹1,63,326 ± 14,347 |
| 5,000 | 0.632 ± 0.008 | ₹1,67,786 ± 11,317 |
| 10,000 | 0.632 ± 0.006 | ₹1,67,712 ± 7,700 |

Table: Table 9.4: Monte Carlo convergence (base case: stock down 17%, 20 years)

Figure 9.4 and Table 9.4 show how much of each number is simulation noise. At the app's 1,000 futures, the probability that holding wins—the input to the recommendation rules—is stable to about ±1.7 points, close to the theoretical binomial standard error of ±1.5 points. The median rupee gap is noisier, varying by about ±14% between runs. This is why the verdict is driven by the probability rather than the rupee figure, and why the rupee gap is presented as "about" a value. Raising the count to 5,000 futures would roughly halve this variation if the rupee figure became more prominent.

## 9.4 Results Across 1,000 Investors and Sensitivity to Assumptions

![Figure 9.5: Share of 1,000 simulated investors whose analysis lands in each verdict band, overall, by horizon, by asset type, and with history replayed exactly (plotted from `paper_evaluation.json`)](figures/fig9_5_population.png){width=95%}

| Group (long-run assumptions) | Investors | Mean P(hold wins) | HOLD / toss-up / SELL |
|---|---|---|---|
| All | 1,000 | 0.635 | 58.1% / 40.8% / 1.1% |
| Horizon 1–3 years | 52 | 0.571 | 29% / 71% / 0% |
| Horizon 4–10 years | 100 | 0.598 | 43% / 57% / 0% |
| Horizon 11–20 years | 275 | 0.624 | 57% / 41% / 2% |
| Horizon 21–30 years | 573 | 0.652 | 64% / 35% / 1% |
| Single stock | 596 | 0.562 | 31% / 67% / 2% |
| Equity fund | 404 | 0.742 | 99% / 1% / 0% |
| Position at a gain / at a loss | 543 / 457 | 0.635 / 0.635 | 59% / 57% HOLD |
| *History replayed exactly* | 1,000 | 0.380 | 5.6% / 37.8% / 56.6% |

Table: Table 9.5: Paired simulation over 1,000 investors drawn from dataset v4.1

Figure 9.5 and Table 9.5 move from single examples to a population. Under the long-run assumptions, holding is clearly favoured for 58% of investors, the comparison is a toss-up for 41%, and selling is favoured for only 1%. The answer depends strongly on what is held and for how long: almost every equity fund (99%) clearly favours holding, while only 31% of single stocks do, because company-specific risk drags down the typical outcome. Short horizons are mostly toss-ups. Whether the position is currently at a gain or a loss makes no difference to the projection, which is exactly the point of the disposition-effect literature: the purchase price should not matter for a forward-looking decision.

The last row is the most important caution in this report. If history from 2007 to 2026 is replayed exactly, gold compounds at about 15% a year instead of the assumed 9%, and **86% of verdicts change**: 52.5% of HOLD verdicts become a toss-up or SELL, and the sign of the median gap reverses for 67% of investors.

![Figure 9.6: Share of verdicts that change across 300 investors when one assumption is changed at a time (plotted from `paper_evaluation.json`)](figures/fig9_6_sensitivity.png){width=90%}

| Change | Base case: P(hold), median gap | Verdicts that change (300 investors) |
|---|---|---|
| None (base) | 0.642, ₹1,88,632 | — |
| Shares grow 9% (not 11%) | 0.536, ₹42,336 | **41.7%** |
| Shares grow 13% | 0.740, ₹4,13,079 | 19.7% |
| Gold grows 6% (not 9%) | 0.698, ₹2,63,194 | 21.7% |
| FD rate 5.5% / 8% (not 6.75%) | 0.664 / 0.620 | 7.3% / 5.3% |
| Stock's own swings 15% / 35% (not 21%) | 0.722 / 0.438 | 19.3% / **41.0%** |
| Sale costs 0.5% or 1% (not 0.15%) | 0.642 | 0% |
| Independent months / 6- / 24-month blocks | 0.636 / 0.626 / 0.648 | 10.3% / 6.7% / 7.0% |
| Tax rules before 23 July 2024 | 0.644 | 1.0% |
| Future starts in a bad year (worst 10%) | 0.518, ₹9,626 | **62.0%** |
| Future starts in a good year (best 10%) | 0.756, ₹4,66,968 | 26.7% |
| History replayed exactly | 0.430, −₹1,32,747 | **86.3%** |

Table: Table 9.6: Sensitivity analysis, one assumption at a time

Figure 9.6 ranks the assumptions by how many verdicts they change. The answer depends most on the growth assumptions (shares and gold), on how volatile the particular stock is, and on the kind of year the future starts in. It barely depends on the block length, the July 2024 tax change, or sale costs; the cost is charged on cashing out in both futures, so it largely cancels. This is why Folium measures each stock's risk at submission instead of assuming it, and why the growth assumptions are stated on every result page.

## 9.5 Each Stock Is Different

![Figure 9.7: Measured company-specific volatility against the share of 20-year futures in which holding wins, for 24 NIFTY 50 stocks; colour shows measured beta (plotted from `simulator_v2_evaluation.json`)](figures/fig9_7_stocks.png){width=82%}

Figure 9.7 shows a clear negative relationship between a stock's own volatility and the advantage of holding it. HDFC Bank, with beta 1.03 and own swings of 14%, wins in 73% of 20-year futures; Wipro, with beta 0.60 and own swings of 25%, wins in 50%. The median of the 24 stocks—beta 1.00 and own swings 21%—is the default used when a stock cannot be measured. Two effects combine here: idiosyncratic volatility drags down the median compound outcome (the $-\sigma^2/2$ term), and a low beta lowers expected growth under the CAPM relation. The second effect is a modelling choice: historically, steady low-beta stocks such as HUL, Infosys and Nestlé have often done better than CAPM predicts.

## 9.6 Paired Gap Against Real History

| | Real windows (independent) | Hold won, real | Hold won, simulated | Real median gap | Simulated median gap | Real outcome inside simulated 10–90% band |
|---|---|---|---|---|---|---|
| 5 years | 169 (3) | 88.8% | 61.0% | ₹56,378 | ₹23,133 | 99.4% |
| 10 years | 109 (1) | 100% | 60.7% | ₹1,25,114 | ₹44,327 | 100% |

Table: Table 9.7: Walk-forward replay of a fund up 30% through every real window

Table 9.7 places what actually happened in each real 5-year and 10-year window inside the simulated distribution for the same case. Every real outcome but one falls inside the simulated 10th–90th percentile band, and the real outcomes sit in the upper middle of the band (median percentile 0.66–0.67): 2007–2026 was a good period for holding equity against this mix of safer assets. With only one to three independent windows, this is a consistency check, not a validation of forecasting ability.

| Year | HOLD median | SELL median | Difference of medians | Median paired gap [p10, p90] | Hold wins |
|---|---|---|---|---|---|
| 5 | ₹1,51,619 | ₹1,29,647 | ₹21,972 | ₹21,787 [−75,796, 2,13,706] | 57.6% |
| 10 | ₹2,33,490 | ₹1,69,700 | ₹63,790 | ₹51,717 [−1,19,371, 5,12,349] | 61.2% |
| 14 | ₹3,10,324 | ₹2,16,030 | ₹94,294 | ₹85,272 [−1,65,144, 9,17,770] | 61.6% |

Table: Table 9.8: Base-case investor, stock down 17%, 14 years: difference of medians against the median paired gap

Table 9.8 illustrates a methodological point. The *difference of the two medians* and the *median of the paired differences* are not the same quantity; they differ here by up to 19% at year 10. Folium reports the paired gap (Section 7.7), with its 10th–90th percentile range, because that range also shows that holding loses in a substantial share of futures even when it wins in the typical one.

## 9.7 Monthly Investing and Portfolio Context

The SIP and freed-up education fees flow into the investor's current mix in both futures, so they leave the gap between holding and selling unchanged (verified by a unit test) but change the size of the whole portfolio. For the base case with ₹15,000 a month, the typical gap at 20 years is 0.7% of the projected portfolio; with no SIP it is 1.7%. Showing this helps an investor put a single decision in proportion.

## 9.8 Cause and Effect

![Figure 9.8: Effect of each factor on the chance of selling: true effect from the generator against the g-computation estimate (plotted from `results/causal_v4.json`)](figures/fig9_8_causal.png){width=100%}

| Factor | Change | Sell | Hold | Buy more |
|---|---|---|---|---|
| A cash shock | having one vs not | +31.8 (+31.3) | −23.6 (−23.3) | −8.2 (−8.0) |
| Having an emergency fund | having one vs not | −7.5 (−5.6) | +1.4 (−0.1) | +6.1 (+5.7) |
| Higher market fear | VIX +10 points | +6.4 (+3.9) | −4.7 (−2.9) | −1.7 (−1.0) |
| A weaker month for NIFTY | 5 points worse | +5.6 (+5.8) | −3.9 (−3.7) | −1.7 (−2.1) |
| A bigger holding | +10 points of liquid assets | +4.8 (+4.7) | +2.7 (+2.8) | −7.5 (−7.5) |
| More years until money is needed | +5 years | −2.4 (−2.3) | +1.4 (+1.4) | +1.0 (+1.0) |
| More swayed by the crowd | +0.1 tendency | +1.9 (+1.8) | −2.8 (−2.5) | +0.9 (+0.7) |
| More gold (negative control) | +10 points | 0.0 (−0.2) | 0.0 (+0.4) | 0.0 (−0.2) |

Table: Table 9.9: Average effects in percentage points, true value with the g-computation estimate in brackets (selected rows of `CAUSAL_V4.md`)

| Accuracy measure | g-computation | DoWhy (linear) |
|---|---|---|
| Effects on selling, mean absolute error | **0.45 points** | 1.07 points |
| All 45 effects, mean absolute error | **0.48 points** | — |
| Correct direction (effects ≥ 0.5 points) | **97%** | — |
| Tendency effect within its situation, mean error | 1.4 points | **0.3 points** |
| Negative control, estimated effect on selling | −0.2 points | −0.0 points |
| Refutation tests passed | — | 12 of 13 |

Table: Table 9.10: Accuracy of the causal estimates against the known truth

Figure 9.8 and Table 9.9 show that money pressure dominates: a cash shock raises the chance of selling by about 32 points, and an emergency fund lowers it by 7.5 points, mostly by absorbing shocks. Market fear and a weak month push towards selling; a bigger holding pushes towards selling (largely through rebalancing) and strongly away from adding. Loss aversion's population-wide effect is small (+0.3 points) because it acts only in specific situations; within them it is substantial.

Table 9.10 shows that the two estimators are good at different things. The flexible g-computation model is far better across the whole population—the linear model, for example, overstates the effect of investing experience about fivefold (−5.8 points against a true −1.1). The linear DoWhy model is better at the effect of a tendency within its situation, where the flexible model smooths and understates it. The one direction g-computation gets wrong is the emergency fund's effect on *holding* (+1.4 true, −0.1 estimated), which the app does not display. The single failed refutation is the gold negative control, whose true effect is zero, so a test against chance cannot confirm anything—an expected outcome rather than a defect.

| Situation | Habit | True: before → after | Estimated: before → after |
|---|---|---|---|
| Loss aversion, sell | Reframing the loss as one step in a plan | 61% → 55% | 59% → 54% |
| Herd, sell | Not watching the crowd while deciding | 48% → 37% | 48% → 41% |
| Herd, buy more | Pausing for an independent analysis | 33% → 23% | 33% → 24% |
| Disposition, sell | Setting selling rules in advance | 56% → 39% | 54% → 40% |
| Disposition, hold | Setting selling rules in advance | 76% → 68% | 71% → 68% |

Table: Table 9.11: Effect of the most helpful habit in each situation (habit modelled as halving the tendency)

The estimates move in the right direction every time and, where they are off, they understate the benefit; they never overclaim. An unexpected finding is that habits can offset each other: for someone holding a deep loser, all three habits together barely help (43% → 42% in truth), while reframing alone helps a lot (43% → 36%), because calming crowd-following also removes some panic-selling and leaves more people holding the loser. This finding is the reason the app offers the single most helpful habit rather than a bundle.

## 9.9 Explanation Quality

![Figure 9.9: Explanation quality across 166 English and 166 Hindi explanations on the current pipeline (plotted from `paper_evaluation.json`)](figures/fig9_9_explanations.png){width=85%}

| Measure | English | Hindi | Target |
|---|---|---|---|
| Completeness (all six sections) | 100% | 100% | 100% |
| Actionability | 100% | 100% | 100% |
| Personalisation | 100% | 100% | 100% |
| Jargon leaks | 0 | 0 | 0 |
| Flesch reading ease (mean / minimum) | 76.4 / 73.5 | — | ≥ 60 |
| Words per sentence | 11.3 | 12.8 | Hindi ≤ 20 |
| Mean length (words) | 939 | 1,058 | — |

Table: Table 9.12: Explanation quality on bias model v4.1, simulator v2 and the template explainer (332 explanations, AI wording off)

All targets are met for every one of the 332 explanations (Figure 9.9). A Flesch score of 76.4 corresponds to "fairly easy" text, and even the hardest explanation (73.5) is well above the target of 60. Flesch is not used for Hindi because its syllable model is undefined for Devanagari, so sentence length is used instead. These are measures of structure and readability; they do not show that the explanations change investor behaviour, which would require a user study.

## 9.10 Application Outputs

The repository does not contain screenshots of the running application, and the application was not run while preparing this report. The figures below are placeholders that must be replaced with real screenshots before submission; Appendix G gives the exact steps to capture them using the demo accounts created by `scripts/seed_demo.py`.

![Figure 9.10: [PLACEHOLDER — screenshot to be inserted] Result page: recommendation with reasons, both futures chart and pattern found](figures/placeholder_result.png){width=75%}

![Figure 9.11: [PLACEHOLDER — screenshot to be inserted] Live five-step progress during an analysis](figures/placeholder_progress.png){width=75%}

![Figure 9.12: [PLACEHOLDER — screenshot to be inserted] Six-part explanation in Hindi with the language switch](figures/placeholder_hindi.png){width=75%}

![Figure 9.13: [PLACEHOLDER — screenshot to be inserted] Portfolio page with net worth, allocation and holdings](figures/placeholder_portfolio.png){width=75%}

![Figure 9.14: [PLACEHOLDER — screenshot to be inserted] "Verify this record" result and "How this was worked out"](figures/placeholder_verify.png){width=75%}

![Figure 9.15: [PLACEHOLDER — screenshot to be inserted] Google sign-in return and the Welcome profile step for a new Google account](figures/placeholder_google.png){width=75%}

## 9.11 Discussion

**What the results demonstrate.** On the development task, the four analytical components each do what they were designed to do. The classifier is accurate, calibrated and consistent with the label definitions. It is significantly better than the rules and a linear model and on par with a random forest; it changes its reading when the action changes, recognises forced sales when the need is stated, and generalises across time periods within the data. The simulator's generator was chosen experimentally against five alternatives; it reproduces the real index's one-year distribution and volatility clustering, its probability output is stable at the app's path count, and every real historical window falls inside its band. The causal estimates recover a known mechanism closely and never overclaim the benefit of habits. The explanations are complete, readable and free of jargon on the current models.

**What the results do not demonstrate.** The behavioural labels are synthetic, so 87.9% accuracy means that the model recovers the generator's labels, not that it diagnoses real investors. A rules-only baseline reaches 85.2%, so most of the accuracy follows from the definitions themselves. The simulator's agreement with history is a distributional and consistency check, not a forecast, and its verdicts depend heavily on the stated growth assumptions (Table 9.6). The causal results describe the generator, not people. No study has measured whether investors who use Folium make better decisions or earn better returns.

**Practical significance.** The combination is more useful than any part alone. For a typical "sell a falling stock" request, the simulator often lands in the toss-up band (two-thirds of single-stock positions do), and the behavioural reading then decides whether waiting is the cautious choice. A stated cash need moves the reading to rational and lets the sale stand. The investor sees why, in their own language, with every figure traceable, and can later verify that the record has not been changed.

**Limitations of the evaluation.** The remaining gaps are those that only real data can close: there are no real investor labels, no user study, and only one independent decade of market history, which is why ten-year generator comparisons and the walk-forward replay are reported as consistency checks only. The optional Gemini paths have been tested with a stand-in rather than the live service. These gaps define the research phase of the roadmap in Chapter 12.
