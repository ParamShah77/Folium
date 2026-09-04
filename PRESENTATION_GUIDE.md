# Project Review — Presentation Guide
### Objectives 1 → 3 complete · Objective 4 next
**A Causal Decision-Time Framework for Behavioral Bias Detection and Long-Horizon Portfolio
Evaluation with Counterfactual Verifiable Intelligence**

---

## PART 0 — The 60-Second Version

> Behavioural biases cost individual investors a large share of their lifetime wealth. Existing
> financial AI detects those biases *after the fact*, predicts the *market* rather than *your*
> portfolio, and explains itself in language only a data scientist can read.
>
> We built a system that does three things instead. **One:** it detects the bias at the moment of
> the decision, and models it causally — not just correlationally. **Two:** it simulates what that
> specific decision does to *this specific person's* money over the next 10 to 30 years.
> **Three:** it explains the whole thing in a story an ordinary investor can read, in English or
> Hindi, without a single technical term.
>
> Objectives 1, 2 and 3 are complete and tested. Objective 4 — a tamper-evident audit trail — is
> what remains.

---

## PART 1 — Why This Project Exists

Four gaps in the literature, and what each one means in practice:

| Gap | The problem | Our objective |
|---|---|---|
| 1 | Bias detection is retrospective and correlational | Detect at decision-time, model causally |
| 2 | Predictions are market-level, not person-level | Individual portfolio simulation over 10–30 years |
| 3 | Explanations are post-hoc and model-centric | Decision-centric counterfactual narrative |
| 4 | Recommendations are unverifiable black boxes | Tamper-evident, auditable decision trail |

**The through-line:** a decision is detected (1), its consequences are simulated (2), the whole
thing is explained to the person (3), and the record is made verifiable (4).

### Why synthetic data
This is the question you will be asked, so answer it before it is asked:

- **Ground truth for biases is impossible in real data.** We cannot read a real investor's mind
  and label "this was loss aversion". Synthetic generation gives us the label.
- **Counterfactuals do not exist in history.** We cannot replay 2020 with the investor holding
  instead of selling. Simulation can.
- **30-year futures have not happened yet.**
- **Causal validation needs known structure.** We know the true data-generating process, so we can
  check whether the causal model recovers it.

Real market data (NIFTY 50 via `yfinance`) is used for *live market context* in the dashboard, so
the system is not purely synthetic at run time.

### The data assets

| Dataset | Size | Role |
|---|---|---|
| `synthetic_users.csv` | 3,057 users × 13 features | Individual financial profiles |
| `synthetic_decisions.csv` | 7,439 decisions × 14 features | Decision events with bias labels |
| `synthetic_bias_profiles.csv` | 1,457 profiles | Ground-truth bias traits |
| `synthetic_market_paths.npy` | 10,000 × 30 years | Market futures with injected crashes |
| `synthetic_counterfactuals.csv` | 10,000 rows | Pre-computed HOLD/SELL outcomes |
| `synthetic_audit_logs.csv` | 5,000 rows | Reference structure for Objective 4 |

---

## PART 2 — Objective 1: Causal Decision-Time Reasoning ✅

> *Design and implement a causal decision-time framework that detects behavioral biases and models
> cause-and-effect relationships beyond retrospective correlational analysis.*

### What we built
A real-time classifier that, given a decision moment, names the behavioural bias at play — and a
causal layer that estimates how much each factor actually *pushed* the decision.

### Why this way
A classifier alone would only tell us *what* pattern matched. It could not answer "what if this
person were less loss-averse?" — which is the question an intervention needs. So the classifier is
paired with a causal model.

### How — the pipeline
1. **Feature engineering** — market context, position state, and personal profile combined into one
   decision-moment feature vector.
2. **Class imbalance** handled with SMOTE on the training split only.
3. **XGBoost multi-class classifier** → four classes: `loss_aversion`, `herd`, `disposition`,
   `rational`.
4. **Causal structure learning** with a deliberate three-tier fallback:
   NOTEARS → Hill-Climb search → domain-knowledge graph. The shipped artefact is the
   **domain-knowledge + correlation graph: 8 nodes, 12 edges, validated as a DAG.**
5. **Effect estimation with DoWhy** — `backdoor.linear_regression` on each treatment.
6. **Intervention simulation** — what happens to sell-probability if we change one thing.

### Tools used
`XGBoost` · `scikit-learn` · `imbalanced-learn` (SMOTE) · `DoWhy` · `CausalNex` / NOTEARS ·
`pgmpy` (Hill-Climb) · `NetworkX` · `SHAP` · `FastAPI` · `yfinance`

### Results — quote these

| Metric | Value |
|---|---|
| Test accuracy | **84.0%** |
| Macro F1 | **0.858** |
| 5-fold CV macro F1 | **0.864 ± 0.009** |
| Herd generalisation test | **1.00** |
| Inference latency | **< 1 second** |

Per-class F1: herd **0.973** · loss aversion **0.904** · rational **0.804** · disposition **0.750**

**Causal effects (DoWhy, effect on sell-probability):**

| Treatment | Effect | Reading |
|---|---|---|
| `market_return` | **−2.068** | Falling markets strongly increase selling |
| `unrealized_gl` | **+0.811** | Losses strongly increase selling |
| `disposition_strength` | **+0.355** | Strongly increases selling |
| `herd_sensitivity` | **+0.164** | Moderately increases selling |
| `loss_aversion` | **+0.038** | Weakly increases selling |
| `crowd_ratio` | **+0.016** | Weakly increases selling |

**Interventions — this is the "causal, not correlational" proof:**

| Intervention | Sell probability | Change |
|---|---|---|
| Baseline | 0.700 | — |
| Reframe losses (cognitive therapy) | 0.609 | **−9.1 pp** |
| Reduce herd sensitivity (independent analysis alert) | 0.680 | −2.0 pp |
| Hide crowd-action widget | 0.690 | −1.0 pp |
| **All three combined** | **0.579** | **−12.1 pp** |

> **Say this:** "A correlational model can tell us loss-averse people sell more. Only the causal
> model lets us ask what happens *if we intervene* — and it says reframing losses cuts panic
> selling by nine percentage points."

### Honest note
Disposition is the weakest class (F1 0.750) and is most often confused with `rational`. That is
expected: the disposition effect only becomes visible across *many* decisions, whereas the model
sees one at a time.

---

## PART 3 — Objective 2: Individual, Portfolio-Aware Long-Horizon Evaluation ✅

> *Develop a personalized portfolio-level simulation engine to evaluate the long-term (10–30 years)
> impact of financial decisions under uncertainty and compounding effects.*

### What we built
A Monte Carlo engine that takes *one person's* portfolio and simulates two futures — holding
versus selling — across their real investment horizon.

### Why this way
A single-point prediction ("you'll have ₹X") would be dishonest; markets are uncertain. A
*distribution* over thousands of futures tells the truth: here is the typical case, here is a bad
case, here is a good one.

### How — the mechanics (know these cold, you will be asked)

**Personalised asset allocation:**
```
base = 0.40 + (risk_tolerance × 0.50)
   age > 60  → × 0.60      age < 30  → × 1.10
   horizon > 20 → × 1.05   horizon < 10 → × 0.90
   clipped to [0.30, 0.90]
```

**The HOLD path:** current wealth × (1 + unrealised P&L), invested at the personalised allocation.

**The SELL path — three separate penalties:**
1. Realise 95% of the gain/loss
2. Pay ~5% transaction and impact cost
3. **Reinvest at 30% of the original stock allocation** — a frightened investor becomes 70% more
   conservative, and the money then compounds near the bond rate (5.5%)

**Each year:** `wealth × (1 + allocation × market_return + (1 − allocation) × bond_return)`,
sampling from 10,000 pre-generated 30-year market paths with crashes injected at years 10 and 20.

> **Say this:** "Point 3 is the finding that surprised us. Selling isn't just leaving one
> investment — people put the money somewhere safe and leave it there. That reallocation, not the
> transaction cost, is what actually destroys long-term wealth."

### Tools used
`NumPy` (vectorised Monte Carlo) · `pandas` · `SciPy` · `Plotly` (trajectory bands) · `joblib`

### Results — Experiment 2, population-level cost of bias

| Metric | Value |
|---|---|
| Users simulated | 100 |
| Assumed portfolio | ₹75,000 |
| Paths per user | 300 |
| **Mean opportunity cost of selling** | **₹28,232** |
| Median opportunity cost | ₹23,201 |
| Mean wealth gap | **16.2%** |
| Users better off holding | **60%** |
| Status | **PASS** |

Validation against pre-computed counterfactuals is available per decision via
`GET /simulate/validate/{decision_id}`.

> **Say this:** "On a ₹75,000 portfolio, the average behavioural mistake costs ₹28,000 over the
> horizon — about 16% of terminal wealth. And notice we report that holding wins in 60% of cases,
> not 100%. The system is not a cheerleader for holding; it computes."

---

## PART 4 — Objective 3: Decision-Centric Explainability ✅ *(this review's work)*

> *Generate decision-centric, counterfactual explanations that clearly show how financial decisions
> causally influence long-term outcomes beyond static post-hoc interpretations.*

### The problem, in one comparison

**Before** — what Objectives 1 and 2 actually showed the user:
```
Detected Loss Aversion bias (confidence 87%, risk 64%).
  [loss_aversion=2.7] causal effect on decision: +0.0412
  [unrealized_gl=-0.15] causal effect on decision: -0.1203
SHAP: unrealized_gain_loss 0.31 | crowd_action_ratio 0.12
hold mean 900,000  p10 320,000  p90 1,400,000
```

**After** — same inputs, nothing recomputed:
> "You're thinking about selling while your investment is down 15%. Before you do, here's what that
> one decision is likely to cost you over the next 14 years… Your investment is down 15% right now,
> and that genuinely hurts. Research on thousands of investors shows a loss feels about twice as
> painful as the same-sized gain feels good. But selling doesn't stop the loss — it makes it
> permanent."

### Why templates, not an LLM
**This is the design decision to defend.** The rupee figures in these explanations drive real money
decisions. A template *physically cannot* invent a number. An LLM can. So:
- Deterministic Jinja2 templates are the authoritative path — always run, fully reproducible.
- An optional LLM layer may improve *wording only*, behind a **numeric guard**: every number and
  rupee amount in the polished text must already exist in the template text, or the polish is
  discarded. Hallucinated figures are structurally unable to reach the user.
- The system runs fully offline with the LLM off — which is how we demo it.

### The six sections the user reads

| # | Section | Answers |
|---|---|---|
| 1 | In short | What am I about to do, and is it wise? |
| 2 | What's going on right now | Why is my brain pushing me here? |
| 3 | Your two possible futures | What is each choice worth, in rupees? |
| 4 | The story of your money | Year by year — and how was this calculated? |
| 5 | Why we're telling you this | What actually drove this conclusion? |
| 6 | What to do now | What should I do, and how sure are you? |

### The jargon translation layer — the heart of the objective

| Internal | Shown to the user |
|---|---|
| `p10` / `p90` | "if things go badly" / "if things go well" |
| `unrealized_gl` | "how much your investment is up or down right now" |
| `opportunity_cost` | "money you'd miss out on by selling" |
| `causal effect +0.0412` | "the biggest factor was how strongly losses affect you" |

18 mapped terms, **30 blocklisted terms**, 14 causal drivers translated. A test fails the build if
any blocklisted term reaches the user. **Current leaks: 0.**

### Bilingual by design
Hindi is **hand-written, not machine-translated** — 34 template strings per language, structural
parity enforced by tests. Hindi therefore works **fully offline with no LLM**. Money is formatted
as लाख / करोड़, not `120000`.

### Tools used
`Jinja2` (templating) · `textstat` (Flesch) · `ReportLab` (PDF) · `google-genai` (optional, guarded)
· `python-dotenv` (secret hygiene) · `pytest`

### Results

| Metric | Target | English | Hindi |
|---|---|---|---|
| Readability | Flesch ≥ 60 | **78.3** | **12.2 words/sentence** |
| Completeness | 100% | 100% | 100% |
| Actionability | 100% | 100% | 100% |
| Personalisation | 100% | 100% | 100% |
| Jargon leaks | 0 | **0** | **0** |

Measured over 64 explanations. **4,102 lines of new code, 128 explainer tests, 256 tests passing.**

> **Say this:** "Flesch 78 is roughly a seventh-grade reading level. That is the number that says
> this objective is met — not that the code runs, but that a person with no finance background can
> read the output."

---

## PART 5 — Next Scope: Objective 4

> *Implement a tamper-proof audit mechanism that records AI recommendations, causal assumptions, and
> counterfactual analyses to ensure transparency, accountability, and verifiable decision trails.*

### Where it stands today — be honest about this
| Already built | Missing |
|---|---|
| SHA-256 hashing of input / output / explanation | **No hash chain** — `previous_hash` does not exist |
| Append-only `audit_logs` table | No compliance query engine |
| Per-record tamper detection | No counterfactual outcome verification |
| `GET /audit/{decision_id}` | No capture of what the user actually did |

**The honest weakness:** records currently self-verify *in isolation*. Deleting a whole record is
undetectable, because nothing links one record to the next.

### The plan
1. **`DecisionBlock`** — block ID, timestamp, user, decision payload, `previous_hash`, own hash.
2. **`BlockchainAuditSystem`** — genesis block, `add_block()`, `verify_chain()` that detects both
   edits *and* deletions, JSON persistence.
3. **Schema migration** — add `previous_hash`, `block_index`, `decision_payload`, `user_action`,
   `followed_advice`, guarded so the existing database survives.
4. **`verify_counterfactual_accuracy()`** — compare what we predicted against what actually
   happened, reusing the Objective 2 validator.
5. **`AuditQueryEngine`** — "all loss-aversion cases in Q1", "cases where the user ignored advice".
6. **Compliance report** — chain integrity, advice-followed rate, counterfactual accuracy.

**Why Objective 3 makes this easy:** the explainer already returns a flat, JSON-serialisable `facts`
dictionary. That is exactly what a block hashes. No rework needed.

### Beyond Objective 4 — future work
- Quantified causal statements in the narrative ("raised your sell probability by 4 points")
- Validation with real investors (readability study)
- More Indian languages — the template architecture already supports it
- Fine-tuning a small model on template output (noted, not recommended: it would train on our own
  output and be less verifiable)

---

## PART 6 — THE SPEAKING SCRIPT
*Target: 12–15 minutes of talking + 5 minutes of demo. Cues in [brackets].*

---

**[SLIDE 1 — Title]**

"Good morning ma'am. This is our major project — a causal decision-time framework for detecting
behavioural biases and evaluating their long-term portfolio impact.

Today I'll cover what we completed in Objectives 1 and 2, then this review's work, which is
Objective 3, and finish with a live demo and where we go next."

---

**[SLIDE 2 — The problem]**

"The starting point is a simple, expensive fact: individual investors lose a significant share of
their wealth to their own behaviour — panic selling, following the crowd, cashing out winners too
early.

Existing financial AI has three weaknesses. It detects these patterns *after* the decision is made,
which is too late to help. It predicts the *market* rather than *your* portfolio. And it explains
itself in language only a data scientist can read.

Our four objectives map directly onto those gaps." [walk the four-gap table]

---

**[SLIDE 3 — Why synthetic data]**

"Before the results, one question we always get: why synthetic data?

Three reasons. We cannot read a real investor's mind to label 'this was loss aversion' — so ground
truth is impossible in real data. We cannot replay history with the person holding instead of
selling — so counterfactuals don't exist. And thirty-year futures haven't happened yet.

Synthetic generation gives us controlled experiments with known answers. Live NIFTY data is still
used for market context at run time, so the system is not purely synthetic in operation."

---

**[SLIDE 4 — Objective 1]**

"Objective 1 is decision-time causal reasoning.

We trained an XGBoost classifier on 7,439 decision events across 3,057 user profiles, using SMOTE
on the training split to handle class imbalance. It classifies four states: loss aversion, herd
behaviour, disposition effect, or rational.

It reaches **84% test accuracy and 0.858 macro F1**, cross-validated at 0.864 with a standard
deviation under 0.01 — so it is stable, not a lucky split. Inference is under a second, which is
what makes it *decision-time* rather than retrospective.

But a classifier alone only tells us what pattern matched. It cannot answer 'what if this person
were less loss-averse?' So we added a causal layer." [pause]

---

**[SLIDE 5 — Objective 1, the causal part]**

"We attempted structure learning with NOTEARS, then Hill-Climb search, and fell back to a
domain-knowledge graph — eight nodes, twelve edges, validated as a proper DAG. We're transparent
that the shipped graph is the domain one; the fallback chain is in the code.

We then used DoWhy with backdoor linear regression to estimate the effect of each factor on
sell-probability. Recent market return has the strongest effect at −2.07 — falling markets drive
selling. Unrealised loss is +0.81. Disposition strength is +0.355.

And here is the part that justifies the word 'causal'." [click to interventions]

"We simulated interventions. Reframing losses — a cognitive-therapy-style intervention — cuts sell
probability from 0.70 to 0.61, a nine-point drop. All three interventions combined take it to 0.58.

A correlational model could never produce that table. It could tell us loss-averse people sell more.
Only a causal model tells us what happens if we *change* it."

---

**[SLIDE 6 — Objective 2]**

"Objective 2 asks what that decision is actually worth over a lifetime.

We built a Monte Carlo simulator that takes one person's portfolio and simulates two futures —
holding and selling — over their real horizon, ten to thirty years, sampling from 10,000
pre-generated market paths that include crashes at years ten and twenty.

Asset allocation is personalised: it starts from risk tolerance and is adjusted for age and horizon.

The important design detail is how we model selling. It is not one penalty, it's three. You realise
the loss. You pay about 5% in costs. And — this is the one people miss — you reinvest at 30% of your
original equity allocation, because a frightened investor becomes conservative and stays that way.
That third effect, not the transaction cost, is what destroys long-term wealth."

---

**[SLIDE 7 — Objective 2 results]**

"Across 100 simulated users on a ₹75,000 portfolio, the average behavioural mistake costs
**₹28,232** — about **16% of terminal wealth**.

I want to draw attention to one number: holding is better in **60%** of cases, not 100%. The system
is not a cheerleader for holding. Sometimes selling genuinely is right, and it says so."

---

**[SLIDE 8 — Objective 3: the problem]**

"Which brings us to this review's work.

After Objectives 1 and 2 we had everything a person needs to make a good decision. And this is what
we were showing them." [click — the BEFORE block]

"`causal effect on decision: plus zero point zero four one two`. A number with no unit and no
consequence. `p10` and `p90` — percentile notation. SHAP values, which explain the *model*, not the
*decision*.

Nothing here connects the bias to the money. Nothing tells the user what to do. The information was
correct and completely unusable."

---

**[SLIDE 9 — Objective 3: the solution]**

"So Objective 3 is a decision-centric explanation engine.

Same inputs, nothing recomputed — only the presentation changes." [click — the AFTER block, read
two or three sentences aloud]

"Six sections: what you're about to do, what's happening in your head, your two possible futures in
rupees, the year-by-year story of your money, why we're telling you this, and what to do now."

---

**[SLIDE 10 — Objective 3: the key design decision]**

"The obvious approach would be to send everything to ChatGPT and ask for a nice explanation. We
deliberately did not do that, and this is the decision I'd most like to defend.

These explanations contain rupee figures that drive real money decisions. A template *physically
cannot* invent a number. A language model can.

So the templates are authoritative and always run. There is an optional AI layer that may improve
the *wording only* — and it sits behind a numeric guard: every number and every rupee amount in the
AI's output must already exist in the template text, or the rewrite is thrown away.

We tested it with a deliberately invalid API key. The user still got a complete explanation, with no
error, in under two seconds. The AI is a garnish; it is never load-bearing."

---

**[SLIDE 11 — Objective 3: jargon layer and Hindi]**

"The engineering heart of this objective is a translation layer — 18 mapped terms, 30 blocklisted
terms, 14 causal drivers converted to plain phrases. `p10` becomes 'if things go badly'. A test
fails the build if any blocklisted term reaches the user. Current leaks: zero.

And the whole thing is bilingual. Hindi is hand-written, not machine translated — 34 template
strings per language, with parity enforced by tests. That means **Hindi works completely offline
with no AI**, which matters for the users this system is actually for."

---

**[SLIDE 12 — Objective 3: results]**

"We validated over 64 explanations. English scores **Flesch 78.3** — roughly a seventh-grade reading
level, against a target of 60. Hindi averages 12 words per sentence against a target of 20.
Completeness, actionability and personalisation are all 100%. Jargon leaks: zero.

4,102 lines of new code, 128 tests for this objective, 256 tests passing across the project.

That Flesch number is what says the objective is met — not that the code runs, but that someone with
no finance background can read the output."

---

**[DEMO — see Part 7. Roughly 5 minutes.]**

---

**[SLIDE 13 — Objective 4, next]**

"That leaves Objective 4 — verifiable auditability.

I want to be precise about where it stands. We already hash every decision with SHA-256 and store it
in an append-only table, and there's an audit endpoint. What is missing is the chain: there is no
`previous_hash` linking one record to the next. So records self-verify in isolation, and deleting a
whole record is currently undetectable.

The plan is a `DecisionBlock` with a previous-hash pointer, chain verification that catches edits
*and* deletions, a query engine for compliance questions, and verification of our counterfactuals
against realised outcomes.

Objective 3 actually makes this easier: the explainer already returns a flat, serialisable facts
dictionary, which is exactly what a block needs to hash."

---

**[SLIDE 14 — Close]**

"To summarise: Objectives 1, 2 and 3 are complete and tested. We can detect a bias at decision time
and reason about it causally. We can simulate what that decision costs a specific person over their
lifetime. And we can now explain all of it in language they can actually read, in two languages.

Objective 4 is the remaining work, and the ground for it is already laid. Thank you — happy to take
questions."

---

## PART 7 — DEMO RUNBOOK

### T-30 minutes: pre-flight
Run these *before* the review. Do not debug in front of the panel.

```bash
python -m pytest tests/ -q
```
Expect: `256 passed`.

```bash
python scripts/evaluate_explanations.py --n-users 10 --n-simulations 200
```
Expect: all targets YES, both languages.

**Set `EXPLAINER_LLM=off` in `.env`.** This makes the demo instant, deterministic and offline —
no dependence on the network or an API quota in the room.

### T-5 minutes: start the two services
Terminal 1:
```bash
python -m uvicorn api:app --app-dir src --port 8000
```
Wait for startup, then confirm in a browser: `http://localhost:8000/health`

Terminal 2:
```bash
streamlit run src/dashboard.py
```
Opens `http://localhost:8501`. **Load the page once before the review** so nothing compiles live.

---

### The demo, step by step

**Step 1 — Set the scene** *(30 seconds)*
> "This is our investor, user 42. Age 26, ₹39,000 a month, risk tolerance 0.22 — quite
> conservative — and a 14-year horizon. Importantly, **no emergency fund**. Watch what the system
> does with that fact later."

Go to **Decision Intelligence Hub**, enter user ID `42`, click **Load Profile**.

**Step 2 — The decision** *(30 seconds)*
Enter: unrealised gain/loss **−15%**, portfolio value **₹75,000**, intent **"Thinking of selling"**.
Monte Carlo paths: **1000**.
> "So: ₹75,000 invested, currently down 15%, and he's thinking of selling. This is the exact moment
> the system is designed for."

Click **Analyse & Simulate**.

**Step 3 — The narrative** *(2 minutes — the centrepiece)*
Scroll slowly. Read two or three sentences **aloud** — the writing is the deliverable.
> "Notice there is no jargon anywhere on this page. No SHAP, no percentiles, no causal
> coefficients."

At the year-by-year table:
> "This is the part we deepened most. It starts from today, and it shows why selling costs ₹2,653
> before any growth happens. Then it shows the two paths diverging."

At the year 10–11 drop:
> "And notice this — the table goes *down* here. That's a market crash in this particular future.
> Rather than leave the user confused, the system detects the drop and explains it: both columns
> fall, staying invested falls hardest, and that is exactly the moment selling feels most obvious."

At the closing line:
> "The closing sentence is generated from the data, not fixed text. When a late crash narrows the
> gap, it says so — and it admits holding wins in 56 of 100 futures here, not all of them."

**Step 4 — Hindi** *(45 seconds — the moment that lands)*
Switch the sidebar language to **हिंदी**.
> "Same decision, same numbers, hand-written Hindi — not machine translation. And notice how fast
> that was: the narrative re-renders locally. It does not re-run the model or the simulation."

**Step 5 — The report** *(30 seconds)*
Click **Report (HTML)**.
> "The user can keep this, print it, or take it to an advisor."

**Step 6 — The technical layer** *(45 seconds — proves the rigour)*
Expand **Technical details**.
> "Everything from Objectives 1 and 2 is still here — SHAP contributions, the causal chain, the full
> distribution statistics. We didn't delete the rigour, we moved it one click away. It's available
> to anyone who wants it, and out of the way of everyone who doesn't."

**Step 7 — Optional, if there's time** *(30 seconds)*
Open `http://localhost:8000/docs` and show `POST /explain`.
> "All of this is also a REST API, so the explanation layer isn't tied to our dashboard."

---

### If something breaks — fallbacks, in order
1. **`notebooks/09_explainability.ipynb`** — already executed with outputs saved. Every point in the
   demo appears there, no server needed.
2. **`OBJ3_DOCUMENTATION.html`** — the offline documentation page with all diagrams.
3. **A pre-generated report** — keep one HTML report open in a browser tab as insurance.

> If the dashboard misbehaves: *"Let me show you this from the notebook instead — it's the same
> pipeline with the outputs saved."* Stay calm; do not debug live.

---

## PART 8 — LIKELY QUESTIONS

**"Why synthetic data? Isn't that a weakness?"**
> Ground-truth bias labels are impossible in real data — we can't read minds. Counterfactuals don't
> exist in history. And the causal model can only be *validated* if we know the true structure. Live
> NIFTY data is used for market context at run time.

**"Why not just use ChatGPT for the explanations?"**
> Because these explanations contain rupee figures that drive real decisions, and a language model
> can invent a number. Our templates cannot. We do offer an optional AI wording layer, but behind a
> numeric guard that discards any output containing a figure not in the source. We demonstrated it
> with an invalid key: the user still got a complete explanation with no error.

**"Is 84% accuracy good enough?"**
> For four-class behavioural classification with cross-validated stability of ±0.01, yes. Herd
> detection is at 0.97 F1 and generalises perfectly on held-out tests. The weakest class is
> disposition at 0.75, which is expected — the disposition effect is only visible across many
> decisions, and the model sees one at a time.

**"What if the model is wrong?"**
> Two safeguards. The explanation always states its confidence honestly — it says "we're fairly
> sure", never "certain". And the recommendation comes from the simulation, not the classifier, so a
> misread bias changes the framing, not the financial advice.

**"How do you know the explanations are actually understandable?"**
> We measure it. Flesch Reading Ease 78.3 against a target of 60, plus automated completeness,
> actionability and personalisation checks, and a jargon blocklist enforced by tests. Sixty-four
> explanations evaluated. The honest gap is that we have not yet run a study with real readers.

**"Why is there no Hindi PDF?"**
> ReportLab has no OpenType text shaper. Devanagari needs one — in कि the matra is stored after the
> consonant but must be drawn before it. Without shaping the PDF would be subtly wrong, so we refuse
> it and offer an HTML report that prints to a correct PDF from any browser.

**"What's left?"**
> Objective 4. Hashing and an append-only audit table exist; the hash *chain* does not, so deleting a
> record is currently undetectable. That is the next build, and Objective 3's serialisable facts
> dictionary is already the right input for it.

---

## Quick Reference — Numbers to Have Ready

| | |
|---|---|
| Users / decisions | 3,057 / 7,439 |
| Market paths | 10,000 × 30 years |
| Obj 1 accuracy / macro F1 | 84.0% / 0.858 |
| Obj 1 CV | 0.864 ± 0.009 |
| Causal graph | 8 nodes, 12 edges |
| Combined intervention | −12.1 pp sell probability |
| Obj 2 mean opportunity cost | ₹28,232 (16.2% of wealth) |
| Obj 2 holding wins | 60% of users |
| Obj 3 Flesch (EN) | 78.3 (target 60) |
| Obj 3 Hindi | 12.2 words/sentence (target 20) |
| Obj 3 jargon leaks | 0 |
| New code (Obj 3) | 4,102 lines |
| Tests | 128 explainer / 256 total |
