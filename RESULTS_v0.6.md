# v0.6 results: does accumulated resilience debt add timing information beyond an instantaneous error threshold?

**Setup:** pre-registered protocol `docs/PROTOCOL_v0.6.md`, revision 4. Single held-out evaluation on seeds 6000–6059 (n = 60), run once from commit `11c2b52`.

**Sources:** every number below comes from `archive/v0.6/eval/analysis/*.csv`, produced by `experiments/analyze_v06.py` without modification.

**Notation:** Δ = first arm − second arm, paired by seed. E = consensus stress (0–1, lower is better). The minimum meaningful effect is |ΔE| = 0.02. Each delay × budget cell is a separate condition.

## 1. Primary: A3 CUSUM-E vs A1 Reactive on E (Holm over 4)

| Cell | ΔE (A3 − A1) | 95% bootstrap CI | 95% t-CI | rank-biserial r | Wilcoxon p | **Holm p** | Δprecision [95% CI] | Verdict |
|---|---|---|---|---|---|---|---|---|
| d = 2, M = 3 | −0.0121 | [−0.0229, −0.0017] | [−0.0228, −0.0014] | −0.33 | 0.0265 | **0.0530** | −0.090 [−0.192, 0.019] (n = 52) | inconclusive |
| d = 2, M = 6 | −0.0152 | [−0.0244, −0.0067] | [−0.0241, −0.0063] | −0.42 | 0.0055 | **0.0165** | −0.052 [−0.087, −0.017] | A3 better, **below the minimum meaningful effect** |
| d = 8, M = 3 | −0.0056 | [−0.0134, 0.0020] | [−0.0135, 0.0023] | −0.13 | 0.402 | **0.402** | −0.103 [−0.199, −0.006] (n = 52) | practically equivalent |
| d = 8, M = 6 | −0.0125 | [−0.0189, −0.0062] | [−0.0190, −0.0059] | −0.49 | 0.0013 | **0.0052** | −0.047 [−0.095, −0.003] | A3 better, **below the minimum meaningful effect** |

**The pre-registered success criterion is met in none of the four cells.** The criterion requires all three of Holm p < 0.05, ΔE ≤ −0.02, and precision non-inferiority (lower CI bound > −0.05).
- In two cells (d = 2, M = 6 and d = 8, M = 6), CUSUM-E has a statistically supported but small advantage in E: 0.012–0.015, below the 0.02 margin.
- **Precision non-inferiority fails in all four cells.** CUSUM-E's mutations fell inside persistent degradation episodes *less* often than Reactive's: primary-label precision 0.41–0.47 vs 0.46–0.59.

## 2. Secondary: E only (Holm over 28)

| Comparison | d2 M3 | d2 M6 | d8 M3 | d8 M6 |
|---|---|---|---|---|
| A2 MovAvg − A1 Reactive | −0.006, equiv. | **−0.022, Holm p = 0.0007, A2 meaningfully better** | −0.002, equiv. | −0.001, equiv. |
| A3 CUSUM-E − A2 MovAvg | −0.006, equiv. | +0.006, equiv. | −0.004, equiv. | −0.012, equiv. |
| A4 CUSUM-ECV − A3 CUSUM-E | +0.008, equiv. | +0.007, equiv. | +0.005, equiv. | **+0.019, Holm p < 0.001, A3 better (below margin)** |
| A5 TCCE-R − A4 | +0.002, equiv. | +0.004, equiv. | −0.000, equiv. | −0.008, equiv. |
| A1 Reactive − A6 Random | **+0.029, p = 0.001, Random meaningfully better** | **+0.034, p = 0.001** | **+0.022, p = 0.025** | **+0.029, p = 0.009** |
| A3 CUSUM-E − A6 Random | +0.017, inconclusive | +0.018, inconclusive | +0.016, inconclusive | +0.016, inconclusive |
| A1 Reactive − A7 Front-loaded | **+0.064, p < 10⁻⁶, Front-loaded meaningfully better** | **+0.074** | **+0.054** | **+0.050** |

"equiv." = Holm p ≥ 0.05 with the 95% CI inside ±0.02. All p-values shown are Holm-adjusted.

Interpretation, as pre-specified in §6.6:
- **Smoothing alone matches CUSUM.** A3 and A2 are practically equivalent in every cell.
- **Adding C and V to the debt does not help.** A4 ≈ A3 everywhere, and A4 is worse at d = 8, M = 6.
- **Adaptive Θ has no effect.** A5 ≈ A4 everywhere.
- **The state-blind controls beat the state-triggered rules.** Random timing beats Reactive by a meaningful margin in all cells. Front-loaded beats Reactive by 0.05–0.07, the largest effects in the study. CUSUM-E vs Random is inconclusive, with Random numerically better.

## 3. Means per arm (60 seeds)

| Cell | Arm | E | E (epochs 40–79) | Disconnected | λ₂ | Mutations (realised / intended) | Precision | False-alarm share | Detection rate |
|---|---|---|---|---|---|---|---|---|---|
| d2 M3 | A0 Static | 0.474 | 0.477 | 0.366 | 0.054 | 0 | — | — | — |
| | A1 Reactive | 0.450 | 0.448 | 0.354 | 0.064 | 2.27 / 3 | 0.588 | 0.214 | 0.467 |
| | A3 CUSUM-E | 0.438 | 0.431 | 0.315 | 0.069 | 2.52 / 3 | 0.455 | 0.404 | 0.560 |
| | A6 Random | 0.422 | 0.401 | 0.312 | 0.080 | 2.10 / 2.10 | 0.158 | 0.816 | 0.183 |
| | A7 Front-loaded | 0.386 | 0.387 | 0.303 | 0.099 | 2.10 / 2.10 | 0.038 | 0.956 | 0.024 |
| d2 M6 | A1 | 0.420 | 0.412 | 0.292 | 0.076 | 5.17 / 6 | 0.484 | 0.343 | 0.696 |
| | A3 | 0.405 | 0.389 | 0.287 | 0.085 | 5.40 / 6 | 0.433 | 0.426 | 0.678 |
| | A6 | 0.386 | 0.353 | 0.291 | 0.099 | 4.78 / 4.78 | 0.183 | 0.789 | 0.364 |
| | A7 | 0.345 | 0.344 | 0.280 | 0.122 | 4.78 / 4.78 | 0.112 | 0.844 | 0.115 |
| d8 M3 | A1 | 0.455 | 0.452 | 0.368 | 0.062 | 2.28 / 3 | 0.588 | 0.214 | 0.455 |
| | A3 | 0.449 | 0.442 | 0.349 | 0.064 | 2.43 / 3 | 0.467 | 0.443 | 0.586 |
| | A6 | 0.433 | 0.412 | 0.329 | 0.074 | 2.08 / 2.08 | 0.146 | 0.836 | 0.173 |
| | A7 | 0.401 | 0.396 | 0.313 | 0.090 | 2.08 / 2.08 | 0.039 | 0.955 | 0.024 |
| d8 M6 | A1 | 0.437 | 0.421 | 0.340 | 0.070 | 5.03 / 6 | 0.460 | 0.367 | 0.661 |
| | A3 | 0.425 | 0.405 | 0.332 | 0.076 | 5.45 / 6 | 0.413 | 0.441 | 0.696 |
| | A6 | 0.408 | 0.380 | 0.314 | 0.088 | 4.47 / 4.47 | 0.193 | 0.782 | 0.357 |
| | A7 | 0.387 | 0.377 | 0.330 | 0.100 | 4.47 / 4.47 | 0.099 | 0.851 | 0.098 |

E for the other arms (full metrics in `archive/v0.6/eval/analysis/summary.csv` and `REPORT.md`):

| Cell | A2 MovAvg | A4 CUSUM-ECV | A5 TCCE-R |
|---|---|---|---|
| d2 M3 | 0.445 | 0.446 | 0.447 |
| d2 M6 | 0.398 | 0.412 | 0.416 |
| d8 M3 | 0.453 | 0.455 | 0.454 |
| d8 M6 | 0.436 | 0.444 | 0.436 |

- **A5 threshold updates per run:** 2.5 (d2 M3), 5.2 (d2 M6), 2.4 (d8 M3), 4.9 (d8 M6).
- **A6/A7 schedule lags:** ≤ 0.05 epochs on average; the backlog rarely mattered.

## 4. Sensitivity and exploratory analyses (descriptive; not used in verdicts)

**Episode labels.**
- A3's precision stays below A1's under every labelling: S3, S6 and the disconnection-based label (A1 0.71–0.81 vs A3 0.66–0.68 under the disconnection label).
- False-alarm shares are identical under primary, S3 and S6 by construction, since the transient and calm definitions are shared.

**C-2, uncapped re-run with the same thresholds.** A3 − A1 on E:

| Cell | ΔE | 95% CI | Mutations (A1 vs A3) |
|---|---|---|---|
| d2 M3 | −0.012 | [−0.021, −0.004] | 3.67 vs 3.68 |
| d2 M6 | −0.018 | [−0.025, −0.011] | 7.30 vs 7.72 |
| d8 M3 | −0.001 | [−0.008, 0.007] | 4.05 vs 3.77 |
| d8 M6 | −0.014 | [−0.023, −0.006] | 7.78 vs 8.87 |

The direction and size match the capped analysis. No difference reaches the 0.02 margin.

**Count balance.**
- A3 realised slightly more mutations than A1: +0.15 to +0.42 per run, with the CI excluding 0 in three cells.
- On seeds where both realised the **same** count (n = 34–42), ΔE(A3 − A1) is −0.009 to −0.014. That is the same direction and below the margin.
- These analyses describe balance only; they are not efficiency estimates.

**Other A3 − A1 differences.**
- λ₂ is higher by 0.002–0.009.
- Second-half E is lower by 0.010–0.022.
- Anchored recovery is faster by 0.1–1.7 epochs; the CI excludes 0 only at d2 M3.
- The wasted-release rate is lower only at d8 M3 (−0.10 [−0.18, −0.02]).

## 5. Interpretation (conclusions are specific to each cell; one network model and one failure model)

1. **No support for the pre-registered claim.** In no cell does accumulated debt (CUSUM-E) add *meaningful* timing information beyond an instantaneous error threshold. Its small E advantage (≤ 0.015) is below the pre-specified margin, and it comes with **lower** precision.
2. **The CUSUM benefit, where present, is not specific to CUSUM.** A 4-epoch moving average performs equivalently.
3. **The extra debt terms and adaptive Θ (the TCCE-R additions) add nothing measurable.**
4. **Timing quality as measured here does not predict outcome.**
   - The state-blind Front-loaded schedule acts at epochs 0, 2, 4, … with almost no mutations in persistent episodes (precision ≈ 0.04–0.11), yet it gives the lowest E in every cell by 0.05–0.07 over Reactive.
   - It does this with *fewer* realised mutations than A1–A5.
   - This confirms the earliness confound flagged in the protocol (C-1, H2). In this environment, making rewires early, so their benefit accrues over more epochs, matters more than reacting to measured stress.
   - Not tested: whether this reflects persistent topological improvement from the λ₂-based selector, or something specific to this failure model.

## 6. Deviations and integrity
- **No execution or integrity failure.**
  - 2,940/2,940 runs, all on seeds 6000–6059, 80 epochs each.
  - Clean commit `11c2b52`; the manifest (32 files) verified before and after the run.
  - The failure-trace rebuild matched the logs for all 60 seeds; the analysis would have aborted otherwise.
- **Revision 4** (A6/A7 count matching) was made before the evaluation and is documented in the protocol. On held-out seeds the controls realised slightly *fewer* mutations than A1–A5 (2.08–2.10 vs 2.27–2.58; 4.47–4.78 vs 4.85–5.45). The residual imbalance works *against* the controls, so it cannot explain their better E.
- **CSV mixed-type warnings** on the text columns `theta_update` and `v06_schedule` had no effect: the lag metric was computed for all 480 control runs with mutations.
- **Nothing was changed after inspecting the results.**

## 7. Reproduce
```
python -m experiments.run_v06 --mode eval      # refuses: evaluation already complete (runs once by design)
python -m experiments.analyze_v06 --run archive/v0.6/eval   # re-derives every table from the archived raw CSVs
```
