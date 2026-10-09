# Diagnostic report: why TCCE-R loses to the reactive baseline (v0.2)

v0.1 is preserved as git tag `v0.1`; its results are in `archive/v0.1/`.
Code changes in v0.2 are limited to the analysis side:
- `experiments/sweep.py` (new)
- `experiments/analyze.py`: adds first-mutation epoch and Holm-adjusted p-values

The simulator and the policies are unchanged.

## Seed protocol

| seeds | use |
|---|---|
| 0–19 | v0.1 results and the stress diagnosis below. No tuning. |
| 100–119 | Tuning sweep only |
| 1000–1029 | Final evaluation, run once after the configuration was selected |

Within any seed, every policy gets the same graph, failure trace and x(0). This is tested in `test_failure_trace_is_policy_independent`.

## 1. How E, C, V and D are computed

| term | definition | range in practice (static policy, seeds 0–19) |
|---|---|---|
| E | `1 − min(1, ln e(T) / ln ε)` | connected: mean 0.39 (p90 0.61); disconnected: mean 0.58 |
| C | 1 if disconnected, otherwise bridges / links | connected: mean **0.042**; disconnected: **exactly 1.0** |
| V | environmental link changes over the last 3 epochs / configured links | mean 0.05, max 0.17 |
| s | `w_E·E + w_C·C + w_V·V` (v0.1: 0.5 / 0.3 / 0.2) | connected: mean 0.22; disconnected: mean 0.60 |
| D | `max(0, D + s − κ)`, κ = 0.30; reset to 0 after a mutation | |

Share of stress above κ (v0.1): 19.8% of connected epochs and 100% of disconnected epochs.

## 2. Why E and V contribute little

- **C is effectively binary.** Its weighted contribution is 0.013 when connected and 0.300 when disconnected. That jump alone pushes s above κ, so debt mostly measures disconnection.
- **V is a near-constant offset.** It is normalized by about 96 configured links, while only about 1.7 link changes happen per epoch. Its weighted contribution is 0.010 ± 0.005. It cannot reach the top of its [0,1] range, and it varies too little to trigger anything.
- **E is the only informative term, but κ masks it.** With w_E = 0.5 and C, V ≈ 0, debt grows only when E > 0.6. That happens in about the top 10–20% of connected epochs. E is also correlated with disconnection (r = 0.44), so even the E term mostly fires in disconnected epochs.
- **CUSUM delays detection by design.** D must accumulate past θ = 1, which takes several epochs of excess stress. The reactive baseline fires on the first epoch with E > threshold.
- **Adaptive θ has almost nothing to learn from.** There are about 2–4 mutations per run, so only about 2–4 θ updates.

## 3. A confound found during diagnosis: mutation timing

The edge budget never binds: the budget averages 112.5 links and about 91 are live. **All mutations in all policies were additions**; the rewire path was never exercised. An added link stays useful until it fails. So with equal mutation counts, the policy that spends its budget earlier gets better time-averaged metrics.

| (held-out, v0.2 config) | mean first-mutation epoch |
|---|---|
| reactive | 17.9 |
| TCCE-R | 22.1 |

In v0.1, the median mutation epoch was 9 for reactive and 33 for TCCE-R. These experiments cannot separate "better timing" from "earlier timing". The reactive baseline also averages about 1 more live link over time, 92.7 vs 91.7, for the same reason.

## 4. Sweep design (fixed before running)

- **Weights:**
  - W0_v01 (0.5, 0.3, 0.2)
  - W1_E (1, 0, 0)
  - W2_EC (0.7, 0.3, 0): V dropped
- **κ for each weighting:** the 50th, 75th and 90th percentiles of s under the static policy, in connected epochs, on the tuning seeds. This follows the usual CUSUM practice of setting the allowance from the in-control distribution. v0.1's κ = 0.30 is included as a reference point.
- **Selection rule:** lowest mean E on the tuning seeds, under per-seed mutation-budget matching against reactive.
- **Equal tuning effort for reactive:** its threshold is picked from the 50th/75th/90th percentiles of static E, plus v0.1's 0.5, by the same rule.
- θ, α, β, the cooldowns, the gate and the budget were **not** tuned.

Command: `python -m experiments.sweep --out results/sweep`. Outputs: `kappa_table.csv`, `uncapped.csv`, `matched_*.csv`, `frontier.png`, `selection.yaml`.

Tuning-seed outcome, budget-matched: **in all 12 TCCE-R configurations, matched reactive had lower E** (TCCE-R 0.317–0.410 vs reactive 0.295–0.400).

Selected configuration:
- TCCE-R: **W1_E, κ = 0.30**
- Reactive threshold: **0.3717** (its q50)

These are saved as `configs/v0.2_selected.yaml`. It differs from `configs/default.yaml` only in `w_E=1, w_C=0, w_V=0, reactive_threshold=0.3717`.

Note that the selection dropped C entirely. The trigger now responds only to consensus stress; connectivity is still prioritized inside the selector and the gate.

## 5. Held-out evaluation (seeds 1000–1029, n = 30)

Commands:
```
python -m experiments.run --config configs/<cfg>.yaml --seed-start 1000 --seeds 30 --no-rounds --out results/eval_<cfg>
python -m experiments.analyze results/eval_<cfg>
```

Values are means ± 95% CI half-widths. Lower is better for E and disconnection; higher is better for λ2.

### Config `v0.2_selected`

| policy | E | disconnected fraction | λ2 | mutations | first mutation epoch | mean live links |
|---|---|---|---|---|---|---|
| static | 0.442 ± 0.036 | 0.262 ± 0.075 | 0.059 ± 0.017 | 0 | — | 89.75 |
| random | 0.412 ± 0.034 | 0.196 ± 0.064 | 0.071 ± 0.017 | 3.60 ± 0.95 | 29.6 | 91.46 |
| periodic | 0.354 ± 0.024 | 0.098 ± 0.030 | 0.103 ± 0.012 | 3.60 ± 0.95 | 29.6 | 91.37 |
| **reactive (thr 0.372)** | **0.295 ± 0.026** | 0.081 ± 0.046 | **0.134 ± 0.014** | 3.73 ± 0.93 | 17.9 | 92.68 |
| TCCE-R | 0.337 ± 0.021 | **0.070 ± 0.028** | 0.110 ± 0.012 | 3.73 ± 0.93 | 22.1 | 91.71 |
| TCCE-R, fixed θ | 0.341 ± 0.022 | 0.077 ± 0.029 | 0.108 ± 0.012 | 3.47 ± 0.83 | 22.1 | 91.61 |

Paired Wilcoxon tests, TCCE-R minus reactive:

| metric | difference | Holm-adjusted p | meaning |
|---|---|---|---|
| E | +0.043 | 0.002 | **TCCE-R is worse** |
| λ2 | −0.024 | 0.001 | **TCCE-R is worse** |
| disconnected | −0.010 | 0.82 | **No detectable difference** |

TCCE-R against the other baselines (Holm-adjusted):
- It beats periodic on all three metrics (p ≤ 0.033).
- It beats random and static on all three (p ≤ 0.002).
- Fixed θ vs adaptive θ: differences of 0.003–0.007, Holm p = 0.088. **Not significant.**

### Config `default` (v0.1 parameters on the same held-out seeds, for reference)

| policy | E | disconnected | λ2 | mutations |
|---|---|---|---|---|
| reactive (thr 0.5) | 0.368 ± 0.029 | 0.106 ± 0.051 | 0.094 ± 0.015 | 1.67 ± 0.42 |
| TCCE-R | 0.408 ± 0.030 | 0.113 ± 0.028 | 0.074 ± 0.015 | 1.67 ± 0.42 |

TCCE-R minus reactive: E +0.040 (Holm p = 0.002), λ2 −0.020 (p = 0.003), disconnected not significant (p = 0.72).

## 6. Budget and mutation-count checks (held-out, both configs)

- Reactive's mutation count equals TCCE-R's on **30/30 seeds**.
- Periodic and random: 27/30 equal; on 3 seeds they made one fewer mutation, because a scheduled slot produced no valid mutation.
- Live links never exceeded the edge budget in any epoch, for any policy.
- All mutations were additions (v0.2: 112 for TCCE-R, 112 for reactive). Rewires never happened, because the budget never binds.

## 7. Conclusions (negative results stated plainly)

1. **No configuration in the pre-specified sweep made TCCE-R beat the reactive baseline** on consensus error or λ2, on tuning or held-out seeds. Reactive is significantly better on both. Disconnection fraction shows no significant difference.
2. TCCE-R does reliably beat static, random and periodic (greedy) at an equal mutation count. Its *timing* rule is better than a fixed schedule, but not better than simple reaction.
3. **The adaptive threshold has no significant effect** at this mutation rate.
4. Retuning helped TCCE-R in absolute terms: on held-out seeds, E fell from 0.408 to 0.337 and the disconnected fraction from 0.113 to 0.070. It helped the reactive baseline just as much, so the gap did not close.
5. The likely mechanism is that, in this environment, mutations are cheap, permanent additions that never conflict with the budget, so reacting early is always right. CUSUM-style accumulation is designed to ignore short excursions. That only pays off when acting has a cost: when false alarms are expensive, when mutations can make things worse, or when the budget forces trade-offs. **This hypothesis has not been tested.**

## 8. What would test the hypothesis in (5) (not done)

- Make the edge budget binding (for example `edge_budget_frac = 1.0`) so mutations become rewires with real costs.
- Add a mutation cost, such as a per-mutation reconfiguration penalty or temporary disruption, and report cost-adjusted performance.
- Add a bursty failure scenario (Gilbert–Elliott), where reacting to transient spikes wastes budget.
- Control for timing, for example by comparing the effect of each mutation over a fixed window after it is applied.
