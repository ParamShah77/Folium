# Chapter 7: Algorithms and Technical Foundations

This chapter states the algorithms used in Folium formally. Notation follows the List of Symbols. Each section ends with the parameter choices made in the repository and the reason for them.

## 7.1 Motive Competition in the Data Generator

For a case with situation $s$ and investor $i$, let $\mathcal{M}(s)$ be the set of applicable bias motives (Listing 6.1) and $r$ the rational motive chosen by `rational_action`. The rational weight is

$$ w_r = 0.7 + 0.025\,y_i + 0.25\,e_i + 3.0\,c_i , $$

where $y_i$ is years of investing, $e_i \in \{0,1\}$ indicates an emergency fund and $c_i \in \{0,1\}$ indicates that the money is genuinely needed. For a bias motive $m$ with label $\ell(m)$,

$$ w_m = S_{\ell(m)} \; \tau_{i,\ell(m)}^{\,1.5} \; I_m(s), $$

where $\tau_{i,\ell} \in [0,1]$ is the investor's hidden tendency, $S_{\text{loss aversion}} = 3.4$, $S_{\text{herd}} = 2.0$, $S_{\text{disposition}} = 2.8$, and $I_m(s) \ge 1$ is the intensity of the situation (for example $I = 1 + \min(3|g|, 1.5)$ for a panic sale with loss $g$, and $I = 1 + \text{crowd ratio}$ for selling into fear, where the crowd ratio is $\mathrm{clip}((V - 10)/40,\ 0.05,\ 1)$ for India VIX value $V$). One motive is sampled with probability

$$ P(\text{motive} = k) = \frac{w_k}{w_r + \sum_{m \in \mathcal{M}(s)} w_m} , $$

and it fixes both the action and the label. The exponent 1.5 makes strong tendencies matter disproportionately, and the large weight for a genuine cash need encodes the idea that necessity is a constraint, not a preference.

## 7.2 Gradient-Boosted Multi-Class Classification

### 7.2.1 Model

Let $\mathbf{x} \in \mathbb{R}^{22}$ be the feature vector and $y \in \{1, \dots, K\}$ with $K = 4$. XGBoost learns, for each class, an additive model of $M$ regression trees:

$$ F_k(\mathbf{x}) = \sum_{m=1}^{M} f_{m,k}(\mathbf{x}), \qquad \hat{p}_k(\mathbf{x}) = \frac{e^{F_k(\mathbf{x})}}{\sum_{j=1}^{K} e^{F_j(\mathbf{x})}} . $$

The training objective combines the weighted multi-class log-loss with a complexity penalty for each tree [5]:

$$ \mathcal{L} = \sum_{i=1}^{n} w_i \, \ell\big(y_i, \hat{\mathbf{p}}(\mathbf{x}_i)\big) + \sum_{m,k} \Omega(f_{m,k}), \qquad \Omega(f) = \gamma T + \tfrac{1}{2}\lambda \lVert \boldsymbol{\omega} \rVert^2 , $$

where $T$ is the number of leaves, $\boldsymbol{\omega}$ the leaf weights, and $w_i$ the regime re-weighting factor $w_i = \frac{\pi^{\text{real}}_{r(i)}}{\pi^{\text{sample}}_{r(i)}}$ for the regime $r(i)$ of case $i$. Each boosting round fits a tree to the first and second derivatives of the loss (Newton boosting), with the leaf weight $\omega_j = -\frac{G_j}{H_j + \lambda}$ for gradient sum $G_j$ and Hessian sum $H_j$ in leaf $j$.

### 7.2.2 Parameter choices

`max_depth = 5`, `learning_rate = 0.03`, `subsample = 0.85`, `colsample_bytree = 0.85`, `min_child_weight = 3`, `reg_lambda = 2.0`, `tree_method = "hist"`, 402 trees. A small learning rate with early stopping trades training time (still only about 81 seconds end to end) for smoother fits; depth 5 allows interactions of up to five inputs, enough for "a loss, in a falling market, with high fear, with a sell action"; row and column subsampling reduce variance.

### 7.2.3 Alternatives considered

Logistic regression would need hand-built interaction terms; a neural network would need more data and lose exact SHAP values; a random forest is a reasonable alternative but tends to give less sharp probabilities. The repository's earlier versions (v1–v3) were also XGBoost but without the action, the portfolio or real markets; the step change from 53.4% to 87.9% accuracy came from better data and features rather than from a different algorithm.

## 7.3 Definitional Guard

Let $m_k(\mathbf{x}) = 1$ if label $k$ is allowed by the definitions for this situation and action (Listing 6.1), with $m_{\text{rational}} \equiv 1$. The guarded probabilities are

$$ \tilde{p}_k = \frac{m_k\,\hat{p}_k}{\sum_{j} m_j\,\hat{p}_j} . $$

Because the model also receives the $m_k$ as inputs (`allows_*`), on the test set the guard never had to change an answer (`guard_changed_answer = 0.0`); it remains as a hard guarantee.

## 7.4 Isotonic Calibration of the Top Label

Let $c = \max_k \tilde{p}_k$ be the confidence of the chosen class and $z \in \{0,1\}$ whether that choice is correct. Isotonic regression finds the non-decreasing function $g$ minimising $\sum_i w_i (z_i - g(c_i))^2$. Plain isotonic regression is a step function, so the repository uses *centred* isotonic regression [47]: the weighted centre of each constant block becomes a knot, and the knots are joined by straight lines, giving a strictly increasing curve. The curve is fitted on out-of-fold predictions, capped at 0.99, and applied by linear interpolation. The calibrated confidence is $g(c)$, floored so that the chosen class cannot fall below the runner-up (Listing 6.3); the remaining probability mass is shared among the other classes in their original ratios.

**Expected calibration error.** With confidence bins $B_1, \dots, B_{10}$ of width 0.1,

$$ \mathrm{ECE} = \sum_{b=1}^{10} \frac{W(B_b)}{W} \,\big|\, \mathrm{acc}(B_b) - \mathrm{conf}(B_b) \,\big| , $$

where $W(B_b)$ is the total sample weight in bin $b$ and accuracy and confidence are weighted averages within the bin (function `ece` in `scripts/train_bias_v4.py`).

## 7.5 Exact TreeSHAP Attribution

For the chosen class $k$, SHAP decomposes the margin additively [7]:

$$ F_k(\mathbf{x}) = \phi_{0,k} + \sum_{j=1}^{22} \phi_{j,k}(\mathbf{x}) , $$

where $\phi_{j,k}$ is the Shapley value of feature $j$—its average marginal contribution over all orderings of features—computed exactly in polynomial time for trees by TreeSHAP [35]. Folium groups features into drivers $D$ and reports $\Phi_{D,k} = \sum_{j \in D} \phi_{j,k}$, which is valid because Shapley values are additive. The repository checks additivity numerically: the largest deviation between $\phi_{0,k} + \sum_j \phi_{j,k}$ and the margin over the test checks is $8.1 \times 10^{-6}$. A driver's share is $|\Phi_{D,k}| / \sum_{D'} |\Phi_{D',k}|$ and its direction is the sign of $\Phi_{D,k}$.

## 7.6 Block-Bootstrap Market Paths

Let $\{r^{E}_t, r^{G}_t\}_{t=1}^{N}$ be monthly log-returns of NIFTY 50 (including a 1.25% annual dividend yield) and gold in rupees, with $N = 228$. To keep the swings of history but set typical growth to stated long-run rates $\mu_E = 11\%$ and $\mu_G = 9\%$, each series is recentred:

$$ \tilde{r}^{E}_t = r^{E}_t - \bar{r}^{E} + \frac{\ln(1+\mu_E)}{12}, \qquad \tilde{r}^{G}_t = r^{G}_t - \bar{r}^{G} + \frac{\ln(1+\mu_G)}{12} . $$

A path of $12H$ months is built by drawing $\lceil 12H / 12 \rceil$ block starts uniformly from $\{0, \dots, N-1\}$ and taking 12 consecutive months from each, indices taken modulo $N$ (circular block bootstrap [12], [33]). The cumulative index level is $E_{s,t} = \exp\big(\sum_{u \le t} \tilde{r}^{E}_{s,u}\big)$, and similarly for gold.

**Why 12-month blocks?** A one-year block keeps intra-year volatility clustering and the immediate recovery after a crash month, while still giving many distinct combinations over a 20-year horizon. **Why recentre?** Gold compounded at about 14.8% a year in 2007–2026 (`history.gold_growth_a_year = 0.1476` in the evaluation file); replaying that as the future would build an unusually strong gold boom into every path. The sensitivity analysis (Section 9.4) shows the effect of replaying history exactly. The choice of 12-month blocks was also tested against five alternative generators—a lognormal (GBM) model, independent months, and 3-, 6- and 24-month blocks—in Section 9.2: only 12- and 24-month blocks reproduce both the spread of real one-year returns and volatility clustering, and 24 months adds nothing measurable.

## 7.7 The Holding and the Two Wealth Paths

For a stock with beta $\beta$ and own monthly volatility $\sigma = \sigma_{\text{own}}/\sqrt{12}$, the typical annual growth follows the capital-asset-pricing relation with the FD rate $r_f = 6.75\%$:

$$ \mu_{\text{pos}} = r_f + \beta\,(\mu_E - r_f) , $$

and the position's monthly log-return on path $s$ is

$$ \rho_{s,t} = \frac{\ln(1+\mu_{\text{pos}})}{12} + \beta\,(\tilde{r}^{E}_{s,t} - \bar{\tilde{r}}^{E}) + \varepsilon_{s,t}, \qquad \varepsilon_{s,t} \sim \mathcal{N}\!\left(-\tfrac{\sigma^2}{2}, \sigma^2\right) . $$

With $V_0$ the value today and $C$ the cost basis, the HOLD value in hand after $t$ months is

$$ W^{(H)}_{s,t} = V_0 e^{\sum_{u \le t} \rho_{s,u}} (1 - \kappa) - \mathrm{Tax}_{E}\!\left(V_0 e^{\sum_{u \le t} \rho_{s,u}} - C,\; m_0 + t\right), $$

where $\kappa = 0.15\%$ are sale charges, $m_0$ the months already held and $\mathrm{Tax}_E$ the equity gains tax. SELL realises today's proceeds $P = V_0 - \mathrm{Tax}_E(V_0 - C, m_0) - \kappa V_0$ and splits them by the investor's current shares $(\alpha_G, \alpha_F, \alpha_S)$ of gold, FDs and savings:

$$ W^{(S)}_{s,t} = \alpha_G P\,G_{s,t} - \mathrm{Tax}_G(\cdot) + \alpha_F P \big(1 + r_f (1-\tau)\big)^{t/12} + \alpha_S P \big(1 + r_{sv} (1-\tau)\big)^{t/12}, $$

where $\tau$ is the investor's marginal slab rate on interest and $r_{sv} = 3\%$. Because both are computed on the same path $s$, the paired difference $\Delta_{s,T} = W^{(H)}_{s,T} - W^{(S)}_{s,T}$ isolates the decision. The outputs are

$$ \tilde{\Delta}_T = \mathrm{median}_s \Delta_{s,T}, \qquad p = \frac{1}{n}\sum_{s=1}^{n} \mathbf{1}\big[\Delta_{s,T} > 0\big], $$

and the 10th, 50th and 90th percentiles of $W^{(H)}$ and $W^{(S)}$ for each year.

## 7.8 Tax Rules (FY 2025-26, New Regime)

| Item | Rule implemented in `TAX` |
|---|---|
| Listed equity held ≤ 12 months | 20% short-term gains tax |
| Listed equity held > 12 months | 12.5% on gains above ₹1,25,000 |
| Gold | 12.5% after 24 months; otherwise slab rate |
| FD and savings interest | Investor's marginal slab rate, every year |
| Cess | 4% on top of each tax |
| Slab rate | taxable = gross − ₹75,000; zero up to ₹12 lakh taxable (Section 87A rebate); above that 0/5/10/15/20/25/30% slabs in steps of ₹4 lakh |

Table: Table 7.1: Tax rules used by the simulator

**From take-home to gross income.** The slab rate depends on income before tax, but the app records take-home pay. Let $T(g)$ be the new-regime income tax with cess on gross annual income $g$, including the Section 87A rebate and its marginal relief, under which tax just above ₹12 lakh taxable income is capped at the excess over ₹12 lakh so that nobody takes home less for earning more. Take-home pay is $h(g) = g - T(g)$, and the simulator needs $\hat{g}$ such that $h(\hat{g}) = 12 \times \text{monthly take-home}$. Because $h$ is increasing everywhere except a short stretch inside the marginal-relief band, $\hat{g}$ is found by bisection between $h$ and $2h$ with 60 iterations (`gross_from_take_home`). Rent received is then added at 70%. For example, a take-home of ₹1.6 lakh a month corresponds to about ₹21.5 lakh gross, so interest is taxed at 26% rather than the 20.8% the take-home figure alone would imply.

These rules follow the capital-gains changes of the Finance (No. 2) Act, 2024 [55] and the new-regime slabs and rebate of the Finance Act, 2025 [56], as encoded by the project. They are a simplification: losses are not set off against other gains, and the full long-term exemption is assumed to be available for this sale.

## 7.9 Causal Estimands and Estimators

For a treatment $A$ and outcome $Y$ (the indicator that the investor takes a given action), the average treatment effect of moving $A$ from $a$ to $a'$ is

$$ \mathrm{ATE} = \mathbb{E}[Y \mid \mathrm{do}(A = a')] - \mathbb{E}[Y \mid \mathrm{do}(A = a)] . $$

Under consistency, positivity and conditional exchangeability given an adjustment set $Z$, the g-formula identifies it from observational data [10], [36], [37]:

$$ \mathbb{E}[Y \mid \mathrm{do}(A = a)] = \sum_{z} \mathbb{E}[Y \mid A = a, Z = z]\,P(Z = z) . $$

**G-computation** estimates $\mathbb{E}[Y \mid A, Z]$ with a flexible classifier (scikit-learn's [48] histogram gradient-boosting model with 400 iterations, learning rate 0.06, 31 leaves) and averages its predictions over the sample with $A$ set to $a$ and to $a'$. **DoWhy backdoor adjustment** identifies the same estimand from a graph and estimates it with a linear probability model; it is then refuted three ways (placebo, random common cause, subset).

**True effect.** Because the generator is known, $\mathbb{E}[Y \mid \mathrm{do}(A=a)]$ can be computed exactly by re-evaluating the generator's motive probabilities (Section 7.1) on every case with $A$ set to $a$. Estimator accuracy is then the mean absolute difference between estimated and true effects over 45 effect–action pairs, and sign agreement over effects of at least 0.5 percentage points.

**Habits.** A habit is an intervention on a hidden tendency, $\mathrm{do}(\tau \leftarrow \tau/2)$, evaluated within the situation where the pattern can occur.

## 7.10 Evidence Rules for the Verdict

| Intent | Rule |
|---|---|
| Sell | $p \ge 0.60$ → HOLD; $p \le 0.40$ → SELL; otherwise HOLD if the sale reads as biased, else SELL |
| Hold | $p \le 0.40$ → SELL; otherwise HOLD |
| Buy more | Herd behaviour, or any bias with confidence $\ge 0.60$ → HOLD; otherwise BUY MORE if $p \ge 0.50$, else HOLD |

Table: Table 7.2: Recommendation rules (`backend/core/recommendation.py::decide`)

The band between 0.40 and 0.60 is treated as a toss-up, in which the behavioural reading acts as the tie-breaker. The rules are asymmetric by design: for a buy-more intent, a herd reading always counsels waiting because buying into a rally is the herd pattern by definition.

## 7.11 Hash-Chained Audit Log

Let $\mathrm{canon}(\cdot)$ be the canonical JSON serialisation (sorted keys, no spaces) and $H$ SHA-256 [45]. For the $i$-th entry of an investor with payload $P_i$:

$$ h_0 = H(\texttt{"GENESIS:"} \,\Vert\, \text{user\_id} \,\Vert\, \texttt{":"} \,\Vert\, \text{created\_at}), \qquad \pi_i = H(\mathrm{canon}(P_i)), \qquad h_i = H(h_{i-1} \,\Vert\, \pi_i) . $$

Changing any byte of $P_i$ changes $\pi_i$ and therefore $h_i, h_{i+1}, \dots$; removing entry $i$ leaves entry $i+1$ pointing at a hash no entry produces. This is the linked time-stamping idea of Haber and Stornetta [44]. Verification is linear in the number of entries.

```text
Algorithm 7.1  verify_chain(entries, genesis)
  for each entry e:
      if H(canon(e.payload)) ≠ e.payload_hash      → report "altered"
      else if H(e.previous_hash ‖ e.payload_hash) ≠ e.chain_hash → report "altered"
  index entries by previous_hash
  cur ← genesis (or the legacy zero genesis if only that is present)
  while some entry has previous_hash = cur:
      if more than one entry has previous_hash = cur → report "fork"
      append that entry to order; cur ← its chain_hash
  every entry not in order and not a reported fork  → report "unlinked"
  return valid = (no problems), order
```

## 7.12 End-to-End Pseudocode of One Analysis

```text
Algorithm 7.2  analyse(decision)
  facts      ← read_comment(decision.user_reasoning)            # rules (+ Gemini if consented)
  x          ← build_v4_inputs(decision, profile, snapshot, facts.cash_need)
  bias       ← predict(x)                                        # guard → calibrate → TreeSHAP
  sim        ← simulate(build_sim_inputs(decision, profile, snapshot))
  causal     ← situation_effects(bias, decision.action)          # from results/causal_v4.json
  text_en, text_hi ← render_templates(build_facts(bias, sim, causal))
  verdict, reasons ← decide(decision.action, bias.type, bias.confidence, sim.p, sim.horizon)
  sides      ← build_cases(decision, sim, bias, facts)           # never read by decide
  append_entry(user, decision)                                   # hash chain
```

## 7.13 Computational Considerations

Inference is light: one XGBoost prediction with SHAP for a single row takes milliseconds (the result records `inference_ms`). The simulator is vectorised with NumPy over a $1000 \times 12H$ matrix; for $H = 30$ it runs in about 103 ms. A convergence study (Section 9.3) shows that at the app's 1,000 paths the probability that holding wins is stable to about ±1.7 percentage points between runs, close to the binomial standard error of ±1.5 points, while the median rupee gap varies by about ±14%. The heavy ML imports are deferred until the first analysis and executed in a worker thread so the asynchronous server stays responsive. Training the classifier (five-fold cross-validation plus the final fit) and the causal study run offline in roughly 81 s and 54 s respectively. Audit verification and appends read one investor's chain, which grows by one entry per analysis.
