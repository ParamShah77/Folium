# GAP 1 Full Completion — Implementation Plan

## Overview
Building missing components for the causal, explainable financial decision intelligence system.
The existing stack: XGBoost bias detector (89% accuracy), NOTEARS causal DAG, OLS causal inference, FastAPI.

## Proposed Changes

### Task 1 — `src/market_data.py` [NEW]
- `MarketDataFetcher` class using `yfinance`
- Fetches NIFTY50 (`^NSEI`) 1-month return + 30-day rolling volatility
- Crowd ratio from India VIX (`^INDIAVIX`) or volatility proxy
- 15-min TTL in-memory cache (`threading.Lock` safe)
- `get_market_context()` → dict with market_return, market_volatility, crowd_ratio, last_updated, data_source
- `is_market_hours()` → NSE hours check (9:15–15:30 IST)
- Graceful fallback to cached/default values on yfinance error

---

### Task 2 — `src/database.py` [NEW]
- `DatabaseManager` class using `sqlite3` (no ORM)
- Creates `data/financial_intelligence.db` on init
- Tables: `user_profiles`, `bias_profiles_live`, `decisions_live`, `audit_logs` (append-only), `market_data_cache`
- All queries parameterized (no SQL injection)
- Methods: `register_user`, `get_user`, `update_bias_profile`, `log_decision`, `append_audit_log`, `get_user_decision_history`, `get_audit_trail`
- Running-average bias profile update after each decision

---

### Task 3 — `src/bias_detector.py` [MODIFY]
- Add `import shap` at top
- After prediction in `detect_bias_realtime()`: compute `shap.TreeExplainer` values for single row
- Return `shap_explanation`: list of top-5 `{feature, value, shap_impact, direction}` dicts
- Add `get_shap_summary(X_test)` method for global SHAP summary
- Apply SMOTE from `imblearn` in `load_data()` for herd class imbalance (target ≥ 100 herd samples)
- Keep all existing functionality intact; retrain and resave model

---

### Task 4 — `src/causal_inference.py` [MODIFY]
- Replace partial-correlation in `estimate_effect_dowhy()` with DoWhy `backdoor.propensity_score_matching`
- Use `dowhy.CausalModel` with loaded `causal_graph.pkl` DAG
- Fallback chain: PSM → `backdoor.linear_regression` → existing partial correlation
- Add refutation tests: `random_common_cause`, `placebo_treatment_refuter`
- Document which method was used in output dict (`method` field)
- Keep `simulate_intervention()` logic intact

---

### Task 5 — `src/api.py` [MODIFY]
New endpoints:
- `POST /user/register` — register user + 5-question onboarding, store in DB
- `GET /user/{user_id}/profile` — full profile + bias history
- `GET /user/{user_id}/decisions` — decision history
- `POST /analyze/decision` (updated) — optional `user_id`, auto market data, SHAP, DB logging, audit hash
- `GET /audit/{decision_id}` — full audit trail + tamper detection
- `GET /market/context` — live market data

Connect `DatabaseManager` and `MarketDataFetcher` as FastAPI lifespan dependencies.

---

### Task 6 — `src/dashboard.py` [NEW]
Streamlit dashboard with 3 pages:
1. **Decision Analysis**: Market banner, decision form, bias alert, causal chain, SHAP bar chart (Plotly), audit hash
2. **User Profile**: Bias score evolution chart, decision history table
3. **Market Context**: Live NIFTY data, market regime indicator

Uses `st.session_state` for user_id persistence. Configurable API base URL via env var. Graceful error handling if API is down.

---

### Task 7 — `scripts/fix_herd_imbalance.py` [NEW]
- Loads `synthetic_decisions.csv`
- Generates synthetic herd samples using Beta/uniform distributions
- Target: ~400 herd samples (balanced with other classes)
- Prints class distribution before/after, saves updated CSV

---

### Additional Files
- `tests/test_market_data.py` [NEW]
- `tests/test_database.py` [NEW]
- `tests/test_api.py` [NEW]
- `requirements.txt` [MODIFY] — add: yfinance, shap, imbalanced-learn, dowhy, streamlit, plotly, networkx

## Verification Plan
1. Run `python scripts/fix_herd_imbalance.py` — check class balance printout
2. Run `python src/bias_detector.py` — verify SHAP output in result dict
3. Run `python src/causal_inference.py` — verify DoWhy method used
4. Run `uvicorn src.api:app --port 8000` — test `/docs` endpoints
5. Run `streamlit run src/dashboard.py` — verify UI loads
6. Run `pytest tests/` — verify all test files pass
