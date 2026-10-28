[[SECTION:arabic]]

# Chapter 1: Introduction

## 1.1 Project Background

Participation of individual investors in Indian equity markets has grown sharply over the last decade. Discount brokers, mobile trading applications and the systematic investment plan (SIP) route into mutual funds have made it possible for a salaried person to own shares with a few taps. Access, however, is not the same as judgement. A first-time investor watching a holding fall 15% while friends discuss a market crash on a messaging group faces a decision that is as much emotional as financial.

Behavioural finance has studied such decisions for more than forty years. Kahneman and Tversky showed that people evaluate outcomes relative to a reference point and feel losses more strongly than equal gains [1]. Shefrin and Statman described the "disposition to sell winners too early and ride losers too long" [4], and Odean found clear evidence of it in brokerage records [2]. Bikhchandani, Hirshleifer and Welch explained how people can rationally follow the crowd and still end up in an informational cascade [3]. These patterns are not rare quirks: they are systematic and they cost money [14].

At the same time, the same action can be perfectly sensible for a different person. Selling a losing share is a mistake if it is driven by panic, but it is the right thing to do if the investor's college fees are due next month and there is no emergency fund. Any tool that labels a decision "biased" without looking at the investor's own finances will be wrong exactly when it matters most.

Folium was built to address this gap. The project began as a research effort on behavioural bias detection with a Streamlit prototype and synthetic data (versions v1 to v3 of the models, kept in the repository as rollback options). Over successive iterations it grew into a complete product: a FastAPI back end, a React front end, a PostgreSQL database with row-level security, a dataset built on real NIFTY 50 and India VIX history, a calibrated classifier, a tax-aware simulator, a causal-analysis module, a bilingual explanation engine and a tamper-evident audit trail.

## 1.2 Domain Overview

The project sits at the intersection of three areas.

**Behavioural finance** supplies the vocabulary of the problem: loss aversion, herd behaviour and the disposition effect are the three patterns Folium looks for, alongside a "rational" class that covers legitimate motives such as rebalancing, a near goal, cutting a loss or needing cash.

**Machine learning and causal inference** supply the tools to read a decision from data. A gradient-boosted tree classifier estimates which pattern best explains the situation and the action; isotonic calibration makes its confidence honest; SHAP attributions explain which inputs pushed the reading; and backdoor adjustment and g-computation estimate which factors change the chance of each action.

**Secure web engineering** supplies the means to deliver all of this to a real person. Financial data is sensitive, so authentication, session management, data isolation, auditability and data-subject rights (export and deletion) are part of the problem, not an afterthought.

## 1.3 Problem Context

Existing investing tools fall broadly into three groups. Brokerage and portfolio-tracking apps show prices, profit and loss, and charts; they describe the asset, not the decision. Robo-advisers construct a portfolio from a risk questionnaire but do not examine an individual trade at the moment it is being considered. Financial news and social media, which strongly influence retail behaviour, offer opinion without any link to the investor's circumstances.

None of these answers the question an investor is really asking at the moment of decision: *"Given my income, loans, emergency fund, the rest of my portfolio and how long I can wait, is what I am about to do sensible, or am I reacting to the moment?"* Answering it requires combining four separate pieces of evidence—the behavioural reading, the financial consequences of each choice, the factors that drive such choices, and a clear explanation—and doing so in a way that never hides an assumption or invents a number.

## 1.4 Problem Statement

To design and implement a secure, explainable decision-support system that, for a single intended action (sell, hold or buy more) on a single holding of an Indian retail investor:

1. identifies the behavioural pattern most likely behind the decision, with a calibrated confidence and a faithful explanation of the inputs that drove the reading;
2. compares the after-tax wealth outcome of holding and of selling over the investor's own horizon, under the same simulated market conditions;
3. estimates which situational and personal factors push investors towards that action, and which single habit would help most;
4. explains all of the above in plain English or Hindi without allowing wording to alter any number;
5. issues a recommendation from transparent evidence rules; and
6. records each analysis in a form that the investor can later verify has not been altered.

## 1.5 Motivation

Three observations motivated the project.

First, the cost of behavioural mistakes is real but invisible at the moment of decision. An investor who panic-sells during a correction rarely sees the counterfactual: what the money would have become had it stayed invested. Folium makes that counterfactual concrete by projecting both paths on identical market scenarios.

Second, existing "AI" financial assistants often produce fluent text whose numbers cannot be traced. For a decision about real money, a single invented rupee figure is unacceptable. We wanted a system in which every figure on screen comes from a deterministic computation and every assumption is disclosed.

Third, the Indian context matters. Taxes (short- and long-term capital gains under the FY 2025-26 regime), the importance of gold and fixed deposits in household portfolios, EMIs and education fees as fixed obligations, and the need for explanations in Hindi are rarely handled by tools designed elsewhere.

## 1.6 Objectives

The objectives of the project, as reflected in the repository, are:

1. **O1 – Behavioural reading.** Build an action-aware, portfolio-aware classifier that distinguishes loss aversion, herd behaviour, the disposition effect and rational decisions, with calibrated confidence and per-decision explanations.
2. **O2 – Consequence projection.** Build a simulator that compares HOLD and SELL over the investor's horizon (1–30 years) on shared market paths, after Indian tax and transaction costs.
3. **O3 – Cause and effect.** Quantify what pushes each action and estimate the benefit of simple debiasing habits, validated against a known ground truth.
4. **O4 – Explanation.** Produce structurally complete, jargon-free explanations in English and Hindi from templates, with an optional language-model rewording that is rejected if it changes any number.
5. **O5 – Recommendation.** Derive HOLD, SELL or BUY MORE from written rules over the simulation and the behavioural reading, never from a language model.
6. **O6 – Trust and security.** Deliver the above through a secure web application with strong authentication, per-user data isolation, a verifiable audit chain, and data export and deletion.

## 1.7 Scope of the Project

**In scope.** Listed Indian shares (NSE/BSE) and equity mutual funds as the subject of a decision; gold, fixed deposits, savings, property, loans, rent received and SIPs as context; three actions (sell, hold, buy more); four behavioural classes; horizons of 1–30 years; English and Hindi output; a web interface usable on desktops and phones.

**Out of scope.** Execution of trades or any broker integration; real-time trading signals; whole-portfolio optimisation (each analysis concerns one position); derivatives, cryptocurrency, credit-card balances and insurance; inflation-adjusted (real) projections; and any claim of personalised investment advice. The application states clearly that it is for information and education.

## 1.8 Intended Users and Stakeholders

| Stakeholder | Interest in the system |
|---|---|
| Retail investor (primary user) | A second opinion on a pending decision, grounded in their own finances, in a language they are comfortable with |
| Administrator | Resetting a user's two-step verification after a verified recovery request |
| Financial educators and researchers | A transparent example of how behavioural patterns, simulation and causal estimates can be combined |
| Project guide and examiners | Evidence that the system is correct, secure and honestly evaluated |

Table: Table 1.1: Stakeholders of the Folium system

## 1.9 Expected Contributions

The project does not claim to invent a new classifier, causal estimator or resampling method. Its contribution is the integration of established methods into one decision-time pipeline governed by explicit numerical safeguards:

- an action-aware classifier whose inputs include which patterns the label definitions permit, guarded so that it can never output a pattern the definitions rule out, with confidence calibrated to real market-regime frequencies;
- a paired hold-versus-sell simulator that uses common random numbers, real NIFTY and gold history, measured stock beta and idiosyncratic risk, and Indian tax rules;
- a causal module validated against an exactly reproducible data generator, including a negative control;
- an explanation layer where templates are authoritative and any AI wording is subject to a number-preservation guard;
- a per-investor hash-chained audit log with verification that detects alteration, deletion, forgery and forks.

## 1.10 Organisation of the Report

Chapter 2 reviews the literature and existing systems. Chapter 3 states the requirements and feasibility. Chapter 4 describes the methodology, including the dataset. Chapter 5 presents the architecture and design diagrams. Chapter 6 explains the implementation module by module with code excerpts. Chapter 7 develops the algorithms and their mathematics. Chapter 8 documents the experimental setup and evaluation, and Chapter 9 presents and discusses the results. Chapter 10 covers testing, Chapter 11 applications and limitations, and Chapter 12 concludes with future scope. References and appendices follow.
