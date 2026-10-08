# Dataset v4: real-market, portfolio-aware investor decisions

Built by `src/dataset_v4.py` (Phase A1, 2026-10-07). It is the training data for bias model v4.

| | |
|---|---|
| Cases | 20,000 investor decisions, 43 columns (`decisions_v4.csv`, 6.0 MB) |
| Market data | Real NIFTY 50 and India VIX, 10 Jun 2008 to 5 Oct 2026, 4,475 trading days (`market_history.csv`) |
| Trading days used | 4,255 different days |
| Reproducible | Fixed seed (2026) plus the cached market file give identical output |
| Tests | `tests/test_dataset_v4.py` (11 tests) |

## What changed from v1–v3

| | v1–v3 | v4 |
|---|---|---|
| Market conditions | Synthetic, about 3–4× more volatile than the real NIFTY | Real values for a real trading day |
| Investor's action | In the data but excluded from features | sell / hold / buy more, used as a feature |
| "Buy more" | Absent | 21% of cases |
| Portfolio | Not modelled | Shares, funds, gold, FDs, savings, property, home loan, other loans, rent received |
| Monthly cash flow | Income and a single expense | Income, EMIs, rent paid, education fees and end year (FOLIUM_MASTER.md §4) |
| Gain or loss | Drawn independently of the market | Real NIFTY move over the holding period × stock beta, plus stock-specific noise |

## How each case is built

1. **A real day.** Days are sampled across 2008–2026, with stress over-represented so every motive has enough examples:

   | Regime | Real trading days | Cases (sampled) |
   |---|---|---|
   | Normal | 39% | 24% |
   | Bull | 29% | 18% |
   | Correction | 20% | 25% |
   | Crash | 6.6% | 24% |
   | Euphoria | 5.2% | 9% |

   Regimes come from the real 1-month return, VIX and 52-week drawdown (see `_regime`). Model calibration (Phase A2) re-weights to the real distribution, so confidence reflects how often each market really occurs.

2. **A household.** Age, income (rounded to ₹1,000), years investing, risk tolerance, horizon, home ownership, rent, EMIs, education fees with an end year, and an emergency fund. The fund is more likely the more money is left over each month.

3. **A portfolio.** Liquid assets scale with income and experience. Equity share follows risk tolerance. Gold is 4–39% of liquid assets (median 17%), typical of Indian households. Property, loans and rent received apply to home-owners.

4. **Hidden tendencies.** Loss aversion, herd sensitivity and disposition tendency. Each is partly explained by things the app can see (financial stress, experience, age, risk tolerance) and partly personal. They are stored as `latent_*` columns and are **never** used as model features.

5. **Motives compete.** The situation decides which bias motives can apply (table below). Each competes with a weight from the investor's tendency and the strength of the situation; a rational motive always competes too. The winning motive sets the action, and **the label is that motive**. So the same sale can be rational or biased, and the model must infer which, as a person would.

## Label definitions (agreed 2026-10-07, "both, by context")

| Label | Motive | Action | Applies when |
|---|---|---|---|
| Loss aversion | panic | sell | the position is at a loss, NIFTY fell 2%+ over the month, and fear is high (VIX ≥ 20 or a correction/crash) |
| Loss aversion | refusal | hold | the position is down 25% or more |
| Disposition effect | sell winner | sell | the position is up 8%+ in a normal or rising market |
| Disposition effect | hold loser | hold | the position is down 5–25% in a normal or rising market |
| Herd behaviour | sell into fear | sell | VIX ≥ 22 or NIFTY down 5%+ over the month |
| Herd behaviour | buy into a rally | buy more | NIFTY up 4%+ over the month |
| Rational | stay the course, add regularly, buy value, average down, cut a loss, rebalance, goal near, needs cash | any | the investor's own situation explains the action |

## Contents

| Label | Cases | Share |
|---|---|---|
| Rational | 11,123 | 55.6% |
| Herd behaviour | 3,948 | 19.7% |
| Disposition effect | 3,053 | 15.3% |
| Loss aversion | 1,876 | 9.4% |

Actions: hold 8,603 · sell 7,187 · buy more 4,210.

| Feature | 5th pct | Median | 95th pct |
|---|---|---|---|
| Age | 28 | 38 | 57 |
| Monthly income | ₹26,000 | ₹75,000 | ₹2,21,000 |
| Fixed monthly payments | ₹0 | ₹13,000 | ₹58,500 |
| Liquid assets | ₹1.6 L | ₹9.7 L | ₹62.5 L |
| Net worth | ₹1.4 L | ₹21.9 L | ₹1.89 Cr |
| Gold share of liquid | 4% | 17% | 39% |
| Position share of liquid | 2% | 12% | 33% |
| Gain or loss on position | −41% | +6% | +109% |
| NIFTY 30-day daily volatility | 0.0052 | 0.0105 | 0.0340 |

80% have an emergency fund, 45% pay rent, 45% pay EMIs, 36% pay education fees, 40% own property and 6% receive rent.

## Difficulty check

A quick gradient-boosted baseline on observable features only (no hidden tendencies, no motive) reaches **87.6% accuracy, 0.847 macro-F1**.

Corrected in Phase A2: once the action is known, the labels are *largely* readable from the definitions themselves. Calling a bias whenever one can apply (loss aversion before disposition before herd) reaches 86.8% accuracy and 0.836 macro-F1 on the real-frequency test set. That follows from the labels being defined by written rules. The hard part is the remaining cases: deciding when a permitted bias is *not* the explanation (rebalancing, a near goal, cutting a loss), and choosing between loss aversion and herd behaviour in a sell-off. A model that also sees the hidden tendencies reaches 90.4%, so about 10% of cases can't be told apart from what the app observes. See `results/reports/BIAS_MODEL_V4.md`.

## Limitations

- Investors are synthetic, though the markets are real. The motive weights encode behavioural-finance theory, not observed Indian investor behaviour. Real feedback data (FOLIUM_MASTER.md §14) would let them be learned rather than set.
- One position per case. Investors hold whole portfolios, but each decision concerns one holding.
- In calm markets, by definition, herd behaviour and panic-driven loss aversion can't occur. A calm-market analysis can only read disposition effect, loss-aversion "refusal" (a deep loser) or rational. That is correct, not a gap.
