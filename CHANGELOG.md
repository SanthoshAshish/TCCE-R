# Changelog

Every version is a git tag, and its results are archived under `archive/`. Model changes after v0.1 sit behind config flags whose defaults reproduce earlier versions. **The current code re-runs v0.1, v0.2 and v0.3 bit-identically on every archived column**; this was checked during the v0.4 audit.

## v0.7: readiness for the eight-method comparison

**Archive regression:** v0.1–v0.4 (7 cases) are identical after each commit. The v0.6 tuning-seed dry run reproduces, including the A5 legacy rule.

| commit | change | files |
|---|---|---|
| v0.7a | Parameter validation (ε ∈ (0,1); weights, κ ≥ 0; H, w ≥ 1; θ_min ≤ Θ₀ ≤ θ_max; α ≥ 0; 0 ≤ β < 1). Docstring fix. Direct tests for volatility, ranking/tie-breaks, and first-order vs exact Δλ₂ (Ghosh & Boyd eqs. 8, 10). | `tccer/config.py`, `tccer/consensus/monitor.py`, `tests/test_math_v07.py` |
| v0.7b | **Counterfactual feedback** (`feedback_rule: counterfactual`; the default `before_after` is unchanged): matched with/without-mutation replays under the observed exogenous record; success / failure / neutral; isolated per mutation; no future information. Engine records observations and attaches them to policies. TCCE-R and the A5 arm support both rules. | `tccer/core/counterfactual.py` (new), `tccer/sim/engine.py`, `tccer/policies/{base,tccer,v06}.py`, `tests/test_feedback_v07.py`, `docs/MATH_SPEC_v0.7.md` |
| v0.7c | Frozen eight-method protocol; scenarios; calibration, run and analysis scripts; smoke test. | `docs/PROTOCOL_v0.7.md`, `configs/v0.7/scenarios/`, `experiments/{v07_common,calibrate_v07,run_v07,analyze_v07}.py`, `tests/test_v07_pipeline.py` |

## v0.6.1: architecture compliance pass (no change to any decision logic)

| change | file | notes |
|---|---|---|
| local-disagreement monitor (diagram stage 2) | `tccer/consensus/algorithm.py` (`run_epoch_state`, `local_disagreement`), `tccer/sim/engine.py` | New logged columns `local_disagreement_total` and `local_disagreement_max`; monitoring only. All existing columns are unchanged: archived v0.1–v0.4 and the v0.6 tuning-seed dry run reproduce. |
| duplicate-key warning | `tccer/config.py` (`duplicate_top_level_keys`) | Warning only; behaviour unchanged (last value wins). `configs/v0.5/custom_4node.yaml` repeats `epochs`, `rounds_per_epoch` and `burst_rate`. |
| chain integration tests | `tests/test_architecture.py` (new) | Full chain on the custom 4-node scenario; no-candidate path; cooldown interaction; v0.6 dry-run reproduction |
| compliance documentation | `docs/ARCHITECTURE_COMPLIANCE.md` (new), `README.md`, `SIMULATOR_GUIDE.md` | Stage-by-stage status, exact equations, documented ambiguities |

## v0.6: trigger-comparison experiment (protocol docs/PROTOCOL_v0.6.md)

Existing policies and the engine are unchanged. Default and earlier configs reproduce v0.1–v0.4 bit for bit (`audit/regression_check.py`).

| change | file | notes |
|---|---|---|
| arms A1–A7 and A2-reset | `tccer/policies/v06.py` (new); registered in `tccer/policies/__init__.py` | Shared rules (one attempt per epoch, cooldown 2, cap M, same selector and gate), backlog semantics for A6/A7, A5 Θ bounds [Θ₀/4, 4Θ₀]. Protocol constants are hard-coded, not configurable. |
| `v06_threshold`, `v06_kappa` config keys | `tccer/config.py` | Read only by the v06 arms; default None means never act |
| experiment scripts | `experiments/v06_common.py`, `calibrate_v06.py`, `run_v06.py`, `analyze_v06.py` (new) | Seed-isolation guards; SHA-256 manifest; eval refuses a dirty tree or a second run; policy-free episode labels; §5 metrics; §6 statistics and verdicts |
| tests | `tests/test_v06.py`, `tests/test_v06_pipeline.py` (new) | Arm mechanics, backlog, Static invariance, common traces, isolation, checksums, analysis functions, end-to-end mini pipeline |
| docs | `docs/PROTOCOL_v0.6.md`, `docs/LITERATURE_REVIEW.md`, `docs/KEY_PAPERS_VERIFICATION.md` | Protocol revision 3 (frozen at the implementation commit) |

**Calibration (commit `c103c29`):** τ = 0.5776, κ_E = 0.3777, κ_s = 0.2105; all 20 calibrated arm–cells feasible.

**Revision 4 (before held-out evaluation):** A6/A7 intended counts are drawn per seed from the tuning-seed distribution of A1–A5 realised counts (protocol §2.3a).
- `tccer/policies/v06.py`: `parse_pmf`, `draw_intended_count`, per-seed cap.
- `tccer/config.py`: new key `v06_count_pmf`.
- `experiments/amend_v06_rev4.py`: rewrites only the 8 A6/A7 configs and adds `control_count_pmf.csv`; every other checksum is verified unchanged.
- `run_v06.py`: `--out` for dry runs, never overwrites.
- `analyze_v06.py`: per-seed intended counts; exploratory count-balance analyses.
- `tests/test_v06_rev4.py`.
- Revision-3 protocol kept as `docs/PROTOCOL_v0.6_rev3.md`.
- Both dry runs archived in `archive/v0.6/`.

## v0.5: demonstration features (no algorithm change)

TCCE-R and the baselines are unchanged. Without a scenario file, the simulator reproduces v0.1–v0.4 bit for bit; this was checked on all archived columns with `python -m audit.regression_check`.

| change | file | notes |
|---|---|---|
| `scenario_file` config key | `tccer/config.py`, `tccer/network/scenario.py` (new), `tccer/sim/engine.py` | Custom nodes, potential/initial links, initial values, and scripted link fail/recover and region outages. Scripted failures are layered on the random ones and are identical for every strategy. Every input error is reported with the file and entry. |
| `n_scripted_down` column; `on_epoch` read-only observer hook | `tccer/sim/engine.py` | The hook is used by the visualizer and does not affect results. |
| `scenario_used.yaml` copied into each run folder | `experiments/run.py` | Provenance. The `--policies` help now states that TCCE-R is always simulated for budget matching. |
| `summary.txt` written automatically | `experiments/analyze.py` | Plain-ASCII summary table, paired comparisons, and notes (budget matching, `n/a` p-values, few-seed warning). The CSV outputs are unchanged. |
| network visualizer | `experiments/visualize.py` (new) | Initial topology plus a strategies × epochs snapshot grid; failed, in-setup, rewired-in and removed links each in a distinct colour **and** line style; `edge_states.csv` holds the raw data. |
| demo config fixed | `configs/v0.5/demo.yaml` (new) | Equal to `configs/v0.4/selected_d2.yaml`; replaces `configs/v0.4/main.yaml` (untuned weights) as the demo config. |
| example scenario | `examples/grid_scenario.yaml`, `examples/grid_scenario_config.yaml` | 4×4 grid with scripted outages that split the network. |
| archive regression script | `audit/regression_check.py` (new) | Re-runs every archived experiment into a scratch folder and compares. |
| config loader | `tccer/config.py` | Reads files as UTF-8, gives a clearer unknown-key message, and resolves `scenario_file` relative to the config. |
| tests 47 → 85 | `tests/test_scenario.py` (new) | See SIMULATOR_GUIDE §9. |
| docs | `SIMULATOR_GUIDE.md` | Beginner walkthrough, scenario format, policy-selection behaviour, visualizer. |

## v0.4: audit, fixes, bursty-failure experiment

**Code (all opt-in unless marked "always"):**

| change | file / function | why |
|---|---|---|
| `degree_basis: configured` | `core/mutations.py: degrees, _degree_ok`; `core/safety.py: SafetyGate.check` | **D1 fix.** The degree limit was checked on live links only. Failed and pending links still occupy ports, so repairs could push a node above `d_max`. In a bursty test scenario, 76/185 commits violated it under the old rule and 0 under the new one. |
| `feedback_after_setup: true` | `core/feedback.py: FeedbackEvaluator.evaluate` | **D2 fix.** The feedback "after" window ignored the link setup delay. At delay ≥ 3 (= H), a mutation was judged entirely before its new link existed. |
| `failed_link_value: if_up` | `core/mutations.py: generate_candidates` | A failed link was always the free choice to release in a rewire, which made reconfiguration nearly costless. It is now valued as if it were up. |
| spatial burst outages (`burst_rate`, `burst_radius`, `burst_min_len`, `burst_max_len`) | `network/events.py: FailureTrace`; `sim/engine.py` | Temporary, spatially correlated failures with recovery, for the v0.4 experiment. Uses a separate RNG stream `[seed, 4]`. |
| guard for zero initial disagreement (always) | `consensus/algorithm.py: run_epoch` | Division by zero gave NaN. This never occurred with random x(0). |
| new log columns (always; additive) | `core/selector.py`, `policies/base.py`, `sim/engine.py` | Log `budget`, `select_outcome`, the M components of the chosen mutation, `reconnect_possible` (side-effect-free dry run), `removed_failed_link` and `n_burst_down`. These make M, reconnection fairness and gate behaviour auditable. |
| `holm()` factored out (no numeric change) | `experiments/analyze.py` | So it can be tested. `paired_tests.csv` is verified identical. |
| new scripts | `experiments/report_v04.py`, `experiments/reproduce_v04.py` | Final aggregation, statistics and figures; a single reproduction command. |
| tests 28 → 47 | `tests/test_v04.py` | Independent gate oracle, bursts, D1/D2, edge cases, CSV/aggregation, Holm/CI, episodes. |

**Configuration:**
- `configs/v0.4/main.yaml`
- `configs/v0.4/base_d{0,2,4,8}.yaml`
- `configs/v0.4/selected_d*.yaml`, produced by tuning

**Docs:**
- `docs/PROTOCOL_v0.4.md` (committed before the run)
- `docs/AUDIT_v0.4.md`
- `SIMULATOR_GUIDE.md`
- `RESULTS_SUMMARY.md`

## v0.3: binding budget and reconfiguration cost

- Added `budget_on`, `link_setup_epochs`, `degree_fix`, with interim-state gate checks.
- **Fixed:**
  - no rewire candidates while disconnected;
  - wasted gate attempts on degree-infeasible candidates;
  - the gate rejecting a mutation if *any* node exceeded `d_max` (this had been present since v0.1).
- Two invalid runs are archived with notes, under `archive/v0.3_INVALID_*`.
- **Result:** reactive was better than TCCE-R on E and λ2. TCCE-R's earlier advantage over periodic disappeared after the fixes.

## v0.2: debt diagnostic

- Decomposed the stress terms: C was nearly binary and V negligible.
- Ran a pre-specified κ/weight sweep on tuning seeds and evaluated on held-out seeds.
- Added a Holm correction and a first-mutation-epoch metric.
- **Result:** reactive was better than TCCE-R; the adaptive θ had no effect.

## v0.1: prototype

- End-to-end nine-component pipeline, five baselines/ablations, CSV logging, plots, 22 tests.
