### 6.11. Revision 2 extension: causality-aware resilience debt (C1)

**What was implemented.** One component of the planned Revision 2 algorithm was built and evaluated: a causality-aware debt ledger (C1) that replaces B8's CUSUM debt. The ledger keeps one liability item per link-failure episode, weights it by the link's first-order share of algebraic connectivity, charges consensus error only to open damage, treats episodes shorter than d + 2 = 4 epochs (setup delay d = 2) as temporary, up-weights failures that begin next to an earlier failure, settles an item when its link is removed by a rewiring or repaired, and keeps a decaying scar after persistent damage. There is no blanket debt reset after a mutation. C1 is B8 with only the debt replaced; the adaptive threshold, counterfactual feedback, predictive selector, cooldown, cap and edge budget are B8's. A retry rule skips re-evaluation after a failed attempt while the decision-relevant state is unchanged. **What was not implemented:** calibrated uncertainty-aware failure prediction, delayed mutation-credit assignment (specified only), the rewire/defer/reserve decision (opportunity-cost optimisation), the long-horizon marginal-gain selector, the formal theoretical results (connectivity, consensus error, budget feasibility, debt stability, optimisation, complexity), Erdős–Rényi, Barabási–Albert and Watts–Strogatz graphs, larger graphs, cascading/correlated/node/unpredictable failure laws, sensitivity analysis and scalability measurements. The ledger's design constants were fixed in advance and not tuned; C1 is a proposal evaluated here, not an established method.

**Protocol.** C1, B8 and A1 were calibrated by the same count-matching rule (Section 5; docs/R2_DESIGN_RULES.md); A7M, A7 and Static are as before. Comparisons were fixed before the held-out runs: the primary family is C1 against B8, A7, A7M and A1 (Holm within the family), with B8 against A1, A7 and A7M as a reference family, margin 0.02. The original evaluation (calibration seeds 8300–8319, held-out seeds 9100–9159) calibrated on the mean count under a cap of 12. Its result is reported in full below because it exposed a flaw in the calibration rule, and it is not replaced. Amendment 1 (written and committed before any amended run; docs/R2_AMENDMENT_1.md) calibrates on the realised count under the actual per-run cap M with fresh seeds (calibration 8400–8419, held-out 9200–9259).

**Original evaluation (seeds 9100–9159).**

**Table 10** Mean consensus error E per arm and condition, with mean realised mutations per run in parentheses (original evaluation, 60 seeds). A1 is excluded in S3, M = 3 (infeasible at calibration).

| Condition | A1 | A7 | A7M | B8 | C1 |
|---|---|---|---|---|---|
| S1, M = 3 | 0.449 (2.10) | 0.387 (2.22) | 0.362 (3.00) | 0.426 (2.27) | 0.441 (1.33) |
| S1, M = 6 | 0.430 (4.50) | 0.335 (4.85) | 0.319 (6.00) | 0.386 (4.73) | 0.413 (3.58) |
| S2, M = 3 | 0.375 (2.30) | 0.356 (2.15) | 0.324 (3.00) | 0.378 (2.15) | 0.411 (1.22) |
| S2, M = 6 | 0.301 (5.27) | 0.296 (4.98) | 0.273 (6.00) | 0.289 (5.13) | 0.380 (3.18) |
| S3, M = 3 | excluded | 0.522 (2.20) | 0.514 (3.00) | 0.534 (2.45) | 0.547 (0.97) |
| S3, M = 6 | 0.536 (4.75) | 0.501 (4.87) | 0.492 (6.00) | 0.517 (4.97) | 0.530 (3.75) |

![Fig. 11. Original evaluation (seeds 9100–9159): mean consensus error per arm with 95% t-intervals; dashed line: Static.](figures_v0.8/fig_r2_E_original.png)

**Table 11** Paired differences in E (first − second; negative: first arm lower error), 95% bootstrap CI; one asterisk marks Holm p < 0.05 within the primary family, two asterisks also |ΔE| ≥ 0.02 (original evaluation).

| Condition | C1 − B8 | C1 − A7 | C1 − A7M | C1 − A1 |
|---|---|---|---|---|
| S1, M = 3 | +0.015 [+0.004, +0.026]* | +0.054 [+0.037, +0.072]** | +0.079 [+0.064, +0.093]** | -0.008 [-0.018, +0.001] |
| S1, M = 6 | +0.027 [+0.012, +0.041]** | +0.078 [+0.058, +0.097]** | +0.094 [+0.075, +0.112]** | -0.017 [-0.032, -0.003] |
| S2, M = 3 | +0.033 [+0.020, +0.046]** | +0.055 [+0.037, +0.074]** | +0.087 [+0.071, +0.103]** | +0.035 [+0.021, +0.049]** |
| S2, M = 6 | +0.091 [+0.072, +0.109]** | +0.084 [+0.062, +0.106]** | +0.107 [+0.086, +0.127]** | +0.079 [+0.059, +0.099]** |
| S3, M = 3 | +0.013 [+0.009, +0.016]* | +0.025 [+0.019, +0.031]** | +0.033 [+0.027, +0.039]** | excluded |
| S3, M = 6 | +0.014 [+0.010, +0.018]* | +0.030 [+0.022, +0.037]** | +0.038 [+0.031, +0.046]** | -0.005 [-0.010, -0.000] |

Fig. 11 shows the mean errors of Table 10 and Table 11 the paired differences. C1 − B8: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), B8 had lower error in 6 (3 beyond the margin), 0 were practically equivalent and 0 inconclusive. C1 − A7: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), A7 had lower error in 6 (6 beyond the margin), 0 were practically equivalent and 0 inconclusive. C1 − A7M: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), A7M had lower error in 6 (6 beyond the margin), 0 were practically equivalent and 0 inconclusive. C1 − A1: 5 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), A1 had lower error in 2 (2 beyond the margin), 2 were practically equivalent and 1 inconclusive.

**Realised budgets differed.** Mean realised mutations per condition ranged over 2.15 to 5.13 (B8) and 0.97 to 3.75 (C1) against the targets M = 3 and 6; the share of runs with no mutation was 0.031 for B8 and 0.283 for C1. The cause is the calibration rule: it matched the mean count of runs capped at 12, which is a sound match for arms with a narrow count distribution (A1, B8) but not for C1, whose counts were bimodal (many runs with no mutation, others reaching the cap), so the actual cap M reduced C1's mean far below M (on the calibration seeds, 1.55 against 3 in every M = 3 condition). Differences between C1 and B8, A7M or A7 in this evaluation are therefore confounded with unequal reconfiguration budgets.

**Amended, budget-matched evaluation (Amendment 1; held-out seeds 9200–9259).** Thresholds were chosen on the realised mean count under the actual cap M (Table F2). Because a capped mean cannot exceed M, the rule selects thresholds at which most runs reach the cap, for all arms; the comparison is then mainly about when and which links are rewired at near-equal budgets.

**Table 12** As Table 10, amended evaluation (60 seeds; mean realised mutations in parentheses).

| Condition | A1 | A7 | A7M | B8 | C1 |
|---|---|---|---|---|---|
| S1, M = 3 | 0.416 (2.98) | 0.369 (3.00) | 0.369 (3.00) | 0.404 (2.95) | 0.380 (3.00) |
| S1, M = 6 | 0.365 (5.95) | 0.326 (5.97) | 0.325 (6.00) | 0.350 (5.88) | 0.338 (6.00) |
| S2, M = 3 | 0.313 (3.00) | 0.316 (2.97) | 0.315 (3.00) | 0.319 (2.97) | 0.351 (2.90) |
| S2, M = 6 | 0.263 (5.97) | 0.261 (5.73) | 0.257 (6.00) | excluded | 0.303 (5.62) |
| S3, M = 3 | 0.542 (3.00) | 0.519 (3.00) | 0.519 (3.00) | 0.522 (2.97) | 0.527 (2.93) |
| S3, M = 6 | 0.528 (5.95) | 0.504 (5.73) | 0.502 (6.00) | 0.509 (5.60) | 0.509 (5.67) |

![Fig. 12. Amended evaluation (seeds 9200–9259): mean consensus error per arm with 95% t-intervals; dashed line: Static.](figures_v0.8/fig_r2_E_amended.png)

**Table 13** As Table 11, amended evaluation.

| Condition | C1 − B8 | C1 − A7 | C1 − A7M | C1 − A1 |
|---|---|---|---|---|
| S1, M = 3 | -0.023 [-0.033, -0.014]** | +0.011 [+0.001, +0.022] | +0.011 [+0.001, +0.022] | -0.036 [-0.047, -0.025]** |
| S1, M = 6 | -0.011 [-0.020, -0.003] | +0.013 [-0.002, +0.027] | +0.013 [-0.002, +0.028] | -0.027 [-0.040, -0.015]** |
| S2, M = 3 | +0.032 [+0.019, +0.045]** | +0.035 [+0.021, +0.048]** | +0.036 [+0.023, +0.049]** | +0.038 [+0.024, +0.051]** |
| S2, M = 6 | excluded | +0.043 [+0.026, +0.059]** | +0.046 [+0.029, +0.063]** | +0.041 [+0.024, +0.057]** |
| S3, M = 3 | +0.005 [+0.002, +0.008]* | +0.008 [+0.003, +0.013]* | +0.008 [+0.003, +0.013]* | -0.015 [-0.019, -0.010]* |
| S3, M = 6 | -0.000 [-0.003, +0.003] | +0.005 [-0.003, +0.012] | +0.007 [-0.000, +0.014] | -0.019 [-0.024, -0.014]* |

Fig. 12 shows the mean errors of Table 12 and Table 13 the paired differences. C1 − B8: 5 evaluable conditions; C1 had lower error with Holm p < 0.05 in 1 (1 beyond the 0.02 margin), B8 had lower error in 2 (1 beyond the margin), 1 were practically equivalent and 1 inconclusive. C1 − A7: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), A7 had lower error in 3 (2 beyond the margin), 1 were practically equivalent and 2 inconclusive. C1 − A7M: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 0 (0 beyond the 0.02 margin), A7M had lower error in 3 (2 beyond the margin), 1 were practically equivalent and 2 inconclusive. C1 − A1: 6 evaluable conditions; C1 had lower error with Holm p < 0.05 in 4 (2 beyond the 0.02 margin), A1 had lower error in 2 (2 beyond the margin), 0 were practically equivalent and 0 inconclusive. The reference comparisons of B8 are in the repository tables (`revision/analysis/R2/amended/reference_tests.csv`).

Mean realised mutations ranged over 2.95 to 5.88 (B8) and 2.90 to 6.00 (C1); the share of runs with no mutation was 0.000 (B8) and 0.003 (C1).

**Table 14** Connectivity, recovery and reconfiguration overhead, amended evaluation (means over 60 seeds; overhead = pending link-epochs + live-link releases).

| Condition | Arm | Disconnected share | Longest disconnection | Anchored recovery | Worst-case E | Overhead |
|---|---|---|---|---|---|---|
| S1, M = 3 | A7M | 0.283 | 10.6 | 4.8 | 0.781 | 8.4 |
| S1, M = 3 | B8 | 0.292 | 9.9 | 4.7 | 0.791 | 6.4 |
| S1, M = 3 | C1 | 0.280 | 9.4 | 4.7 | 0.787 | 7.3 |
| S1, M = 6 | A7M | 0.271 | 10.0 | 4.5 | 0.773 | 16.5 |
| S1, M = 6 | B8 | 0.242 | 7.8 | 3.7 | 0.784 | 13.6 |
| S1, M = 6 | C1 | 0.253 | 8.1 | 3.9 | 0.783 | 14.8 |
| S2, M = 3 | A7M | 0.153 | 8.6 | 4.6 | 0.681 | 8.6 |
| S2, M = 3 | B8 | 0.117 | 6.5 | 3.0 | 0.684 | 7.9 |
| S2, M = 3 | C1 | 0.149 | 8.5 | 4.4 | 0.712 | 7.6 |
| S2, M = 6 | A7M | 0.128 | 7.2 | 3.5 | 0.648 | 17.3 |
| S2, M = 6 | C1 | 0.111 | 6.0 | 3.1 | 0.698 | 15.3 |
| S3, M = 3 | A7M | 0.415 | 14.3 | 6.6 | 0.781 | 8.2 |
| S3, M = 3 | B8 | 0.372 | 10.6 | 5.2 | 0.780 | 6.7 |
| S3, M = 3 | C1 | 0.378 | 10.6 | 5.3 | 0.782 | 6.7 |
| S3, M = 6 | A7M | 0.394 | 12.8 | 5.8 | 0.776 | 15.9 |
| S3, M = 6 | B8 | 0.346 | 8.8 | 4.7 | 0.778 | 12.7 |
| S3, M = 6 | C1 | 0.350 | 9.4 | 4.8 | 0.778 | 13.2 |

**Table 15** Performance per realised mutation, amended evaluation: mean improvement in E over Static (same scenario and seed) divided by mean realised mutations (exploratory; higher is better).

| Condition | A1 | A7 | A7M | B8 | C1 |
|---|---|---|---|---|---|
| S1, M = 3 | 0.0180 | 0.0337 | 0.0337 | 0.0225 | 0.0299 |
| S1, M = 6 | 0.0176 | 0.0242 | 0.0242 | 0.0204 | 0.0219 |
| S2, M = 3 | 0.0417 | 0.0411 | 0.0410 | 0.0402 | 0.0301 |
| S2, M = 6 | 0.0294 | 0.0309 | 0.0301 | excluded | 0.0240 |
| S3, M = 3 | 0.0038 | 0.0113 | 0.0113 | 0.0105 | 0.0089 |
| S3, M = 6 | 0.0043 | 0.0086 | 0.0085 | 0.0079 | 0.0079 |


**Interpretation.** These results are reported as estimates; none supports a claim that the causality-aware ledger improves consensus resilience. Where C1's error is not lower than B8's or the front-loaded baselines', the ledger did not help under this design and these constants; because the constants were fixed rather than tuned and only one scenario family was tested, this does not show that a better causality-aware design could not help. The original evaluation is a pre-registered result with an identified calibration flaw; the amended evaluation corrects that flaw on fresh seeds and is the budget-matched comparison. Both are kept.
