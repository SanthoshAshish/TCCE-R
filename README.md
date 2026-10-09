# TCCE-R simulator (v0.5)

Resilience-debt driven topology–consensus co-evolution. Python + NetworkX + NumPy.

**Start here:**
- [`SIMULATOR_GUIDE.md`](SIMULATOR_GUIDE.md): architecture, commands, outputs
- [`RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md): final v0.4 results
- [`docs/AUDIT_v0.4.md`](docs/AUDIT_v0.4.md): audit findings
- [`docs/PROTOCOL_v0.4.md`](docs/PROTOCOL_v0.4.md): experiment protocol
- [`CHANGELOG.md`](CHANGELOG.md): version history

| version | git tag | report | results |
|---|---|---|---|
| v0.1 prototype | `v0.1` | this README (bottom) | `archive/v0.1/` |
| v0.2 debt diagnostic + sweep | `v0.2` | [`DIAGNOSTIC_v0.2.md`](DIAGNOSTIC_v0.2.md) | `archive/v0.2/` |
| v0.3 binding budget + reconfiguration cost | `v0.3` | [`RESULTS_v0.3.md`](RESULTS_v0.3.md) | `archive/v0.3/` |
| v0.4 audit + bursty failures × delay {0,2,4,8} | `v0.4` | [`RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md) | `archive/v0.4/` |
| v0.5 scenario files, network pictures, summary.txt, demo config (no algorithm change) | `v0.5` | [`SIMULATOR_GUIDE.md`](SIMULATOR_GUIDE.md) §2–5 | `archive/v0.5/` (example run) |

**Current status:** in every pre-specified held-out condition tested (v0.2–v0.4), TCCE-R is significantly worse than a simple reactive baseline on consensus error and λ2, at an equal mutation budget. There is no supported difference in disconnection fraction. No superiority claim is supported.

## Setup and run (Windows PowerShell, from this folder)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m pytest -q                                                        # 85 tests
python -m experiments.run --config configs/default.yaml --seeds 20 --out results/default
python -m experiments.analyze results/default

# v0.2 diagnostic: sweep on tuning seeds 100-119, then held-out evaluation on seeds 1000-1029
python -m experiments.sweep --out results/sweep
python -m experiments.run --config configs/v0.2_selected.yaml --seed-start 1000 --seeds 30 --no-rounds --out results/eval_v0.2_selected
python -m experiments.analyze results/eval_v0.2_selected

# v0.4 final experiment (tuning -> held-out evaluation -> report)
python -m experiments.reproduce_v04

# v0.3 binding-budget experiment: see RESULTS_v0.3.md, section 3, for the full command list
python -m experiments.sweep --config configs/v0.3_binding_base.yaml --out results/sweep_v0.3
python -m experiments.run --config configs/v0.3_selected.yaml --seed-start 4000 --seeds 30 --no-rounds --policies static periodic reactive tccer tccer_fixed --out results/eval_v0.3_matched
python -m experiments.analyze results/eval_v0.3_matched
```

The default config runs 20 seeds × 6 policies in about 25 s. Add `--no-rounds` to skip the large per-round CSV.

Outputs in `results/default/`:

| file | content |
|---|---|
| `epochs.csv` | one row per (seed, policy, epoch): E, final error, convergence round, λ2, components, C, V, debt, θ, trigger, mutation, feedback, gate rejections |
| `rounds.csv` | one row per consensus round: disagreement e(t) |
| `summary.csv` | per-policy mean ± 95% CI over seeds |
| `paired_tests.csv` | paired Wilcoxon signed-rank, TCCE-R vs each baseline (unadjusted p-values) |
| `timeseries.png`, `summary_bars.png`, `tccer_trace.png` | plots |
| `config_used.yaml` | exact config used for the run |

## Component map (professor's 9 components)

| # | Component | Code | Status |
|---|---|---|---|
| 1 | Dynamic Network State | `tccer/network/` | RGG, Bernoulli transient + permanent fail/repair |
| 2 | Distributed Consensus Monitor | `tccer/consensus/` | Metropolis average consensus, fresh x(0) per epoch |
| 3 | Resilience Debt Estimator | `tccer/core/debt.py` | CUSUM over s = w_E·E + w_C·C + w_V·V |
| 4 | Adaptive Mutation Trigger | `tccer/core/trigger.py`, `threshold.py` | D > θ, cooldown, multiplicative θ update |
| 5 | Coupling Evaluator | `tccer/core/coupling.py` | first-order Δλ2, Δcomponents, Δbridges, link length |
| 6 | Safety Gate | `tccer/core/safety.py` | connectivity, λ2 floor, degree, edge budget, edge cooldown |
| 7 | Mutation Selector | `tccer/core/selector.py`, `mutations.py` | lexicographic; add or rewire |
| 8 | Reconfigured Network | `NetworkState.apply` | — |
| 9 | Feedback Loop | `tccer/core/feedback.py` + `sim/engine.py` | before/after mean E over H epochs → θ |

## Established vs proposed

**Established:**
- Metropolis–Hastings consensus weights (Xiao & Boyd 2004)
- λ2 / Fiedler vector (Fiedler 1973)
- first-order Δλ2 ≈ (f_i − f_j)² (Ghosh & Boyd 2006)
- bridges
- random geometric graphs
- CUSUM accumulation (Page 1954)
- Wilcoxon signed-rank test

**Proposed (ours, unvalidated):**
- the stress terms E/C/V and their weights
- using CUSUM debt to trigger topology mutation
- the θ adaptation rule
- the success criterion
- the lexicographic ordering (components → gain → bridges → length)

Verify all citations during the literature review.

## Definitions used

- `E = 1 − min(1, ln e(T) / ln ε)`: the fraction of the required log-error decay not achieved this epoch. This replaced `conv_round/T`, which saturated at 1.
- `C = 1` if disconnected, otherwise the fraction of links that are bridges.
- `V = (environmental link-state changes in the last w epochs) / configured links`. Our own mutations are excluded.
- `D_k = max(0, D_{k−1} + s_k − κ)`, reset to 0 after a mutation is applied.
- Success means the mean E over the H epochs after a mutation is lower than over the H epochs before it.

## Fairness controls

- Common random numbers: the graph, failure draws and x(0) are pre-generated from the seed, so they are identical for every policy (tested).
- All policies share the candidate set, safety gate and edge budget.
- Budget matching: baselines get `mutation_cap = M_TCCE-R` per seed; periodic and random space their M mutations evenly.

## v0.1 first results (seeds 0–19, default config). Superseded by DIAGNOSTIC_v0.2.md

| policy | E (lower better) | fraction of epochs disconnected | λ2 | mutations |
|---|---|---|---|---|
| static | 0.441 ± 0.051 | 0.263 ± 0.112 | 0.058 | 0 |
| random | 0.431 ± 0.049 | 0.231 ± 0.093 | 0.062 | 1.70 |
| periodic (greedy) | 0.404 ± 0.043 | 0.169 ± 0.072 | 0.074 | 1.70 |
| **reactive (fixed E threshold)** | **0.370 ± 0.045** | **0.089 ± 0.051** | **0.092** | 1.85 |
| tccer | 0.403 ± 0.049 | 0.107 ± 0.043 | 0.075 | 1.85 |
| tccer_fixed (no θ adaptation) | 0.403 ± 0.049 | 0.106 ± 0.041 | 0.075 | 1.70 |

What this does and does not show:
- With an equal number of mutations, TCCE-R has fewer disconnected epochs than static, random and periodic (paired Wilcoxon p < 0.05, unadjusted).
- **The simple reactive baseline beats TCCE-R** on E and λ2 (p ≈ 0.001). The disconnection difference is not significant (p = 0.14).
- **Adaptive θ has no measurable effect.** With about 2 mutations per run, θ barely updates.
- In the TCCE-R trace, debt only accumulates in disconnected epochs (C = 1 dominates the stress). In this regime TCCE-R behaves like a delayed disconnection detector.
- Nothing here supports a claim that TCCE-R improves performance.

## Not implemented / incomplete

- Targeted attacks, Gilbert–Elliott bursty failures, trust, traffic and load (out of v1 scope).
- Hyperparameter tuning on held-out seeds, and sensitivity sweeps (κ, weights, θ bounds, p_fail, n). The current values were set by a quick look at one smoke run.
- Multiple scenarios (network size, failure rate) and multiple-comparison correction.
- Ablations: no-V term, λ2-only selection.
- A pure "remove" mutation (only add and rewire exist).
- The success criterion is noisy (risk R7): environmental changes are not separated from mutation effects.
- The controller is centralized: λ2 and the Fiedler vector are computed globally.
- The `test_selector_prefers_reconnecting_edge` test is conditional and can pass vacuously.
