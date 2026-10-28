# Chapter 6: Detailed Implementation

This chapter walks through the implementation module by module. Code listings are excerpts copied from the repository; where lines have been omitted for space this is shown with `...`. Identifiers and logic are unchanged. Proposed improvements are kept out of the listings and discussed in Chapter 12.

## 6.1 Repository Organisation

| Path | Contents |
|---|---|
| `backend/` | Product API: `api/v1/` routes, `auth/`, `core/` (pipeline and steps), `services/`, `db/` (pool, Redis client, Alembic migrations 0001–0012), `schemas/`, `middleware/`, `tests/` |
| `frontend/` | React application (`src/pages`, `src/components`, `src/lib`, `src/providers`, `src/test`) |
| `src/` | Models and engines. Current: `dataset_v4.py`, `bias_model_v4.py`, `simulator_v2.py`, `causal_v4.py`, `explainer.py`, `explanation_templates.py`, `explanation_report.py`, `llm_polish.py`, `market_data.py`. Earlier versions kept for rollback or reference: `bias_detector.py` (v3), `simulator.py` (v1), `causal_inference.py`, and the old Streamlit prototype (`api.py`, `dashboard.py`) |
| `models/` | `bias_detector_v4.json` and `.meta.json` (current); v4.0 and pickled v1–v3 models (rollback) |
| `data/` | `v4/decisions_v4.csv`, `v4/market_history.csv`, `v4/DATASET_CARD.md`, `sim_v2/monthly_history.csv` |
| `results/` | `causal_v4.json`, evaluation JSONs and `reports/` (three model reports) |
| `scripts/` | Training, evaluation, seeding, purging, key generation, environment checks |
| `tests/` | Tests for the models and engines (no database needed) |
| `notebooks/`, `archive/` | Research notebooks (01–09) and archived scripts and results from earlier versions |

Table: Table 6.1: Repository organisation

## 6.2 Dataset Generator (`src/dataset_v4.py`)

**Purpose.** Produce the 20,000 labelled decisions used to train the bias model and to validate the causal module.

**Inputs and outputs.** Input: cached market history and a seed (2026). Output: `data/v4/decisions_v4.csv` with situation, household, portfolio, action, label and hidden `latent_*` columns.

**Processing logic.** The key function for the rest of the system is `applicable_bias_motives`, which encodes the label table, and its action-specific wrapper `allowed_labels`, which the bias model uses both as an input and as a guard. Keeping the table in exactly one place means the generator, the model and the tests cannot disagree about what a label means.

::: {custom-style="Listing Caption"}
Listing 6.1: The label rules in code form — `applicable_bias_motives` and `allowed_labels` (`src/dataset_v4.py`)
:::

```python
def applicable_bias_motives(s: dict) -> list[Motive]:
    """The bias motives the situation allows — LABEL_RULES in code form."""
    gl, r1m, vix, regime = s["unrealized_gl"], s["nifty_1m_return"], s["vix"], s["regime"]
    falling_fear = gl < -0.03 and r1m <= FALLING_1M and (vix >= FEAR_VIX or regime in ("crash", "correction"))
    calm = regime in ("normal", "bull")
    out: list[Motive] = []
    if falling_fear:
        out.append(Motive("loss_aversion_panic", "loss_aversion", "sell"))
    if gl <= DEEP_LOSS:
        out.append(Motive("loss_aversion_refusal", "loss_aversion", "hold"))
    if calm and gl >= EARLY_WIN:
        out.append(Motive("disposition_sell_winner", "disposition", "sell"))
    if calm and DEEP_LOSS < gl <= MODERATE_LOSS:
        out.append(Motive("disposition_hold_loser", "disposition", "hold"))
    if vix >= HERD_FEAR_VIX or r1m <= HERD_FEAR_1M:
        out.append(Motive("herd_sell_fear", "herd", "sell"))
    if r1m >= FRENZY_1M:
        out.append(Motive("herd_buy_frenzy", "herd", "buy_more"))
    return out

def allowed_labels(unrealized_gl, nifty_1m_return, vix, action) -> set[str]:
    s = {"unrealized_gl": unrealized_gl, "nifty_1m_return": nifty_1m_return,
         "vix": vix, "regime": _regime(nifty_1m_return, vix, 0.0)}
    return {"rational"} | {m.label for m in applicable_bias_motives(s) if m.action == action}
```

The thresholds (`DEEP_LOSS = -0.25`, `MODERATE_LOSS = -0.05`, `EARLY_WIN = 0.08`, `FEAR_VIX = 20`, `HERD_FEAR_VIX = 22`) are module constants, so the dataset card, the tests and the code all refer to the same values. The regime function classifies a day as crash, correction, euphoria, bull or normal from its 1-month return, VIX and 52-week drawdown; inside `allowed_labels` the drawdown is passed as 0 because every rule treats crash and correction alike.

The motive competition (`_choose`) builds a list of candidates—one rational motive chosen by `rational_action`, plus every applicable bias motive—and samples one with probability proportional to its weight (Section 7.1). `rational_action` encodes the legitimate reasons in priority order: needs cash, rebalance an oversized position (above 35% of liquid assets), goal near with a gain, buy value in a fall with spare cash and a long horizon, add regularly, cut a loss, average down, and otherwise stay the course.

**Reproducibility.** The generator uses `numpy.random.default_rng(2026)` and the cached market file, so rebuilding gives identical output (verified by `tests/test_dataset_v4.py`).

## 6.3 Bias Model v4.1 (`src/bias_model_v4.py`)

**Purpose.** Read the behavioural pattern most likely behind a decision, with calibrated confidence and an explanation.

**Inputs.** The 20 raw inputs in `INPUTS` (action, gain or loss, months held, market values, age, horizon, risk tolerance, income, rent received, outflow, emergency fund, position/equity/gold shares, liquid assets, property, loans and `cash_need_stated`).

**Outputs.** A dictionary with `bias_type`, calibrated `confidence`, all four calibrated `probabilities`, the raw `model_probabilities`, the `allowed` labels, whether the guard changed the answer, the top drivers, the computed features and the inference time.

::: {custom-style="Listing Caption"}
Listing 6.2: Feature construction shared by training and live requests — excerpt of `build_features` (`src/bias_model_v4.py`)
:::

```python
def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in INPUTS if c not in raw.columns]
    if missing:
        raise KeyError(f"bias model v4 inputs missing: {missing}")
    ...
    allowed = [allowed_labels(g, r, v, a)
               for g, r, v, a in zip(gl, r1m, vix, raw["action"])]
    income = raw["monthly_income"].astype(float)
    surplus = income + raw["rent_received"].astype(float) - raw["monthly_outflow"].astype(float)
    X = pd.DataFrame({
        "action_sell": (raw["action"] == "sell").astype(int),
        ...
        "allows_disposition": [int("disposition" in a) for a in allowed],
        "allows_herd": [int("herd" in a) for a in allowed],
        "allows_loss_aversion": [int("loss_aversion" in a) for a in allowed],
        ...
        "surplus_ratio": _ratio(surplus, income).clip(-2.0, 2.0),
        "debt_ratio": _ratio(raw["loans_outstanding"],
            raw["liquid_assets"].astype(float) + raw["real_estate_value"].astype(float),
        ).clip(0.0, 5.0),
        "cash_need_stated": raw["cash_need_stated"].astype(int),
    }, index=raw.index)
    return X[list(FEATURES)]
```

The function refuses to run with missing inputs, rejects unknown actions, and guards divisions with `_ratio`, which returns 0 when the denominator is not positive. Returning columns in the fixed `FEATURES` order matters because the booster expects features by position.

::: {custom-style="Listing Caption"}
Listing 6.3: The definitional guard and top-label calibration — `apply_guard` and `calibrate_top_label` (`src/bias_model_v4.py`)
:::

```python
def apply_guard(p: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Zero the patterns the definitions rule out, then renormalise."""
    q = p * mask
    return q / q.sum(axis=1, keepdims=True)

def calibrate_top_label(p, curve_x, curve_y):
    p = np.asarray(p, dtype=float)
    k = p.argmax(axis=1)
    rows = np.arange(len(p))
    top = p[rows, k]
    rest = 1.0 - top
    second = np.sort(p, axis=1)[:, -2]
    c = np.interp(top, curve_x, curve_y)
    floor = np.where(rest > 0, second / np.maximum(rest + second, 1e-12) + 1e-6, top)
    c = np.clip(np.maximum(c, floor), 0.0, 1.0)
    scale = np.where(rest > 1e-12, (1.0 - c) / np.maximum(rest, 1e-12), 0.0)
    q = p * scale[:, None]
    q[rows, k] = c
    return q
```

Because "rational" is always allowed, the mask never zeroes every class, so the renormalisation in `apply_guard` is safe. `calibrate_top_label` replaces only the chosen class's probability with its calibrated value and rescales the others to fill the remainder, preserving their ratios. The `floor` term is a careful detail: it ensures calibration can lower the stated confidence but can never demote the chosen class below the runner-up. In the words of the docstring, calibration "changes how sure the model says it is, never what it says".

::: {custom-style="Listing Caption"}
Listing 6.4: One prediction with exact TreeSHAP drivers — excerpt of `predict` (`src/bias_model_v4.py`)
:::

```python
def predict(inputs: Mapping[str, Any], top_n: int = 5) -> dict[str, Any]:
    bundle = load()
    meta = bundle["meta"]
    raw = pd.DataFrame([{k: inputs[k] for k in INPUTS}])
    X = build_features(raw)
    margins, contribs = _margins_and_contribs(bundle["booster"], X)
    p_model = softmax(margins)
    mask = allowed_mask(raw)
    p_guarded = apply_guard(p_model, mask)
    curve = meta["calibration"]
    p = calibrate_top_label(p_guarded, np.array(curve["x"]), np.array(curve["y"]))[0]
    k = int(p.argmax())
    label = LABELS[k]
    return {
        "bias_type": label,
        "confidence": round(float(p[k]), 4),
        ...
        "drivers": _drivers(contribs[0, k, :-1], X.iloc[0], top_n),
        ...
    }
```

`_margins_and_contribs` asks XGBoost for both the raw margins and `pred_contribs=True`, which returns exact TreeSHAP values per class. Only the chosen class's contributions (`contribs[0, k, :-1]`, dropping the bias column) are passed to `_drivers`, which sums them by the `DRIVER_OF` mapping into plain drivers such as "gain or loss", "market fear" or "position size", ranks them by magnitude and records whether each pushes towards or against the reading. This fixed a defect of the earlier v3 model, whose explanation ranked factors for whichever class had the largest total attribution—in 98.6% of test cases not the class it displayed (per `bias_v4_evaluation.json`).

**Artefacts and loading.** The model is stored as native XGBoost JSON (`models/bias_detector_v4.json`), not a pickle, with a metadata file holding the feature list, the calibration curve and the training medians. `load` caches the booster behind a lock and refuses to run if the metadata's feature list differs from the code's.

**Training** (`scripts/train_bias_v4.py`). The 20,000 cases are split 80/20 into development and test sets, stratified by label × regime (seed 7). Five-fold stratified cross-validation with early stopping (up to 3,000 trees, patience 80) determines the tree count: the mean best iteration × 1.1 = 402 trees. The same folds produce out-of-fold predictions for fitting the isotonic curve. Sample weights re-weight each regime to its real frequency. Hyper-parameters are listed in Table 8.2.

## 6.4 Bias Step in the Product (`backend/core/bias_detector.py`, `comment_reader.py`)

**Purpose.** Assemble model inputs from the database, run the comment reader and the model, and store the results.

`build_v4_inputs` reads the decision row, the user's profile and the portfolio snapshot captured at submission. It computes the position, equity and gold shares from the snapshot and fills any missing profile field with the training median from the model's metadata, appending its name to `assumed_defaults`. Missing market values use the median real trading day. The bridge then runs `predict` in a worker thread, maps the label to the product vocabulary and writes `bias_detected`, `bias_confidence` and the bias block of `explainer_output`.

**Comment reading** runs first so that `cash_need_stated` is available to the model. The rule-based reader scans the comment with regular expressions in English, Hinglish and Hindi.

::: {custom-style="Listing Caption"}
Listing 6.5: Excerpt of the phrase rules for facts and feelings (`backend/core/comment_reader.py`)
:::

```python
_FACT_RULES: dict[str, tuple[str, ...]] = {
    "cash_need": (
        r"\bneed (the |some |that |this )?(money|cash|funds?)\b",
        r"\b(school|college|tuition|education|exam) fees?\b",
        r"\b(medical|hospital|surgery|treatment|operation)\b",
        r"\b(lost my job|job loss|laid off|layoffs?|unemployed|no salary)\b",
        r"\b(paisa|paise|paison) (chahiye|ki zarurat|ki zaroorat|chahiye the)\b",
        ...
    ),
    ...
}
_CUE_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "fear": ("loss_aversion", (
        r"\b(scared|afraid|frightened|panic\w*|nervous|worried|anxious)\b",
        r"\bbefore it (gets worse|falls more|drops more)\b",
        ...)),
    "crowd": ("herd_behavior", (
        r"\b(everyone|everybody)\b",
        r"\b(whatsapp|telegram) group\b",
        ...)),
    ...
}
```

Each match is returned with the whole sentence that contains it, quoted verbatim, so the investor sees exactly which words were read. The design separates *facts* (statements about the investor's situation) from *cues* (feelings). Only the `cash_need` fact changes anything—it sets the model input. Feelings are quoted back in "In your own words" with a note on whether they agree with the reading, but they never change the reading or the verdict. When the investor has consented and the server has a key, Gemini may read the comment as well; its answer is accepted only if every item has an allowed kind and a quote that appears word for word in the comment. Otherwise the rule-based reading stands.

## 6.5 Simulator v2 (`src/simulator_v2.py`) and Its Bridge (`backend/core/simulator.py`)

**Purpose.** Compare holding and selling one position over the investor's horizon.

**Inputs.** A `SimInputs` dataclass: position value and cost basis, months held, asset type (stock or equity fund), horizon (clamped to 1–30), annual income, the rest of the liquid portfolio, beta and own volatility, monthly SIP and education fees with their end year, number of paths (1,000) and seed.

**Outputs.** Year-by-year 10th/50th/90th percentiles for both paths, end-of-horizon summaries, the sale breakdown (tax, charges, proceeds, destination split), the comparison (median paired gap, probability holding wins), portfolio context and every assumption used.

::: {custom-style="Listing Caption"}
Listing 6.6: Circular 12-month block bootstrap — `_bootstrap` (`src/simulator_v2.py`)
:::

```python
def _bootstrap(rng: np.random.Generator, n_paths: int, months: int, n_hist: int) -> np.ndarray:
    """(n_paths, months) indices into history: 12-month blocks, joined end to end.

    Circular (Politis & Romano): a block may wrap from the last month to the
    first, so every month is equally likely. Without it the first and last
    months of history are under-sampled — and October 2007 starts with the
    2008 crash.
    """
    b = int(ASSUMPTIONS["block_months"])
    n_blocks = -(-months // b)
    starts = rng.integers(0, n_hist, size=(n_paths, n_blocks))
    return ((starts[:, :, None] + np.arange(b)) % n_hist).reshape(n_paths, -1)[:, :months]
```

The function is fully vectorised: it draws all block starts at once, expands each into 12 consecutive month indices with broadcasting, wraps them with the modulo operator and trims to the required length. The same index matrix is then used for equity and gold, which preserves their real month-by-month relationship.

::: {custom-style="Listing Caption"}
Listing 6.7: The paired HOLD and SELL valuation, after tax — excerpt of `simulate` (`src/simulator_v2.py`)
:::

```python
    growth = a["fd_rate"] + beta * (market_growth - a["fd_rate"])
    eq_shock = eq_log[idx] - eq_log.mean()
    own = rng.normal(-own_vol ** 2 / 2, own_vol, size=(n, m))
    pos_cum = np.exp(np.cumsum(math.log1p(growth) / 12 + beta * eq_shock + own, axis=1))
    ...
    # ── HOLD: the position stays; in hand = value - costs - tax on the gain ──
    hold_value = inp.position_value * pos_cum
    hold_gain = hold_value - inp.cost_basis
    hold_in_hand = hold_value * (1 - a["sale_cost"]) - equity_gains_tax(hold_gain, inp.months_held + months_ahead)

    # ── SELL: tax and costs now; proceeds into the safer money ──────────────
    sale = sale_today(inp)
    split = destination(inp)
    p = float(sale["proceeds"])
    gold_part = p * split["gold"] * gd_cum
    gold_in_hand = gold_part - gold_gains_tax(gold_part - p * split["gold"], months_ahead, slab)
    sell_in_hand = (gold_in_hand + p * split["fixed_deposits"] * fd_after_tax
                    + p * split["savings"] * sav_after_tax)
    ...
    diff = hold_end - sell_end
    opp = float(np.median(diff))
    prob_hold = float((diff > 0).mean())
```

Three design points are visible here. First, the holding's typical growth is set with the capital-asset-pricing relation (FD rate plus beta times the equity premium), so that a volatile stock is not projected to grow faster merely because it is volatile. Second, the own-volatility shock has mean $-\sigma^2/2$ in log space, so that its expected multiplicative effect is one. Third, HOLD is valued as if cashed in each year (charges and capital-gains tax deducted), while SELL paid its tax on day one and is taxed on interest each year; the two are therefore compared like for like. The headline gap is the *median* of the paired differences, because single-stock outcomes are right-skewed and the mean would overstate the usual result.

::: {custom-style="Listing Caption"}
Listing 6.8: Indian tax helpers — `marginal_slab_rate` and `equity_gains_tax` (`src/simulator_v2.py`)
:::

```python
def marginal_slab_rate(annual_income: float) -> float:
    taxable = max(0.0, float(annual_income) - TAX["standard_deduction"])
    if taxable <= TAX["rebate_up_to"]:
        return 0.0
    for upper, rate in TAX["slabs"]:
        if taxable <= upper:
            return rate * (1 + TAX["cess"])
    return TAX["slabs"][-1][1] * (1 + TAX["cess"])

def equity_gains_tax(gain, months_held, exemption: float | None = None):
    gain = np.maximum(np.asarray(gain, dtype=float), 0.0)
    months = np.asarray(months_held, dtype=float)
    exempt = TAX["ltcg_exemption"] if exemption is None else exemption
    short = months <= TAX["equity_ltcg_after_months"]
    stcg = gain * TAX["equity_stcg"]
    ltcg = np.maximum(gain - exempt, 0.0) * TAX["equity_ltcg"]
    return np.where(short, stcg, ltcg) * (1 + TAX["cess"])
```

The helpers work on whole arrays, so tax is computed for all 1,000 paths and every month in one call. Losses pay nothing; set-off against other gains is not modelled (a stated limitation).

**The bridge** (`backend/core/simulator.py::build_sim_inputs`) builds `SimInputs` from the decision, the profile and the portfolio snapshot. It uses the beta and own volatility measured at submission by `backend/services/prices.py::stock_risk` (from 10 years of monthly prices), falling back to the median NIFTY 50 stock (beta 1.0, own volatility 21%) and recording that in `fixed_inputs`. Because the profile records take-home pay, the bridge first converts it to gross income before the slab rate is looked up: `annual_income = gross_from_take_home(12 × monthly income) + 12 × 0.7 × rent received`, where rent counts at 70% because of the 30% standard deduction on house property (Section 7.8). It also writes legacy columns (`hold_median_20y` and similar) that keep their historical names even though the horizon is now the investor's own; this naming inconsistency is cosmetic and noted in Section 10.8.

## 6.6 Cause-and-Effect Module (`src/causal_v4.py`)

**Purpose.** Estimate what pushes each action and which habit helps most, and verify the estimates against the truth.

**Processing logic.** `action_probabilities` re-implements the generator's motive weights so that, for any case, it returns the exact probability of sell, hold and buy more; `consistency_with_stored_data` confirms that it matches the stored motive share of all 20,000 cases (maximum absolute error 0.0, per `results/causal_v4.json`). A `do(...)` helper applies an intervention to a data frame. The *true* effect of an intervention is then the mean change in these exact probabilities. The *estimated* effect comes from two estimators trained on the observed data only.

::: {custom-style="Listing Caption"}
Listing 6.9: G-computation estimator — `GComputation` (`src/causal_v4.py`)
:::

```python
class GComputation:
    """S-learner: P(action | everything observed), queried under interventions."""

    def __init__(self, df: pd.DataFrame, seed: int = 0):
        from sklearn.ensemble import HistGradientBoostingClassifier

        self.model = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
                                                    l2_regularization=1.0, random_state=seed)
        self.model.fit(df[OBSERVED], df.action.map({a: i for i, a in enumerate(ACTIONS)}))

    def probabilities(self, df: pd.DataFrame) -> np.ndarray:
        p = self.model.predict_proba(_refresh_derived(df)[OBSERVED])
        out = np.zeros((len(df), 3))
        out[:, self.model.classes_] = p
        return out
```

The g-computation estimate of an intervention is the average predicted probability after the intervention minus the average before it (`_delta`). Note that `_refresh_derived` recomputes the surplus ratio after an intervention on income or outflow, so derived features stay consistent.

The DoWhy estimator (`dowhy_effect`) builds a GML graph in which every observed variable points to the outcome and profile variables point to the latent tendencies, identifies the effect with the maximal adjustment set, estimates it with `backdoor.linear_regression`, and runs three refuters—placebo treatment, random common cause and a data subset—each with 10 simulations. An effect passes when the placebo effect is below 25% of the estimate, adding a random common cause changes it by less than 10%, and the subset estimate is within 25%.

**Habits.** Each habit is modelled as halving the tendency it targets (for example "reframing the loss" halves loss aversion); "not watching the crowd" caps the market fear reaching the investor at VIX 15. The results file stores, for each (pattern, action) situation, the share who take the action and the change the best habit would make. `backend/core/explainer.py` reads `results/causal_v4.json` and caches it.

## 6.7 Recommendation (`backend/core/recommendation.py`)

::: {custom-style="Listing Caption"}
Listing 6.10: The evidence rules for the sell intent — excerpt of `decide` (`backend/core/recommendation.py`)
:::

```python
_STRONG, _WEAK = 0.60, 0.40
_BIAS_CONFIDENT = 0.60

def decide(intent, bias, confidence, p_hold, horizon_years=20):
    """Return (verdict, reasons). Pure function — unit-testable without a DB."""
    p = 0.5 if p_hold is None else p_hold
    biased = bias != "rational"
    ...
    if intent == "sell":
        if p >= _STRONG:
            reasons.append(f"Holding beat selling in {pct} of {horizon_years}-year simulations.")
            if biased:
                reasons.append(f"The urge to sell shows signs of {bias_name}.")
            return "HOLD", reasons
        if p <= _WEAK:
            reasons.append(f"Holding beat selling in only {pct} of simulations.")
            return "SELL", reasons
        reasons.append(f"The simulations are close to even ({pct} favour holding).")
        if biased:
            reasons.append(f"With {bias_name} detected, the cautious choice is to wait.")
            return "HOLD", reasons
        ...
        return "SELL", reasons
```

`decide` is a pure function: it takes values, returns a verdict and a list of reasons, and touches neither the database nor the network, which makes it directly unit-testable. If no simulation result is available, the odds are treated as even and that fact is stated. When a reason mentions the confidence of a bias reading, `confidence_band` writes it in words (high ≥ 0.85, medium ≥ 0.65, otherwise low), never as a percentage, matching the product rule that no raw probability is shown to the investor. The step wrapper `recommend` stores a `debate_transcript` with `engine = "evidence_rules_v1"`, the reasons, the exact inputs used and the "both sides" cases built afterwards by `backend/core/debate.py`. The cases are never read by the verdict.

## 6.8 Pipeline Orchestrator (`backend/core/pipeline.py`)

::: {custom-style="Listing Caption"}
Listing 6.11: The step loop and failure handling — excerpt of `run_analysis_pipeline` (`backend/core/pipeline.py`)
:::

```python
    try:
        for step_name in STEP_ORDER:
            await _set_status(db, decision_id, user_id, "processing", step_name)
            await publish_event(redis, decision_id, {"step": step_name, "status": "running"})
            # Reload before each step so it sees the previous steps' writes
            decision = await _load_decision(db, decision_id, user_id)
            if decision is None:
                raise LookupError(f"decision {decision_id} not found for user {user_id}")
            ctx = PipelineContext(decision_id=decision_id, user_id=user_id,
                                  decision=decision, db=db, redis=redis)
            result = await resolve_step(step_name)(ctx)
            await _apply_updates(db, decision_id, user_id, result.updates)
            await publish_event(redis, decision_id,
                                {"step": step_name, "status": "done", **result.event})
        await _set_status(db, decision_id, user_id, "complete", None, completed=True)
        await publish_event(redis, decision_id, {"step": "complete", "status": "done"})
    except Exception as exc:  # noqa: BLE001 — any step failure fails the decision
        sentry_sdk.capture_exception(exc)
        try:
            await _set_status(db, decision_id, user_id, "failed", None,
                              error_message=str(exc)[:500])
        finally:
            await publish_event(redis, decision_id,
                {"step": "failed", "status": "error", "error": str(exc)[:500]})
```

The loop guarantees two properties. Each step sees what earlier steps wrote, because the row is reloaded every time. And a connected browser always learns that the run ended: the success path publishes `complete`, and the failure path publishes `failed` inside a `finally` block, so even a failure while writing the status still notifies the stream. `_apply_updates` builds a parameterised `UPDATE` (column names come from the step's own code, values are bound as parameters), casts JSONB columns explicitly and converts floats to `Decimal` through their string form to avoid binary-float noise in `NUMERIC` columns.

## 6.9 Explanation Engine (`src/explainer.py`, `explanation_templates.py`, `explanation_report.py`, `llm_polish.py`)

**Purpose.** Turn every model output into a six-section story—*In short*; *What's going on right now*; *Your two possible futures*; *The story of your money*; *Why we're telling you this*; *What to do now*—in English and Hindi, plus HTML and PDF reports.

**Processing logic.** `build_facts` gathers all numbers into one dictionary. Templates are rendered by Jinja2 [57] with `StrictUndefined`, so a missing fact raises an error during tests rather than printing a blank. A translation layer replaces internal terms ("p10", "opportunity cost", causal variable names) with plain phrases, and a 30-term jargon blocklist is enforced by tests. Money is formatted the Indian way (₹1.2 lakh in prose; ₹1,32,451 in tables). The narrative quotes the *typical* (median) outcome rather than the mean, because wealth distributions are right-skewed. English and Hindi template banks are hand-written and structurally identical (34 templates each, enforced by tests), so Hindi works offline.

::: {custom-style="Listing Caption"}
Listing 6.12: The number-preservation guard for optional AI wording — `guard_ok` (`src/llm_polish.py`)
:::

```python
def guard_ok(original: str, polished: str) -> bool:
    """
    The whole safety argument for this module.

    Rejects the polished text if it contains any number or rupee amount that
    is not present in the original, or if its length has drifted far enough
    to suggest content was invented or dropped.
    """
    if not polished or not polished.strip():
        return False
    invented_numbers = _numbers(polished) - _numbers(original)
    if invented_numbers:
        return False
    invented_money = _money(polished) - _money(original)
    if invented_money:
        return False
    ratio = len(polished) / max(len(original), 1)
    if not 0.6 <= ratio <= 1.8:
        return False
    return True
```

`_numbers` normalises numeric tokens (so "1,20,000" and "120000" compare equal) and `_money` extracts rupee amounts including "lakh" and "crore". Tables are replaced with placeholder tokens before the text is sent and restored afterwards, so the model never sees them. Any failure—no key, bad key, quota, timeout, malformed reply—returns the template text, and two consecutive failures open a five-minute circuit breaker. As written, the guard rejects *added* numbers; a *dropped* number is caught only indirectly through the length bound. Section 10.8 records this as a gap between the code and the stronger wording in the master document.

**Reports.** `explanation_report.py` produces a self-contained, print-ready HTML report in both languages and a PDF in English using ReportLab. A Hindi PDF is refused with an explanation because ReportLab cannot shape Devanagari; the HTML version prints correctly from a browser.

## 6.10 Data Layer and Row-Level Security (`backend/db/`)

::: {custom-style="Listing Caption"}
Listing 6.13: Setting the per-transaction user for RLS — `Database.rls_transaction` (`backend/db/pool.py`) and the policy from migration 0007
:::

```python
    async def rls_transaction(self, user_id):
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.current_user_id', $1::text, true)",
                    str(user_id) if user_id is not None else "",
                )
                yield conn
```

```sql
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY decisions_isolation ON decisions
    FOR ALL
    USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
```

The third argument `true` to `set_config` makes the setting local to the transaction, so it cannot leak to the next request that reuses the pooled connection. `NULLIF(..., '')` turns an unset setting into `NULL`, so a query that forgot to set the user sees zero rows instead of failing. The migration's docstring records an important lesson: PostgreSQL superusers bypass RLS unconditionally, so the application must connect as the non-superuser `app_user`; the commit history shows this was fixed explicitly (`fix(M1): enforce RLS by connecting the app as non-superuser app_user`). A consequence for the API is that another user's decision is simply invisible, so requesting it returns 404 rather than 403, revealing nothing about its existence.

## 6.11 Tamper-Evident Audit Chain (`backend/core/audit.py`)

::: {custom-style="Listing Caption"}
Listing 6.14: Appending an entry under a per-investor lock — `append_entry` (`backend/core/audit.py`)
:::

```python
def genesis_hash(user_id: str, created_at: datetime) -> str:
    return sha256(f"GENESIS:{user_id}:{created_at.isoformat()}")

async def append_entry(conn, user_id, decision_id, row, recorded_at=None):
    """Append one entry under a per-investor lock. ``conn`` must be inside a transaction."""
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))", str(user_id))
    entries, genesis = await load_chain(conn, user_id)
    previous = chain_head(entries, genesis)
    payload = build_payload(row, recorded_at or datetime.now(timezone.utc))
    payload_hash = sha256(canonical(payload))
    chain_hash = sha256(previous + payload_hash)
    await conn.execute(
        """INSERT INTO audit_logs (decision_id, user_id, event_type, payload_hash,
                                   previous_hash, chain_hash, payload)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
        decision_id, user_id, payload["event"], payload_hash, previous, chain_hash, canonical(payload),
    )
```

The payload contains two fingerprints: `inputs_hash` over 21 input fields (holding, prices, action, reason, market snapshot, portfolio snapshot and comment reading) and `analysis_hash` over 14 output fields (pattern, confidence, projections, explanation, transcript and verdict). `canonical` serialises with sorted keys and no spaces, and `_normalise` makes values identical however they arrive from the database (for example `Decimal('1600.00')` and `1600` both become `"1600"`). The advisory lock serialises appends per investor, so two analyses finishing together cannot both claim the same predecessor. Each payload also lists the fields its fingerprints cover, so the set can grow later without old entries failing verification.

**Verification.** `verify_chain` walks the entries by following links from the genesis rather than sorting by timestamp, which lets it detect an altered entry (its hashes no longer recompute), a removed entry (the next link points at nothing), a forged entry (it does not link in) and a fork (two entries claim the same predecessor). `verify_decision` recomputes both fingerprints from the current decision row and names which part changed, if any. At the database level, migration 0004 adds `DO INSTEAD NOTHING` rules for `UPDATE` and `DELETE` on `audit_logs`, making the table append-only.

## 6.12 Authentication and Session Security (`backend/auth/`, `backend/middleware/`)

| Concern | Implementation |
|---|---|
| Passwords | bcrypt with cost 12; zxcvbn score ≥ 3 required (`auth/password.py`) |
| Tokens | RS256 JWT; access 15 minutes, refresh 7 days with rotation (`auth/jwt_handler.py`); both in httpOnly cookies, `SameSite=Lax`, `Secure` outside development (`auth/cookies.py`) |
| Revocation | Dual-jti blacklist in Redis invalidates both tokens on logout and refresh |
| CSRF | Double-submit: the `csrf_token` cookie must equal the `X-CSRF-Token` header on every mutating request (`middleware/csrf.py`) |
| Two-step | pyotp TOTP with `valid_window=1`; secret encrypted with Fernet; 8 bcrypt-hashed backup codes; recovery requests limited to one per e-mail per 24 hours (`auth/mfa_handler.py`) |
| Rate limits | slowapi with a Redis store: login 5/min, register 3/h, forgot-password 3/h, analyze 10/min, admin 20/min (`middleware/rate_limiter.py`) |
| Headers | Security headers on every response; CORS restricted to the configured origin |
| Google sign-in | OpenID Connect via Authlib; single-use `state` in Redis (10 minutes); only Google-verified addresses accepted; outcome returned in the URL fragment (Section 6.12.1) |
| Errors | One shape for all errors: `{"error", "message", "request_id"}` (`backend/errors.py`) |

Table: Table 6.2: Authentication and session-security controls

### 6.12.1 Google sign-in (`backend/auth/routes.py`, `frontend/src/pages/auth/GoogleReturn.tsx`, `Welcome.tsx`)

Google sign-in uses OpenID Connect through Authlib. `GET /v1/auth/google/login?remember=&next=` creates a random, single-use `state` value, stores it in Redis for ten minutes together with the "keep me signed in" choice and the in-app page to return to (only in-app paths are accepted, so the parameter cannot be abused as an open redirect), and redirects the browser to Google. When Google sends the browser back to `GET /v1/auth/google/callback`, the server consumes the state, exchanges the code for the user's profile and accepts it only if Google reports the e-mail address as verified. Without that check, someone could link an unverified address to another person's account. A verified address either opens a new account or links to the existing account with the same e-mail.

The callback always answers with a redirect to `/auth/google#…` in the web app, with the outcome in the URL *fragment*. Browsers never send a fragment to any server, so the single-use tokens it may carry stay out of server logs and `Referer` headers, and `GoogleReturn.tsx` removes the fragment from the address bar as soon as it has read it. The page then completes one of several outcomes: a normal sign-in; a two-step code prompt when the account has TOTP enabled; "Keep my account" for an account in its deletion grace period (`POST /v1/auth/google/keep-account`, protected by a single-use token instead of a session, and therefore exempt from CSRF like the other pre-session endpoints); or a plain explanation when the user cancelled, the request expired or Google refused.

A new account created through Google has no financial profile yet. The user object therefore carries `needs_profile` (true while any required Tier-1 field—age, income, risk tolerance, horizon—is empty) and `has_password`. The front end's route guard sends such a user to `/app/welcome` until the profile is complete. Because sensitive changes, turning off two-step verification and deleting an account all require the password, a Google-only account is offered "Set a password" in Settings, which uses the existing reset-link e-mail. The locally registered callback address is `http://localhost:3000/v1/auth/google/callback`, reached through the Vite proxy; a deployment must add its own address to the OAuth client.

## 6.13 Portfolio, Prices and Market Context (`backend/services/`)

`portfolio.py` computes the derived figures listed in Table 6.3. `prices.py` fetches quotes (NSE symbols with suffix `.NS`, BSE `.BO`) and mutual-fund NAVs, caching them for 15 minutes; a failed lookup returns no price rather than an error, and the holding is valued at average cost with a "price unavailable" flag. `market_data.py` captures the NIFTY 1-month return, 30-day volatility and India VIX with a timeout; when unavailable, a calm median market is assumed and disclosed.

| Figure | Formula |
|---|---|
| Committed outflow | EMIs + rent paid + education fees |
| Monthly surplus | income + rent received − committed outflow |
| Liquid assets | stocks + mutual funds + gold + fixed deposits + savings |
| Net worth | liquid + property − home loan − other loans |
| Equity share | (stocks + mutual funds) / liquid |
| Position share | value of the holding / liquid |
| Gold price per gram | GC=F (USD/troy oz) × INR=X / 31.1034768 |

Table: Table 6.3: Derived portfolio figures (`backend/services/portfolio.py`)

## 6.14 Account Deletion and Data Export (`backend/services/account_deletion.py`)

Deleting an account requires the password (and a TOTP code if two-step is on) and signs the user out everywhere. For 30 days, logging in offers "Keep my account". After that, a periodic task in the API process (every 6 hours by default) or `scripts/purge_deleted_accounts.py` anonymises the account: name, e-mail, phone, credentials, two-step secret, profile and financial data, holdings, sessions, backup codes and profile history are erased, and each analysis loses its comment, portfolio snapshot, explanation and projections. The user identifier and creation time—the chain's genesis anchor—remain, together with the audit entries, unlinked to any person. Outright deletion is impossible by design because `audit_logs` is append-only. "Download my data" (`GET /v1/users/me/export`) returns everything held about the investor as JSON, excluding the password hash, the two-step secret and tokens.

## 6.15 Front End (`frontend/src/`)

The front end is a React 19 single-page application written in TypeScript and built with Vite. `lib/api.ts` configures an axios client that echoes the `csrf_token` cookie in the `X-CSRF-Token` header on mutating requests and, on an expired session, calls `/v1/auth/refresh` once (shared by concurrent requests) and retries. `lib/queries.ts` defines TanStack Query hooks for every resource. Forms use React Hook Form with Zod schemas. `pages/app/DecisionPage.tsx` (865 lines, the largest page) uses a stream hook from `components/decision.tsx` that opens an `EventSource` on the stream endpoint; the page renders the five steps as they progress, falls back to polling if the stream fails, and then lays out the result sections listed in Section 5.9. Charts use Recharts. `lib/domain.ts` holds shared constants such as the confidence bands (High ≥ 0.85, Medium ≥ 0.65), which the training script mirrors. Route guards send signed-out visitors to the login page while remembering where they were going, and send a signed-in user whose profile is incomplete to the Welcome page. The front end has 25 Vitest tests, including a dedicated suite for the Google return page.

## 6.16 Error Handling and Edge Cases

| Situation | Behaviour (as implemented) |
|---|---|
| No live price | Valued at average cost, flagged "price unavailable"; for a new analysis the investor enters today's price |
| Market data unavailable or slow | Calm median market assumed (NIFTY +1.0%/month, VIX 16.9) and disclosed; capture bounded by a timeout |
| Profile or portfolio gaps | Training medians used and listed under "How this was worked out" |
| Stock with too little history | Median NIFTY 50 stock (beta 1.0, own swings 21%) used and disclosed |
| No horizon | 20 years, stated; horizons above 30 are capped |
| Payments exceed income | `surplus_ratio` clipped at −2; a stated cash need reads a sale as rational |
| Very large position (> ~35% of liquid) | A sale can be read as rational rebalancing |
| Goal within 3 years with a gain | A sale can be read as rational |
| Reload during analysis | Event backlog replayed; polling fallback |
| Two analyses finishing together | Per-investor advisory lock keeps the audit chain linear |
| Unverified account registers again | Unverified record replaced; verified e-mail returns "already registered" |
| First sign-in with Google | Account created; Tier-1 profile requested on the Welcome page before any other page (Settings stays reachable) |
| Google sign-in cancelled, expired or refused | The app explains what happened and offers to try again; an address Google has not verified cannot sign in or be linked |
| Account made with Google has no password | "Set a password" offered, since sensitive changes, disabling two-step and deletion need one |
| Account in its deletion grace period signs in with Google | Google's confirmation stands in for the password; "Keep my account" offered |
| AI help fails or misquotes | Rule-based reading / template text used |
| Hindi PDF requested | Refused with explanation; HTML offered |

Table: Table 6.4: Edge cases and their handling (from `FOLIUM_MASTER.md` §5, cross-checked against the code)
