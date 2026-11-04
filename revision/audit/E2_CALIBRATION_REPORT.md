# E2 calibration report (seeds 8000-8019 only), with Amendment 1

Everything below used ONLY calibration seeds 8000-8019 and ONLY mutation counts. No development (8100-8119), held-out (9000-9059) or v0.7 result entered any threshold. The frozen v0.7 baseline and its backup are untouched.

## Pass 1 (2026-11-04, commit `047d7c7`)
`python -m experiments.calibrate_v08`: 10,720 runs (60 Static + 10,080 grid of 28 points x 6 arms x 3 scenarios x 20 seeds + 580 capped) in 2,225 s. Result: 29 of 36 calibrated arm-cells feasible; 7 excluded; B8 in S2 at M=6 sat on the grid minimum (Theta0 = 0.05). Frozen copy kept unchanged in `configs/v0.8/frozen_pass1/` (its manifest still verifies).
Problems found: (1) the count falls very steeply between adjacent thresholds (e.g. B4 S1 M=3: h 0.683 -> 4.7, 0.717 -> 1.85), so a 28-point grid stepped over the +-15% window; (2) B3 S1 M=3 had a mean count of exactly 2.55 = -15.0% from 3, rejected by a floating-point artefact (`0.4500000000000002 <= 0.45` false); (3) B8 S2 M=6 at the grid edge.

## Amendment 1 (made before any held-out run; `python -m experiments.amend_calibration_v08`)
1. **Rule fix:** `experiments/v08_common.choose` replaces the v0.6 `choose` for v0.8: a relative gap exactly at 15% is accepted (1e-9 absolute tolerance); selection is otherwise the same (closest mean count to M; ties to the larger threshold). The v0.6/v0.7 code is untouched. Tests: `tests/test_v08_pipeline.py::test_choose_*`.
2. **Supplementary grids (search ranges, `results/v0.8/E2/calibration/amendment1_search_ranges.csv`):** for each of the 7 excluded arm-cells, 11 equally spaced interior thresholds inside the bracket (the two adjacent pass-1 grid points whose counts straddle M): B3 S1 M=3 [0.550, 0.5833]; B3 S1 M=6 [0.5167, 0.550]; B4 S1 M=3 [0.6833, 0.7167]; B4 S1 M=6 [0.650, 0.6833]; A1 S3 M=3 [0.7533, 0.7785]; B4 S3 M=3 [0.6833, 0.7167]; B2 S3 M=6 [0.8167, 0.850]. For B8 in S2 at M=6: 13 geometric thresholds 0.005-0.0419 (below the pass-1 minimum 0.05). 1,800 runs (77 bracket thresholds + 13 lower-bound thresholds = 90 thresholds, x 20 seeds), runs capped at 12 mutations as in pass 1, seeds 8000-8019 only (`amendment1_counts.csv`: seeds 8000-8019, 1,800 rows).
3. **Selection:** only these 8 arm-cells were re-chosen (closest mean count over pass-1 points plus the new points, same +-15% rule). **Every other arm-cell keeps its pass-1 config byte for byte** (checked: the only changed files are the 8 re-chosen cells' configs, B5/B6/B7/H1 in S2 M=6 which inherit B8, the five A7 configs whose count PMF changed, and the manifest, report, constants and PMF table). A first execution of the amendment re-read kappa and thresholds from rounded CSV/YAML and altered other cells by 1e-11 to 1e-16; I detected this by diffing against the pass-1 snapshot, restored the pass-1 freeze, fixed the script to reuse the exact pass-1 configs, and re-ran it. The numbers below are from the corrected run (selections were identical).
4. **A7 PMFs** were rebuilt from the pooled capped counts of all calibratable arm-cells (pass-1 capped counts kept for unchanged cells; 160 new capped runs for the 8 re-chosen cells, seeds 8000-8019). Mean intended count: S1 M3 2.46, M6 5.15; S2 M3 2.29, M6 4.94; S3 M3 2.36, M6 4.94.
5. **Re-freeze:** `configs/v0.8/frozen/MANIFEST.sha256` regenerated (78 entries); `python revision/audit/check_calibration_v08.py` verifies it.

### Amended selections
| cell (scenario, M) | arm | pass 1 threshold (count) | final threshold | final mean count |
|---|---|---|---|---|
| S1, 3 | B3 | 0.5833 (2.55, excluded) | 0.5750 | 3.05 |
| S1, 3 | B4 | 0.7167 (1.85, excluded) | 0.7028 | 3.00 |
| S1, 6 | B3 | 0.5167 (7.00, excluded) | 0.5306 | 6.05 |
| S1, 6 | B4 | 0.6833 (4.70, excluded) | 0.6722 | 5.90 |
| S3, 3 | A1 | 0.7533 (3.75, excluded) | 0.7638 | 2.95 |
| S3, 3 | B4 | 0.7167 (2.10, excluded) | 0.7056 | 3.15 |
| S3, 6 | B2 | 0.8167 (7.55, excluded) | 0.8278 | 5.95 |
| S2, 6 | B8 | 0.0500 (5.60, grid edge) | 0.01447 | 6.00 |
**Remaining exclusions: none (36 of 36 calibrated arm-cells feasible).**

## Final frozen thresholds (h for A1, B2-B4; Theta0 for A5, B8 -- B5, B6, B7, H1 inherit B8's) and calibration mean counts
| cell | A1 | A5 | B2 | B3 | B4 | B8 |
|---|---|---|---|---|---|---|
| S1, M=3 | 0.7533 (3.20) | 2.7144 (2.95) | 0.8500 (2.90) | 0.5750 (3.05) | 0.7028 (3.00) | 2.7144 (2.65) |
| S1, M=6 | 0.7030 (5.75) | 1.3950 (5.80) | 0.8167 (5.60) | 0.5306 (6.05) | 0.6722 (5.90) | 1.1173 (6.40) |
| S2, M=3 | 0.6526 (2.75) | 0.7169 (3.15) | 0.7167 (3.10) | 0.4833 (2.80) | 0.5833 (3.10) | 0.4599 (3.00) |
| S2, M=6 | 0.5015 (5.85) | 0.0779 (5.90) | 0.3500 (5.40) | 0.3833 (5.70) | 0.2833 (5.90) | 0.01447 (6.00) |
| S3, M=3 | 0.7638 (2.95) | 4.2308 (2.65) | 0.8500 (3.15) | 0.5833 (2.70) | 0.7056 (3.15) | 3.3888 (2.90) |
| S3, M=6 | 0.7281 (5.60) | 2.1742 (5.40) | 0.8278 (5.95) | 0.5500 (5.75) | 0.6833 (6.00) | 1.1173 (5.80) |
Constants from Static runs (seeds 8000-8019): kappa_s = 0.2287 (S1), 0.2327 (S2), 0.2685 (S3); tau = 0.6267, 0.5646, 0.6686; kappa_E = 0.4196, 0.4217, 0.5018 (`constants.yaml`; the configs carry the exact, unrounded kappa). H1: F = 2 for M=3, F = 3 for M=6.

## Diagnostics
- The B8 value in S2 at M=6 (Theta0 = 0.0145, theta_min = Theta0/4) is very low: the trigger then fires whenever the cooldown allows, so B5-B8 and H1 behave nearly like "act as soon as allowed" in that cell. This is what matching the mean count to M requires there; it is reported, not a free choice.
- Realised mutation counts of the derived arms at B8's Theta0 on the calibration seeds (diagnostic only, `revision/audit/calibration_v08_derived_arm_counts.csv`; nothing was tuned from them): M=3: B5 2.50-2.65, B6 2.40-2.45, B7 2.40-2.55, H1 2.75-3.00; M=6: B5 5.60-5.70, B6 4.90-5.15, B7 5.05-5.30, H1 5.65-5.95 (ranges over scenarios). Counts differ between arms by design and will be reported with the E2 results.
- Verified: B5, B6, B7 configs equal B8's in every cell; H1 equals B8's with `v08_front` = F; A7 configs carry the PMF, A7M none; all evaluation job lists contain only seeds 9000-9059 (checked from `build_jobs`; the runner also asserts it).

## E2 as frozen
12 arms x 6 cells = 72 arm-cells x 60 seeds = 4,320 runs plus Static 3 x 60 = 180 -> **4,500 evaluation runs**; nothing excluded by calibration. Command: `python -m experiments.run_v08 --mode eval` (seeds 9000-9059; output `results/v0.8/E2/eval`, git-ignored; guards: manifest verifies, tracked tree clean, output folder absent, seeds only 9000-9059).
