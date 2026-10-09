# Changelog

Every version is a git tag, and its results are archived under `archive/`. Model changes after v0.1 sit behind config flags whose defaults reproduce earlier versions. **The current code re-runs v0.1, v0.2 and v0.3 bit-identically on every archived column**; this was checked during the v0.4 audit.

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
