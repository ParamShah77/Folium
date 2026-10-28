# Folium Blackbook — Companion Guide

This file accompanies `Folium_Blackbook.docx` / `.pdf`. It lists what you still need to supply, every placeholder and assumption, the validation checklist, and a viva preparation guide.

## 1. Repository audit summary

| Item | Finding | Evidence |
|---|---|---|
| Confirmed title | "Folium: Behavioural Decision Intelligence through Calibrated Bias Detection, Causal Analysis and Paired Long-Horizon Portfolio Simulation". The provisional title "Predictive Customer Lifetime Value Engine" does **not** match anything in the repository and was not used. | `README.md`, `FOLIUM_MASTER.md`, your research paper |
| Purpose | Decide sell / hold / buy more on one holding, judged against the investor's whole financial picture | `README.md` |
| Stack | FastAPI, PostgreSQL 18 + RLS, Redis/Memurai, React 19 + Vite + TypeScript; XGBoost, SHAP, DoWhy, scikit-learn | `backend/requirements*.txt`, `frontend/package.json` |
| Data | 20,000 synthetic decisions on real NIFTY 50 / India VIX days (2008–2026); real NIFTY + gold monthly history for simulation | `data/v4/DATASET_CARD.md` |
| Verified results | All numbers come from committed JSON evaluation files (dated 2026-08-22 to 2026-10-08) | `results/` |
| Not implemented | Admin panel (only MFA reset), Google sign-in redirect, deployment/HTTPS/CI, live Gemini run | `FOLIUM_MASTER.md` §1, §15 |
| Inconsistencies found | 9 items, listed in Table 10.5 of the report (stale docstring, one-directional number guard, explanation eval predates final models, legacy `_20y` column names, outdated root requirements, old figures) | Chapter 10.8 |

## 2. Evidence you must supply before submission

1. **Five screenshots** replacing Figures 9.7–9.11 (steps in Appendix G). In Word: right-click the placeholder → *Change Picture*.
2. **Test-run logs.** The test suites were **not re-run** for this report; counts (334 / 255 / 17) are as documented in `FOLIUM_MASTER.md`. Run the commands in Appendix D and keep the pytest/Vitest summary lines.
3. **System-test observations.** Fill the "Observed" column of Table 10.4 after repeating the `DEMO.md` walkthrough.
4. **Re-run explanation evaluation** (`python scripts/evaluate_explanations.py`) — the current file predates bias model v4.1 and simulator v2. If numbers change, update Table 9.7 and Figure 9.6 (`python blackbook/make_figures.py`, then `python blackbook/build.py`).

## 3. Placeholders and assumptions

| Location | Placeholder / assumption |
|---|---|
| Cover page, title page | `[Roll / UID No.]` ×3, `[Month, Year of Submission]` |
| Certificate | `[Name of Head of Department]`, `[Name of Principal]` |
| Acknowledgements | `[Name of Examiner / Reviewer]`; the sentence about the guide's emphasis on traceable numbers is a reasonable inference — edit to reflect your actual experience |
| Approval certificate, statement | Signatures, names and dates left blank intentionally |
| Gender titles | "Mr." used for all three candidates — correct if needed |
| Section 3.3 | Hardware figures are practical estimates, not measured benchmarks |
| Chapter 9.8 | Five screenshot placeholders |
| Table 10.4 | "Observed" column `[to be filled]` |
| Degree name | "Bachelor of Technology in Computer Engineering, University of Mumbai" taken from the college template; confirm for your batch |

## 4. Final validation checklist

| Check | Status |
|---|---|
| Rendered page count ≥ 70 | ✅ 134 pages (PDF, LibreOffice render; Word may differ by a few pages) |
| All required chapters (1–12), references and appendices A–I present | ✅ |
| TOC, List of Figures, List of Tables populated | ✅ in PDF; in Word they refresh on open (accept the "update fields" prompt) or right-click → Update Field |
| Roman numbering for preliminaries, arabic from Chapter 1, unnumbered title pages | ✅ |
| Figures numbered and captioned, each referenced in text and labelled as generated diagram / plotted from file / placeholder | ✅ (20 figures + 5 placeholders) |
| Code listings numbered with source file and function | ✅ 14 listings, copied from the repository |
| Equations render | ✅ (Word native equations; LibreOffice needed `libreoffice-math`) |
| Every number traceable to a repository file | ✅ (Table 8.1 lists the files) |
| References genuine and all cited | ✅ 57 references, all cited in text; 34 match your research paper |
| No secrets or personal data | ✅ `.env` values not reproduced; only `.env.example` variable names |
| Screenshots / test logs / observations | ⚠️ to be supplied (Section 2 above) |

## 5. Viva preparation guide

**One-line pitch.** Folium judges an investor's intended sell/hold/buy-more decision against their whole financial picture: it reads the likely behavioural pattern with calibrated confidence, projects both choices after tax on the same simulated markets, explains it in English or Hindi without ever inventing a number, recommends from transparent rules, and seals the analysis in a verifiable hash chain.

**Questions you should expect, with short answers grounded in the report:**

1. *Why synthetic labels? Isn't 87.9% meaningless then?* — No public dataset links Indian investors' decisions, finances and true motives. Markets are real; labels are synthetic. The 87.9% shows the model recovers the generator's motives; we say explicitly it is not a psychological diagnosis (Sections 8.6, 11.3).
2. *A rules-only baseline gets 85.2% — what does the model add?* — Judgement where rules over-call bias (right 64% vs 36% when they disagree: rebalancing, near goal, cutting a loss, stated cash need) and calibrated confidence (High right 98.7%) (Table 8.8).
3. *What is calibration and why isotonic?* — Stated confidence should equal accuracy; isotonic is a monotone, non-parametric map fitted on out-of-fold predictions; we use the centred variant to avoid a staircase. ECE 0.014 (Section 7.4).
4. *SHAP vs causal effects?* — SHAP explains the model's score; causal effects explain what would change behaviour. We keep them separate: SHAP drives "What weighed most", causal_v4 drives "Cause and effect" (Sections 2.3, 7.5, 7.9).
5. *How do you know the causal estimates are right?* — The generator is known exactly, so we compute true effects by intervention and compare: MAE 0.48 points, 97% correct sign; gold share is a negative control (Section 9.6).
6. *Why the same market paths for hold and sell?* — Common random numbers: the difference measures the decision, not noise (Section 7.7).
7. *Why 12-month blocks and recentring?* — Keep volatility clustering and crash–recovery pairs; recentre because 2007–2026 gold (~15%/yr) would bias every path. Replaying history exactly flips the base case to 42% (Table 9.3).
8. *Why median gap, not mean?* — Single-stock outcomes are right-skewed; the mean overstates the typical result.
9. *Why not let an LLM recommend?* — A verdict about money must be checkable; the rules are a pure function with stored reasons. Gemini may only reword, and `guard_ok` rejects new numbers (Listing 6.12). Admit the known gap: it doesn't yet reject *dropped* numbers (D-5).
10. *How does RLS work and why app_user?* — Policy compares `user_id` with a transaction-local setting; superusers bypass RLS, so the app connects as a non-superuser (Listing 6.13).
11. *How does the hash chain detect tampering?* — Each entry hashes its payload and links to the previous chain hash from a genesis derived from user id + sign-up time; verification walks links and catches edits, deletions, forgeries and forks (Section 7.11).
12. *What happens if market data is down?* — A calm median market is assumed and disclosed; analysis still completes (Table 6.4).
13. *What would you do next?* — Consented real data and a user study; LR/RF baselines with confidence intervals; two-way number guard; finish Google sign-in, admin panel and deployment (Section 12.5).

**Numbers to remember:** 20,000 cases · 22 features · 402 trees · 87.9% / 0.840 / 0.014 · High band 98.7% · out-of-time 86.5% · rules-only 85.2% · ceiling 90.0% · simulator −6.9/+11.6/+34.7 vs real −7.5/+11.3/+33.3 · 1,000 paths, ~0.1 s · causal MAE 0.48 pts, 97% sign, 12/13 refutations · Flesch 78.3.

## 6. Rebuilding the document

```bash
python blackbook/make_figures.py
python blackbook/build.py
```

Requires pandoc, python-docx, matplotlib and LibreOffice (with `libreoffice-math`). Chapter text is in `blackbook/chapters/*.md`; edit there and rebuild, or edit the .docx directly.
