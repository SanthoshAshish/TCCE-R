| Arm | Code policy | Attempt when | Candidate selection | Threshold | Feedback | Calibrated |
|---|---|---|---|---|---|---|
| A0 Static | static | never | - | - | - | no (reference) |
| A1 Reactive (B1) | v06_reactive | E_k > h | lexicographic first choice | fixed h | - | yes (h) |
| A5 TCCE-R (v0.7) | v06_tccer | D_k > Θ (E, C, V debt) | lexicographic first choice | adaptive Θ | counterfactual | yes (Θ₀) |
| A7 Front-loaded | v06_front | epochs 0, 2, 4, … until the intended count | lexicographic first choice | - | - | count PMF from calibrated arms |
| A7M Front-loaded, exact M | v06_front (no PMF) | epochs 0, 2, …, 2(M−1) | lexicographic first choice | - | - | no |
| B2 E + C | v08_b2 | (0.5E + 0.3C)/0.8 > h | lexicographic first choice | fixed h | - | yes (h) |
| B3 E + V | v08_b3 | (0.5E + 0.2V)/0.7 > h | lexicographic first choice | fixed h | - | yes (h) |
| B4 E + C + V | v08_b4 | 0.5E + 0.3C + 0.2V > h | lexicographic first choice | fixed h | - | yes (h) |
| B5 debt (= A4) | v06_cusum_ecv | D_k > Θ (E, C, V debt) | lexicographic first choice | fixed Θ = B8's Θ₀ | - | no (inherits B8) |
| B6 debt + predictive | v08_rcpr_fixed | D_k > Θ | predictive, risk-filtered (Sec. 4.5) | fixed Θ = B8's Θ₀ | - | no (inherits B8) |
| B7 B8, legacy feedback | v08_rcpr_legacy | D_k > Θ | predictive | adaptive Θ | legacy before/after | no (inherits B8) |
| B8 predictive controller | v08_rcpr | D_k > Θ | predictive | adaptive Θ | counterfactual | yes (Θ₀) |
| H1 Hybrid-FrontRisk | v08_hybrid | phase 1: A7-style, F = ceil(M/2); then as B8 | lexicographic (phase 1), predictive (phase 2) | adaptive Θ (phase 2) | counterfactual (phase 2) | no (inherits B8) |
