# Revision 2, Amendment 1: calibration on the realised count under the actual cap (budget-matched evaluation)

Written and committed BEFORE any amended calibration or evaluation run. The original evaluation (calibration 8300-8319, held-out 9100-9159,
commits d15b74c / d7f6a40 / 4e4435d) is kept unchanged and is reported as "original".

## Reason
The original rule matched the mean realised count of runs capped at 12 to M. A1 and B8 have narrow count distributions and were close to M
under the actual cap; C1's distribution is wide and bimodal (SD 3.1-4.1; 30-45% of runs with no mutation at M=3), so the actual cap M cut its
mean to 1.55 (M=3) / 4.25-4.40 (M=6) on the calibration seeds and to 0.97-1.33 / 3.18-3.75 in the held-out run. The original comparison of C1
with B8 and A7M is therefore confounded by unequal realised budgets (docs/R2_DESIGN_RULES.md was silent on capped means; this is a gap in
the registered rule, not an after-the-fact reinterpretation of results).

## Amended rule (the only change)
* Seeds: calibration **8400-8419**; held-out **9200-9259**. Both disjoint from every earlier range; guards in the scripts reject others.
* The realised count used for threshold choice is the count **under the actual per-run cap M** of the cell. Because a cap only stops mutations
  after the M-th, the count under cap M equals min(count under a larger cap, M) exactly (checked on 340 earlier seed-level pairs: 0 mismatches).
  The grid is therefore run once with cap 6 and capped at M=3 by min(count, 3). The script re-runs every chosen configuration under its actual
  cap and **aborts if any count differs** from the derived value.
* Rule unchanged otherwise: per scenario, same 28-point grids (A1 linear 0.30-0.98; B8, C1 geometric 0.05-20), adaptive threshold on for B8/C1,
  threshold whose mean capped count over the 20 seeds is closest to M (ties: larger threshold, 1e-9 tolerance), feasible only within +-15% of M,
  one decade extension if a B8/C1 winner is on a grid edge (counts only), infeasible cells excluded and reported, never retuned. No outcome
  metric is used.
* Fixed (not tuned), as before: C1 cd_tau = setup delay + 2, r2_retry = state, other cd_* defaults; B8 kappa_s from Static runs on the
  calibration seeds. A7M = exactly M attempts; A7 = PMF of the capped counts of the calibrated arms; A0 = Static.
* Comparisons, families (primary: C1 vs A7, A7M, A1, B8; reference: B8 vs A1, A7, A7M), Holm, margin 0.02, bootstrap, metrics, per-mutation
  efficiency: exactly as in `experiments/analyze_r2.py` (selected with `--amended`).

## Expected consequence (stated in advance, not a hypothesis in favour of C1)
Since a capped mean cannot exceed M, "closest to M" selects thresholds at which almost every run reaches the cap, for all arms. The amended
comparison is then mostly about WHEN and WHICH links are rewired at near-equal budgets. It also means all arms may approach A7M's exactly-M
budget. Any such saturation will be reported. If an arm's winner sits on a grid edge or a cell is infeasible, that is reported, not repaired.

## Commands
    python -m experiments.calibrate_r2a            # seeds 8400-8419 -> configs/r2a/frozen (refuses if frozen)
    python -m experiments.run_r2 --mode eval --amended
    python -m experiments.analyze_r2 --amended     # -> revision/analysis/R2/amended
