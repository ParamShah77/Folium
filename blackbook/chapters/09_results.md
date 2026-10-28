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

Figure 9.1 and Table 9.1 show that simulator v2's one-year distribution lies within 1.4 percentage points of the real index at all three quantiles, whereas the earlier v1 paths produced bad years roughly twice as bad as reality. Over ten years, v2 is deliberately wider than the real record: the real 10-year annualised growth ranged from 8.8% to 14.8% (10th to 90th percentile), while v2's middle 80% spans 2.4% to 19.8%. The repository's report justifies this: the real record holds only about two independent decades, so the simulator allows for decades better and worse than 2008–2026. This is a matching of one-year marginal distributions, not evidence of forecasting ability.

## 9.2 The Horizon Matters

![Figure 9.2: (a) Share of futures in which holding beats selling and (b) median paired gap, by horizon, for the base case (plotted from `simulator_v2_evaluation.json`)](figures/fig9_2_horizon.png){width=100%}

| Horizon | Stock down 17%: holding wins | Typical gap | Fund up 30%: holding wins | Typical gap |
|---|---|---|---|---|
| 1 year | 55% | ₹3,592 | 66% | ₹6,377 |
| 3 years | 60% | ₹13,950 | 70% | ₹22,244 |
| 5 years | 59% | ₹21,124 | 70% | ₹41,640 |
| 10 years | 62% | ₹59,925 | 75% | ₹1.09 L |
| 20 years | 64% | ₹1.81 L | 80% | ₹4.09 L |
| 30 years | 61% | ₹3.49 L | 81% | ₹13.9 L |

Table: Table 9.2: Effect of horizon (₹1 lakh position; investor on ₹18 lakh a year with ₹11 lakh liquid)

Figure 9.2(a) shows the central practical result of the simulator. For a single stock down 17%, the probability that holding beats selling stays between 55% and 64% at every horizon—mostly inside or near the 40–60% band that the recommendation rules treat as a toss-up. A diversified fund, which carries little company-specific risk, favours holding much more clearly, reaching 80% at 20 years. The previous simulator always used a 20-year horizon and therefore tilted every recommendation towards holding, even for someone who needs the money in three years. A second observation is that the typical gap grows with horizon even when the probability does not, because the size of outcomes grows with time; the year-by-year comparison is not monotonic in every scenario, which is why the result page shows the whole table rather than a single number.

The v1 simulator gave essentially the same answer (62–64% holding wins) for a stock or a fund, a gain or a loss, short- or long-term. v2 separates these cases for the reasons a planner would give: a fund up 30% held for a long horizon wins 80% of the time, while a short-term gain on a stock incurs ₹4,800 of short-term tax if sold today.

## 9.3 Sensitivity to Assumptions

![Figure 9.3: Sensitivity of the probability that holding wins (stock down 17%, 20 years; base 63.9%) to each assumption (plotted from `simulator_v2_evaluation.json`)](figures/fig9_3_sensitivity.png){width=90%}

| Change | Holding wins | Typical gap |
|---|---|---|
| Base case | 64% | ₹1.81 L |
| Shares grow 9% instead of 11% | 54% | ₹44,036 |
| Shares grow 13% | 72% | ₹3.86 L |
| Stock's own swings 15% instead of 21% | 72% | ₹3.09 L |
| Stock's own swings 35% | 45% | −₹70,915 |
| Gold grows 6% instead of 9% | 68% | ₹2.43 L |
| All the sale goes to an FD | 70% | ₹2.30 L |
| All the sale goes to gold | 50% | ₹2,365 |
| No slab tax on interest | 60% | ₹1.30 L |
| History replayed exactly (gold ~15% a year) | 42% | −₹1.23 L |

Table: Table 9.3: Sensitivity analysis

Figure 9.3 makes the dependence on assumptions explicit. The answer depends most on how fast shares are assumed to grow relative to the safer assets, and on how volatile the particular stock is. Replaying 2007–2026 exactly reverses the conclusion, because gold's exceptional run in that period would then be assumed to continue. This is why Folium measures each stock's risk at submission instead of assuming it, and why it states the growth assumptions on the result page.

## 9.4 Each Stock Is Different

![Figure 9.4: Measured company-specific volatility against the share of 20-year futures in which holding wins, for 24 NIFTY 50 stocks; colour shows measured beta (plotted from `simulator_v2_evaluation.json`)](figures/fig9_4_stocks.png){width=82%}

Figure 9.4 shows a clear negative relationship between a stock's own volatility and the advantage of holding it. HDFC Bank, with beta 1.03 and own swings of 14%, wins in 73% of 20-year futures; Wipro, with beta 0.60 and own swings of 25%, wins in 50%. The median of the 24 stocks—beta 1.00 and own swings 21%—is the default used when a stock cannot be measured. Two effects combine here: idiosyncratic volatility drags down the median compound outcome (the $-\sigma^2/2$ term), and a low beta lowers expected growth under the CAPM relation. The report notes that the second effect is a modelling choice: historically, steady low-beta stocks such as HUL, Infosys and Nestlé have often done better than CAPM predicts.

## 9.5 Monthly Investing and Portfolio Context

The SIP and freed-up education fees flow into the investor's current mix in both futures, so they leave the gap between holding and selling unchanged (verified by a unit test) but change the size of the whole portfolio. For the base case with ₹15,000 a month, the typical gap at 20 years is 0.7% of the projected portfolio; with no SIP it is 1.7%. Showing this helps an investor put a single decision in proportion.

## 9.6 Cause and Effect

![Figure 9.5: Effect of each factor on the chance of selling: true effect from the generator against the g-computation estimate (plotted from `results/causal_v4.json`)](figures/fig9_5_causal.png){width=100%}

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

Table: Table 9.4: Average effects in percentage points, true value with the g-computation estimate in brackets (selected rows of `CAUSAL_V4.md`)

| Accuracy measure | g-computation | DoWhy (linear) |
|---|---|---|
| Effects on selling, mean absolute error | **0.45 points** | 1.07 points |
| All 45 effects, mean absolute error | **0.48 points** | — |
| Correct direction (effects ≥ 0.5 points) | **97%** | — |
| Tendency effect within its situation, mean error | 1.4 points | **0.3 points** |
| Negative control, estimated effect on selling | −0.2 points | −0.0 points |
| Refutation tests passed | — | 12 of 13 |

Table: Table 9.5: Accuracy of the causal estimates against the known truth

Figure 9.5 and Table 9.4 show that money pressure dominates: a cash shock raises the chance of selling by about 32 points, and an emergency fund lowers it by 7.5 points, mostly by absorbing shocks. Market fear and a weak month push towards selling, a bigger holding pushes towards selling (largely through rebalancing) and strongly away from adding. Loss aversion's population-wide effect is small (+0.3 points) because it acts only in specific situations; within them it is substantial.

Table 9.5 shows that the two estimators are good at different things. The flexible g-computation model is far better across the whole population—the linear model, for example, overstates the effect of investing experience about fivefold (−5.8 points against a true −1.1). The linear DoWhy model is better at the effect of a tendency within its situation, where the flexible model smooths and understates it. The one direction g-computation gets wrong is the emergency fund's effect on *holding* (+1.4 true, −0.1 estimated), which the app does not display. The single failed refutation is the gold negative control, whose true effect is zero, so a test against chance cannot confirm anything—an expected outcome rather than a defect.

| Situation | Habit | True: before → after | Estimated: before → after |
|---|---|---|---|
| Loss aversion, sell | Reframing the loss as one step in a plan | 61% → 55% | 59% → 54% |
| Herd, sell | Not watching the crowd while deciding | 48% → 37% | 48% → 41% |
| Herd, buy more | Pausing for an independent analysis | 33% → 23% | 33% → 24% |
| Disposition, sell | Setting selling rules in advance | 56% → 39% | 54% → 40% |
| Disposition, hold | Setting selling rules in advance | 76% → 68% | 71% → 68% |

Table: Table 9.6: Effect of the most helpful habit in each situation (habit modelled as halving the tendency)

The estimates move in the right direction every time and, where they are off, they understate the benefit; they never overclaim. An unexpected finding is that habits can offset each other: for someone holding a deep loser, all three habits together barely help (43% → 42% in truth), while reframing alone helps a lot (43% → 36%), because calming crowd-following also removes some panic-selling and leaves more people holding the loser. This finding is the reason the app offers the single most helpful habit rather than a bundle.

## 9.7 Explanation Quality

![Figure 9.6: Explanation quality across 32 English and 32 Hindi explanations (plotted from `explanation_quality.json`)](figures/fig9_6_explanations.png){width=85%}

| Measure | English | Hindi | Target |
|---|---|---|---|
| Completeness (all six sections) | 100% | 100% | 100% |
| Actionability | 100% | 100% | 100% |
| Personalisation | 100% | 100% | 100% |
| Jargon leaks | 0 | 0 | 0 |
| Flesch reading ease (mean / minimum) | 78.3 / 77.4 | — | ≥ 60 |
| Words per sentence | 10.9 | 12.2 | Hindi ≤ 20 |
| Mean length (words) | 975 | 1,079 | — |

Table: Table 9.7: Explanation quality (`explanation_quality.json`, 64 explanations, AI wording off)

All targets are met (Figure 9.6). A Flesch score of 78.3 corresponds to "fairly easy" text. Flesch is not used for Hindi because its syllable model is undefined for Devanagari, so sentence length is used instead. These are measures of structure and readability; they do not show that the explanations change investor behaviour, which would require a user study.

## 9.8 Application Outputs

The repository does not contain screenshots of the running application, and the application was not run while preparing this report. The figures below are placeholders that must be replaced with real screenshots before submission; Appendix G gives the exact steps to capture them using the demo accounts created by `scripts/seed_demo.py`.

![Figure 9.7: [PLACEHOLDER — screenshot to be inserted] Result page: recommendation with reasons, both futures chart and pattern found](figures/placeholder_result.png){width=75%}

![Figure 9.8: [PLACEHOLDER — screenshot to be inserted] Live five-step progress during an analysis](figures/placeholder_progress.png){width=75%}

![Figure 9.9: [PLACEHOLDER — screenshot to be inserted] Six-part explanation in Hindi with the language switch](figures/placeholder_hindi.png){width=75%}

![Figure 9.10: [PLACEHOLDER — screenshot to be inserted] Portfolio page with net worth, allocation and holdings](figures/placeholder_portfolio.png){width=75%}

![Figure 9.11: [PLACEHOLDER — screenshot to be inserted] "Verify this record" result and "How this was worked out"](figures/placeholder_verify.png){width=75%}

## 9.9 Discussion

**What the results demonstrate.** On the development task, the four analytical components each do what they were designed to do. The classifier is accurate, calibrated and consistent with the label definitions; it changes its reading when the action changes, recognises forced sales when the need is stated, and generalises across time periods within the data. The simulator reproduces the real index's one-year return distribution closely and distinguishes stocks from funds, gains from losses, and short from long horizons. The causal estimates recover a known mechanism closely and never overclaim the benefit of habits. The explanations are complete, readable and free of jargon.

**What the results do not demonstrate.** The behavioural labels are synthetic, so 87.9% accuracy means that the model recovers the generator's labels, not that it diagnoses real investors. A rules-only baseline reaches 85.2%, so most of the accuracy follows from the definitions themselves. The simulator's agreement with history is a marginal-distribution check, not a forecast. The causal results describe the generator, not people. No study has measured whether investors who use Folium make better decisions or earn better returns.

**Practical significance.** The combination is more useful than any part alone. For a typical "sell a falling stock" request, the simulator often lands in the toss-up band, and the behavioural reading then decides whether waiting is the cautious choice. A stated cash need moves the reading to rational and lets the sale stand. The investor sees why, in their own language, with every figure traceable, and can later verify that the record has not been changed.

**Limitations of the evaluation.** No confidence intervals across multiple seeds are reported; baselines include rules-only and the previous model but not logistic regression or random forests on the same splits; the explanation evaluation predates the final models; and the Gemini paths have been tested only with a stand-in. These gaps are carried into the future work of Chapter 12.
