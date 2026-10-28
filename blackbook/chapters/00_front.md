::: {custom-style="Cover Title"}
FOLIUM: BEHAVIOURAL DECISION INTELLIGENCE THROUGH CALIBRATED BIAS DETECTION, CAUSAL ANALYSIS AND PAIRED LONG-HORIZON PORTFOLIO SIMULATION
:::

::: {custom-style="Cover Text"}
Project Report

submitted in partial fulfilment of the requirement for the award of the Degree of

**Bachelor of Technology**

in

**Computer Engineering**

by

**Jesil Shah ([Roll / UID No.])**

**Param Shah ([Roll / UID No.])**

**Het Shah ([Roll / UID No.])**

under the guidance of

**Dr. Nataash Raul**
:::

::: {custom-style="Cover Logo"}
![](figures/spitlogo.png){width=1.3in}
:::

::: {custom-style="Cover Text"}
**Department of Computer Engineering**

Bharatiya Vidya Bhavan's

**Sardar Patel Institute of Technology**

(Autonomous Institute Affiliated to University of Mumbai)

Munshi Nagar, Andheri (West), Mumbai – 400058

University of Mumbai

[Month, Year of Submission]
:::

[[PAGEBREAK]]

::: {custom-style="Front Heading"}
Certificate
:::

This is to certify that the Project entitled "Folium: Behavioural Decision Intelligence through Calibrated Bias Detection, Causal Analysis and Paired Long-Horizon Portfolio Simulation" has been completed to our satisfaction by Mr. Jesil Shah, Mr. Param Shah and Mr. Het Shah under the guidance of Dr. Nataash Raul for the award of the Degree of Bachelor of Technology in Computer Engineering from the University of Mumbai.

::: {custom-style="Cover Text"}
**Certified by**
:::

[[BLANK:3]]
[[SIG:**Dr. Nataash Raul**|**[Name of Head of Department]**]]
[[SIG:Project Guide|Head of Department]]
[[BLANK:3]]
[[SIGC:**[Name of Principal]**]]
[[SIGC:Principal]]
[[BLANK:1]]

::: {custom-style="Cover Text"}
**Department of Computer Engineering**

Bharatiya Vidya Bhavan's Sardar Patel Institute of Technology

(Autonomous Institute Affiliated to University of Mumbai)

Munshi Nagar, Andheri (West), Mumbai – 400058

[Month, Year of Submission]
:::

[[PAGEBREAK]]

::: {custom-style="Front Heading"}
Project Approval Certificate
:::

This is to certify that the Project entitled "Folium: Behavioural Decision Intelligence through Calibrated Bias Detection, Causal Analysis and Paired Long-Horizon Portfolio Simulation" by Mr. Jesil Shah, Mr. Param Shah and Mr. Het Shah is found to be satisfactory and is approved for the award of the Degree of Bachelor of Technology in Computer Engineering from the University of Mumbai.

[[BLANK:4]]
[[SIG:**External Examiner**|**Internal Examiner**]]
[[BLANK:3]]
[[SIG:(Signature)|(Signature)]]
[[BLANK:1]]
[[SIG:Name:|Name:]]
[[BLANK:1]]
[[SIG:Date:|Date:]]
[[BLANK:3]]

::: {custom-style="Cover Text"}
**Seal of the Institute**
:::

[[PAGEBREAK]]

::: {custom-style="Front Heading"}
Statement by the Candidates
:::

We wish to state that the work embodied in this report titled "Folium: Behavioural Decision Intelligence through Calibrated Bias Detection, Causal Analysis and Paired Long-Horizon Portfolio Simulation" forms our own contribution to the work carried out under the guidance of Dr. Nataash Raul at the Sardar Patel Institute of Technology. We declare that this written submission represents our ideas in our own words and, where others' ideas or words have been included, we have adequately cited and referenced the original sources. We also declare that we have adhered to all principles of academic honesty and integrity and have not misrepresented, fabricated or falsified any idea, data, fact or source in our submission.

[[BLANK:4]]
[[SIGL:**Name and Signature:**]]
[[BLANK:1]]
[[SIGL:1. Jesil Shah            ______________________]]
[[BLANK:1]]
[[SIGL:2. Param Shah           ______________________]]
[[BLANK:1]]
[[SIGL:3. Het Shah               ______________________]]
[[BLANK:1]]
[[SIGL:Date: ______________]]

[[SECTION:roman]]

::: {custom-style="Front Heading"}
Acknowledgements
:::

It is a pleasure to acknowledge the help and support that went into this project. We express our sincere gratitude to our guide, Dr. Nataash Raul, for his guidance throughout the work. His insistence that every number shown to an investor should be traceable to evidence shaped many of the design decisions described in this report.

We thank [Name of Examiner / Reviewer] for advice during the project reviews, and the Head of Department and the staff of the Department of Computer Engineering, Sardar Patel Institute of Technology, for the facilities required to carry out this work.

Finally, we thank our families and friends for their constant encouragement.

[[BLANK:2]]
[[SIGR:Jesil Shah]]
[[SIGR:Param Shah]]
[[SIGR:Het Shah]]

[[PAGEBREAK]]

::: {custom-style="Front Heading"}
Abstract
:::

Retail investors in India often decide to sell, hold or add to a share under the influence of recent price movements, social signals and the pain of a paper loss, rather than in the light of their own finances and time horizon. Most investing tools describe the stock; very few examine the decision that the investor is about to take. This project presents Folium, a full-stack decision-support web application that evaluates one intended action on one holding against the investor's whole financial picture.

For every analysis, Folium (i) reads the free-text reason given by the investor for stated cash needs and feelings, (ii) classifies the most likely behavioural pattern behind the decision—loss aversion, herd behaviour, the disposition effect or a rational motive—using an XGBoost classifier with 22 features, an isotonic calibration curve and exact TreeSHAP explanations, (iii) projects the HOLD and SELL alternatives over the investor's own horizon on the same 1,000 block-bootstrapped market paths built from real NIFTY 50 and gold history, after Indian capital-gains tax and charges, (iv) estimates what pushes such decisions using DoWhy backdoor adjustment and g-computation, (v) renders a six-part explanation from hand-written English and Hindi templates, (vi) issues a HOLD, SELL or BUY MORE verdict from explicit evidence rules rather than a language model, and (vii) seals the analysis into a per-investor SHA-256 hash chain that can be verified later. The system is built with FastAPI, PostgreSQL with row-level security, Redis and a React/TypeScript front end.

On a held-out test set of 4,000 synthetic decisions placed on real market days and re-weighted to real regime frequencies, the classifier reaches 87.9% accuracy, a macro-F1 score of 0.840 and an expected calibration error of 0.014; readings shown with High confidence are correct 98.7% of the time. Trained only on 2008–2019 and tested on 2020–2026, it scores 86.5%. The simulator's one-year return quantiles lie within 1.4 percentage points of the real index, and the causal estimates recover the known generator effects with a mean absolute error of about 0.5 percentage points. Because the behavioural labels are synthetic, these figures are development-stage results; they do not establish psychological diagnosis, real-market causality or improved investor returns.

**Keywords:** behavioural finance, decision support, XGBoost, probability calibration, SHAP, causal inference, block bootstrap, Monte Carlo simulation, explainable AI, row-level security.

[[PAGEBREAK]]

::: {custom-style="Front Heading"}
Executive Summary
:::

**What was built.** Folium is a working web application with sign-up, two-step verification, a portfolio of Indian assets with live prices, a five-step analysis pipeline with live progress, bilingual explanations and downloadable reports, a tamper-evident audit chain, and data-export and account-deletion tools. The machine-learning research code (in `src/`) is called by the product back end through a single bridge module, so the figures reported in this book are produced by the same code that serves users.

**What was measured.** Every numerical result in this report comes from evaluation files committed in the repository: `results/reports/bias_v4_evaluation.json`, `results/reports/simulator_v2_evaluation.json`, `results/causal_v4.json` and `results/reports/explanation_quality.json`. The charts in Chapters 8 and 9 were plotted directly from these files by `blackbook/make_figures.py`.

**Headline results (development stage, synthetic labels).** Bias model v4.1: 87.9% accuracy, macro-F1 0.840, ECE 0.014, 21 of 21 behavioural sense checks passed, against 53.4% accuracy for the previous v3 model on the same cases. Simulator v2: bad-year, typical-year and good-year returns of −6.9%, +11.6% and +34.7% against −7.5%, +11.3% and +33.3% for the real NIFTY 50. Causal module: 45 effects recovered with a mean absolute error of 0.48 percentage points and the correct sign in 97% of cases. Explanations: 100% completeness and zero jargon leaks across 64 explanations; English Flesch reading ease 78.3.

**What is not yet done.** Google sign-in does not yet return the browser into the web app, the admin panel is limited to an MFA-reset endpoint, the optional Gemini features have not been run against the live API, and the system has not been deployed with HTTPS. No study with real investors has been carried out, so no claim is made about improved investment outcomes.

[[TOC]]

[[LOF]]

[[LOT]]

::: {custom-style="Front Heading"}
List of Abbreviations and Symbols
:::

| Abbreviation | Meaning |
|---|---|
| API | Application Programming Interface |
| ATE | Average Treatment Effect |
| CSRF | Cross-Site Request Forgery |
| DAG | Directed Acyclic Graph |
| DFD | Data-Flow Diagram |
| ECE | Expected Calibration Error |
| EMI | Equated Monthly Instalment |
| ER | Entity–Relationship |
| FD | Fixed Deposit |
| GUC | Grand Unified Configuration (PostgreSQL run-time setting) |
| JSONB | Binary JSON column type in PostgreSQL |
| JWT | JSON Web Token |
| LTCG / STCG | Long-Term / Short-Term Capital Gains |
| MFA | Multi-Factor Authentication |
| NIFTY 50 | National Stock Exchange of India's 50-stock benchmark index |
| ORM | Object-Relational Mapping |
| RLS | Row-Level Security |
| RS256 | RSA signature with SHA-256 |
| SHAP | SHapley Additive exPlanations |
| SIP | Systematic Investment Plan |
| SPA | Single-Page Application |
| SSE | Server-Sent Events |
| TOTP | Time-based One-Time Password |
| UI | User Interface |
| VIX | Volatility Index (here, India VIX) |
| XGBoost | eXtreme Gradient Boosting |

| Symbol | Meaning |
|---|---|
| $\mathbf{x} \in \mathbb{R}^{d}$ | Feature vector of one decision ($d = 22$) |
| $K$ | Number of behavioural classes ($K = 4$) |
| $F_k(\mathbf{x})$ | Raw boosted-tree score (margin) for class $k$ |
| $\hat{p}_k(\mathbf{x})$ | Predicted probability of class $k$ |
| $\phi_{j,k}$ | SHAP contribution of feature $j$ to class $k$ |
| $m_k(\mathbf{x})$ | Rule mask: 1 if the label definitions allow class $k$ |
| $g(\cdot)$ | Isotonic calibration map |
| $W^{(H)}_{s,T}, W^{(S)}_{s,T}$ | After-tax wealth of HOLD / SELL on path $s$ at year $T$ |
| $\Delta_{s,T}$ | Paired difference $W^{(H)}_{s,T} - W^{(S)}_{s,T}$ |
| $p$ | Share of simulated paths in which holding beats selling |
| $\beta$ | Sensitivity of a stock to the NIFTY 50 |
| $\sigma_{\text{own}}$ | Company-specific yearly volatility |
| $\mathrm{do}(A=a)$ | Intervention that sets treatment $A$ to $a$ |
| $h_i$ | Chain hash of the $i$-th audit entry |
