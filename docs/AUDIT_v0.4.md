# v0.4 audit: architecture, mathematics, implementation

I audited the v0.3 code (tag `v0.3`) file by file. Each finding below was checked against the code with a reproduction, not taken from earlier reports.

## 1. Execution flow (actual, from `tccer/sim/engine.py`)

```
setup:  RGG positions/links [seed,0] -> NetworkState; FailureTrace (transient, background, bursts [seed,1],[seed,4]);
        x(0) for every epoch [seed,2]; policy RNG [seed,3]; MutationPipeline (budget, gate, cooldown table)
epoch k:
  1  background on/off update; down = background | burst[k]; V input = state flips among configured links
  2  60 Metropolis rounds over live links, minus per-round transient outages -> e(t) -> E
  3  λ2 (0 if disconnected), components, C, V; reconnect_possible (dry run, logging only)
  4  policy.decide(k, obs, state)
       TCCE-R: feedback on old mutations -> Θ; D update; trigger (D > Θ, cooldown); selector
       reactive: E > thr; periodic: schedule; static: none
       selector: candidates (add | rewire) -> M ranking -> gate (<= 30 tries) -> mutation | None
  5  apply: configured updated now; new link usable from k+1+setup; cooldown table updated
  6  log one CSV row
```

The mutation is chosen at the end of epoch k and first affects epoch k+1. No information from epoch k+1 is used at epoch k.

## 2. Component and variable status

| # | component | status | notes |
|---|---|---|---|
| 1 | Dynamic Network State | implemented | Transient, background on/off and (v0.4) spatial bursts. Traffic and node load are **absent**. |
| 2 | Consensus Monitor | implemented | Metropolis average consensus; E, final error, convergence round and rate logged. Trust/uncertainty is **absent**. |
| 3 | Resilience Debt Estimator | implemented | CUSUM. C nearly binary, V small (see issues A1, A2). |
| 4 | Adaptive Mutation Trigger | implemented | D > Θ with cooldown; Θ multiplicative and clipped. |
| 5 | Coupling Evaluator | implemented as a **lexicographic vector**, not a scalar ratio | Chosen in the design phase (D7). Components are now logged as `M_*`. |
| 6 | Safety Gate | implemented | Defect D1 fixed (opt-in). Matches an independent oracle on 300 random candidates. |
| 7 | Mutation Selector | implemented | Add or rewire; when disconnected, only failed links may be released. |
| 8 | Reconfigured Network | implemented | Break-before-make setup delay. |
| 9 | Feedback Loop | implemented | Defect D2 fixed (opt-in); success signal still noisy (A3). |

| variable | implemented as | logged |
|---|---|---|
| E | `1 − min(1, ln e(T)/ln ε)` | `E_hat` |
| C | 1 if disconnected, otherwise bridge fraction | `C` |
| V | windowed flip count / configured links | `V` |
| D | CUSUM | `debt` |
| Θ | adaptive threshold | `theta` |
| M | (Δcomponents, Δλ2 first-order, Δbridges, length) | `M_dcomp`, `M_gain`, `M_dbridges`, `M_length` (v0.4) |
| R | λ2 (algebraic connectivity); R_min = `lambda2_min` | `lambda2` |

**Architectural gaps:**
- There is no scalar M; the vector form was chosen in the design phase.
- R is not a separate quantity; it is λ2.
- Trust, traffic and load are not implemented.
- The controller is centralized, because it uses the global Fiedler vector.

## 3. Issues

Each issue lists: where it lives, a reproduction, the impact, the fix, and the regression test.

### Defects fixed in v0.4 (opt-in flags; defaults keep v0.1–v0.3 reproducible)

**D1. The degree limit ignored failed and pending links.**
- **Where:** `core/safety.py: SafetyGate.check`; `core/mutations.py: _degree_ok`.
- **Reproduction:**
  - `audit/repro_v03_defects.py`: 3 of 457 mutations in the v0.3 held-out configuration gave a node more configured links than `d_max`.
  - In a bursty scenario with `d_max=5`, the old rule allowed 76 of 185 commits above `d_max`.
- **Impact:** after repairs or link setup, a node could exceed its port limit. The effect was small in v0.3 and larger under bursts.
- **Fix:** `degree_basis: configured`.
- **Tests:** `test_degree_basis_configured_counts_failed_links`, `test_configured_degree_never_raised_above_dmax_in_simulation`.

**D2. The feedback window ignored the setup delay.**
- **Where:** `core/feedback.py: FeedbackEvaluator.evaluate`.
- **Reproduction:** with delay 2 and H = 3, two of the three "after" epochs come before the new link is usable. With delay ≥ 3, all of them do.
- **Impact:** Θ was updated from evidence that could not reflect the mutation. In v0.3 (delay 2) this biased feedback towards "failure".
- **Fix:** `feedback_after_setup: true`.
- **Test:** `test_feedback_waits_for_link_setup`.

**D3. Failed links were free to release.**
- **Where:** `core/mutations.py: generate_candidates`.
- **Reproduction:** `test_failed_link_value_if_up_does_not_make_failed_links_free`. Under v0.3, a valuable failed link is always released first.
- **Impact:** reconfiguration was almost costless, which favours eager strategies. This was flagged in v0.3 as the likely reason reactive won.
- **Fix:** `failed_link_value: if_up`.
- **Test:** the same one.

**D4. NaN when x(0) is already in consensus.**
- **Where:** `consensus/algorithm.py: run_epoch`.
- **Impact:** none observed, because x(0) is random.
- **Fix:** a guard, always on.
- **Test:** `test_constant_initial_state_gives_zero_error_not_nan`.

**D5. Logging gaps.**
- **Where:** `sim/engine.py`.
- **Impact:** M, the budget, why a selection failed, and whether reconnection was possible could not be audited.
- **Fix:** additive CSV columns.
- **Tests:** `test_run_writes_csv_and_analysis_aggregates`, `test_can_reconnect_has_no_side_effects`.

### Previously reported issues, re-verified

| # | issue | verified now? | evidence | action |
|---|---|---|---|---|
| A1 | C nearly binary | **yes** | Static, tuning seeds, v0.4 environment: C averages 0.033 when connected and is exactly 1 when disconnected (`audit/calibrate_bursts.py`). | Not changed, because that would alter the model's definition. The selected configurations put w_C = 0 in every delay condition (see RESULTS_SUMMARY). A graded C, for example 1 − (largest-component share), is future work. |
| A2 | V tiny | **yes, though less so under bursts** | V mean 0.06, p90 0.15 under the v0.4 environment, vs 0.05 / 0.09 before. | Not changed (definition). |
| A3 | Θ adaptation without effect | re-tested in v0.4 | TCCE-R vs fixed-Θ comparison at four delays (RESULTS_SUMMARY). | D2 fixed first so the test is fair. |
| A4 | TCCE-R loses to reactive | re-tested in v0.4 | Primary hypothesis (RESULTS_SUMMARY). | Investigated, not forced. |
| A5 | degree-check defect | old "any node" bug fixed in v0.3 (`degree_fix`); **related defect D1 found and fixed** | see D1 | — |
| A6 | no reconnection under a strict budget | the v0.3 fix holds | `test_strict_budget_can_reconnect_disconnected_graph`, `test_bursty_runs_reconnect_when_possible`; per-epoch `reconnect_possible` logged in all v0.4 runs | — |
| A7 | TCCE-R > periodic vanished after the fix | re-tested in v0.4 | secondary tests | — |

### Checked and found correct (no change)

- **Consensus:** Metropolis W is symmetric and doubly stochastic, the step equals W·x, the mean is preserved under failures, and the empirical rate equals the SLEM (tests).
- **Resilience metrics:** λ2 matches closed forms for path, cycle and complete graphs, and is 0 when disconnected.
- **CUSUM:** the recursion stays at 0 below κ, grows by (s − κ) per epoch under a step, resets on repayment, and decays monotonically to 0 afterwards.
- **Θ:** clipped to [θ_min, θ_max].
- **Trigger:** cooldown counted from the last *successful* mutation. A firing that finds no valid move does not repay debt, so the trigger re-fires next epoch. This is intended.
- **Safety gate:** agrees with an independent NetworkX oracle on 300 random add/remove/rewire candidates, both accepting and rejecting (`test_gate_matches_independent_oracle_on_random_candidates`).
- **Setup delay:** links are unusable until `ready_at` and the interim state is gate-checked (tests).
- **Common random numbers:** the failure trace is identical across policies, including bursts (tests).
- **Determinism:** the same seed gives identical CSVs, and v0.1–v0.3 re-run identically.
- **Statistics:** the t-based CI and the Holm step-down procedure match known values (tests). Wilcoxon is paired over seeds.

### Known limitations kept (not defects)

- While disconnected, the rewire releases the lowest-index failed link, because the Fiedler vector is undefined. This is an arbitrary but policy-independent tie-break.
- If a periodic slot finds no valid mutation, that mutation is lost. Budget matching is therefore checked and reported per seed.
- The first-order Δλ2 estimate is unreliable when λ2 is a repeated eigenvalue. The gate always checks the exact λ2.
- The success criterion compares E before and after a mutation, and the environment changes over the same window.
