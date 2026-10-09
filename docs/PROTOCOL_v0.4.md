# v0.4 experiment protocol: bursty failures × reconfiguration delay

**This protocol was written and committed before any v0.4 tuning or evaluation run.** The commit that adds this file comes before the commit containing results.

## Question

Under a strict edge budget, with temporary spatially correlated failure bursts and a break-before-make reconfiguration cost, does TCCE-R's debt-based timing beat fixed-error reactive adaptation? The comparison is at equal mutation budgets, with reconfiguration delays of 0, 2, 4 and 8 epochs.

## Environment (`configs/v0.4/main.yaml`; the only per-condition change is `link_setup_epochs`)

- **Network:** RGG, n = 40, initial links within 0.22, candidate links within radio range 0.32.
- **Strict budget:** `budget_on: configured`, `edge_budget_frac: 1.0`. Every mutation is a rewire; no strategy can add links.
- **Reconfiguration cost:** `link_setup_epochs` d ∈ {0, 2, 4, 8}. The removed link goes immediately and the new link is usable after d epochs. The gate also checks the interim state.
- **Failure model:**
  - transient per-round link loss, p = 0.05;
  - background per-link on/off Markov process, p_fail = 0.005, p_repair = 0.10;
  - **spatial bursts:** start with probability 0.10 per epoch; centre uniform; every link whose midpoint is within 0.15 fails for U{2..6} epochs, then recovers.

  All draws come from the seed alone (common random numbers), so every strategy faces an identical failure trace.
- **No cheap replacement:** `failed_link_value: if_up`. A failed link is valued as if it were up, so releasing it is not automatically free. Bursts make this a real trade-off, because a released burst-failed link would have recovered.
- **Audit fixes on:** `degree_fix: true`, `degree_basis: configured`, `feedback_after_setup: true`.

### Burst calibration
Calibration used the static policy only, on tuning seeds 100–119 (`audit/calibrate_bursts*.py`). The target, fixed in advance, was a static network disconnected in roughly 15–35% of epochs. The chosen setting gives 28.1%, against 9.9% without bursts. No other strategy was run during calibration.

## Strategies

| strategy | when it mutates | how it chooses |
|---|---|---|
| static | never | — |
| periodic | every ⌊80/(M+1)⌋ epochs, at most M times | shared lexicographic selector |
| reactive | when this epoch's E > threshold, cooldown 2, at most M times | shared selector |
| TCCE-R | when CUSUM debt D > θ (adaptive), cooldown 2 | shared selector |
| TCCE-R fixed θ | as TCCE-R, but θ never adapts | shared selector (ablation for the θ question) |

M is TCCE-R's mutation count on the same seed (budget matching, as in v0.2/v0.3). Every strategy shares the candidate generator, the safety gate, the edge budget and the failure trace.

## Tuning (seeds 100–119 only), per delay condition

This uses the unchanged `experiments/sweep.py` procedure from v0.2/v0.3:
- weights {(0.5, 0.3, 0.2), (1, 0, 0), (0.7, 0.3, 0)};
- κ = the 50th/75th/90th percentiles of static in-control stress, plus 0.30;
- TCCE-R selected by lowest budget-matched mean E;
- reactive threshold selected with equal effort from the same quantiles of static E, plus 0.5.

The selected configurations are saved as `configs/v0.4/selected_d{D}.yaml`. **There is no tuning on evaluation seeds**, and no re-tuning after the evaluation is seen.

## Evaluation

Fresh held-out seeds **5000–5029** (n = 30), never used before. All four delays are evaluated once.

## Metrics (per seed, averaged over 80 epochs)

| metric | definition |
|---|---|
| consensus stress E | mean of `1 − min(1, ln e(T)/ln ε)` per epoch |
| disconnected fraction | share of epochs with more than one component |
| λ₂ | mean algebraic connectivity (0 when disconnected) |
| mutations, time to first mutation | counts; first-mutation epoch is 80 if none |
| recovery time | mean length of disconnection episodes (a final open episode is right-censored and flagged) |
| gate rejections | cumulative count |
| edge-budget violations | epochs with configured links > budget |
| reconnection failures | epochs where the strategy tried to act while disconnected and got no valid mutation |
| reconnect-impossible epochs | disconnected epochs where the shared selector + gate had no reconnecting move |

## Hypotheses and decision rules (fixed now)

- **Primary (4 tests):** at each delay, TCCE-R vs reactive on mean E. Paired two-sided Wilcoxon signed-rank over seeds, Holm-adjusted across the 4 delays. "TCCE-R outperforms reactive at delay d" **only if** Holm p < 0.05 **and** the mean paired difference is below 0.
- **Secondary:** TCCE-R vs {reactive, periodic, static, fixed θ} on {E, disconnected fraction, λ₂} at every delay, excluding the primary tests. Holm-adjusted as one family. The adaptive-threshold question is answered by TCCE-R vs fixed θ.
- **Practical significance:** |ΔE| ≥ 0.02, |Δdisconnected| ≥ 0.02, |Δλ₂| ≥ 0.01. A statistically supported difference below these is reported as negligible.
- **No result will be reported as a success** unless it meets these rules. No delay condition will be singled out after the fact.

## Commands

```
python -m experiments.reproduce_v04          # tune -> eval -> report
python -m pytest -q
```
