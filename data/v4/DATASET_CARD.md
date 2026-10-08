# Dataset v4.1: real-market, portfolio-aware investor decisions

Built by `src/dataset_v4.py`. It is the training data for bias model v4.1 and the basis of the cause-and-effect analysis.

| | |
|---|---|
| Cases | 20,000 investor decisions (`decisions_v4.csv`) |
| Market data | Real NIFTY 50 and India VIX, 10 Jun 2008 to 5 Oct 2026, 4,475 trading days (`market_history.csv`) |
| Trading days used | 4,268 different days |
| Reproducible | Fixed seed (2026) plus the cached market file give identical output |
| Tests | `tests/test_dataset_v4.py` (15) |
| Previous version | `data/v4/v4.0/` (before stretched households and cash shocks), kept with its model for comparison |

## How it differs from the v1–v3 data

| | v1–v3 | v4.1 |
|---|---|---|
| Market conditions | Synthetic, about 3–4× more volatile than the real NIFTY | Real values for a real trading day |
| Investor's action | In the data but excluded from features | sell / hold / buy more, used as a feature |
| "Buy more" | Absent | 19% of cases |
| Portfolio | Not modelled | Shares, funds, gold, FDs, savings, property, home loan, other loans, rent received |
| Monthly cash flow | Income and a single expense | Income, EMIs, rent paid, education fees and end year |
| Money pressure | None | Stretched borrowers, missing emergency funds, cash shocks, and a stated cash need |
| Gain or loss | Drawn independently of the market | Real NIFTY move over the holding period × stock beta, plus stock-specific noise |

## How each case is built

1. **A real day.** Days are sampled across 2008–2026, with stress over-represented so every motive has enough examples:

   | Regime | Real trading days | Cases (sampled) |
   |---|---|---|
   | Normal | 39.4% | 23.8% |
   | Bull | 29.0% | 17.8% |
   | Correction | 19.9% | 24.4% |
   | Crash | 6.6% | 24.5% |
   | Euphoria | 5.2% | 9.6% |

   Regimes come from the real 1-month return, VIX and 52-week drawdown (`_regime`). The bias model's evaluation and calibration re-weight to the real distribution.

2. **A household.** Age, income (rounded to ₹1,000), years investing, risk tolerance, horizon, home ownership, rent (12–40% of income), EMIs (home loan 15–45%, other loans 4–20%), education fees (3–20%) with an end year, and an emergency fund. The fund is likelier the more money is left over each month.

3. **Stretched borrowers.** 14% of borrowers carry extra debt (personal loans, cards, consumer EMIs) worth 25–65% of income on top. RBI's Financial Stability Report treats EMIs above 60% of income as the zone where a household's monthly margin turns negative.

4. **A portfolio.** Liquid assets scale with income and experience. Equity share follows risk tolerance. Gold is 4–38% of liquid assets (median 17%). Property, loans and rent received apply to home-owners.

5. **Hidden tendencies.** Loss aversion, herd sensitivity and disposition tendency, each partly explained by what the app can see (financial stress, experience, age, risk tolerance) and partly personal.

6. **A possible cash shock.** A job loss, a medical bill or fees falling due, with probability `0.04 + 0.06 × (no emergency fund) + 0.12 × clip((0.30 − surplus ratio) / 0.30, 0, 1)`. An emergency fund absorbs 70% of shocks. The money is **needed** when a shock isn't absorbed, or when fixed payments exceed income and there is no fund.

7. **A stated cash need.** What the app can observe, from the decision's comment: said by 65% of investors who need the money, and by 3% who don't (people mention money vaguely). This is the bias model's `cash_need_stated` input.

8. **Motives compete.** The situation decides which bias motives can apply (table below). Each competes with a weight from the investor's tendency and the strength of the situation; a rational motive always competes too, with a weight of `0.7 + 0.025 × years investing + 0.25 × emergency fund`, plus **3.0 when the money is needed** (necessity is a constraint, not a preference). The winning motive sets the action, and **the label is that motive**.

Hidden truth (the tendencies; whether a shock happened, what kind, whether the fund covered it) is stored in `latent_*` columns and is **never** a model input.

## Label definitions (agreed 2026-10-07, "both, by context")

| Label | Motive | Action | Applies when |
|---|---|---|---|
| Loss aversion | panic | sell | the position is at a loss, NIFTY fell 2%+ over the month, and fear is high (VIX ≥ 20 or a correction/crash) |
| Loss aversion | refusal | hold | the position is down 25% or more |
| Disposition effect | sell winner | sell | the position is up 8%+ in a normal or rising market |
| Disposition effect | hold loser | hold | the position is down 5–25% in a normal or rising market |
| Herd behaviour | sell into fear | sell | VIX ≥ 22 or NIFTY down 5%+ over the month |
| Herd behaviour | buy into a rally | buy more | NIFTY up 4%+ over the month |
| Rational | stay the course, add regularly, buy value, average down, cut a loss, rebalance, goal near, **needs cash** | any | the investor's own situation explains the action |

## Contents

| Label | Cases | Share |
|---|---|---|
| Rational | 11,134 | 55.7% |
| Herd behaviour | 3,929 | 19.6% |
| Disposition effect | 2,937 | 14.7% |
| Loss aversion | 2,000 | 10.0% |

Actions: hold 8,251 · sell 7,995 · buy more 3,754.

| Motive | Cases | | Motive | Cases |
|---|---|---|---|---|
| Rational: stay the course | 6,731 | | Rational: buy value | 702 |
| Herd: sell into fear | 2,405 | | Rational: goal near | 465 |
| Disposition: sell a winner | 2,223 | | Rational: cut a loss | 456 |
| Herd: buy into a rally | 1,524 | | Rational: rebalance | 363 |
| Rational: add regularly | 1,450 | | Rational: average down | 78 |
| Loss aversion: panic | 1,194 | | Loss aversion: refusal | 806 |
| **Rational: needs cash** | **889** | | Disposition: hold a loser | 714 |

| Feature | 5th pct | Median | 95th pct |
|---|---|---|---|
| Age | 28 | 38 | 56 |
| Monthly income | ₹26,000 | ₹75,000 | ₹2,19,000 |
| Fixed monthly payments | ₹0 | ₹16,500 | ₹79,500 |
| Money left each month (share of income) | 35% | 75% | 100% |
| Liquid assets | ₹1.6 L | ₹9.7 L | ₹62.7 L |
| Net worth | ₹0.9 L | ₹20.5 L | ₹1.88 Cr |
| Gold share of liquid | 4% | 17% | 38% |
| Position share of liquid | 2% | 12% | 32% |
| Gain or loss on position | −42% | +5% | +106% |
| NIFTY 30-day daily volatility | 0.005 | 0.011 | 0.034 |

Money pressure: 0.7% of households pay out more than they earn; 8.2% of borrowers have EMIs above 60% of income; 44% have no emergency fund; cash shocks hit 6.8% of decisions (medical 466, job loss 454, fees due 449); the money is needed in 1,165 cases, and 889 of them end in a forced sale.

Other shares: 45% pay rent, 45% pay EMIs, 36% pay education fees, 40% own property, 6% receive rent.

## How hard the labels are

Once the action is known, the labels are largely readable from the definitions themselves. Calling a bias whenever one can apply (loss aversion before disposition before herd) reaches 85.2% accuracy on the real-frequency test set. That follows from the labels being defined by written rules. The hard part is the rest: deciding when a permitted bias is *not* the explanation (rebalancing, a near goal, cutting a loss, needing the money), and choosing between loss aversion and herd behaviour in a sell-off. A model that also sees the hidden tendencies reaches 90.0%, so about one case in ten can't be told apart from what the app observes. Details: `results/reports/BIAS_MODEL_V4.md`.

## Limitations

- Investors are synthetic, though the markets are real. The motive weights encode behavioural-finance theory, not observed Indian investor behaviour; real feedback data would let them be learned rather than set.
- The money-pressure figures are anchored to published Indian figures where they exist (RBI's 60% EMI threshold; surveys finding about three in four Indians without an emergency fund), but the exact rates and the weight of a forced sale are set, not measured.
- One position per case. Investors hold whole portfolios, but each decision concerns one holding.
- In calm markets, by definition, herd behaviour and panic-driven loss aversion can't occur, so a calm-market analysis can only read disposition effect, loss-aversion "refusal" (a deep loser) or rational. That is correct, not a gap.
