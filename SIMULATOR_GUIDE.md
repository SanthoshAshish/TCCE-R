# TCCE-R Simulator Guide (v0.5)

A discrete-time simulator for **TCCE-R** (resilience-debt driven topology–consensus co-evolution), with three baseline controllers. Python 3.11, NetworkX, NumPy/SciPy, pandas and matplotlib.

## 1. Install and check

```powershell
cd "E:\SEM5\CN\CN LAB PROJECT\tcce_r"
python -m venv .venv; .venv\Scripts\Activate.ps1      # optional
pip install -r requirements.txt
python -m pytest -q                                     # expected: all tests pass
```

Run every command from the `tcce_r` folder.

## 2. Beginner walkthrough: a complete experiment in four commands

This uses the example network in `examples/`: 16 nodes on a 4×4 grid with scripted outages.

```powershell
python -m experiments.run --config examples/grid_scenario_config.yaml --seeds 5 --policies static periodic reactive tccer --out results/grid_demo
python -m experiments.analyze results/grid_demo
python -m experiments.visualize --config examples/grid_scenario_config.yaml --seed 0 --epochs 0 8 17 25 --out results/grid_demo/network
notepad results/grid_demo/summary.txt
```

| step | what it does | files written |
|---|---|---|
| `run` | simulates each strategy on 5 seeds | `epochs.csv` (raw: one row per seed × strategy × epoch), `rounds.csv` (raw: one row per consensus round), `config_used.yaml`, `scenario_used.yaml` |
| `analyze` | compares the strategies | `summary.txt` (readable summary), `summary.csv` (mean ± 95% CI), `paired_tests.csv` (TCCE-R vs each baseline), `timeseries.png`, `summary_bars.png`, `tccer_trace.png` |
| `visualize` | draws the network | `network_initial.png`, `network_snapshots.png` (strategies × epochs), `edge_states.csv` (the data behind the pictures) |

**What to expect in this example.** The grid starts as a well-connected "ladder". The adaptive strategies rewire *during* the scripted outages, which has two costs:
- Some released links were only temporarily failed and would have come back.
- A requested replacement only works one epoch later.

As a result, in this example **all three adaptive strategies end up with higher consensus stress than the static network**. This is genuine simulator behaviour, not a bug. The example demonstrates the features; it is not an evaluation. The TCCE-R and reactive settings were tuned for the 40-node random network, not for this grid.

## 3. Other runs

| goal | command |
|---|---|
| demo on the seed-generated 40-node network (v0.4-selected settings) | `python -m experiments.run --config configs/v0.5/demo.yaml --seeds 5 --policies static periodic reactive tccer --out results/demo`, then `python -m experiments.analyze results/demo` and `python -m experiments.visualize --config configs/v0.5/demo.yaml --seed 0 --out results/demo/network` |
| reproduce the final v0.4 experiment | `python -m experiments.reproduce_v04` (about 35 min; rewrites `results/v0.4/` and `configs/v0.4/` with identical content; `archive/v0.4/` is never touched) |
| rebuild the v0.4 report from the raw CSVs | `python -m experiments.reproduce_v04 --stage report` (seconds) |
| check that every archived result still reproduces | `python -m audit.regression_check --out <scratch folder>` (about 12 min; reads `archive/`, never writes to it) |
| older versions | `git checkout v0.1` … `v0.4` |

Use `configs/v0.5/demo.yaml` for demos, **not** `configs/v0.4/main.yaml`. The latter keeps the untuned v0.1 debt weights.

### Which strategies run (`--policies`)

`experiments.run` options:
- `--policies`: any of `static`, `periodic`, `reactive`, `tccer`, `tccer_fixed`, `random`.
- `--seeds N` and `--seed-start S`: seeds S..S+N−1.
- `--no-rounds`: skip `rounds.csv`.
- `--unmatched`: no budget matching.

**TCCE-R is always simulated, even if you leave it out of `--policies`.**
- **Why:** for a fair comparison, every baseline may make at most as many topology changes as TCCE-R made on the same seed; periodic spreads its changes evenly. The runner therefore runs TCCE-R first to learn that number, and TCCE-R's rows appear in `epochs.csv`.
- **Exceptions:** `tccer_fixed` is an ablation and is not capped, and `--unmatched` removes the cap for a secondary analysis.

**Few seeds give no evidence.** With fewer than 5 seeds no p-values are computed (`n/a` in `summary.txt`). With only a handful of seeds, differences can point the opposite way from the 30-seed held-out result. Present `RESULTS_SUMMARY.md` as the result of record and any live run as an illustration.

## 4. Your own network and failures: scenario files

Add `scenario_file: my_scenario.yaml` to a config. A relative path is resolved against the config file's folder. Without this key the network is generated from the seed, exactly as in v0.1–v0.4.

```yaml
description: optional text
nodes:            [[0.1, 0.1], [0.5, 0.1], [0.9, 0.1], [0.5, 0.6]]   # (x, y) of each node; node index = list position
potential_links:  [[0, 1], [1, 2], [0, 3], [1, 3], [2, 3], [0, 2]]   # links that may ever exist (optional;
                                                                    #   default: pairs closer than radio_range)
initial_links:    [[0, 1], [1, 2], [1, 3], [2, 3]]                  # working at the start; subset of potential_links
initial_values:   [0.0, 1.0, 0.5, 0.2]       # optional: one value per node (every epoch), or one list per epoch
failure_events:                              # optional; 0-based epochs, applied at the start of the epoch
  - {epoch: 5,  link: [1, 3], action: fail}          # down from epoch 5 ...
  - {epoch: 9,  link: [1, 3], action: recover}       # ... up again from epoch 9
  - {epoch: 12, region: {center: [0.7, 0.2], radius: 0.25}, duration: 3}   # every link whose midpoint is in
                                                                           #   the circle: down epochs 12-14
```

Rules:
- **Layering.** Scripted failures are added on top of the random failure processes: a link is down if either says so. Every strategy receives the same scripted events.
- **Recovery.** `recover` only ends a scripted `fail`; it does not repair a link that a random process broke.
- **Purely scripted scenario.** Set `p_transient`, `p_fail` and `burst_rate` to 0 in the config.
- **Ignored settings.** `n_nodes`, `init_radius` and, when `potential_links` is given, `radio_range` are ignored, because the scenario defines the network.

Errors give the file name and the exact entry, for example:
- `failure_events[3]: link [0, 1] recovers at epoch 4 without an earlier scripted 'fail'`
- `initial_links[2]: node index 7 does not exist (valid indices are 0..3)`

The loader also rejects:
- duplicate links and self-links;
- links outside `potential_links`;
- epochs outside 0..epochs−1;
- duplicate or conflicting events for one link;
- regions that contain no link;
- wrong-length `initial_values`;
- unknown keys.

The run copies the scenario into the output folder (`scenario_used.yaml`), and `epochs.csv` gains a column `n_scripted_down`.

## 5. Network pictures (`experiments.visualize`)

`python -m experiments.visualize --config <cfg> --seed 0 --epochs 0 10 20 --policies static reactive tccer --out <folder>`

- **What it runs.** It re-runs that one seed with the same budget matching as `experiments.run`, so the pictures show exactly the runs in `epochs.csv`. A test checks that the link counts match. The output is deterministic.
- **`network_initial.png`.** Initial links (solid) and possible links (faint dotted).
- **`network_snapshots.png`.** One row per strategy and one column per requested epoch; every strategy faces the same failures. Link styles:

  | link status | style |
  |---|---|
  | active (working) | solid grey |
  | failed | red dashed |
  | in setup (requested, not usable yet) | blue dash-dot |
  | rewired in since the previous column | thick green |
  | removed since the previous column | orange dotted |

  Nodes cut off from the largest component are hollow orange squares; active scripted failure regions are shaded red circles. Each panel title gives the epoch, the consensus stress E, the number of components and the number of working links.
- **`edge_states.csv`.** The status of every configured link at each snapshot epoch.

## 6. Architecture: the professor's nine components in the code

```
for epoch k = 0..epochs-1:
  (1) Dynamic Network State     network/state.py, events.py, scenario.py   failures: transient, background, bursts, scripted
  (2) Consensus Monitor         consensus/algorithm.py, monitor.py     Metropolis rounds from x(0) -> E
      resilience metrics        metrics/resilience.py                  λ2 (= R), components, C (bridges), V
  (3) Resilience Debt           core/debt.py                           D_k = max(0, D_{k-1} + w·(E,C,V) − κ)
  (4) Adaptive Trigger          core/trigger.py, core/threshold.py     fire if D > Θ and cooldown elapsed; Θ adapts
  (5) Coupling Evaluator        core/coupling.py                       M = (Δcomponents, Δλ2 est., Δbridges, length)
  (6) Safety Gate               core/safety.py                         connectivity, λ2 floor R_min, degree, budget, cooldown, interim state
  (7) Mutation Selector         core/selector.py, core/mutations.py    add (budget slack) or rewire (budget full)
  (8) Reconfigured Network      NetworkState.apply                     removal now, new link usable after setup delay
  (9) Feedback Loop             core/feedback.py, policies/tccer.py    mean E before vs after -> Θ ← Θ(1−β) or Θ(1+α)
```

Baselines (`policies/baselines.py`) share components (5)–(8) with TCCE-R and differ only in *when* they act:
- **static** never acts.
- **periodic** acts on a fixed schedule.
- **reactive** acts when the current epoch's E exceeds a fixed threshold.

### Variables

| symbol | name in code / CSV | meaning | status |
|---|---|---|---|
| E | `E_hat` | consensus stress: 0 = reached ε, 1 = no progress | implemented, logged |
| C | `C` | 1 if disconnected, otherwise the fraction of links that are bridges | implemented, logged; nearly binary in practice |
| V | `V` | environmental link-state changes over 3 epochs / configured links | implemented, logged; small in practice |
| D | `debt` | CUSUM resilience debt | implemented, logged |
| Θ | `theta` | adaptive trigger threshold | implemented, logged |
| M | `M_dcomp`, `M_gain`, `M_dbridges`, `M_length` | coupling score of the chosen mutation, as a **lexicographic vector** (not a scalar ratio; design decision D7) | implemented, logged per mutation |
| R | `lambda2` | network resilience = algebraic connectivity; the gate floor R_min is `lambda2_min` | implemented, logged |
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

## 7. Key configuration

| group | keys |
|---|---|
| network | `n_nodes`, `init_radius`, `radio_range`, `scenario_file` (v0.5) |
| consensus | `epochs`, `rounds_per_epoch`, `eps` |
| failures | `p_transient`, `p_fail`, `p_repair`, `burst_rate`, `burst_radius`, `burst_min_len`, `burst_max_len` |
| debt / trigger | `w_E`, `w_C`, `w_V`, `kappa`, `theta0`, `theta_min`, `theta_max`, `alpha`, `beta`, `trigger_cooldown`, `feedback_horizon` |
| gate / budget | `lambda2_min` (R_min), `d_max`, `edge_budget_frac`, `budget_on`, `edge_cooldown`, `link_setup_epochs` |
| audit fixes (v0.3/v0.4; off by default for reproducibility) | `degree_fix`, `degree_basis`, `feedback_after_setup`, `failed_link_value` |
| baselines | `reactive_threshold`, `period`, `mutation_cap` |

A misspelled key is rejected with an error naming it.

Seeds: the graph, failures, initial values and policy randomness each come from a separate stream, `default_rng([seed, i])`. For a given seed, every strategy sees identical conditions; this is tested.

## 8. Reading the outputs

- **`epochs.csv`**: one row per (seed, policy, epoch). It holds every variable above, plus:
  - `components`, `live_edges`, `configured_edges`, `budget`, `pending_links`, `n_down_potential`, `n_burst_down`, `n_scripted_down`
  - `triggered`, `feedback`, `mutation`, `mutation_kind`, `n_mutations`, `gate_rejections` (cumulative)
  - `select_outcome` (`mutated` / `no_candidates` / `all_rejected` / `capped`), `reconnect_possible`, `removed_failed_link`
- **`summary.txt`**: the readable version of `summary.csv` and `paired_tests.csv`, with notes.
- **`results/v0.4/report/`** (the final experiment):
  - `per_seed_metrics.csv` is the unit of analysis.
  - `summary.csv` gives means and 95% CIs.
  - `paired_tests.csv` gives Wilcoxon + Holm results, verdicts and practical-significance flags.
  - `fig1…fig7` are the figures.

## 9. Tests

`python -m pytest -q` runs these suites:
- `tests/test_consensus.py`: Metropolis weights, mean preservation, convergence rate = SLEM.
- `tests/test_resilience.py`: λ2 closed forms, vulnerability.
- `tests/test_controller.py`: debt, trigger, threshold, feedback, gate, selector.
- `tests/test_engine.py`: determinism, common random numbers.
- `tests/test_binding_budget.py`: strict budget, setup delay, interim gate, reconnection.
- `tests/test_v04.py`:
  - the audit fixes and bursts;
  - a safety-gate check against an independent NetworkX oracle;
  - the no-candidate edge case;
  - CSV output and aggregation, Holm and CI values.
- `tests/test_scenario.py`:
  - scenario files: exact event epochs, region durations, identical traces across strategies, purely scripted runs, and 20 invalid-input cases;
  - default runs identical to the archived v0.4 rows;
  - the demo config;
  - an end-to-end run → analyze → visualize, including a check that the pictures match the CSV.
