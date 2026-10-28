# Chapter 10: Testing and Validation

## 10.1 Testing Objectives

Testing in Folium has four goals: (1) to show that each model and engine behaves as its specification says, including behavioural "sense" properties rather than only code paths; (2) to show that the security controls actually block what they are meant to block; (3) to show that the pipeline, database and live-progress stream work together end to end; and (4) to prevent regressions when models are retrained or replaced.

## 10.2 Test Suites and Execution Status

| Suite | Location | Tests (documented) | Needs | Framework |
|---|---|---|---|---|
| Models and engines | `tests/` (11 files) | 334 collected; 329 run, 5 skipped without an AI key | Python venv | pytest |
| Back end, unit (no database) | `backend/tests/unit/` (6 files) | 162 (subset of the 255 below) | Python venv | pytest |
| Back end, full | `backend/tests/` (17 files + unit) | 255 | PostgreSQL + Redis | pytest, httpx, pytest-asyncio |
| Front end | `frontend/src/test/` | 17 | Node | Vitest, Testing Library |

Table: Table 10.1: Test suites in the repository

The counts in Table 10.1 are those recorded in `FOLIUM_MASTER.md` (dated 2026-10-08), which states that the suites passed at that time. Counting `def test_` functions in the source gives 275 in `tests/` and 195 in `backend/tests/`; the higher collected counts come from parametrised tests, where one function runs over many cases. **The suites were not re-executed while preparing this report**, so the pass status is as documented by the team, not independently verified here. Appendix D gives the commands to re-run them; the run log should be attached to the final report.

## 10.3 Unit Testing

Unit tests exercise pure functions and engines without a database. Representative examples, with the property each one asserts:

| ID | Test (file :: function) | Property checked |
|---|---|---|
| UT-1 | `tests/test_bias_model_v4.py::test_one_row_and_batch_build_identical_features` | Training and live feature paths agree |
| UT-2 | `::test_missing_input_and_unknown_action_are_rejected` | Invalid input raises instead of silently filling |
| UT-3 | `::test_the_true_label_is_allowed_for_the_whole_dataset` | Label rules and dataset agree for all 20,000 rows |
| UT-4 | `::test_guard_removes_ruled_out_patterns` | Guard zeroes disallowed classes |
| UT-5 | `::test_calibration_never_changes_the_answer` | Calibration changes confidence, not the chosen class |
| UT-6 | `::test_drivers_explain_the_chosen_pattern_exactly` | SHAP drivers sum to the chosen class's margin |
| UT-7 | `::test_the_action_changes_the_reading` | Same situation, different action → different reading |
| UT-8 | `tests/test_simulator_v2.py::test_short_term_equity_gain_pays_20_percent_plus_cess` | Tax rule |
| UT-9 | `::test_long_term_equity_gain_is_exempt_up_to_125000` | Exemption rule |
| UT-10 | `::test_horizon_is_the_investors_within_1_to_30_years` | Horizon clamping |
| UT-11 | `::test_same_inputs_same_answer` | Determinism with a fixed seed |
| UT-12 | `::test_a_fund_is_less_spread_out_than_a_single_stock` | Fund vs stock risk |
| UT-13 | `::test_monthly_investing_sizes_the_portfolio_not_the_decision` | SIP leaves the gap unchanged |
| UT-14 | `::test_simulated_years_resemble_real_nifty` | Realism within tolerance |
| UT-15 | `::test_beta_sets_typical_growth_the_standard_way` | CAPM growth rule |
| UT-16 | `backend/tests/unit/test_pipeline_logic.py::test_decide` (parametrised) | Recommendation rules over intents, biases and $p$ |
| UT-17 | `::test_missing_simulation_is_disclosed_and_treated_as_even` | Missing $p$ handled and stated |
| UT-18 | `::test_inr_uses_lakh_and_crore` | Indian money formatting |
| UT-19 | `backend/tests/unit/test_audit_chain.py::test_an_edited_entry_is_caught` | Tamper detection |
| UT-20 | `::test_a_removed_entry_is_caught`, `::test_a_forged_insertion_is_caught`, `::test_a_fork_is_caught` | Deletion, forgery and fork detection |
| UT-21 | `::test_fingerprints_survive_database_round_trips` | Canonical hashing stable across Decimal/UUID/JSON |
| UT-22 | `::test_a_chain_started_by_the_placeholder_still_verifies` | Backward compatibility with legacy entries |
| UT-23 | `backend/tests/unit/test_comment_and_debate.py` (18 tests) | Comment rules in three languages; quotes verbatim; cases never alter the verdict |
| UT-24 | `tests/test_explainer.py` (88 functions, 128 collected) | Six sections, EN/HI structural parity, jargon blocklist, number guard |

Table: Table 10.2: Representative unit tests

## 10.4 Integration Testing

Integration tests in `backend/tests/` run the FastAPI app against real PostgreSQL and Redis instances through an HTTP client.

| ID | Test file | Scenario | Expected result |
|---|---|---|---|
| IT-1 | `test_auth_flow.py` | Register → verify e-mail → log in → refresh → log out | Cookies set and rotated; old tokens blacklisted |
| IT-2 | `test_mfa.py`, `test_mfa_recovery.py` | Enable TOTP, log in with code, use a backup code, request recovery | Second factor enforced; backup code single-use; one recovery request per 24 h |
| IT-3 | `test_csrf.py` | Mutating request with missing / mismatched / matching CSRF header | 403 / 403 / passes; login exempt |
| IT-4 | `test_rls.py` | User A's rows queried by user B; query with no user set | Zero rows in both cases |
| IT-5 | `test_rate_limit.py` | Repeated logins beyond the limit | HTTP 429 |
| IT-6 | `test_portfolio_api.py` | Add, edit, delete holdings; price outage | Values computed; outage falls back to average cost |
| IT-7 | `test_decisions.py`, `test_pipeline.py` | Submit an analysis and run the pipeline | 202; status moves pending → processing → complete; columns filled |
| IT-8 | `test_decisions_stream.py` | Open the stream mid-run and after completion | Backlog replayed; no duplicate events; terminal event received |
| IT-9 | `test_audit_chain_db.py` | Two analyses; tamper with a row; verify | Chain linear; tampering detected and named |
| IT-10 | `test_comment_reading_db.py` | Analysis with "college fees are due" in the reason | `comment_facts.cash_need = true`; sale can read rational |
| IT-11 | `test_account_deletion.py` | Delete, log in during grace, purge after grace | "Keep my account" offered; data anonymised; audit kept |
| IT-12 | `test_oauth.py` | Google sign-in for four account cases (mocked provider) | Accounts created or linked correctly |

Table: Table 10.3: Integration test scenarios

## 10.5 Functional and System Testing

Functional behaviour of the product as a whole was exercised through the demonstration walkthrough in `DEMO.md`, which uses accounts and analyses seeded by `scripts/seed_demo.py`. The walkthrough covers sign-in, the dashboard, the portfolio, a new analysis with live progress, the result page in both languages, report downloads, record verification and the data tools. We have not found a written record of the outcome of each walkthrough step in the repository; Table 10.4 therefore lists the system test cases with their expected results, and the "Observed" column must be completed when the walkthrough is repeated for the final submission.

| ID | Test case | Steps | Expected | Observed |
|---|---|---|---|---|
| ST-1 | Analysis with stated cash need | Sell a losing holding; reason "need money for college fees in March" | Pattern reads rational; quote shown; verdict SELL or HOLD with reasons | [to be filled] |
| ST-2 | Calm-market sale of a winner | Sell a holding up 30% with no reason | Disposition effect with High or Medium confidence | [to be filled] |
| ST-3 | Buy more in a rally | Buy more after NIFTY +5% month | Herd reading; verdict HOLD | [to be filled] |
| ST-4 | Hindi explanation | Switch language on the result page | All six sections in Hindi; same numbers | [to be filled] |
| ST-5 | Hindi PDF | Request PDF with `lang=hi` | Refused with explanation; HTML offered | [to be filled] |
| ST-6 | Reload during analysis | Refresh the page at step 2 | Steps 1–2 shown from backlog; progress continues | [to be filled] |
| ST-7 | Verify record | Click "Verify this record" | "Verified"; chain intact | [to be filled] |
| ST-8 | Tampered record | Edit the stored recommendation in the database, verify again | "Changed"; names the analysis part | [to be filled] |
| ST-9 | Market data off | Set `MARKET_DATA_ENABLED=false`, run analysis | Calm market assumed and disclosed | [to be filled] |
| ST-10 | Data export | Settings → Download my data | JSON without password hash, TOTP secret or tokens | [to be filled] |

Table: Table 10.4: System test cases (expected results from the specification; observed results to be recorded)

## 10.6 Input Validation and Edge-Case Testing

Input validation is enforced at three layers. Pydantic schemas in `backend/schemas/` reject malformed requests with HTTP 422 before any logic runs. Database `CHECK` constraints enforce domain rules regardless of the code path—for example `age BETWEEN 18 AND 100`, `holding_quantity > 0`, `bias_confidence BETWEEN 0.0 AND 1.0`, and `recommendation IN ('HOLD','SELL','BUY_MORE')` (migrations 0001 and 0003). The model and simulator raise on missing inputs or invalid values (`build_features`, `SimInputs.__post_init__`), which the tests UT-2 and `test_bad_inputs_are_rejected` check. Edge cases from Table 6.4 are covered by tests such as UT-10 (horizon), UT-17 (missing simulation) and IT-6 (price outage).

## 10.7 Performance Testing

No load or stress test has been performed. Two timing measurements are recorded in the evaluation files: one simulation of 1,000 paths over 30 years takes 103.4 ms, and each bias prediction reports its own inference time in milliseconds. Because analyses run in the background and the analyze endpoint is rate-limited to 10 per minute per client, request latency is dominated by the initial context capture (market data and stock risk, bounded by a timeout). A proper load test (for example with Locust against a deployed instance) is listed as future work.

## 10.8 Defects, Inconsistencies and Open Issues

The following issues were found while auditing the repository for this report or are documented by the team. None of them changes a reported result, but each should be known before the viva.

| # | Issue | Evidence | Status / suggested action |
|---|---|---|---|
| D-1 | Superuser connection bypassed RLS | Commit `fix(M1): enforce RLS by connecting the app as non-superuser app_user` | Fixed |
| D-2 | v3 explanations described a different class than shown (98.6% of cases) | `bias_v4_evaluation.json` | Fixed in v4 by explaining only the chosen class |
| D-3 | Google sign-in callback returns JSON instead of redirecting into the app | `FOLIUM_MASTER.md` §15 | Open |
| D-4 | Stale docstring: `recommendation.py` says nothing reads the user's free-text reason, but the comment reader (Phase B3) now does | `backend/core/recommendation.py` | Open (comment only; behaviour correct) |
| D-5 | `guard_ok` rejects added numbers but not removed ones; removal is only bounded by the 0.6× length limit, while the master document says a number may not be removed | `src/llm_polish.py` | Open; add a check that every number in the original appears in the rewording |
| D-6 | Explanation-quality evaluation (2026-08-22) predates bias model v4.1 and simulator v2 | `explanation_quality.json` | Re-run `scripts/evaluate_explanations.py` |
| D-7 | Column names such as `hold_median_20y` remain although the horizon is now variable | migration 0003, `backend/core/simulator.py` | Cosmetic; rename in a future migration |
| D-8 | Root `requirements.txt` lists older ranges (and `causalnex`) unlike the pinned `backend/requirements-ml.txt` | both files | Use the pinned file; tidy the root file |
| D-9 | Figures in `results/figures/` and `results/simulations/` are from v1–v3 | file names and dates | Not used in this report; archive them |

Table: Table 10.5: Defects and inconsistencies
