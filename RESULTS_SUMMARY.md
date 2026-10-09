# TCCE-R v0.4: results summary

Every number below is read from simulator outputs in `results/v0.4/report/` (`summary.csv`, `paired_tests.csv`). Raw per-epoch logs are in `results/v0.4/eval_d{0,2,4,8}/epochs.csv`, and an archived copy is in `archive/v0.4/`.

## 1. Bottom line

- **TCCE-R did not outperform reactive control in any pre-specified held-out condition.**
  - At all four reconfiguration delays it was significantly worse on consensus stress E (primary family, Holm p ≤ 7·10⁻⁶) and on λ₂.
  - The disconnected fraction showed no statistically supported difference.
- TCCE-R beat the static network on E and λ₂ at every delay.
- **TCCE-R was worse than periodic adaptation** on E at delays 2 and 4, and on λ₂ at delays 2, 4 and 8.
- **The adaptive threshold Θ had no measurable effect**: TCCE-R vs fixed-Θ was not significant on any metric at any delay.
- These conclusions cover one network model (RGG, n = 40), one failure model and one budget regime.

## 2. Methodology (full protocol: `docs/PROTOCOL_v0.4.md`, committed before the run)

- **Environment:**
  - strict edge budget: every mutation is a rewire, and no strategy can add links;
  - break-before-make reconfiguration delay d ∈ {0, 2, 4, 8} epochs;
  - failures: transient per-round loss, background on/off failures, and **temporary spatial bursts** (start probability 0.10 per epoch, radius 0.15, lasting 2–6 epochs, then recovering);
  - failed links are valued "as if up", so replacing them is not free;
  - all v0.4 audit fixes on.
- **Strategies:**
  - static;
  - periodic;
  - reactive (rewire when this epoch's E exceeds a fixed threshold);
  - TCCE-R (rewire when CUSUM debt D > adaptive Θ);
  - TCCE-R with fixed Θ (ablation).

  All share the candidate generator, the safety gate, the edge budget and, per seed, the identical failure trace.
- **Fair budgets:** reactive and periodic were capped at TCCE-R's mutation count for every seed. Counts matched on **30/30 seeds at every delay**.
- **Tuning:** a pre-specified sweep on seeds 100–119, separately per delay. The same configuration was selected at every delay:
  - TCCE-R: weights (w_E, w_C, w_V) = (1, 0, 0), κ = 0.30;
  - reactive threshold: 0.378.
- **Evaluation:** fresh seeds 5000–5029 (n = 30), run once.
- **Statistics:**
  - paired two-sided Wilcoxon signed-rank over seeds;
  - 95% t-interval of the paired mean difference;
  - Holm correction within the primary family (4 tests) and the secondary family (44 tests);
  - practical thresholds: |ΔE| ≥ 0.02, |Δdisconnected| ≥ 0.02, |Δλ₂| ≥ 0.01.

## 3. Metrics

| metric | meaning |
|---|---|
| E | consensus stress per epoch: 0 means disagreement reached ε = 0.01 within 60 rounds, 1 means no progress (dimensionless) |
| disconnected | fraction of the 80 epochs in which the live graph had more than one component |
| λ₂ | algebraic connectivity of the live graph (Laplacian eigenvalue; 0 if disconnected) |
| mutations / first mutation | rewires per run; epoch of the first rewire (80 = never) |
| recovery | mean length of disconnection episodes, in epochs (final open episodes are right-censored, see §6) |
| integrity | gate rejections, edge-budget violations, reconnection failures, reconnect-impossible epochs |

## 4. Results (held-out seeds 5000–5029; mean ± 95% CI)

| delay | strategy | E ↓ | disconnected ↓ | λ₂ ↑ | mutations | first mutation (epoch) | recovery (epochs) |
|---|---|---|---|---|---|---|---|
| 0 | static | 0.449 ± 0.034 | 0.329 ± 0.067 | 0.065 ± 0.020 | 0 | — | 6.41 ± 1.71 |
| 0 | periodic | 0.342 ± 0.028 | 0.253 ± 0.049 | 0.123 ± 0.019 | 6.67 ± 0.95 | 12.3 | 4.67 ± 0.62 |
| 0 | **reactive** | **0.312 ± 0.027** | 0.235 ± 0.064 | **0.135 ± 0.018** | 6.67 ± 0.95 | 0.9 | 4.78 ± 1.57 |
| 0 | TCCE-R | 0.356 ± 0.023 | 0.225 ± 0.041 | 0.109 ± 0.016 | 6.67 ± 0.95 | 8.5 | 4.00 ± 0.55 |
| 2 | static | 0.449 ± 0.034 | 0.329 ± 0.067 | 0.065 ± 0.020 | 0 | — | 6.41 ± 1.71 |
| 2 | periodic | 0.340 ± 0.026 | 0.241 ± 0.042 | 0.125 ± 0.018 | 7.57 ± 1.14 | 11.4 | 4.35 ± 0.55 |
| 2 | **reactive** | **0.317 ± 0.022** | 0.232 ± 0.043 | **0.134 ± 0.016** | 7.57 ± 1.14 | 0.9 | 4.51 ± 0.60 |
| 2 | TCCE-R | 0.369 ± 0.024 | 0.258 ± 0.048 | 0.105 ± 0.016 | 7.57 ± 1.14 | 8.5 | 4.78 ± 0.70 |
| 4 | static | 0.449 ± 0.034 | 0.329 ± 0.067 | 0.065 ± 0.020 | 0 | — | 6.41 ± 1.71 |
| 4 | periodic | 0.347 ± 0.026 | 0.257 ± 0.043 | 0.121 ± 0.018 | 7.67 ± 1.33 | 11.5 | 4.81 ± 0.62 |
| 4 | **reactive** | **0.337 ± 0.025** | 0.269 ± 0.050 | **0.123 ± 0.017** | 7.67 ± 1.33 | 0.9 | 4.95 ± 0.75 |
| 4 | TCCE-R | 0.383 ± 0.027 | 0.289 ± 0.055 | 0.098 ± 0.017 | 7.67 ± 1.33 | 8.5 | 5.63 ± 1.26 |
| 8 | static | 0.449 ± 0.034 | 0.329 ± 0.067 | 0.065 ± 0.020 | 0 | — | 6.41 ± 1.71 |
| 8 | periodic | 0.366 ± 0.031 | 0.294 ± 0.060 | 0.110 ± 0.020 | 8.67 ± 1.33 | 10.4 | 5.42 ± 1.03 |
| 8 | **reactive** | **0.352 ± 0.031** | 0.296 ± 0.063 | **0.114 ± 0.019** | 8.67 ± 1.33 | 0.9 | 5.67 ± 1.14 |
| 8 | TCCE-R | 0.396 ± 0.028 | 0.311 ± 0.059 | 0.091 ± 0.017 | 8.67 ± 1.33 | 8.5 | 6.03 ± 1.12 |

The figures are in `results/v0.4/report/`:

| figure | shows |
|---|---|
| `fig1_consensus_stress.png` | E vs delay |
| `fig2_disconnected.png` | disconnected fraction vs delay |
| `fig3_lambda2.png` | λ₂ vs delay |
| `fig4_mutations.png` | mutations vs delay |
| `fig5_first_mutation.png` | first-mutation epoch vs delay |
| `fig6_recovery.png` | recovery time vs delay |
| `fig7_paired_tccer_minus_reactive.png` | paired differences, TCCE-R minus reactive |

### Primary hypothesis: TCCE-R vs reactive on E (paired, n = 30)

| delay | TCCE-R − reactive (95% CI) | Holm p | verdict |
|---|---|---|---|
| 0 | +0.044 (±0.018) | 6.9·10⁻⁶ | TCCE-R worse; practically meaningful |
| 2 | +0.052 (±0.013) | 7.5·10⁻⁸ | TCCE-R worse; practically meaningful |
| 4 | +0.046 (±0.016) | 2.5·10⁻⁶ | TCCE-R worse; practically meaningful |
| 8 | +0.044 (±0.017) | 6.5·10⁻⁶ | TCCE-R worse; practically meaningful |

### Secondary results (Holm-adjusted over 44 tests)

- **vs reactive:**
  - λ₂ is worse at every delay (Holm p ≤ 6.5·10⁻⁴).
  - Disconnected fraction: no supported difference at any delay. Delay 2 has raw p = 0.012 but Holm p = 0.26.
- **vs periodic:**
  - E is worse at delays 2 (p = 0.016) and 4 (p = 0.002).
  - λ₂ is worse at delays 2, 4 and 8.
  - Everything else is not significant.
- **vs static:**
  - E and λ₂ are better at every delay.
  - Disconnected fraction is better at delays 0 and 2.
- **vs fixed Θ:** no supported difference on any metric at any delay. **The adaptive threshold has no measurable effect.**
- **Effect of the reconfiguration delay:** it hurts every adaptive strategy, but it does not change the ranking. The gap between TCCE-R and reactive stays at 0.044–0.052 across all delays, so no crossover was observed.

### Integrity checks (sums over 30 seeds; `audit/check_v04_integrity.py`)

- **Edge-budget violations: 0** in every condition. Configured links are identical across strategies (99.1).
- **Mutation counts:** reactive and periodic equal TCCE-R's on 30/30 seeds at every delay.
- **Gate rejections:**
  - TCCE-R: 0.
  - Reactive: 60 at delay 2 and 240 at delay 8.
  - Periodic: 30 at delay 8.

  All of them are the λ₂-floor rule correctly refusing rewires that would weaken connectivity.
- **Reconnection failures** (a strategy tried to act while disconnected and found no valid move): 1 in total (TCCE-R, delay 2).
- **Reconnect-impossible epochs** (79–159 per condition). Causes, from an instrumented replay of delays 2 and 8 (TCCE-R, budget-matched reactive and periodic; 842 epochs):
  - 72% (610) physically impossible, because every in-range link between components had failed;
  - 24% (206) a reconnecting link was already in setup;
  - 3% (26) blocked by cooldown or the gate.

  Every strategy therefore had the same opportunity to reconnect.
- **Reconfiguration cost:** pending link-epochs were essentially equal across strategies (for example at delay 8: 68 periodic, 67 reactive, 64 TCCE-R).

## 5. Why reactive wins (descriptive; `audit/why_reactive_wins.py`)

With the same number of rewires, the strategies spend them differently:

| (delay 2) | median mutation epoch | share in first 20 epochs | share made while disconnected | share that reconnect components | share releasing a failed link |
|---|---|---|---|---|---|
| reactive | 12 | 74% | 52% | 37% | 52% |
| periodic | 40 | 21% | 33% | 27% | 35% |
| TCCE-R | 37 | 29% | 74% | 61% | 75% |

The other delays show the same pattern.

1. **Earliness.** Reactive spends about three quarters of its budget in the first 20 epochs. Structural improvements persist, so they pay off over more epochs.
2. **TCCE-R is an outage responder.** Debt builds during burst outages, so 74–77% of TCCE-R's rewires happen while disconnected. Most of them reconnect components by releasing a failed link, often a burst-failed link that would have recovered within a few epochs.

   *Hypothesis, not tested:* those moves buy little lasting improvement, which would explain why TCCE-R is also worse than periodic, and why its many reconnecting moves don't produce a lower disconnected fraction.
3. **Θ adaptation stays inactive.** With 7–9 mutations per run and a noisy before/after success signal, Θ changes too little to matter, even after fixing the feedback timing (D2).

## 6. Limitations

- One topology model and size (RGG, n = 40, 80 epochs), one failure/burst parameterisation and one budget regime. **No general claim** follows from these results.
- Burst parameters were calibrated on tuning seeds (static policy only) to a pre-stated target. A different burst regime might change the picture.
- Recovery time is descriptive. 28–36 runs per strategy end in an open (censored) disconnection episode, and the means exclude no episodes.
- The tuning sweep was restricted to TCCE-R's weights and κ and to reactive's threshold. Θ bounds, α, β, the cooldowns and H keep their v0.1 values.
- M is a lexicographic vector, not the scalar "improvement per resilience cost" ratio in the diagram. R is λ₂.
- Trust/uncertainty, traffic and node load are **not implemented**.
- The controller is logically centralized.
- While disconnected, the rewire releases the lowest-index failed link: a deterministic, policy-independent tie-break.
- The success signal behind Θ is confounded by environmental change.

## 7. Reproduce

```powershell
pip install -r requirements.txt
python -m pytest -q                       # 47 tests
python -m experiments.reproduce_v04       # tuning -> held-out evaluation -> report (about 25 min)
python -m experiments.reproduce_v04 --stage report    # rebuild report from existing raw CSVs only
```

Configurations:
- `configs/v0.4/main.yaml`
- `configs/v0.4/base_d*.yaml`
- `configs/v0.4/selected_d*.yaml`

Seeds: tuning 100–119, evaluation 5000–5029.
