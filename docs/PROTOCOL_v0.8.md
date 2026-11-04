# v0.8 protocol: component ablation, matched-budget A7 comparison and hybrid (DRAFT FOR REVIEW)

**Status: DRAFT, decisions D1-D10 taken on 2026-11-04 (section 14). E1 (predictor validation) has been run on development seeds; E2 has NOT been run.** The protocol becomes binding for E2 only when the calibration is frozen and committed (section 9). v0.7 (`docs/PROTOCOL_v0.7.md`, `docs/MATH_SPEC_v0.7.md`) is frozen and unchanged; where this document says "as v0.7" it refers to those.

Labels used throughout:
- **[I]** implemented in the code today (file named);
- **[I*]** implemented in this phase (new, with tests);
- **[P]** proposed, not implemented;
- **[D]** decision needed from you (collected in section 14).

## 1. Research question and hypotheses
**RQ.** Under constrained network evolution (at most M rewirings per run, strict edge budget, setup delay), when does resilience-aware topology adaptation provide a benefit over simpler reactive and timing-based strategies?

The v0.7 held-out data already say that full TCCE-R (A5) was not better than Reactive (A1) and was worse than the state-blind Front-loaded schedule (A7) in all 6 cells. v0.8 therefore does **not** assume TCCE-R is superior. Pre-stated hypotheses (each may be refuted):
- **Q1 (components).** Which component, if any, improves E over instantaneous E-thresholding: extra stress terms (C, V), accumulation (debt), predictive selection, adaptive threshold, counterfactual feedback?
- **Q2 (timing vs triggering).** Does any state-triggered arm, including the revised TCCE-R (B8), match or beat A7 at matched mutation budget?
- **Q3 (hybrid).** Does a front-loaded phase followed by risk-aware adaptation (H1) match or beat A7 and B8?
- **Q4 (resilience profile).** Do the arms differ in disconnection, recovery, worst-case error and reconfiguration overhead, not only in mean E?

**Primary outcome:** per-seed mean consensus error E over the 80 epochs (as v0.7). **Practical-effect margin:** |dE| = 0.02, retained from v0.7 because it was fixed before the v0.6/v0.7 runs and is the same scale as the effects seen there (A5-A7 differences 0.024-0.076); it is stated, not tuned. **Secondary outcomes:** section 11.
**Allowed conclusions:** a verdict per cell using the v0.7 verdict table (section 12). A negative or mixed result is a valid outcome and will be reported as such.

## 2. Setting (unchanged from v0.7) [I]
Scenarios S1 (RGG-40, bursty), S2 (RGG-40, background failures only), S3 (RGG-80, bursty) from `configs/v0.7/scenarios`; 80 epochs x 60 rounds; Metropolis consensus with a fresh x(0) each epoch; setup delay d = 2; strict edge budget (every mutation is a rewire); cooldown 2; budgets M in {3, 6}; common random numbers (graph, failure trace, x(0) identical across arms for a seed). Cells = scenario x M = 6. Centralised controller: global lambda2/Fiedler, exact-model counterfactual replay. **Not modelled:** load, traffic, trust/uncertainty, adversaries. ER/BA graphs, larger n, imperfect information, other failure laws: later phases, not in this protocol.

## 3. Notation and shared mechanics [I]
Epoch k = 0..79. Measured signals: E_k (consensus stress, v0.7 sec. 2), C_k (1 if disconnected, else bridge fraction), V_k (volatility over w = 3 epochs). Stress s_k = wE E_k + wC C_k + wV V_k. All arms share: one attempt per epoch; cooldown 2 after a success; cap M; the candidate generator (one removed link r with smallest first-order lambda2 loss, plus each admissible added link); the safety gate (v0.7 MATH_SPEC sec. 5); strict budget. Only **when** an attempt is made and **which candidate** is chosen differ.

## 4. Resilience debt and trigger [I] (`core/debt.py`, `policies/v06.py`)
D_k = max(0, D_{k-1} + s_k - kappa), D_{-1} = 0, kappa >= 0 (frozen per scenario from Static runs: kappa_s = median of 0.5E+0.3C+0.2V over connected epochs). Fire when D_k > Theta_k and the cooldown has elapsed. D resets to 0 after a successful mutation (except H1 phase 1, section 7). Stress weights for A4/A5/B5-B8: (0.5, 0.3, 0.2), hard-coded in `v06.py` (`ECV_WEIGHTS`); B2-B4 use the subsets in section 6 normalised by the weight sum.
**Mapping to the professor's debt formulation:** the recurrence is the "existing debt recurrence" D_k = max(0, D_{k-1} + s_k - kappa); every term is defined above.

## 5. Adaptive threshold and feedback
**[I] Adaptive Theta** (`core/threshold.py`, `v06.py`): success: Theta <- max(Theta0/4, 0.9 Theta); failure: Theta <- min(4 Theta0, 1.25 Theta); neutral (counterfactual only): unchanged. Constants: BETA = 0.10, ALPHA = 0.25, bounds [Theta0/4, 4 Theta0], feedback horizon H = 3 (hard-coded in `v06.py`).
**[I] Counterfactual feedback** (`core/counterfactual.py`; v0.7 MATH_SPEC sec. 4): for each mutation at epoch m, replay the window m+1..m+d+3 from the pre-mutation snapshot with and without the mutation under the identical observed exogenous record; Delta = mean E_with - mean E_without; success if Delta < 0, failure if Delta > 0, neutral (no update) if Delta = 0. Assumes an exact model of the consensus dynamics.
**[I] Legacy feedback** (`core/feedback.py`): success iff mean E over the 3 epochs after setup < mean E over the 3 epochs up to and including m. Known biased towards "success" (67-73% on Static placebo, v0.7 MATH_SPEC sec. 4).
**[I*] B7 is now self-defining:** `v08_rcpr_legacy` always uses the legacy rule, regardless of `cfg.feedback_rule`. Before this phase it differed from B8 only through the config and silently equalled B8 under a counterfactual config. Tests: `tests/test_v08_variants.py::test_b7_*`.

## 6. Arms (professor's B-labels mapped to code) [D1]
| Label | Code policy | Trigger | Selection | Threshold | Feedback | Config calibrated |
|---|---|---|---|---|---|---|
| A0 | `static` | never | - | - | - | none (reference, constants) |
| **B1 = A1 Reactive** | `v06_reactive` | E_k > h | lexicographic | fixed | - | h |
| B2 | `v08_b2` | s'_k > h, s' = (0.5E + 0.3C)/0.8 | lexicographic | fixed | - | h |
| B3 | `v08_b3` | s'_k > h, s' = (0.5E + 0.2V)/0.7 | lexicographic | fixed | - | h |
| B4 | `v08_b4` | s'_k > h, s' = (0.5E + 0.3C + 0.2V)/1.0 | lexicographic | fixed | - | h |
| **B5 = A4** | `v06_cusum_ecv` | D_k > Theta (E, C, V debt) | lexicographic | fixed at **B8's Theta0** | - | derived from B8 |
| B6 | `v08_rcpr_fixed` | D_k > Theta | **predictive** (section 8) | fixed at **B8's Theta0** | none | derived from B8 |
| B7 | `v08_rcpr_legacy` | D_k > Theta | predictive | adaptive | **legacy** | derived from B8 |
| **B8 revised TCCE-R (RCPR)** | `v08_rcpr` | D_k > Theta | predictive | adaptive | **counterfactual** | Theta0 |
| ~~P1~~ | `v08_pred_only` | **dropped from E2**: no requirement of the brief asks for a predictive-only arm, and it needs an extra untested grid (b) | - | - | - | - |
| **H1 Hybrid-FrontRisk** | `v08_hybrid` | phase 1 front-loaded, then as B8 | see section 7 | adaptive | counterfactual (phase 2 only) | derived from B8, F = 2 (M = 3), 3 (M = 6) |
| Comparator A5 | `v06_tccer` | D_k > Theta | lexicographic | adaptive | counterfactual | Theta0 (v0.7 TCCE-R) |
| **Comparator A7** | `v06_front` | epochs 0, 2, 4, ... | lexicographic | - | - | count PMF (v0.6 rev 4) |
| Comparator A7M | `v06_front`, no PMF | epochs 0, 2, ..., 2(M-1) | lexicographic | - | - | none (exactly M attempts) |

Reading the chain: B1 -> B2/B3 -> B4 adds stress components under an instantaneous trigger; B4 -> B5 adds accumulation; B5 -> B6 adds predictive selection; B6 -> B8 adds adaptive threshold with counterfactual feedback; B8 vs B7 isolates the feedback rule; B8 vs P1 isolates the debt trigger. B2-B4 need not equal "B1 plus a term" exactly because their statistic is normalised by the weight sum: this is a design choice; thresholds are calibrated per arm on mutation counts only, so scale differences do not matter. A5 versus B5/B8 shows what the predictive selector adds to the v0.7 TCCE-R.
**Mapping validation (2026-11-04).** (i) *B5 = A4* is exact in the code: `RCPRFixedArm` shares A4's statistic, weights, trigger, cooldown, cap and reset; with its selector replaced by the lexicographic one it reproduces A4 row for row (`tests/test_v08_pipeline.py::test_b5_is_a4_and_differs_from_b6_only_by_the_selector`). (ii) *B6 vs B8* differ only in threshold adaptation: B8 with the update disabled reproduces B6 row for row (`test_b6_differs_from_b8_only_by_threshold_adaptation`). For that to hold in the experiment, **B5, B6, B7 and H1 use B8's calibrated Theta0 and kappa** (their configs are copies of B8's, `derive_from_b8`); only B8 (and A1, A5, B2-B4) are calibrated on mutation counts. Consequence: their realised mutation counts can differ from B8's, which is reported, and the cap M bounds all of them. (iii) *B1 = A1* is exact (instantaneous E threshold, same selector). (iv) **Flagged ambiguity:** the brief defines B1-B4 as signal sets (E; E+bridge; E+volatility; E+bridge+volatility) and B5 as "full resilience debt with fixed threshold" without saying whether B1-B4 accumulate. If they accumulated, B4 would be identical to B5, so the only non-degenerate reading is that B1-B4 use an instantaneous trigger, which is what is implemented. A debt-based version of B2/B3 would be `v06_cusum_ecv` with `v08_w` set to 0.5,0.3,0 / 0.5,0,0.2 (no new code; kappa would need recalibration); it is not in E2 and can be added if your professor means that. (v) The only source for the brief is the list of areas in the original task statement; nothing else was available to validate against.

## 7. Hybrid H1 (Hybrid-FrontRisk) [I*] (`policies/v08.py::HybridArm`)
Parameter F = `v08_front` (explicit; 0 gives B8 exactly). **Decided: F = ceil(M/2), i.e. F = 2 for M = 3 and F = 3 for M = 6.** This is a design choice, not an established advantage; F is not tuned.
- **Phase 1** lasts until F phase-1 rewirings have succeeded or epoch 4F, whichever is first. In phase 1 the only attempts are the owed front-loaded ones: an attempt is owed at epoch k iff k >= 2 n_front, selected state-blind by the shared lexicographic selector, exactly as A7 (the cooldown/gate still apply; a failed attempt is retried at later epochs).
- Phase-1 mutations count against the cap M. They do **not** reset the debt and are **not** registered for threshold feedback (they are not decisions of the adaptive rule). The debt keeps accumulating, so if the debt already exceeds Theta when phase 2 starts, B8 acts at once. **Decided:** keep this behaviour (no debt reset, no feedback in phase 1) as a design choice; the alternative is not evaluated in E2.
- **Phase 2** is exactly B8 for the remaining budget M - n_front.
- Not count-matched through a PMF (the intended count is simply up to M); mutation counts are reported.
Tests (`test_v08_variants.py`): phase-1 attempts at epochs 0, 2; no debt reset and no feedback registration (stub pipeline, exact debt values); the plain B8 control does reset/register on the same inputs; phase window = 4F; F = 0 equals B8; in simulation only phase-2 moves drive Theta and the cap/budget hold.

## 8. Prediction model and risk calculation [I] (`core/predict.py`, `policies/v08.py`)
The shared generator + gate give a shortlist `feas` of at most `cand_k` = 10 feasible rewires taken from the first 30 lexicographic candidates (they share one removed link). For the null action a0 and each candidate a, with horizon H = d + `pred_horizon_extra` = 5:
1. **Hazards.** From the last `hz_window` = 10 epochs of observed up/down transitions of configured links: h = (fails + h0 w)/(up-epochs + w), r = (repairs + r0 w)/(down-epochs + w), clipped to [1e-4, 0.9] and [1e-3, 0.99]; priors h0 = 0.02, r0 = 0.10, w = 20 (`hz_prior_*`; configurable [I*], defaults unchanged).
2. **Survival weights.** q_e = (1 - h)^(H/2) (1 - p_tr) if link e is up now, (1 - (1 - r)^(H/2)) (1 - p_tr) if down; the added link counts as up. p_tr = `p_transient`.
3. **Predicted consensus error.** Expected Metropolis matrix with edge weight q_e/(1 + max(d_u, d_v)), d = expected degrees (sum of q); rho = second-largest eigenvalue; E(a) = 1 - clip(T (-ln rho) / ln(1/eps), 0, 1), T = rounds per epoch. **Heuristic** (Jensen gap ignored); it is a spectral-gap proxy for the simulator's E, **not validated yet** [P: experiment E1].
4. **Disconnection-risk proxy.** R(a) = min(1, (c - 1)(1 - r)^H + (#bridges)(1 - (1 - h)^H)) on the graph of configured links that are not down (c = components). Union bound; counts links still in setup as up (the live graph excludes them): known simplification. It is an **empirical proxy, not a probability guarantee**.
5. **Rewiring cost.** C(a) = c0 + c1 [a releases a link that is currently working], c0 = 0.25, c1 = 0.75 (`rcpr_c_*`, configurable [I*]); C(null) = 0.
6. **Setup penalty.** S(a) = max(0, E_interim(a) - E(null)) d/H, E_interim on the break-before-make graph (removed link gone, added link not yet usable).
7. **Objective.** J(a) = alpha E(a) + beta R(a) + gamma C(a) + delta S(a), (alpha, beta, gamma, delta) = (1, 0.5, 0.05, 1) = `j_*` (untuned defaults). **No uncertainty term U** is included because uncertainty is not modelled.
8. **Constraint (empirical).** Discard a if R(a) > max(`risk_eps`, R(null)), risk_eps = 0.20.
9. **Decision.** a* = argmin J over the remaining candidates. B6/B7/B8: act iff J(null) - J(a*) > 0. P1: act iff > b. Otherwise the attempt is a failed attempt (deferral): no cooldown consumed, the trigger may fire again next epoch.
**Mapping to your suggested objective** J_k(a) = alpha E_{k+H} + beta R_{k+H} + gamma C_rewire + delta D_setup + eta U_{k+H}: E <-> E(a); R <-> the **risk proxy R(a)** (a quantity to minimise; it is not lambda2); C_rewire <-> C(a); D_setup <-> S(a); U omitted. |A_k| <= M <-> cap; connectivity/safety constraints <-> the gate (sec. 3). The risk constraint is an empirical criterion, not a guarantee.
**Known limitations (reviewed in `revision/audit/V08_CODE_REVIEW.md`):** the E predictor is unvalidated; hazards include burst-induced failures; all candidates share the same removed link, so J chooses only among added links; constants other than those made configurable above are untuned.

## 8a. E1 findings (predictor validation; development seeds 8100-8119 only)
Full report: `revision/audit/E1_PREDICTOR_VALIDATION.md`; raw output `results/v0.8/E1` (git-ignored). Held-out seeds were not used and nothing was tuned. 11,390 candidates in 1,139 decisions from a passive probe on the unadapted network.
- Predicted vs replayed error change: Spearman **0.57** (95% seed-cluster bootstrap 0.51-0.62), similar in all three scenarios (0.53-0.57); **direction agreement 85%**. Both pre-declared criteria were met, so the model is "informative" in that narrow, pre-declared sense.
- **Selector advantage over the lexicographic first choice is only 0.0016** in window-level error (CI -0.0030 to -0.0002; the margin is 0.02). Over the average candidate it is 0.0127. **No predictive superiority is demonstrated or claimed.**
- **Absolute predicted error is poorly calibrated** (about 0.8-0.9 predicted vs 0.4-0.5 in the simulator); only the change and the ranking carry information.
- **The deferral rule is ineffective:** it defers 15% of decisions, yet in 80% of those the best candidate would still have helped.
- The within-decision correlation (mean 0.41, median 0.54, positive in 80%) and the scale comparison were **exploratory**, computed after seeing the data, and are not part of the pre-declared criteria.
- Limitations: unadapted-network states only; one deterministic replay per candidate; candidates share one removed link; the criteria thresholds were the author's proposal.
Consequence for E2: B6/B8/B7/H1 are expected to differ little from B5/A4/A5; any difference will be reported as measured.

## 9. Calibration and freezing (as v0.7 protocol sec. 4, extended) [P]
Per scenario, from Static runs on calibration seeds: tau, kappa_E, kappa_s (as v0.7). For each threshold-bearing arm and cell, choose the threshold whose **mean realised mutation count** on calibration seeds is closest to M (ties: larger), feasible only within +-15% of M; outcome metrics are never used. Calibrated arms (28-point grids, calibration runs capped at 12 mutations): A1 (h, linear 0.30-0.98); B2, B3, B4 (h, linear 0.05-0.95); A5 and B8 (Theta0, geometric 0.05-20). B5, B6, B7, H1 are not calibrated: they inherit B8's Theta0 and kappa (section 6). A7M needs no calibration. A7 intended counts: empirical PMF of the capped realised counts of the calibrated arms (A1, A5, B2, B3, B4, B8; v0.6 rev 4 procedure) on the calibration seeds; A7M none (exactly M attempts). Infeasible arm-cells are excluded and reported, never retuned on evaluation seeds. Freeze configs, constants and PMFs with a SHA-256 manifest and commit **before** the evaluation; refuse recalibration afterwards. Scripts (written, smoke-tested on development seeds, **not run on calibration or held-out seeds**): `experiments/v08_common.py`, `calibrate_v08.py` (writes `configs/v0.8/frozen`, refuses if frozen), `run_v08.py` (guards: manifest verifies, tracked tree clean, output folder absent, seeds 9000-9059 only). The clean-tree guard means the code and the frozen calibration must be committed before the held-out run; that needs your approval.

## 10. Experiments, seeds and run counts [P] (nothing launched)
Seeds (decided): calibration **8000-8019** (20), development/E1/smoke **8100-8119** (never reported as results), held-out evaluation **9000-9059** (60); all disjoint from every earlier range (0-7059); stage guards reject foreign seeds (tested).
- **E0 (done in this phase)**: unit and smoke tests only.
- **E1 predictor validation (DONE on development seeds; `revision/audit/E1_PREDICTOR_VALIDATION.md`):** at the decision epochs of dev seeds, compare predicted J-components (E(a) - E(null)) with the counterfactual-replay dE for the same candidate; report rank correlation and sign agreement. About 20 dev seeds x ~3 decisions x 10 candidates: minutes. Purpose: decide whether the E predictor may be described as informative [D5].
- **E2 main experiment (the minimum set the brief asks for):** 6 cells x 12 arms (A1, A5, A7, A7M, B2, B3, B4, B5, B6, B7, B8, H1) x 60 seeds = 4,320 runs, plus Static 3 x 60 = 180 → **4,500 evaluation runs**. Because every arm sees the same graph, failure trace and x(0) per seed, all comparisons are paired.
- **Calibration runs:** 3 scenarios x 6 calibrated arms x 28 grid points x 20 seeds = 10,080, plus 60 Static and about 720 capped PMF runs.
- **Measured single-run cost (idle machine, one dev seed, this phase):** n = 40: A1 0.65 s, A7 0.71 s, A5 0.71 s, B8 1.2 s, H1 1.0 s, P1 1.0 s; n = 80: A1 1.7 s, A5 1.9 s, B8 3.8 s, H1 2.0 s, P1 3.7 s. Estimate: evaluation about 7,000 CPU-s (about 12-20 min on 11 workers), calibration about 17,000 CPU-s (about 1-1.5 h). **Total about 1.5-2 h wall time;** uncapped low-threshold calibration runs may cost more, which is why calibration runs are capped at 2M as in the focused plan.
- **Deliberately out of E2:** ER/BA graphs, n > 80, sensitivity grids, other failure laws, imperfect information; these come after you review E2.

## 11. Metrics (one definition for all experiments)
Existing, unchanged [I] (`experiments/analyze_v06.py`): E (mean over 80 epochs); disconnected fraction; lambda2 (provisional R); realised mutations; pending link-epochs; live-link releases and wasted releases; anchored recovery (mean time from the start of each Static disconnection episode until the arm is connected; censored at the horizon); own disconnection length (mean length of the arm's own disconnection episodes); A5-type feedback shares (success/failure/neutral, mean Delta).
New [P], computed from raw `epochs.csv` by one function: (i) **disconnection frequency** = number of maximal runs of consecutive epochs with components > 1; (ii) **longest disconnection** = longest such run (0 if none); (iii) **worst-case error** = max over epochs of E_hat, per seed (summaries: mean and 95th percentile over seeds); (iv) **time to consensus** = mean over epochs of `conv_round` (rounds until the error falls below eps; epochs that never converge are censored at T = 60 and their share is reported); (v) **reconfiguration overhead** = pending link-epochs + live-link releases (reported separately and as the pair); (vi) **adaptation success rate** = successes / (successes + failures) of Theta updates (adaptive arms only; neutral outcomes reported separately). Window: all 80 epochs; missing data: an arm-cell excluded by calibration yields no row (recorded), a run with fewer than 80 epochs is an error, not a drop.

## 12. Statistics [P] (as v0.7 sec. 7)
Unit = seed (n = 60), paired within a cell; two-sided Wilcoxon signed-rank (p = 1 if all differences are zero); Holm within pre-declared families; 95% bootstrap CI (10,000 resamples, seed 20261010) and t CI; rank-biserial r; margin 0.02. **No pooling across cells.** Verdicts as v0.7: "first arm meaningfully better" (Holm p < 0.05 and dE <= -0.02), "... better, below minimum", mirror images, "practically equivalent" (Holm p >= 0.05 **and** bootstrap CI inside +-0.02), else "inconclusive". "No detectable difference" is never reported as equivalence unless the CI condition holds.
- **Primary family (18 tests):** B8-A1, B8-A7, H1-A7 on E in each of the 6 cells.
- **Ablation family (48 tests):** adjacent steps B2-A1, B3-A1, B4-B2, B4-B3, B5-B4, B6-B5 (selector only), B8-B6 (adaptation only), B8-B7 (feedback rule only) on E in each cell. B5-B4 (accumulation) also changes how the threshold is chosen (B4 own h; B5 inherits B8's Theta0): read it with that caveat.
- **Matched-budget family (12 tests):** B8-A7M, H1-A7M, per cell; and exploratory: all comparisons on the subset of seeds with equal realised counts.
- **Exploratory (no p-values):** all other metrics, paired mean differences with bootstrap CIs.
- Power: with paired SD about 0.04, 60 seeds detect about 0.02-0.025 at the strictest Holm step; smaller effects may be missed (stated, not adjusted).

## 13. Claim discipline
No superiority claim for B8 or H1 unless a primary-family verdict supports it; A1 and A7 stay in every table; every analysis states its cell; the centralised, exact-model, RGG-only, three-scenario scope is repeated in the limitations; the risk constraint is empirical; A7's advantage in v0.7 is reported alongside any new result.

## 14. Decisions
Taken on 2026-11-04: **D1** mapping kept with the validation and flagged ambiguity in section 6; **D2** F = ceil(M/2); **D3** phase-1 behaviour kept, recorded as a design choice; **D4** seeds 8000-8019 / 8100-8119 / 9000-9059; **D5** E1 run first (done; informative under the pre-declared criteria, small headroom, see its report); **D6** B5 = A4 at B8's Theta0 (validated); **D7** P1 dropped; **D8** margin 0.02 retained; **D9** no hysteresis/EWMA baselines; **D10** ER/BA candidate-density matching deferred, ER/BA not in the immediate runs.
**Still open:** (a) your confirmation that E1's outcome justifies launching E2 (note the small selector headroom: predicted-best beats the lexicographic first choice by only 0.0016 in window dE); (b) your approval to commit the code and frozen calibration before the held-out run (the run script refuses a dirty tree); (c) whether the professor means debt-based B1-B4 (section 6 (iv)).
