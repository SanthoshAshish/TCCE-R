# Focused v0.7 comparison: A1 Reactive vs A3 CUSUM-E vs A5 TCCE-R

**Status:** exploratory, fixed before running. This is **not** the pre-registered eight-method evaluation (`docs/PROTOCOL_v0.7.md`). That evaluation, and its reserved seeds 200–219, 300–319 and 7000–7059, are untouched.

**Code:** `experiments/focused_v07.py`. Nothing new in the simulator or the policies: it reuses `tccer/policies/v06.py` (A1, A3, A5), the three v0.7 scenarios, the v0.6 count-matching rule, and the v0.6/v0.7 metric and statistics functions.

## Question
In the three v0.7 scenarios and at two mutation budgets, how do TCCE-R (A5) and CUSUM-E (A3) compare with the instantaneous Reactive threshold (A1) on consensus error?

## Design

| item | value |
|---|---|
| Arms compared | A1 Reactive, A3 CUSUM-E, A5 TCCE-R (counterfactual feedback, as in v0.7) |
| Reference (not compared) | A0 Static: simulated only to get κ, τ, episode labels and recovery anchors |
| Scenarios | the three existing ones: S1 RGG-40 bursty, S2 RGG-40 background failures only, S3 RGG-80 bursty (`configs/v0.7/scenarios`) |
| Budgets | M ∈ {3, 6}; setup delay 2; strict edge budget (every mutation is a rewire) |
| Cells | 3 scenarios × 2 budgets = **6**, analysed separately |
| Calibration seeds | **400–419** (20) |
| Evaluation seeds | **500–559** (60), used once |

Seeds are disjoint from the full v0.7 plan (200–219, 300–319, 7000–7059) and from every archived range.

## Calibration (mutation counts only)
1. **Per scenario, from A0 on the calibration seeds:** τ, κ_E (median of E over connected epochs) and κ_s (median of 0.5E + 0.3C + 0.2V over connected epochs).
2. **Per arm and scenario:** run over a 24-point threshold grid and pick, for each M, the value whose **mean mutation count** is closest to M (ties go to the larger threshold). It is feasible if within ±15% of M; otherwise that arm–cell is **excluded and reported**, never retuned on evaluation seeds. No outcome metric is used.
   - A1 h: linear 0.50 → 0.90
   - A3 Θ: geometric 0.30 → 4.0
   - A5 Θ₀: geometric 0.50 → 6.0
3. Freeze configs, constants and report with a SHA-256 manifest. The evaluation refuses to run if any file changed. Recalibration is refused once frozen.

**Differences from the full v0.7 calibration (deliberate, to save time):** 3 arms instead of 5; grids restricted to the ranges that mattered in v0.6, with the same resolution as the 40-point protocol grid (about 0.75 mutations per grid step); calibration runs capped at 12 mutations (≥ 2M) instead of uncapped. The cap only affects thresholds far below the ones selected.

## Run counts (exact)

| stage | formula | runs |
|---|---|---|
| calibration: static | 3 scenarios × 20 seeds | 60 |
| calibration: grid | 3 arms × 3 scenarios × 24 thresholds × 20 seeds | 4,320 |
| **calibration total** | | **4,380** |
| evaluation: static | 3 scenarios × 60 seeds | 180 |
| evaluation: A1, A3, A5 | 3 arms × 6 cells × 60 seeds | 1,080 |
| **evaluation total** | | **1,260** |
| **everything** | | **5,640** |

Each arm–cell that turns out not calibratable removes 60 evaluation runs. The calibration runs are already spent by then.

**Time (estimate):** about **15 minutes** (range 12–25) on 11 workers.
- Measured on an idle machine: 0.25–0.34 s per run (40-node), 0.7–1.4 s (80-node); the worst uncapped case was 1.25 s.
- Calibration plus evaluation ≈ 3,000 CPU-seconds; the parallel speed-up was 3–4.6× in earlier runs.
- The smoke test ran 138 runs in 25 s.

## Statistics (fixed now)
- **Unit:** the seed; arms paired by seed within a cell; two-sided Wilcoxon signed-rank (p = 1 if all differences are zero).
- **Primary family (12 tests, Holm):** A5 − A1 and A3 − A1 on E in each of the 6 cells.
- **Secondary family (6 tests, Holm):** A5 − A3 on E (the effect of adding C and V to the debt plus adaptive Θ).
- **Margin:** |ΔE| = 0.02 is the minimum meaningful effect. Verdicts, from `experiments/analyze_v06.py`:
  - "first arm meaningfully better": Holm p < 0.05 and ΔE ≤ −0.02;
  - "first arm better, below minimum": Holm p < 0.05 and −0.02 < ΔE < 0;
  - the mirror images for the second arm;
  - "practically equivalent": Holm p ≥ 0.05 and the 95% bootstrap CI inside ±0.02;
  - "inconclusive": otherwise.
- **Effect sizes:** mean paired difference with 95% bootstrap CI (10,000 resamples, seed 20261010) and t-interval; rank-biserial r.
- **Exploratory (no p-values):** disconnected fraction, λ₂, second-half E, precision, false alarms, detection rate, anchored recovery, mutation counts, pending link-epochs, live-link releases, wasted releases, A5 feedback outcome shares, E on seeds with equal realised counts.

**Power:** with paired SD ≈ 0.04 (v0.6) and 60 seeds, the smallest effect detectable at 80% power at the strictest Holm step (α = 0.05/12) is about 0.023. Smaller effects may be missed.

## Limitations (read before interpreting)
1. **Exploratory.** It supports no confirmatory claim, and conclusions are specific to each cell.
2. **No state-blind controls.** A6 Random and A7 Front-loaded are not included. In v0.6 the early fixed schedule beat every state-triggered arm, so a result here cannot say whether any trigger beats *no* trigger. Whatever A1 or A5 does, the earliness confound stays open.
3. **A5 differs from A1 in several ways at once** (accumulated debt, C and V terms, adaptive Θ, counterfactual feedback). Only A3 − A1 isolates accumulation, and A5 − A3 the rest.
4. **Counts are matched on average,** not per seed. Realised counts are reported (and the equal-count analysis is exploratory).
5. **The counterfactual feedback assumes an exact model of the consensus dynamics** (`docs/MATH_SPEC_v0.7.md` §4).
6. **R = λ₂ is provisional and M is a lexicographic ranking** (`docs/MATH_SPEC_v0.7.md` §2–3).
7. **Not modelled:** load, traffic, trust/uncertainty, attacks.

## Commands (from the `tcce_r` folder)
```powershell
# one command: calibrate -> freeze -> evaluate -> analyze (about 15 min)
python -m experiments.focused_v07 --stage all

# or step by step (lets you commit the frozen calibration before evaluating)
python -m experiments.focused_v07 --stage calibrate
git add configs/v0.7_focused; git commit -m "focused v0.7: frozen calibration"
python -m experiments.focused_v07 --stage eval
python -m experiments.focused_v07 --stage analyze

# 25-second smoke test of the whole pipeline (development seeds, separate folder)
python -m experiments.focused_v07 --stage all --smoke
```

## Outputs
- `configs/v0.7_focused/frozen/`: frozen configs, `constants.yaml`, `calibration_report.csv`, `MANIFEST.sha256`
- `results/v0.7_focused/calibration/`: raw calibration counts, static runs, `run_info.json`
- `results/v0.7_focused/eval/<cell>/epochs.csv`: raw per-epoch logs; `run_info.json` (commit, script hash, library versions, manifest, config hashes, completeness)
- `results/v0.7_focused/eval/analysis/`: `REPORT.md`, `primary_tests.csv`, `secondary_tests.csv`, `exploratory_diffs.csv`, `per_seed_metrics.csv`, `summary.csv`, `feedback_quality.csv`, `fig_E_by_cell.png`, `fig_forest_E.png`
