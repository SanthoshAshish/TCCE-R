# v0.3: binding edge budget with a real reconfiguration cost

**Question:** when the edge budget truly binds and every reconfiguration has a cost, does TCCE-R's debt-based timing beat reactive adaptation?

**Answer on fresh seeds 4000–4029:** no.
- Reactive is significantly better on consensus error and λ2.
- Disconnection fraction shows no detectable difference.
- The reconfiguration cost narrows the gap only slightly, and that narrowing is not statistically significant.

v0.1 and v0.2 are preserved as git tags, with their results in `archive/`. With default settings, the v0.3 code reproduces both bit for bit. This is checked against the archived CSVs.

## 1. What changed (all opt-in; defaults reproduce v0.1/v0.2)

| config key | effect | component |
|---|---|---|
| `budget_on: configured` | Failed links still count against the budget until the controller releases them. With `edge_budget_frac: 1.0`, the network starts at full budget, so **every mutation is a rewire** (remove one link, add one). | (6) Safety gate, (7) Selector |
| `link_setup_epochs: 2` | **Break-before-make cost.** The removed link disappears immediately; the new link becomes usable only 2 epochs later. The gate also checks the interim state for connectivity and the λ2 floor. | (1) State, (6) Gate, (8) Reconfigured network |
| `degree_fix: true` | Bug fix; see section 2. | (6) Gate, (7) Selector |

Rewire rule:
- Release the configured link with the smallest first-order λ2 loss.
- A failed link has loss 0. Releasing it frees budget but gives up its possible repair.
- A live link must not be a bridge.
- While the graph is disconnected, only failed links may be released.

The nine-component architecture is unchanged.

## 2. Harness defects found during this experiment

Two earlier runs were **invalidated and archived, not deleted**:
- `archive/v0.3_INVALID_seeds2000/`
- `archive/v0.3_INVALID_seeds3000/`

Each archive has a NOTE explaining why.

1. **No rewire while disconnected** (new in v0.3). Removals were ranked with the Fiedler vector, which doesn't exist when the graph is disconnected. Under the strict budget, no policy could ever reconnect the network.
2. **The selector wasted gate attempts** on candidates that broke the degree limit, so a fired trigger often produced nothing.
3. **Gate degree rule (present since v0.1).** A mutation was rejected if *any* node had degree > d_max, not just the endpoints of the new link. Some initial RGG nodes have degree above 10, so on those graphs every mutation was blocked.

Effect on earlier versions: gate rejections in the archived v0.2 held-out run were 5,490 for TCCE-R and 660 for reactive. Re-running the v0.2 configuration with the fix on the same seeds (1000–1029) **does not change the v0.2 conclusion**:

| v0.2 config + fix | E | disconnected | λ2 | mutations |
|---|---|---|---|---|
| reactive | 0.283 | 0.072 | 0.141 | 4.2 |
| TCCE-R | 0.326 | 0.050 | 0.114 | 4.2 |

The archived v0.1/v0.2 numbers remain valid as results *under the old gate rule*.

After each fix, the protocol was repeated from the tuning sweep onward, and each repeat used new evaluation seeds. The sweep picked the same configuration all three times.

## 3. Protocol (fixed before the final run)

- **Base config:** `configs/v0.3_binding_base.yaml`. That is `configs/default.yaml` plus `budget_on: configured`, `edge_budget_frac: 1.0`, `link_setup_epochs: 2`, `degree_fix: true`.
- **Tuning:** the same pre-specified sweep as v0.2 (`python -m experiments.sweep --config configs/v0.3_binding_base.yaml --out results/sweep_v0.3`), on seeds 100–119. Weights × data-derived κ for TCCE-R, and equal-effort threshold tuning for reactive.
- **Selected:** TCCE-R weights (w_E, w_C, w_V) = (1, 0, 0), κ = 0.30. Reactive threshold 0.3717. Saved as `configs/v0.3_selected.yaml`.
- **Primary evaluation:** seeds 4000–4029, never used before. Mutation budgets matched per seed to TCCE-R's count.
- **Secondary analyses** on the same seeds:
  - (a) uncapped, where each policy acts as often as its own rule says;
  - (b) `configs/v0.3_selected_nodelay.yaml`, the same but `link_setup_epochs: 0`, to isolate the cost.

```
python -m experiments.run --config configs/v0.3_selected.yaml --seed-start 4000 --seeds 30 --no-rounds \
    --policies static periodic reactive tccer tccer_fixed --out results/eval_v0.3_matched
python -m experiments.run --config configs/v0.3_selected.yaml --seed-start 4000 --seeds 30 --no-rounds \
    --policies static periodic reactive tccer tccer_fixed --unmatched --out results/eval_v0.3_uncapped
python -m experiments.run --config configs/v0.3_selected_nodelay.yaml --seed-start 4000 --seeds 30 --no-rounds \
    --policies static periodic reactive tccer tccer_fixed --out results/eval_v0.3_nodelay_matched
python -m experiments.analyze results/eval_v0.3_<name>
```

## 4. Fairness checks (primary run)

- **Strict budget:** configured links never exceeded the initial count, in any epoch, for any policy. Configured links are identical across policies (100.0 ± 5.4).
- **Mutations:** all 510 were rewires.
- **Mutation counts:** reactive and periodic equal TCCE-R's count on **30/30 seeds**. Mean 4.3 ± 0.87 each.
- **Gate rejections:** 0 for every policy.
- **Common random numbers:** the failure trace is identical across policies (tested).
- **Live links:** 92.2–92.3 on average across the mutating policies, so the edge count is effectively equal.
- **Reconfiguration exposure:** links in setup average 0.107–0.108 per epoch, equal across policies.

## 5. Primary result: binding budget, setup delay 2, matched mutation budget (n = 30)

Values are means ± 95% CI half-widths.

| policy | consensus error E ↓ | fraction of epochs disconnected ↓ | λ2 ↑ | live links | mutations | first mutation epoch |
|---|---|---|---|---|---|---|
| static | 0.432 ± 0.029 | 0.205 ± 0.064 | 0.064 ± 0.014 | 92.0 | 0 | — |
| periodic | 0.344 ± 0.018 | 0.087 ± 0.031 | 0.109 ± 0.011 | 92.3 | 4.3 ± 0.87 | 18.3 |
| **reactive** | **0.300 ± 0.022** | 0.082 ± 0.042 | **0.131 ± 0.013** | 92.3 | 4.3 ± 0.87 | 1.2 |
| TCCE-R | 0.338 ± 0.016 | 0.065 ± 0.022 | 0.112 ± 0.011 | 92.2 | 4.3 ± 0.87 | 11.3 |
| TCCE-R, fixed θ | 0.334 ± 0.017 | 0.063 ± 0.022 | 0.113 ± 0.011 | 92.2 | 4.1 ± 0.77 | 11.3 |

Paired Wilcoxon tests, TCCE-R minus baseline, Holm-adjusted across the table:

| comparison | E | disconnected | λ2 |
|---|---|---|---|
| vs reactive | +0.038, **p = 0.0002 (TCCE-R worse)** | −0.017, p = 1.0 (n.s.) | −0.019, **p = 0.0007 (TCCE-R worse)** |
| vs periodic | −0.006, p = 0.88 (n.s.) | −0.023, p = 0.11 (n.s.) | +0.003, p = 0.66 (n.s.) |
| vs fixed θ | +0.004, p = 0.66 (n.s.) | +0.002, p = 1.0 (n.s.) | −0.001, p = 1.0 (n.s.) |

TCCE-R beats static on every metric.

**Correction to v0.2:** once the gate bug is fixed, TCCE-R is **no longer significantly better than periodic** in this setting.

## 6. Does the reconfiguration cost help TCCE-R? (primary vs no-delay, same seeds)

| | reactive | TCCE-R | periodic |
|---|---|---|---|
| E with delay 0 | 0.282 | 0.329 | 0.342 |
| E with delay 2 | 0.300 | 0.338 | 0.344 |
| **cost of the delay (ΔE)** | **+0.018** | **+0.009** | +0.002 |

- The cost hurts reactive about twice as much as TCCE-R. This fits the hypothesis that eager reaction pays more for reconfiguration.
- The E gap between TCCE-R and reactive shrinks from 0.047 to 0.038. That change is **not significant** (paired Wilcoxon p = 0.16), and the gap remains significant in reactive's favour.
- **Conclusion:** at this cost level, debt-based timing does not give a net benefit. The direction of the effect is consistent with a crossover at higher costs, but this experiment does not show one.

## 7. Uncapped (each policy mutates as often as its own rule says)

| policy | E | disconnected | λ2 | mutations |
|---|---|---|---|---|
| periodic (every 5 epochs) | 0.224 ± 0.030 | 0.047 ± 0.020 | 0.188 ± 0.023 | 15.0 |
| reactive | 0.227 ± 0.019 | 0.037 ± 0.017 | 0.176 ± 0.014 | 10.9 ± 1.8 |
| TCCE-R | 0.338 ± 0.016 | 0.065 ± 0.022 | 0.112 ± 0.011 | 4.3 ± 0.9 |

Even with a strict budget and break-before-make cost, **more rewiring is better**: 10–15 rewires beat about 4. TCCE-R's selectivity is not an advantage here; it simply under-reconfigures. Rewiring remains net-beneficial at this cost level, because the selector usually releases failed links, whose immediate loss is 0.

## 8. Conclusions

1. **No support for TCCE-R superiority.** With a binding budget and a reconfiguration cost, the reactive baseline is significantly better on consensus error and λ2. Disconnection fraction shows no significant difference. TCCE-R is not significantly better than periodic.
2. **The adaptive threshold has no measurable effect.** This holds for the third experiment in a row.
3. **The cost asymmetry goes in the predicted direction but is too small to matter.** The cost hurt reactive about twice as much, but the gap change is not significant (p = 0.16).
4. **Why debt timing still loses:**
   - The selector mostly swaps failed links for live ones, which has almost no downside.
   - Acting is therefore nearly always beneficial, and the first epoch with high stress is the best time to act. Reactive's first mutation comes at epoch 1.2 on average, TCCE-R's at 11.3.
   - CUSUM accumulation is designed to delay action until evidence piles up. That only helps if acting on transient stress is harmful, and here it isn't.

## 9. Limitations

- One topology model (RGG, n = 40), one failure regime (p_fail = 0.01, p_repair = 0.1, p_transient = 0.05) and one cost level (2-epoch setup).
- No cost sweep was run, so no crossover point can be claimed.
- Only TCCE-R's weights and κ and reactive's threshold were tuned. θ, α, β, the cooldowns and the gate parameters keep their v0.1 values.
- Releasing failed links makes rewires cheap. A setting where every removal costs a live link would be a harsher test.
- The success criterion behind adaptive θ remains noisy (risk R7).
- About 4 mutations per run gives θ few updates.
- Tuning seeds 100–119 were reused across all three tuning passes. Evaluation seeds were fresh each time.
- The controller is centralized (global λ2 and Fiedler vector).

## 10. What would test the remaining hypothesis (not done)

- Sweep `link_setup_epochs` over {0, 2, 4, 8} and look for a crossover in the TCCE-R minus reactive gap.
- Add bursty (Gilbert–Elliott) failures, where reacting to short spikes wastes rewires on links that come back.
- Disallow releasing failed links, so every rewire sacrifices a live link.
