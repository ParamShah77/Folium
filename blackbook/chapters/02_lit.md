# Chapter 2: Literature Review and Existing Systems

This chapter reviews the theory and prior work on which Folium is built. For each strand we state what the work establishes, what it does not, and how it is used in the project. The review follows the one carried out for our research paper on Folium, extended with the engineering sources relevant to the implementation.

## 2.1 Behavioural Foundations

### 2.1.1 Prospect theory and reference dependence

Kahneman and Tversky's prospect theory explains departures from expected-utility predictions under risk [1]. Its central features are reference-dependent valuation (outcomes are judged as gains or losses relative to a reference point such as the purchase price), loss aversion (losses loom larger than equal gains) and non-linear weighting of probabilities. Cumulative prospect theory later extended the framework to rank-dependent probability weighting [17]. Prospect theory is descriptive: it explains why a person may behave as if a paper loss matters, but it gives no procedure for classifying a particular live decision. In Folium it justifies treating the unrealised gain or loss and the market's fear level as candidate signals, without treating every loss-making sale as irrational.

### 2.1.2 The disposition effect

Shefrin and Statman linked the tendency to sell winners and hold losers to mental accounting, regret aversion and self-control [4]. Odean confirmed the effect empirically in the trading records of a discount brokerage, showing that investors realised gains at a higher rate than losses [2]. Thaler's work on mental accounting supports the idea that people place gains and losses in separate mental "accounts" [18]. A single decision observed at one moment can only suggest the disposition effect; it cannot prove it. Folium therefore uses the gain or loss and the market regime as features and reports the reading as a tendency to watch for, not a diagnosis.

### 2.1.3 Herding and informational cascades

Bikhchandani, Hirshleifer and Welch showed that sequential decision-makers can rationally ignore their own information and follow others, producing fragile cascades [3]. De Long et al. showed that noise traders can move prices even in the presence of rational arbitrageurs [19]. Together these imply that following the crowd is not automatically irrational and that crowd signals carry information. Folium uses market fear (India VIX) and strong monthly index moves as proxies for crowd pressure, and the comment reader looks for explicit mentions of friends, colleagues or messaging groups; neither is treated as conclusive evidence of herding.

### 2.1.4 Empirical investor behaviour

Barber and Odean found that individual investors who trade more earn lower net returns [14], and that overconfidence shows up in trading intensity [15]. Grinblatt and Keloharju showed that investor traits, past returns and the trading context jointly affect trading decisions [16]. These studies caution against drawing individual conclusions from group-level patterns and suggest that a single questionnaire and one market snapshot cannot capture everything. Folium accordingly avoids demographic shortcuts: years of investing, for instance, was deliberately excluded as an input because the app does not collect it.

### 2.1.5 Market efficiency as a counterweight

Fama's review of efficient markets [20] reminds us that trading in response to new information can be entirely rational. This is why Folium always includes a rational class with several legitimate motives and why the classifier's "allows" logic ensures that a bias is only considered when the situation makes it possible.

## 2.2 Machine Learning for Tabular Financial Classification

### 2.2.1 Gradient boosting and XGBoost

Friedman formulated gradient boosting as stage-wise functional optimisation [26]. Chen and Guestrin's XGBoost added second-order optimisation, regularisation, sparsity-aware split finding and efficient histogram-based training [5]. Gradient-boosted trees are widely regarded as a strong default for medium-sized tabular data because they capture non-linear interactions—such as the joint effect of a loss, a falling market and high fear—without a hand-specified functional form. Breiman's random forests [25] are the natural alternative tree ensemble. Folium uses XGBoost for its multi-class classifier and compares it with logistic regression and a 500-tree random forest on identical splits (Section 8.6). The comparison finds the two tree ensembles statistically tied, which is consistent with this literature: on tabular data of this size, the choice between well-tuned tree ensembles matters less than the features and the labels.

### 2.2.2 Probability calibration

A classifier can be accurate yet badly calibrated: its stated probabilities may not match how often it is right. Zadrozny and Elkan showed how to transform classifier scores into calibrated multi-class probabilities, including through isotonic regression [6]. Niculescu-Mizil and Caruana compared calibration across learners and showed that boosted trees in particular tend to push probabilities away from 0 and 1 [27]. Guo et al. demonstrated that high accuracy does not imply good calibration, introducing expected calibration error (ECE) as a standard summary [28]. Folium calibrates the top-class probability with an isotonic curve fitted on out-of-fold predictions and reports ECE and reliability bins.

### 2.2.3 Evaluation under imbalance and time

Saito and Rehmsmeier showed that precision–recall analysis is more informative than ROC analysis under class imbalance [29]; Folium reports per-class precision, recall and F1 and uses macro-F1 because loss aversion is the smallest class (10%). López de Prado warns that random splits of financial data overstate generalisation because of temporal dependence and leakage [24]. Folium therefore adds an out-of-time evaluation: trained only on 2008–2019 decisions and tested on 2020–2026.

## 2.3 Explainable Machine Learning

### 2.3.1 SHAP feature attribution

Lundberg and Lee unified several attribution methods under Shapley values from cooperative game theory [7], and later gave an exact polynomial-time algorithm for tree ensembles, TreeSHAP [35]. SHAP values are additive: the contributions of all features plus a base value equal the model's raw output. Folium uses XGBoost's built-in exact TreeSHAP and groups the 22 feature contributions into 18 plain-language "drivers". An important limitation is that SHAP explains the prediction function, not the causal mechanism: a large SHAP value means a feature moved the score, not that changing it in the real world would change behaviour [31].

### 2.3.2 Local surrogates and counterfactual explanations

LIME fits a simple surrogate model around an instance [8]; its explanations depend on how perturbations are sampled. Counterfactual explanations describe the smallest change to the input that would change the prediction [9], and DiCE generates diverse counterfactuals [30]. These ideas are related to Folium's hold-versus-sell comparison but are not the same thing: Folium's comparison is a scenario simulation of two actions on shared market paths, not a perturbation of classifier inputs.

### 2.3.3 Explainable AI in finance

Weber, Carl and Hinz's systematic review of explainable AI in finance stresses that explanation methods must be evaluated in their financial context [34]. Folium contributes a specific design rule for this context: explanations are rendered from templates fed by computed facts, so wording cannot introduce numbers.

## 2.4 Causal Modelling

Pearl's structural causal models formalise interventions with the $\mathrm{do}(\cdot)$ operator and graphical criteria for identifying effects from observational data [10]. Robins introduced g-computation (the parametric g-formula) [36], and Hernán and Robins give a modern treatment of identification assumptions—consistency, positivity and conditional exchangeability [37]. Sharma and Kiciman's DoWhy library organises causal analysis into four steps: model the graph, identify the estimand, estimate, and refute [11]. Chernozhukov et al.'s double machine learning offers another route with flexible nuisance models [32].

A recurring caution in this literature is that refutation tests passing does not rule out unobserved confounding. Folium's causal work uses a synthetic dataset whose generator is known exactly, which allows the estimates to be checked against the true effects—an option real-world studies do not have. The results are therefore validation of the method on a known mechanism, not evidence about how Indian investors behave.

## 2.5 Long-Horizon Simulation and Resampling

Simulating future wealth requires plausible market paths. Drawing independent monthly returns destroys volatility clustering and the link between crashes and recoveries. Künsch's block bootstrap resamples contiguous blocks of a dependent series [12]; Politis and Romano's stationary bootstrap uses random block lengths and a circular wrap [33]. Efron and Tibshirani's bootstrap framework motivates reporting quantiles rather than a single forecast [13]. Hamilton's regime-switching model [23] reminds us that the past may not contain future regimes. Markowitz's portfolio selection [21] and Merton's lifetime portfolio choice [22] establish that a decision should be judged at the level of the whole portfolio and over the investor's horizon.

Folium uses a circular 12-month block bootstrap over 2007–2026 NIFTY 50 and gold-in-rupee history, recentres the average growth to stated long-run rates, and reports the 10th, 50th and 90th percentiles of both paths.

## 2.6 Security Foundations for a Financial Web Application

Several standards underpin the application layer. JSON Web Tokens are defined in RFC 7519 [38]; Folium signs them with RS256. Time-based one-time passwords for two-step verification follow RFC 6238 [39]. Passwords are hashed with bcrypt [40] and their strength is checked with zxcvbn [41]. Cross-site request forgery is mitigated with the double-submit cookie pattern described by OWASP [42]. Per-user data isolation uses PostgreSQL row-level security policies [43]. The tamper-evident audit log follows the hash-chaining idea of Haber and Stornetta [44] using SHA-256 as specified in FIPS 180-4 [45]. Live progress is delivered with server-sent events as defined in the HTML standard [46].

## 2.7 Comparison of Existing Approaches

| Approach | Looks at the decision? | Uses investor's finances? | Explains numbers? | Weakness relevant to this problem |
|---|---|---|---|---|
| Brokerage / portfolio trackers | No | Holdings only | Charts only | Describe the asset, not whether the action is sensible |
| Robo-advisers | At onboarding | Risk questionnaire | Allocation rationale | Do not evaluate an individual pending trade |
| Behavioural questionnaires | No | Self-reported | Score only | Measure a trait, not the present situation |
| Generic LLM chat assistants | Yes | Only if typed in | Fluent text | Numbers may be invented; no calibration or audit |
| Academic bias studies [2], [14] | Retrospectively | Account data | In papers | Population-level; not a decision-time tool |
| **Folium (this work)** | **Yes, at decision time** | **Income, outflows, fund, portfolio, horizon** | **Every figure traced to computation** | **Synthetic behavioural labels (Section 11.3)** |

Table: Table 2.1: Comparison of existing approaches with Folium

## 2.8 Research and Implementation Gaps

From the review, five gaps emerge that the project tries to address in a measurable way:

1. **Context-blind bias labelling.** Studies and tools tend to treat a loss-making sale or a winner sold early as a bias. A decision-time tool must recognise forced sales, rebalancing and near goals as rational.
2. **Uncalibrated confidence.** Classifiers presented to end users rarely report whether "90%" means right nine times in ten.
3. **Prediction confused with causation.** Feature attributions are often presented as reasons that, if changed, would change outcomes. Causal claims need a graph, an estimand and validation.
4. **Unpaired, untaxed simulations.** Simple "what if" calculators compare actions on different random scenarios or ignore tax, inflating noise and overstating the case for holding.
5. **Untraceable explanations.** Generated text may misstate figures. A guard that rejects any wording containing a number not in the source facts is rarely implemented.

## 2.9 How the Proposed System Addresses the Gaps

Folium's response is to keep each question separate and answer it with the appropriate tool: the classifier reads the pattern (gap 1 and 2: action-aware features, a definitional guard, cash-need input and isotonic calibration), the causal module answers "what pushes this action" against a known truth (gap 3), the simulator compares both actions on the same after-tax paths (gap 4), and the explanation engine turns verified facts into words under a numeric guard (gap 5). The recommendation is a small, readable rule set over these outputs, and the audit chain lets the investor confirm later that nothing was changed.
