# Simulation v2: evaluation and comparison with v1

Phase A3, 2026-10-07. Engine: `src/simulator_v2.py`. Evaluation: `scripts/evaluate_simulator_v2.py`, which writes every number below to `results/reports/simulator_v2_evaluation.json`. Tests: `tests/test_simulator_v2.py` (28) and `backend/tests/unit/test_sim_v2_bridge.py`.

## What changed

| | v1 | v2 |
|---|---|---|
| How far ahead | Always 20 years | **The investor's own horizon**, 1–30 years (20 only when none is given, and the page says so) |
| Market futures | 10,000 synthetic paths, wilder than the real NIFTY | **Real NIFTY and gold-in-rupee history** (Oct 2007–Sep 2026), resampled in 12-month blocks |
| The holding | Blended into a share/bond mix | **The holding itself**: its own measured beta and company-specific swings for a stock; the market for a fund |
| Selling | 5% cost, then "30% of the old share allocation" | **0.15% charges plus real capital-gains tax**; the money goes into the investor's own FDs, savings and gold in their current split |
| Tax | None | **FY 2025-26, new regime**: equity 20% short-term / 12.5% long-term above ₹1.25 lakh; FD and savings interest at the slab rate every year; gold 12.5% after 24 months; 4% cess |
| What is compared | Pre-tax wealth, average gap | **What you'd have in hand after tax**; the gap is the typical (median) difference, future by future |
| Hold vs sell | Different random markets for each | **The same markets** for both, so the comparison measures the decision, not noise |
| Monthly investing | None | **SIP, plus education fees once they end**, in both futures, to size the whole portfolio |
| Speed | — | ~0.1 s for 1,000 futures × 30 years |

## How the futures are built

1. **Swings from history.** Each simulated month is a real month of NIFTY (plus a 1.25% dividend yield) and gold in rupees, taken in 12-month blocks. Blocks wrap around the series ("circular" resampling), so the 2008 crash at the start is not under-sampled. This keeps the real link between shares and gold (correlation −0.08) and keeps crashes and recoveries together.
2. **Growth from stated long-run rates.** Replaying 2007–2026 as it was would assume gold keeps compounding at 14.8% a year. So the swings are kept and the typical growth is reset: shares 11%, gold 9%. FDs pay 6.75% and savings 3% before tax.
3. **The holding.** A stock moves with the market by its own **beta** and adds its own **company-specific swings**, both measured from its last 10 years of monthly prices when the analysis is submitted. Its typical growth is set the standard way: FD rate + beta × (share growth − FD rate). A stock with no history gets the median NIFTY 50 stock (beta 1.0, 21%), and the page says so. A mutual fund tracks the market within 3% a year.
4. **In hand after tax.** Every year shows what you'd get if you cashed in then: holding pays tax on the gain at that point; the sale paid its tax on day one, its FD and savings interest is taxed each year, and its gold is taxed when cashed in.

## Realism: simulated NIFTY against the real thing

| | Bad year (1 in 10) | Typical year | Good year (1 in 10) | Years below −20% |
|---|---|---|---|---|
| **Real NIFTY**, rolling 12 months (217 windows) | −7.5% | +11.3% | +33.3% | 4.6% |
| **v2** (long-run growth) | −6.9% | +11.6% | +34.7% | 4.3% |
| v2 replaying history exactly | −8.1% | +10.3% | +33.0% | 4.6% |
| v1 synthetic paths | −15.8% | +9.5% | +35.1% | 6.8% |

v2's single years match the real index closely; v1's bad years were twice as bad as reality. Over 10 years v2 is more spread out than the real record (real 10-year growth ran 8.8%–14.8% a year, v2's middle 80% is 2.4%–19.8%). The real record holds only about two independent decades, so v2 deliberately allows for decades better and worse than 2008–2026.

## The horizon matters

A ₹1 lakh position, investor on ₹18 lakh a year with ₹11 lakh liquid (FDs, savings, gold, other shares):

| Horizon | Stock down 17%: holding wins | Typical gap | Fund up 30%: holding wins | Typical gap |
|---|---|---|---|---|
| 1 year | 55% | ₹3,592 | 66% | ₹6,377 |
| 3 years | 60% | ₹13,950 | 70% | ₹22,244 |
| 5 years | 59% | ₹21,124 | 70% | ₹41,640 |
| 10 years | 62% | ₹59,925 | 75% | ₹1.09 L |
| 20 years | 64% | ₹1.81 L | 80% | ₹4.09 L |
| 30 years | 61% | ₹3.49 L | 81% | ₹13.9 L |

v1 gave everyone the 20-year answer. Under the recommendation rules a sale is a toss-up between 40% and 60%, so short horizons now often land there, while long horizons with a fund clearly favour holding.

## v1 and v2 on the same positions (20 years)

| Position | v1: holding wins | v2: holding wins | v2 at 5 years | Tax on selling today (v2) |
|---|---|---|---|---|
| Stock down 17% | 62% | 64% | 59% | none (a loss) |
| Stock up 30%, held 18 months | 64% | 64% | 59% | none (gain under ₹1.25 lakh) |
| Stock up 30%, held 8 months | 64% | 65% | 61% | ₹4,800 short-term |
| Fund up 30% | 64% | **80%** | 70% | none |

v1 could not tell these apart: the same 62–64% for a stock or a fund, a loss or a gain, short- or long-term. v2 separates them for the reasons a planner would give.

## Each stock is different

Measured from 10 years of monthly prices, the way the app measures them at submission. "Holding wins" is the 20-year base case above with each stock's own figures.

| Stock | Beta | Own swings | Holding wins | | Stock | Beta | Own swings | Holding wins |
|---|---|---|---|---|---|---|---|---|
| HDFCBANK | 1.03 | 14% | 73% | | KOTAKBANK | 0.96 | 18% | 66% |
| ICICIBANK | 1.21 | 17% | 71% | | ITC | 0.77 | 18% | 64% |
| LT | 1.17 | 17% | 71% | | TITAN | 1.03 | 24% | 61% |
| AXISBANK | 1.36 | 20% | 69% | | ASIANPAINT | 0.77 | 21% | 59% |
| ULTRACEMCO | 1.03 | 19% | 66% | | TCS | 0.76 | 21% | 59% |
| RELIANCE | 1.11 | 20% | 65% | | NESTLEIND | 0.53 | 19% | 58% |
| SBIN | 1.37 | 25% | 63% | | ONGC | 0.97 | 27% | 55% |
| BAJFINANCE | 1.68 | 29% | 62% | | HINDUNILVR | 0.44 | 20% | 54% |
| MARUTI | 1.00 | 22% | 63% | | INFY | 0.66 | 24% | 53% |
| M&M | 1.33 | 23% | 65% | | WIPRO | 0.60 | 25% | 50% |

20 of the 24 stocks are shown; all 24 are in the JSON. Median of the 24: beta 1.00, own swings 21% (the default when a stock can't be measured). For comparison, a diversified fund: 80%.

## Sensitivity (stock down 17%, 20 years; base: holding wins 64%, typical gap ₹1.81 L)

| Change | Holding wins | Typical gap |
|---|---|---|
| Shares grow 9% instead of 11% | 54% | ₹44,036 |
| Shares grow 13% | 72% | ₹3.86 L |
| Stock's own swings 15% instead of 21% | 72% | ₹3.09 L |
| Stock's own swings 35% | 45% | −₹70,915 |
| Gold grows 6% instead of 9% | 68% | ₹2.43 L |
| All the sale goes to an FD | 70% | ₹2.30 L |
| All the sale goes to gold | 50% | ₹2,365 |
| No slab tax on interest (income under ₹12.75 L) | 60% | ₹1.30 L |
| **History replayed exactly** (gold at ~15% a year) | 42% | −₹1.23 L |

The answer depends most on how fast shares are assumed to grow relative to the safer assets, and on how jumpy the particular stock is. That is why the assumptions are stated on the result page and each stock is measured rather than assumed.

## Monthly investing

The SIP and freed-up education fees go into the investor's current mix in **both** futures, so they don't change the gap between holding and selling (checked by test). They set the size of the whole portfolio, which shows how much the decision matters: with ₹15,000 a month, the typical gap above is 0.7% of the projected portfolio in 20 years; with no SIP, 1.7%.

## In the app

- `backend/core/simulator.py` builds the inputs (`build_sim_inputs`) from the analysis, the profile and the portfolio snapshot. Anything filled in is listed in `fixed_inputs` and shown under "How this was worked out": holding period, portfolio, monthly investing, stock risk.
- At submission, `backend/services/prices.py::stock_risk` measures the stock's beta and own swings and stores them in the analysis snapshot, so a re-run reproduces the result.
- New optional field: **Monthly investing (SIPs)** on the Portfolio page (migration 0010).
- The result page shows the real horizon, after-tax figures, the tax and charges on selling today, where the money would go, and the stock's measured risk. The explanation's "story of your money" (English and Hindi) describes the same.
- The recommendation quotes the horizon ("Holding beat selling in 63% of 22-year simulations").
- `SIMULATOR_VERSION=v1` in `.env` switches back to v1.

## Limitations

- **Typical growth is an assumption** (shares 11%, gold 9%, FD 6.75%). The sensitivity table shows how much it matters.
- **Beta-based growth** gives low-beta stocks (HUL, Infosys, Nestlé) a lower typical growth. That is the standard model; historically, steady stocks have often done better than it predicts.
- **Nominal rupees.** Inflation is not taken out; both futures are affected alike.
- **Where a sale goes** is assumed from the investor's current safer money. Someone who would buy another stock instead isn't modelled.
- **Tax rules are FY 2025-26** and assume the ₹1.25 lakh long-term exemption is available for this sale; losses aren't set off against other gains.
- **Mutual funds are treated as equity funds.** A debt or hybrid fund would be projected as too risky.
- **The rest of the portfolio is shown before tax**, and SIPs don't grow with salary.
- **Gold uses the international price**, before Indian import duty and GST, as elsewhere in the app.
