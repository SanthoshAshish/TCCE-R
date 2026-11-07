# Revision 2: design rules proposed after the C1 diagnostic (sections 1-3 ACCEPTED and FINAL as of the commit that adds this line; section 4 is a specification only; nothing is calibrated or evaluated)

Evidence: `results/r2/diag_c1`, `diag_retry`, `diag_repair` (development seeds 8200-8219 only; regenerate with
`experiments.diagnose_r2_c1`, `diagnose_r2_retry`, `analyze_r2_retry_evidence`, `analyze_r2_repair_times`).

## 1. Retry / deferral
**Cause.** `V06Policy.decide` calls `wants_attempt` on every cooled-down epoch; only a *successful* mutation updates the
cooldown clock and (for B8) resets debt. A deferral changes nothing, so while debt > Theta the predictor re-runs every epoch. B8 does
the same; it is inherited, not a ledger defect.
**Measured.** Re-attempts on a literally unchanged decision-relevant state (configured, down, ready) are rare: 0.05-0.70 per run
(S2 M6: 0.70 of 24 failed attempts). Suppressing exactly those (`r2_retry="state"`) reproduces the unsuppressed mutation sequence in
120/120 runs and `audit` mode is behaviour-identical to `none` in 120/120 (zero flips).
**Margins do not discriminate.** 1,463 failed attempts (C1+B8 pooled): the next attempt succeeds in 16-24% of cases in every margin bin
(<=-0.05: 17%; -0.005..0: 24%). Mutations preceded by >=3 failed attempts succeed (counterfactual replay) in 88%, as do first
tries (88%); the replay baseline is lenient, so this says retries are not harmful by that criterion, not that they are valuable.
**Proposal.** (a) Adopt the exact-state rule for C1 (`r2_retry="state"`): decision-neutral on dev data (compute saving only),
hold = H = d + pred_horizon_extra (no new constant); `audit` counters stay in the log. (b) Do **not** adopt margin- or
retry-count suppression: dev data give no support. (c) Whether to attempt, defer or reserve budget is a question of expected
value of waiting and belongs to MOCO, which is not implemented here.
Caveat: hazard drift and edge-cooldown (tabu) expiry are not in the fingerprint; `audit` showed no effect.

## 2. cd_tau
Failure-episode lengths (initial configured links, three scenarios, 6,358 episodes, 20 dev seeds): mean 5.8 / 8.7 / 6.0 epochs
(S1/S2/S3), median 4 / 6 / 4; share of episodes of length 1, 2, 3 = 6%, 18%, 15% (pooled); background repair is geometric
(p_repair 0.1, mean 10), bursts last 2-6. With cd_tau = 2 only 5-10% of episodes are temporary, hence the near-empty class.
**Rule (derived, not fitted):** a response decided when a failure is first seen is usable from onset + 1 + d, so it can help only
against failures of at least d + 2 epochs. Failures shorter than that cannot be remedied by rewiring: **cd_tau = d + 2 = 4**
(`setup_derived_tau`). Temporary share then = P(length < 4): S1 40%, S2 30%, S3 41% (measured on dev seeds, report only).
Fixed before calibration; sensitivity (tau 2..6) reported on classes and on dev-seed outcomes, never used for selection.

## 3. Pre-registered calibration rule for C1 (binding only once committed before any run on 8300-8319)
* Seeds: calibration **8300-8319** only (assertion in the script); held-out **9100-9159** untouched until freeze; 8200-8219 are development only.
* Fixed, NOT tuned: cd_tau = d+2; cd_rho_t = 0.25; cd_w_prop = 1.5; cd_lam_E = 1.0; cd_scar = 0.25; cd_gamma = 0.8; cd_e_ok = 0.30;
  cd_w_pred = 0 (forward term is a separate ablation arm); r2_retry = state. Changing any of these after seeing calibration outcomes
  is a protocol amendment, written down and applied to all arms.
* One tuned scalar per cell, Theta0, exactly as B8 in v0.8: 28-point geometric grid 0.05-20, adaptive threshold ON, bounds
  [Theta0/4, 4 Theta0], uncapped-ish runs (cap 12), choose the grid point whose **mean realised mutation count** over the 20 seeds is
  closest to M (ties: larger Theta0), feasible only within +-15% of M. No outcome metric (E, lambda2, disconnection, J) is used.
  If the winner is on a grid edge, extend the grid by one decade once in that direction (count-only), documented.
* Symmetry: B8 and A1 are recalibrated on 8300-8319 by the same code path and rule; A7/A7M derived as in v0.8. The v0.8 frozen B8
  (calibrated on 8000-8019) is kept as a secondary reference. C1 and B8 therefore face the same mutation budget.
* Infeasible arm-cells are excluded and reported, never retuned. Freeze configs + SHA-256 manifest, commit, then refuse recalibration.
* Any comparison reports equal-count subsets and performance per successful mutation next to raw means; no superiority claim without
  the pre-declared paired tests (Holm, margin 0.02).

## 4. Delayed credit for added capacity (specification only; not implemented)
Mutation m (epoch k_m, adds link a, removes link b), usable from k_m+1+d, evaluated at k_m+d+H by the existing counterfactual replay
(Delta_m = mean E_with - mean E_without over the window; snapshot includes all earlier mutations, no later one).
1. *Removal settlement* (already implemented): if b is an open failed item it is settled at once. This is not credit for a.
2. *Capacity credit* at evaluation time: chi_m = clip(-Delta_m / Ebar_without, 0, 1) x L_m, with L_m the open accrued liability at
   k_m excluding b. chi_m is spread over items still open, proportional to accrued debt, each item capped at
   cap_e = acc_e(k_m) - credited_e.
3. *No double counting:* (i) per-item `credited_e`; later natural repair writes off and scars only (acc - credited); (ii) credit is
   keyed by mutation id and applied once, unevaluated mutations get none; (iii) ordered marginal attribution: m's baseline contains earlier
   mutations only, so overlapping effects go to the later mutation (stated bias); (iv) D >= 0 enforced; (v) no information after k_m+d+H.
4. The same Delta_m also drives the Theta update; credit acts on the debt state, the update on the threshold. The correlation is
   acknowledged and handled by an ablation (credit on/off), not assumed away.
Invariant tests to write with the implementation: sum credited <= sum accrued; idempotence; order dependence documented; D >= 0.
Open: chi_m's proportional conversion is a heuristic, not derived.
