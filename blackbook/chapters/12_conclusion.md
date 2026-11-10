# Chapter 12: Conclusion and Future Scope

## 12.1 Summary of the Problem

Retail investors often decide to sell, hold or buy more under the pull of recent losses, market fear or the crowd, and the tools available to them describe the asset rather than the decision. A useful decision-support system must tell a biased decision from a sensible one using the investor's own finances, show the financial consequences of each choice honestly, explain itself without inventing numbers, and be trustworthy with sensitive data.

## 12.2 Summary of the Implemented Solution

We built Folium, a full-stack web application with a React front end, a FastAPI back end, PostgreSQL with row-level security and Redis. For each decision, a five-step background pipeline reads the investor's comment, classifies the behavioural pattern with a calibrated, guarded XGBoost model explained by exact TreeSHAP, projects HOLD and SELL on the same block-bootstrapped market paths after Indian tax, attaches causal estimates validated against a known generator, renders a six-part explanation in English and Hindi, derives a verdict from explicit evidence rules, and seals the analysis into a per-investor hash chain. Investors sign in by e-mail or with Google; accounts are protected with two-step verification, CSRF protection and rate limits, and investors can export or delete their data.

## 12.3 Key Outcomes and Verified Findings

All figures below are taken from the evaluation files committed in the repository and are development-stage results on synthetic behavioural labels.

| Objective | Outcome | Achieved? |
|---|---|---|
| O1 Behavioural reading | 87.9% accuracy, macro-F1 0.840, ECE 0.014; High band right 98.7%; 21/21 sense checks; out-of-time 86.5%; significantly above rules and logistic regression, tied with random forest | Achieved on synthetic labels; real-world validity is the next research step |
| O2 Consequence projection | One-year quantiles within 1.4 points of the real NIFTY; best of six generators (KS 0.027); stable to ±1.7 points at 1,000 paths; horizon-specific, after-tax, paired | Achieved |
| O3 Cause and effect | 45 effects, mean absolute error 0.48 points, 97% correct sign; 12/13 refutations | Achieved on a known generator |
| O4 Explanation | 332 explanations on the current models: 100% completeness, 0 jargon leaks, Flesch 76.4 (EN), 12.8 words/sentence (HI) | Achieved |
| O5 Recommendation | Pure rule function with stored reasons and inputs; never an LLM | Achieved |
| O6 Trust and security | RLS, hash chain with verification, MFA, CSRF, rate limits, Google sign-in (OpenID Connect), export and deletion | Achieved; public deployment with HTTPS is the next milestone |

Table: Table 12.1: Achievement of objectives

## 12.4 Boundaries of the Present Work

Two boundaries define what the results can claim. The first is scientific: the behavioural labels are synthetic by design, because no public dataset links Indian investors' decisions to their finances and true motives. The readings are therefore validated against a known generator, not against real people, and no claim is made that the system improves investment outcomes. The second is about modelling: the simulator's verdicts depend on stated long-run growth rates (Table 9.6), projections are in nominal rupees, tax handling is simplified, and each analysis concerns one position. Both boundaries are stated to the investor on every result page, and both are addressed directly in the roadmap below.

## 12.5 Roadmap and Future Scope

The project already follows a milestone plan (`FOLIUM_MASTER.md` §14). Phase C, the productisation phase, began with Google sign-in (C1), which is complete. The remaining work is organised in three phases, each building on foundations that already exist in the repository.

| Phase | Milestone | What it delivers | Foundation already in place |
|---|---|---|---|
| **C — Productisation** | C2 Administrator console | Usage statistics, user management, MFA-recovery queue | `admin_stats_view` (aggregates, no personal data); audited MFA-status and MFA-reset endpoints; `role` column and admin guard |
| | C3 Continuous integration | Every push runs the back-end, model and front-end suites and the production build | 635 tests runnable with one command each; pinned dependencies; `verify_ml_env.py` |
| | C4 Public deployment | HTTPS, production e-mail, registered Google callback | `Dockerfile.backend`, `docker-compose.yml`; `Secure` cookies and CORS switch on outside development; Resend e-mail integration |
| | Live AI assistance | Gemini comment reading and wording for consenting users | Implementation, consent switch, verbatim-quote and number guards, circuit breaker—all tested with a stand-in |
| **D — Validation with real users** | Consented decision data | Anonymised real decisions and investors' own later reflections, so motive weights can be learned rather than set | Data export, consent model and audit chain; `outcome_tracked`, `actual_outcome_pct` and `recommendation_followed` columns already in `decisions` |
| | Prospective user study | Whether investors who use Folium decide differently | Explanation engine with measured readability; seeded demo flow |
| | Two-way number guard | AI wording must keep every original number, not only avoid new ones (D-5) | `guard_ok` and its test suite |
| **E — Richer analysis** | Simulation extensions | Inflation-adjusted outputs, debt and hybrid funds, loss set-off and tax-harvesting, other destinations for sale proceeds, regime-aware scenarios | Evaluation hooks `paths=` and `return_gaps=`; sensitivity framework |
| | Whole-portfolio decisions | Rebalancing across several holdings | Portfolio snapshot and asset-mix computation |
| | Wider language support | Learned comment patterns and more Indian languages | Bilingual template banks with structural-parity tests |
| | Scale | Background analyses on a job queue with dedicated workers; load testing | Stateless API; Redis already holds shared state |

Table: Table 12.2: Roadmap by phase

Phase C turns a complete local product into a publicly available service, Phase D turns development-stage evidence into evidence about people, and Phase E widens what the system can analyse. Longer-term ideas from the original plan—broker integration, WhatsApp alerts and monthly retraining from tracked outcomes—follow naturally once Phase D produces real outcome data.

## 12.6 Potential for Further Research and Deployment

The project shows that established methods—calibrated gradient boosting, TreeSHAP, block bootstrapping, backdoor adjustment and hash chaining—can be combined into a single decision-time process with explicit numerical safeguards. The known-truth evaluation approach used for the causal module is itself reusable for testing causal methods. With consented real data and a user study, Folium could become an evidence-based tool for investor education. Until then, it should be presented exactly as it presents itself: information and education, not investment advice.

# References

[1] D. Kahneman and A. Tversky, "Prospect theory: An analysis of decision under risk," *Econometrica*, vol. 47, no. 2, pp. 263–291, 1979, doi: 10.2307/1914185.

[2] T. Odean, "Are investors reluctant to realize their losses?" *The Journal of Finance*, vol. 53, no. 5, pp. 1775–1798, 1998, doi: 10.1111/0022-1082.00072.

[3] S. Bikhchandani, D. Hirshleifer, and I. Welch, "A theory of fads, fashion, custom, and cultural change as informational cascades," *Journal of Political Economy*, vol. 100, no. 5, pp. 992–1026, 1992, doi: 10.1086/261849.

[4] H. Shefrin and M. Statman, "The disposition to sell winners too early and ride losers too long: Theory and evidence," *The Journal of Finance*, vol. 40, no. 3, pp. 777–790, 1985, doi: 10.1111/j.1540-6261.1985.tb05002.x.

[5] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in *Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2016, pp. 785–794, doi: 10.1145/2939672.2939785.

[6] B. Zadrozny and C. Elkan, "Transforming classifier scores into accurate multiclass probability estimates," in *Proc. 8th ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2002, pp. 694–699, doi: 10.1145/775047.775151.

[7] S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in *Advances in Neural Information Processing Systems*, vol. 30, 2017, pp. 4765–4774.

[8] M. T. Ribeiro, S. Singh, and C. Guestrin, "'Why should I trust you?': Explaining the predictions of any classifier," in *Proc. 22nd ACM SIGKDD*, 2016, pp. 1135–1144, doi: 10.1145/2939672.2939778.

[9] S. Wachter, B. Mittelstadt, and C. Russell, "Counterfactual explanations without opening the black box: Automated decisions and the GDPR," *Harvard Journal of Law & Technology*, vol. 31, no. 2, pp. 841–887, 2018.

[10] J. Pearl, *Causality: Models, Reasoning, and Inference*, 2nd ed. Cambridge, U.K.: Cambridge University Press, 2009.

[11] A. Sharma and E. Kiciman, "DoWhy: An end-to-end library for causal inference," arXiv:2011.04216, 2020.

[12] H. R. Künsch, "The jackknife and the bootstrap for general stationary observations," *The Annals of Statistics*, vol. 17, no. 3, pp. 1217–1241, 1989, doi: 10.1214/aos/1176347265.

[13] B. Efron and R. J. Tibshirani, *An Introduction to the Bootstrap*. New York, NY, USA: Chapman & Hall, 1993.

[14] B. M. Barber and T. Odean, "Trading is hazardous to your wealth: The common stock investment performance of individual investors," *The Journal of Finance*, vol. 55, no. 2, pp. 773–806, 2000, doi: 10.1111/0022-1082.00226.

[15] B. M. Barber and T. Odean, "Boys will be boys: Gender, overconfidence, and common stock investment," *The Quarterly Journal of Economics*, vol. 116, no. 1, pp. 261–292, 2001, doi: 10.1162/003355301556400.

[16] M. Grinblatt and M. Keloharju, "What makes investors trade?" *The Journal of Finance*, vol. 56, no. 2, pp. 589–616, 2001, doi: 10.1111/0022-1082.00338.

[17] A. Tversky and D. Kahneman, "Advances in prospect theory: Cumulative representation of uncertainty," *Journal of Risk and Uncertainty*, vol. 5, pp. 297–323, 1992, doi: 10.1007/BF00122574.

[18] R. Thaler, "Mental accounting and consumer choice," *Marketing Science*, vol. 4, no. 3, pp. 199–214, 1985, doi: 10.1287/mksc.4.3.199.

[19] J. B. De Long, A. Shleifer, L. H. Summers, and R. J. Waldmann, "Noise trader risk in financial markets," *Journal of Political Economy*, vol. 98, no. 4, pp. 703–738, 1990, doi: 10.1086/261703.

[20] E. F. Fama, "Efficient capital markets: A review of theory and empirical work," *The Journal of Finance*, vol. 25, no. 2, pp. 383–417, 1970, doi: 10.2307/2325486.

[21] H. Markowitz, "Portfolio selection," *The Journal of Finance*, vol. 7, no. 1, pp. 77–91, 1952, doi: 10.2307/2975974.

[22] R. C. Merton, "Lifetime portfolio selection under uncertainty: The continuous-time case," *The Review of Economics and Statistics*, vol. 51, no. 3, pp. 247–257, 1969, doi: 10.2307/1926560.

[23] J. D. Hamilton, "A new approach to the economic analysis of nonstationary time series and the business cycle," *Econometrica*, vol. 57, no. 2, pp. 357–384, 1989, doi: 10.2307/1912559.

[24] M. López de Prado, *Advances in Financial Machine Learning*. Hoboken, NJ, USA: Wiley, 2018.

[25] L. Breiman, "Random forests," *Machine Learning*, vol. 45, pp. 5–32, 2001, doi: 10.1023/A:1010933404324.

[26] J. H. Friedman, "Greedy function approximation: A gradient boosting machine," *The Annals of Statistics*, vol. 29, no. 5, pp. 1189–1232, 2001, doi: 10.1214/aos/1013203451.

[27] A. Niculescu-Mizil and R. Caruana, "Predicting good probabilities with supervised learning," in *Proc. 22nd Int. Conf. Machine Learning (ICML)*, 2005, pp. 625–632, doi: 10.1145/1102351.1102430.

[28] C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, "On calibration of modern neural networks," in *Proc. 34th Int. Conf. Machine Learning (ICML)*, PMLR 70, 2017, pp. 1321–1330.

[29] T. Saito and M. Rehmsmeier, "The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets," *PLOS ONE*, vol. 10, no. 3, e0118432, 2015, doi: 10.1371/journal.pone.0118432.

[30] R. K. Mothilal, A. Sharma, and C. Tan, "Explaining machine learning classifiers through diverse counterfactual explanations," in *Proc. Conf. Fairness, Accountability, and Transparency (FAT\*)*, 2020, pp. 607–617, doi: 10.1145/3351095.3372850.

[31] D. Janzing, L. Minorics, and P. Blöbaum, "Feature relevance quantification in explainable AI: A causal problem," in *Proc. 23rd Int. Conf. Artificial Intelligence and Statistics (AISTATS)*, PMLR 108, 2020, pp. 2907–2916.

[32] V. Chernozhukov, D. Chetverikov, M. Demirer, E. Duflo, C. Hansen, W. Newey, and J. Robins, "Double/debiased machine learning for treatment and structural parameters," *The Econometrics Journal*, vol. 21, no. 1, pp. C1–C68, 2018, doi: 10.1111/ectj.12097.

[33] D. N. Politis and J. P. Romano, "The stationary bootstrap," *Journal of the American Statistical Association*, vol. 89, no. 428, pp. 1303–1313, 1994, doi: 10.1080/01621459.1994.10476870.

[34] P. Weber, K. V. Carl, and O. Hinz, "Applications of explainable artificial intelligence in finance—a systematic review of finance, information systems, and computer science literature," *Management Review Quarterly*, vol. 74, pp. 867–907, 2024, doi: 10.1007/s11301-023-00320-0.

[35] S. M. Lundberg, G. Erion, H. Chen, A. DeGrave, J. M. Prutkin, B. Nair, R. Katz, J. Himmelfarb, N. Bansal, and S.-I. Lee, "From local explanations to global understanding with explainable AI for trees," *Nature Machine Intelligence*, vol. 2, pp. 56–67, 2020, doi: 10.1038/s42256-019-0138-9.

[36] J. Robins, "A new approach to causal inference in mortality studies with a sustained exposure period—application to control of the healthy worker survivor effect," *Mathematical Modelling*, vol. 7, no. 9–12, pp. 1393–1512, 1986, doi: 10.1016/0270-0255(86)90088-6.

[37] M. A. Hernán and J. M. Robins, *Causal Inference: What If*. Boca Raton, FL, USA: Chapman & Hall/CRC, 2020.

[38] M. Jones, J. Bradley, and N. Sakimura, "JSON Web Token (JWT)," IETF RFC 7519, May 2015, doi: 10.17487/RFC7519.

[39] D. M'Raihi, S. Machani, M. Pei, and J. Rydell, "TOTP: Time-Based One-Time Password Algorithm," IETF RFC 6238, May 2011, doi: 10.17487/RFC6238.

[40] N. Provos and D. Mazières, "A future-adaptable password scheme," in *Proc. USENIX Annual Technical Conference (FREENIX Track)*, 1999, pp. 81–91.

[41] D. L. Wheeler, "zxcvbn: Low-budget password strength estimation," in *Proc. 25th USENIX Security Symposium*, 2016, pp. 157–173.

[42] OWASP Foundation, "Cross-Site Request Forgery Prevention Cheat Sheet," OWASP Cheat Sheet Series. [Online]. Available: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

[43] The PostgreSQL Global Development Group, "Row Security Policies," *PostgreSQL Documentation*. [Online]. Available: https://www.postgresql.org/docs/current/ddl-rowsecurity.html

[44] S. Haber and W. S. Stornetta, "How to time-stamp a digital document," *Journal of Cryptology*, vol. 3, no. 2, pp. 99–111, 1991, doi: 10.1007/BF00196791.

[45] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, Aug. 2015, doi: 10.6028/NIST.FIPS.180-4.

[46] WHATWG, "Server-sent events," *HTML Living Standard*, ch. 9.2. [Online]. Available: https://html.spec.whatwg.org/multipage/server-sent-events.html

[47] A. P. Oron and N. Flournoy, "Centered isotonic regression: Point and interval estimation for dose–response studies," *Statistics in Biopharmaceutical Research*, vol. 9, no. 3, pp. 258–267, 2017, doi: 10.1080/19466315.2017.1286256.

[48] F. Pedregosa *et al.*, "Scikit-learn: Machine learning in Python," *Journal of Machine Learning Research*, vol. 12, pp. 2825–2830, 2011.

[49] R. Flesch, "A new readability yardstick," *Journal of Applied Psychology*, vol. 32, no. 3, pp. 221–233, 1948, doi: 10.1037/h0057532.

[50] S. Ramírez, "FastAPI," official documentation. [Online]. Available: https://fastapi.tiangolo.com

[51] Meta Open Source, "React," official documentation. [Online]. Available: https://react.dev

[52] R. Aroussi, "yfinance: Download market data from Yahoo! Finance's API," open-source library. [Online]. Available: https://github.com/ranaroussi/yfinance

[53] MFAPI.in, "Mutual Fund API for India." [Online]. Available: https://www.mfapi.in

[54] NSE Indices Ltd., "NIFTY 50 Index" and National Stock Exchange of India, "India VIX." [Online]. Available: https://www.niftyindices.com and https://www.nseindia.com

[55] Government of India, *The Finance (No. 2) Act, 2024* (Act No. 15 of 2024), provisions on capital-gains tax rates and the long-term capital-gains exemption.

[56] Government of India, *The Finance Act, 2025*, provisions on new-regime income-tax slabs and the Section 87A rebate.

[57] Pallets Projects, "Jinja," official documentation. [Online]. Available: https://jinja.palletsprojects.com
