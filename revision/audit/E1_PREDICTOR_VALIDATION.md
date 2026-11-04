# E1: predictor validation (run 2026-11-04, development seeds 8100-8119 only)

Command: `python -m experiments.validate_predictor_v08` (script hash and git state in `results/v0.8/E1/run_info.json`; raw candidates in `results/v0.8/E1/candidates.csv`, git-ignored). 60 probe runs (3 scenarios x 20 seeds), 116 s on 11 workers. The held-out seeds 9000-9059 were not touched; no parameter was tuned. The criteria below were written in the script header before the first run (a 2-seed smoke run preceded the real run; its numbers were not used).

## What was measured
A passive probe (never mutates; topology = unadapted network) visits epochs 2, 6, ..., 74. At each, the controller's feasible shortlist (same generator, gate and `cand_k = 10` as RCPR; they share one removed link) is scored by the predictor. Each candidate is then replayed from the pre-decision snapshot with and without the mutation on the window k+1..k+5 (the counterfactual-feedback window), giving the realised change in consensus error dE. 11,390 candidates in 1,139 decisions.

## Results (reported in full, `results/v0.8/E1/REPORT.md`)
| quantity | value |
|---|---|
| pooled Spearman, window-matched predicted dE vs realised dE (non-neutral) | **0.568**, 95% seed-cluster bootstrap [0.506, 0.620]; per scenario 0.567 / 0.534 / 0.532 (S1/S2/S3) |
| sign agreement (predicted vs realised direction) | 0.848 |
| predicted dJ vs realised dE (the quantity RCPR actually uses) | 0.474 |
| risk proxy: Spearman(predicted dR, realised change in disconnected epochs) | 0.327 (disconnection changes in 9.3% of candidates) |
| realised dE of the predicted-best candidate / lexicographic first / candidate mean / oracle | -0.0298 / -0.0282 / -0.0171 / -0.0406 |
| predicted-best minus candidate mean (paired by decision) | **-0.0127**, 95% CI [-0.0154, -0.0103] |
| predicted-best minus lexicographic first | **-0.0016**, 95% CI [-0.0030, -0.0002] |
| top-1 agreement with the oracle | 0.331 (chance 0.100) |

Pre-declared criteria: C1 (rho lower bound > 0.10 and rho > 0 in each scenario) **met**; C2 (predicted-best better than the candidate mean, CI upper bound < 0) **met**. Verdict under the pre-declared rule: **informative**.

## Post-hoc supplement (not part of the pre-declared criteria; same data)
- Within-decision Spearman (decisions with >= 5 candidates and non-constant values, n = 1,125): mean 0.41, median 0.54, positive in 80%. The pooled 0.568 therefore reflects both within-decision ranking and between-decision differences (Spearman of decision means: 0.55).
- Scale of the change: mean predicted window dE -0.0168 vs mean realised -0.0169 (sd 0.038 vs 0.030). The absolute predicted E is not calibrated (null-action mean E about 0.79-0.94 vs the simulator's typical 0.4-0.5), so the model is useful for the change and the ranking, not as an error estimate.

## Claims allowed and not allowed
Allowed: on development seeds the predictor's window-matched error change correlates with the counterfactual replay (Spearman 0.57, direction agreement 85%) and the pre-declared criteria were met. Not allowed: that the predictive selector is superior (its advantage over the lexicographic choice is 0.0016, far below the 0.02 margin), that the absolute error prediction is calibrated (it is not), that the deferral rule helps (it does not), or that RCPR/B8 outperforms any baseline. The within-decision statistics above are exploratory (post-hoc).

## How to read this
1. The predictor **does track the counterfactual replay** for ranking added links and for the sign/size of the change; this is consistent with using it as a selector but does not show that it is a better one.
2. It also shows the selector's **practical headroom is small**: choosing by predicted J beats the lexicographic first choice by only 0.0016 in window-level dE (CI barely excludes zero), a tiny fraction of the 0.02 margin, and the lexicographic first choice already captures most of the gain over an average candidate (0.0282 vs 0.0171). Do not expect B6/B8 to differ much from B5/A4/A5 in E2. The oracle gap (-0.0406) shows that a better predictor could matter, but this one is not it.
3. The act/defer rule is weak evidence: when the rule defers (15% of decisions), the best move would still have been beneficial in 80% of them, so deferral is mostly not protecting against harm.
4. Limitations: unadapted-network states only; one deterministic replay per candidate on the single realised trace; candidates share the removed link; criteria thresholds were this author's proposal; development seeds only; this is a model diagnostic, not evidence about any baseline comparison.
