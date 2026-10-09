# TCCE-R Simulator Guide (v0.4)

A discrete-time simulator for **TCCE-R** (resilience-debt driven topology–consensus co-evolution), with three baseline controllers. Python 3.11, NetworkX, NumPy/SciPy, pandas and matplotlib.

## 1. Install and check

```powershell
cd tcce_r
python -m venv .venv; .venv\Scripts\Activate.ps1      # optional
pip install -r requirements.txt
python -m pytest -q                                     # expected: all tests pass
```

## 2. Run something

| goal | command | output |
|---|---|---|
| one quick comparison (3 seeds, all strategies) | `python -m experiments.run --config configs/v0.4/main.yaml --seeds 3 --policies static periodic reactive tccer --out results/demo` then `python -m experiments.analyze results/demo` | `results/demo/epochs.csv`, `rounds.csv`, `summary.csv`, `paired_tests.csv`, plots |
| reproduce the final v0.4 experiment | `python -m experiments.reproduce_v04` (about 15–25 min) | `configs/v0.4/selected_d*.yaml`, `results/v0.4/` |
| only rebuild the report from existing raw CSVs | `python -m experiments.reproduce_v04 --stage report` | `results/v0.4/report/` |
| older versions | `git checkout v0.1` / `v0.2` / `v0.3` (each is also bit-reproducible with the current code and its own config; see CHANGELOG) | |

`experiments.run` options:
- `--seeds N` and `--seed-start S`: the seeds are S..S+N−1.
- `--policies ...`: choose from static, periodic, reactive, tccer, tccer_fixed, random.
- `--no-rounds`: skip the large per-round CSV.
- `--unmatched`: baselines are not budget-matched.

## 3. Architecture: the professor's nine components in the code

```
for epoch k = 0..79:
  (1) Dynamic Network State     network/state.py, network/events.py   failures: transient, background on/off, spatial bursts
  (2) Consensus Monitor         consensus/algorithm.py, monitor.py     60 Metropolis rounds from a fresh x(0) -> E
      resilience metrics        metrics/resilience.py                  λ2 (= R), components, C (bridges), V
  (3) Resilience Debt           core/debt.py                           D_k = max(0, D_{k-1} + w·(E,C,V) − κ)
  (4) Adaptive Trigger          core/trigger.py, core/threshold.py     fire if D > Θ and cooldown elapsed; Θ adapts
  (5) Coupling Evaluator        core/coupling.py                       M = (Δcomponents, Δλ2 est., Δbridges, length)
  (6) Safety Gate               core/safety.py                         connectivity, λ2 floor R_min, degree, budget, cooldown, interim state
  (7) Mutation Selector         core/selector.py, core/mutations.py    add (budget slack) or rewire (budget full)
  (8) Reconfigured Network      NetworkState.apply                     removal now, new link usable after setup delay
  (9) Feedback Loop             core/feedback.py, policies/tccer.py    mean E before vs after -> Θ ← Θ(1−β) or Θ(1+α)
```

Baselines live in `policies/baselines.py`. They share (5)–(8) with TCCE-R and differ only in *when* they act:
- **static** never mutates.
- **periodic** acts on a fixed schedule.
- **reactive** acts when the current epoch's E exceeds a fixed threshold.

### Variables

| symbol | name in code / CSV | meaning | status |
|---|---|---|---|
| E | `E_hat` | consensus stress, 0 = reached ε, 1 = no progress | implemented, logged |
| C | `C` | 1 if disconnected, otherwise fraction of links that are bridges | implemented, logged; nearly binary in practice |
| V | `V` | environmental link-state changes over 3 epochs / configured links | implemented, logged; small in practice |
| D | `debt` | CUSUM resilience debt | implemented, logged |
| Θ | `theta` | adaptive trigger threshold | implemented, logged |
| M | `M_dcomp`, `M_gain`, `M_dbridges`, `M_length` | coupling score of the chosen mutation, as a **lexicographic vector** (not a scalar ratio; design decision D7) | implemented, logged per mutation |
| R | `lambda2` | network resilience = algebraic connectivity; the gate's floor R_min is `lambda2_min` | implemented, logged |
| trust/uncertainty, traffic, node load | — | **not implemented** (deferred since v0.1) | absent |

### Established vs proposed parts

**Established:**
- Metropolis consensus weights
- λ2 and the Fiedler first-order estimate
- bridges
- the CUSUM recursion
- random geometric graphs
- on/off failure processes
- the Wilcoxon test and Holm correction

**Proposed (ours, unvalidated):**
- the E/C/V stress and its weights
- using CUSUM debt to trigger topology mutation
- the Θ update rule
- the success criterion
- the lexicographic M

## 4. Key configuration (`configs/v0.4/main.yaml`)

| group | keys |
|---|---|
| network | `n_nodes`, `init_radius`, `radio_range` |
| consensus | `epochs`, `rounds_per_epoch`, `eps` |
| failures | `p_transient`, `p_fail`, `p_repair`, `burst_rate`, `burst_radius`, `burst_min_len`, `burst_max_len` |
| debt / trigger | `w_E`, `w_C`, `w_V`, `kappa`, `theta0`, `theta_min`, `theta_max`, `alpha`, `beta`, `trigger_cooldown`, `feedback_horizon` |
| gate / budget | `lambda2_min` (R_min), `d_max`, `edge_budget_frac`, `budget_on`, `edge_cooldown`, `link_setup_epochs` |
| audit fixes (v0.3/v0.4; off by default for reproducibility) | `degree_fix`, `degree_basis`, `feedback_after_setup`, `failed_link_value` |
| baselines | `reactive_threshold`, `period`, `mutation_cap` |

Seeds: the graph, failures, initial values and policy randomness each come from a separate stream, `default_rng([seed, i])`. Every strategy therefore sees identical conditions for a given seed. This is tested.

## 5. Reading the outputs

- **`epochs.csv`**: one row per (seed, policy, epoch). It holds every variable above, plus:
  - `components`, `live_edges`, `configured_edges`, `budget`, `pending_links`, `n_down_potential`, `n_burst_down`
  - `triggered`, `feedback`, `mutation`, `mutation_kind`, `n_mutations`, `gate_rejections` (cumulative)
  - `select_outcome` (`mutated` / `no_candidates` / `all_rejected` / `capped`), `reconnect_possible`, `removed_failed_link`
- **`results/v0.4/report/`**:
  - `per_seed_metrics.csv` is the unit of analysis.
  - `summary.csv` gives the mean and 95% CI.
  - `paired_tests.csv` gives the Wilcoxon tests with Holm adjustment, verdicts, and practical-significance flags.
  - `fig1…fig7` are the figures.

## 6. Tests

`python -m pytest -q` runs these suites:
- `tests/test_consensus.py`: Metropolis weights, mean preservation, convergence rate = SLEM.
- `tests/test_resilience.py`: λ2 closed forms, vulnerability.
- `tests/test_controller.py`: debt, trigger, threshold, feedback, gate, selector.
- `tests/test_engine.py`: determinism, common random numbers.
- `tests/test_binding_budget.py`: strict budget, setup delay, interim gate, reconnection.
- `tests/test_v04.py`:
  - the audit fixes and bursts;
  - a safety-gate check against an independent NetworkX oracle (both accepting and rejecting);
  - the no-candidate edge case;
  - CSV output and aggregation, Holm and CI values.
