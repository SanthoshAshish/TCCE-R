# Reproducibility report (Phase 2)

## Full test run (working tree, `python -m pytest -q`, 2026-11-04)
**176 passed, 2 failed, 0 skipped, 62 warnings; 300 s.** The log was scratch output; the command reproduces it.

### Failures
| Test | Cause |
|---|---|
| `tests/test_engine.py::test_same_seed_same_result` | column `decide_ms` differs 100% between two identical runs |
| `tests/test_v06.py::test_static_invariant_to_delay_and_budget` | same column, 71% differ |

**Root cause (verified from the assertion output and `git diff`):** the uncommitted edit to `tccer/sim/engine.py` adds `obs["decide_ms"] = 1000 * (time.perf_counter() - t_dec)`, a wall-clock timing field, to each epoch row. Wall-clock time is non-deterministic, so whole-frame equality tests fail. All other compared columns agree. This is an instrumentation side effect, not a change in dynamics.
Proposed fix (Phase 6; scientific logic untouched): keep the timer out of the frames compared for determinism, or log it in a separate file. Not applied; no test was edited.

### `test_v06_dry_run_rows_reproduce[A6-v06_random]`
- **Not reproduced.** It passes in the current dirty tree (3 passed, in isolation and in the full suite) **and** at a clean checkout of HEAD `4fa6f2a` (git worktree, 3 passed).
- So the earlier failure is not explained by RNG, seed handling, archived-result inconsistency or a regression in the present code. Plausible but **unverified** explanations: it was observed on an earlier working-tree state (the `_select` refactor in `v06.py` is present now), or in a different environment. I cannot tell which without the original failure log. No expected result was changed.
- The test compares only columns common to the archive and the new run, for seed 100 against `archive/v0.6/dryrun_rev4`.

## Other reproducibility checks
- Frozen-config SHA manifests verify (v0.7: 47 entries, focused: 21; 0 mismatches).
- Baseline file hashes are captured in `revision/baseline/baseline_manifest.json`.
- The common-random-numbers design is covered by existing tests.
- The claim that new v0.8 options "reproduce v0.7 exactly" at defaults is supported by the dry-run tests passing, but **not yet verified against `results/v0.7`**. Planned in Phase 6: replay a few seeds per cell for A1, A5, A7 from the frozen configs and compare with the stored `epochs.csv`.

## Warnings
`experiments/analyze_v06.py:98`: "Mean of empty slice" / "invalid value in scalar divide" (empty groups in pipeline tests). Benign, pre-existing.

## Documentation drift
README claims 85 tests and "v0.7 not yet run"; the actual count is 178 tests and v0.7 has been run. v0.7 has no RESULTS document other than `analysis/REPORT.md`.

## Not done
No experiment was re-run end to end (v0.7 eval is about 5 min; calibration 25-40 min by the protocol's estimate).

---
# Update 2 (after approval of the git/telemetry/equivalence steps), 2026-11-04

## decide_ms: separated from scientific outputs
- `tccer/sim/engine.py`: `simulate(..., timing=None)`. Decision wall-time is appended to the optional `timing` list only; **it is no longer written into epoch rows**. Callers that don't pass `timing` get rows with no timing field (the clock is still read once per epoch, which does not affect results).
- New `tests/test_timing_isolation.py`: (1) rows contain no timing column; (2) for `tccer`, `v06_reactive`, `v06_random`, `static`, results (epoch rows and per-round rows) are identical with and without a `timing` list, and the list has one non-negative entry per epoch.
- No expected value was changed in any existing test.

## Full test suite, after the change
**180 passed, 0 failed, 0 skipped, 62 warnings (390 s).** (Previously 176 passed / 2 failed; the 2 formerly failing tests now pass, plus 2 new tests.) Warnings are the same benign `analyze_v06.py` empty-slice warnings.

## Default-equivalence: do default v0.8 options reproduce frozen v0.7 outputs?
Script: `revision/audit/check_v07_equivalence.py --seeds 10` (read-only; reports in `revision/audit/*.json`). It re-simulates every evaluated arm-cell of `configs/v0.7/frozen` for held-out seeds 7000-7009 (**440 runs; 9 groups; row counts per group are in the JSON**) and compares every column stored in `results/v0.7/eval/*/epochs.csv`.

Results (current working tree, v0.8 defaults):
- **No stored column is missing and the v0.8 code adds no extra columns** to A-arm outputs.
- **All discrete / decision outputs are identical**: mutations, mutation kind, trigger attempts, gate rejections, select outcomes, n_mutations, theta-update counters, components, edge counts, and `E_hat`, `final_error`, `conv_round`, `lambda2`, `C`, `V`.
- **Float round-off differences only**, in a few derived columns: `local_disagreement_total/max` (max |diff| 3.4e-21), `v06_stat`, `debt`, `theta` (max |diff| 4.4e-16 typically, 3.6e-15 worst case). 7 of 9 groups show them; 2 groups (A0 S2, A0 S3) are bit-exact.
- **Cause (attributed by control experiment):** the identical comparison run on a clean checkout of tag `baseline-v0.7` (pristine v0.7 code, no v0.8 edits) gives **exactly the same differences in every group** (`v07_equivalence_report_baseline_checkout.json`). So the differences are not caused by the v0.8 changes; they come from the stored results having been generated in a slightly different numerical context from today's (sub-ULP effects such as BLAS/threading or summation order; I did not isolate which). They do not alter any decision, count, or the primary metric E (`E_hat` is exact).
- **Conclusion:** with default options the v0.8-draft code is scientifically equivalent to v0.7 on 10 of 60 held-out seeds (all arms, all cells), bit-exact on all discrete outcomes and on E, up to float round-off <= 3.6e-15 in derived diagnostics. Not verified: seeds 7010-7059 (full replay would take about 5 min if you want it), the focused-run configs, and the non-default v0.8 options (untested, no results).

## Honest caveats
- "Equivalent up to 1e-15" is not bit-for-bit reproduction of the stored files; if bit-exactness is required, we would need to recover the original numerical environment.
- The v0.8 policies (`v08_*`) and ER/BA/shock/observation-noise code paths are still unreviewed and untested beyond "all policies run" tests.

---
# Update 3 (Phase 1 verification), 2026-11-04

## 1. Baseline results backup
- Destination: `E:\SEM5\CN\CN LAB PROJECT\tcce_r_baseline_backup_v0.7\` (sibling of the repository, did not exist before; no file overwritten). Contents: copies of `results/v0.7` (169 files, 67.2 MB) and `results/v0.7_focused` (69 files, 27.3 MB) = 238 files, 94.5 MB; 312 GB free on E:. All files set read-only (0 writable files remain).
- Verification: every source file re-hashed against its copy (238/238 identical), and `sha256sum -c SHA256SUMS.txt` inside the backup (238/238 OK). The 39 baseline result files listed in `baseline_manifest.json` were re-hashed in place after all of today's work: 0 changed.
- Limitation: same physical drive as the repository, so this protects against accidental edits and deletion, **not against disk failure**. Copy it to another disk or cloud store if that matters.

## 2. Full 60-seed v0.7 replay
Command: `python revision/audit/check_v07_equivalence.py --seeds 60` (seeds 7000-7059; every evaluated arm-cell of `configs/v0.7/frozen`; 2,640 runs; same configs and policies as `run_v07.py`).
Rule: stored `epochs.csv` vs re-simulation after a CSV round trip, every stored column. EXACT = identical; TOLERANCE = not identical but `|a-b| <= 1e-12 + 1e-9|b|`; FAIL = otherwise.
- **Cells compared: 10,118,400. EXACT: 10,116,977 (99.986%). TOLERANCE: 1,423. FAIL: 0.** No missing or extra columns, no row/key mismatch.
- All 1,423 non-identical cells are in five float columns of the pre-existing code path: `debt` (297 cells, max |diff| 3.6e-15), `v06_stat` (297, 3.6e-15), `theta` (460, 4.4e-16), `local_disagreement_total` (88, 3.4e-21), `local_disagreement_max` (281, 3.4e-21). They fall in 59 of 60 seeds for `debt`/`v06_stat`, 22 for `theta`, 35-52 for `local_disagreement_*`.
- Every discrete or decision-bearing field and `E_hat`, `final_error`, `lambda2`, `C`, `V`, `conv_round`, mutation descriptors and counts, gate rejections, and the Theta update strings are exact in all 2,640 runs.
- Every mismatch (group, arm, seed, epoch, field, stored, replay, |diff|) is listed in `revision/audit/v07_equivalence_60seeds_mismatches.csv`; per-group counts in `v07_equivalence_60seeds.json`.
- Attribution: the 10-seed run of the same comparison on a clean `baseline-v0.7` checkout showed the same differences (update 2), so they do not come from the v0.8 changes. Not isolated further.
- Caveat: this replay began before the config-validation edit (item 3 below). Validation only rejects invalid values and all 66 frozen/scenario configs still load, and the focused replay and the final test suite ran after the edit.

## 3. Focused-run replay (exploratory A1/A3/A5, seeds 500-559)
`python revision/audit/check_v07_equivalence.py --suite focused --seeds 60`: 1,140 runs, 3,940,800 cells: EXACT 3,939,712, TOLERANCE 1,088, **FAIL 0**; the same five columns, max |diff| 3.6e-15. Report: `focused_equivalence_60seeds*.{json,csv}`.

## 4. v0.8 code review and configuration coverage
Full review: `revision/audit/V08_CODE_REVIEW.md` (15 findings; validation added; nothing scientific changed).
Coverage of the options (default value in brackets):
| Option group | Used by any frozen/baseline config? | Covered by tests? | Still unverified |
|---|---|---|---|
| `graph_family` er/ba [`rgg`], `er_p_init`, `er_p_pot`, `ba_m` | No (all 66 baseline configs use defaults) | Yes: determinism, connectivity, cap/budget, common trace, validation | Whether the ER/BA settings are sensible; calibration; cross-family fairness |
| `shock_*` [off] | No | Yes: window, other streams untouched, off == absent, overrun | Severity distribution across seeds |
| `obs_noise`, `obs_delay` [0] | No | Yes: truth unchanged, delayed/noisy stat, reproducible, clip | Effect on feedback/selection (not perturbed by design) |
| `v08_w` [None] | No | Format validation only | Behaviour of a weight override end to end |
| `j_*`, `risk_eps`, `cand_k`, `pred_horizon_extra` and the v08 arms | No | Yes: run/cap/budget/determinism, predictor ranges and J formula | Predictor accuracy, RCPR performance, runtime at n >= 80 |
| `v08_front` (hybrid) [0] | No | Yes: 0 == B8; front phase acts at epochs 0 and 2 | Intended hybrid definition |
So the focused-run configuration itself exercises **no** non-default v0.8 option; non-default behaviour has smoke-test coverage only.

## 5. Tests
Command: `python -m pytest -q`. **211 passed, 0 failed, 0 skipped, 62 warnings (264 s)** = 180 earlier + 31 new smoke tests (`tests/test_v08_smoke.py`). The warnings are the same `analyze_v06.py` empty-slice warnings. No expected value was changed.

## 6. README
Fixed: stale "85 tests" (now 211, with a pointer to this report), "not yet run"/"smoke test only" for v0.7 (now states what was run, seeds, commit, and that `results/` is git-ignored), and added the verified v0.7 headline numbers and a v0.8-draft status line. Unchanged: the README title still says v0.6.1, and its v0.1 results section is historical.

## Unresolved
See the open items in `V08_CODE_REVIEW.md` (notably: no v0.8 protocol/equations document, unvalidated predictor, no calibration/runner for B-arms, hybrid undefined, B7 depends on config). The earlier `A6-v06_random` failure remains unexplained (does not reproduce). The 1e-15 float drift vs the stored files is attributed to the environment, not isolated.

---
# Update 4 (specification phase), 2026-11-04
- **Code changes (all small, in the untracked/modified v0.8 draft; frozen v0.7 files untouched):** `v08_rcpr_legacy` (B7) now forces the legacy feedback rule itself; `HybridArm` redefined (explicit F, phase-1 moves do not reset the debt or register feedback; phase window 4F; F = 0 equals B8); predictor/hazard constants moved to validated config options with unchanged defaults.
- **Regression check (pre/post snapshots, seed 8, 40 epochs, two configs, 10 policies):** 19 of 20 (config, policy) row sets bit-identical. The single difference is B7 under a counterfactual config, which is the intended fix (it previously equalled B8). B7 under a before_after config is bit-identical.
- **New tests:** `tests/test_v08_variants.py` (12): B7 independence from `feedback_rule` and difference from B8; B6 fixed vs B8 adaptive threshold; hybrid phase-1 behaviour with exact debt values, control showing B8 does reset/register, phase window, simulation-level cap/budget/threshold-driver check; configurable predictor constants with old defaults; validation. One existing smoke test was adjusted only to ignore the new hybrid-only log column `hyb_n_front` when comparing H1(F=0) with B8.
- **Smoke cost measurements** (idle machine, one development seed 8100, single runs): n = 40: A1 0.65 s, A5 0.71 s, B8 1.2 s, H1 1.0 s; n = 80: A1 1.7 s, A5 1.9 s, B8 3.8 s, P1 3.7 s. Used for the estimates in `docs/PROTOCOL_v0.8.md` section 10. Seed 8100 is in the proposed development range and is never reported.
- **Claim correction:** earlier text said A7 beat A5 in "5 evaluable cells"; the v0.7 primary table has A5-A7 in all **6** cells (only A5-A1 has 5). README, audit and matrix corrected.

---
# Update 5 (E1 and E2 preparation), 2026-11-04
- **New scripts (untracked until you approve a commit):** `experiments/v08_common.py` (seeds, arm tables, derived configs), `calibrate_v08.py`, `run_v08.py`, `validate_predictor_v08.py`. They reuse v0.6/v0.7 helpers unchanged; all outputs go to `results/v0.8/**` (git-ignored) and `configs/v0.8/frozen`.
- **Seed separation verified by test** (`tests/test_v08_pipeline.py`): 8000-8019 / 8100-8119 / 9000-9059 are mutually disjoint and disjoint from 0-7059; calibration, E1 and evaluation stages reject foreign seeds; smoke runs use development seeds only; no output path contains v0.7 or v0.6.
- **Ablation isolation verified by test:** B6 with the lexicographic selector equals A4 (= B5) row for row; B8 with threshold updates disabled equals B6 row for row; derived arms' configs equal B8's.
- **E1 run** on development seeds (not held-out): see `E1_PREDICTOR_VALIDATION.md`. 60 probe runs, 116 s.
- **E2 smoke (development seeds 8100-8103, 6-point grids, NOT results):** `python -m experiments.calibrate_v08 --smoke` (120 s, 216 grid runs) then `python -m experiments.run_v08 --mode smoke` (150 runs, 39 s). All 12 arms ran in all 6 cells with the intended policies; 75 configs frozen with a manifest. Smoke thresholds and counts are meaningless by design (2 seeds, coarse grid) and are not reported.
- **Not run:** real calibration (seeds 8000-8019), E2 evaluation (9000-9059). The held-out runner refuses a dirty tracked tree, so a commit is needed first.
