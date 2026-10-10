# v0.7 protocol: eight-method comparison with bias-corrected adaptive feedback

**Status: FROZEN with the implementation commit, before any v0.7 calibration or held-out run.**
- This protocol adopts the v0.6 protocol (`docs/PROTOCOL_v0.6.md`, revision 4) wherever not stated otherwise.
- The v0.6 evaluation is frozen and is not repeated.
- Mathematical definitions: `docs/MATH_SPEC_v0.7.md`.

## 1. Question
Across three network/failure scenarios and two mutation budgets, how do the eight methods compare on consensus error at matched reconfiguration activity? In particular, does **full TCCE-R (A5)**, now with counterfactual (bias-corrected) Θ feedback, outperform:
- **Reactive (A1)**, and
- the **Front-loaded schedule (A7)**, the best method in v0.6?

No outcome is assumed. **Conclusions are specific to each cell.**

## 2. Arms (identical shared machinery; only the trigger differs)
Definitions are those of v0.6 §2 (`tccer/policies/v06.py`), with one change: **A5 uses `feedback_rule: counterfactual`.**

| Arm | Trigger |
|---|---|
| A0 Static | never acts |
| A1 Reactive | E_k > h |
| A2 Moving average | 4-epoch mean of E > h |
| A3 CUSUM-E | debt on E with κ_E; fixed Θ |
| A4 CUSUM-ECV | debt on 0.5E + 0.3C + 0.2V with κ_s; fixed Θ |
| A5 Full TCCE-R | A4 with adaptive Θ ∈ [Θ₀/4, 4Θ₀], α = 0.25, β = 0.10, H = 3, **counterfactual feedback** (success / failure / neutral) |
| A6 Random timing | schedule at random epochs (gaps ≥ 2) |
| A7 Front-loaded timing | schedule at epochs 0, 2, 4, … |

- **A6/A7 counts:** per-seed intended count drawn from the calibration-seed distribution of A1–A5 realised counts (v0.6 revision 4 procedure).
- **Shared by all arms:** one attempt per epoch; cooldown 2; cap M; the same selector, safety gate, strict budget and failure trace.

## 3. Scenarios, cells and seeds

| Scenario | File | Network | Failures |
|---|---|---|---|
| S1_rgg40_bursty | `configs/v0.7/scenarios/S1_rgg40_bursty.yaml` | RGG n = 40, init radius 0.22, range 0.32 | transient 0.05; background p_fail 0.005, p_repair 0.10; bursts (rate 0.10, radius 0.15, 2–6 epochs) |
| S2_rgg40_background | `…/S2_rgg40_background.yaml` | as S1 | transient 0.05; background p_fail 0.01, p_repair 0.10; **no bursts** |
| S3_rgg80_bursty | `…/S3_rgg80_bursty.yaml` | RGG n = **80**, radii × √(40/80) (0.1556 / 0.2263), the same expected degree | as S1 |

- **Shared settings:** strict edge budget (every mutation is a rewire), setup delay **d = 2**, 80 epochs × 60 rounds, all audit fixes on, `feedback_rule: counterfactual`.
- **Cells:** 3 scenarios × M ∈ {3, 6} = **6 cells**.

**Seeds** (disjoint from every earlier range):

| Purpose | Seeds | Use |
|---|---|---|
| Calibration | 200–219 | thresholds, constants, A6/A7 count distributions only |
| Development / smoke | 300–319 | tests and smoke runs only; never reported |
| **Held-out** | **7000–7059** | one evaluation run only; never used for tuning |

## 4. Calibration (tuning seeds only; `experiments/calibrate_v07.py`)
1. **Per scenario, from A0 runs:**
   - τ = 75th percentile of E;
   - κ_E = median of E over connected epochs;
   - κ_s = median of 0.5E + 0.3C + 0.2V over connected epochs.
2. **Thresholds:** for each arm A1–A5 and scenario, run uncapped over a 40-point grid (h: 0.30–0.98 linear; Θ/Θ₀: 0.05–20 geometric). For each M, choose the value whose **mean uncapped mutation count** is closest to M (ties → larger). Feasibility: within ±15% of M, otherwise *not calibratable* and excluded. **No outcome metric is used.**
3. **A6/A7 count distributions:** run capped A1–A5 with the chosen thresholds on the same seeds; the realised counts give the empirical count distribution per cell.
4. **Freeze:** write all configs, constants, the report and the count distributions to `configs/v0.7/frozen/` with a SHA-256 manifest, and **commit before** the held-out run. Recalibration is refused once frozen.

## 5. Held-out run (`experiments/run_v07.py --mode eval`)
- A0 runs once per scenario and seed; the seven other arms run per cell.
- **Runs: 3 × 60 + 7 × 6 × 60 = 2,700.**
- **Guards:**
  - the manifest verifies;
  - the tracked tree is clean;
  - the output folder doesn't exist;
  - seeds are 7000–7059 only.
- **Records:** the commit, library versions, manifest, every config's SHA-256 and a completeness check (every arm × seed × 80 epochs) go into `run_info.json`.
- **The run happens once.**

## 6. Metrics (per seed; v0.6 §5 definitions unless stated)
- **Primary:** consensus stress **E**, the mean over 80 epochs.
- **Connectivity:** disconnected fraction; λ₂ (= R, provisional).
- **Recovery:** anchored recovery time (from Static disconnection onsets).
- **Activity:** mutations (realised and intended).
- **Reconfiguration cost:**
  - pending link-epochs (links in setup);
  - **live-link releases**, i.e. mutations whose removed link was working;
  - wasted releases.
- **Timing quality:** precision, false-alarm share and detection rate, with episode labels from the A0 run and τ per scenario.
- **A5 feedback quality:** number of Θ updates; shares of success, failure and neutral; mean Δ.
- **Robustness (exploratory):** second-half E; E on seeds with equal realised counts.

## 7. Statistics
- **Unit of analysis:** the seed (n = 60), paired within a cell.
- **Test:** two-sided Wilcoxon signed-rank (`zero_method="wilcox"`); p = 1 when every difference is zero.
- **Primary family (12 tests, Holm):** A5−A1 and A5−A7 on E in each of the 6 cells.
- **Secondary family (42 tests, Holm):** on E in each cell:
  - A2−A1, A3−A1, A3−A2, A4−A3, A6−A1, A7−A1;
  - A5−A4 (the effect of Θ adaptation with counterfactual feedback).
- **Exploratory:** all other metrics. Paired mean differences with 95% bootstrap CIs (10,000 resamples, seed 20261010) and t-intervals; **no p-values**.
- **Effect sizes:** mean paired difference, bootstrap and t CIs, rank-biserial r.
- **Minimum meaningful effect:** |ΔE| = **0.02**.

**Verdict per test** (v0.6 §6.6 without the precision clause):

| Verdict | Condition |
|---|---|
| "first arm meaningfully better" | Holm p < 0.05 and ΔE ≤ −0.02 |
| "first arm better, below minimum" | Holm p < 0.05 and −0.02 < ΔE < 0 |
| "second arm meaningfully better" / "…below minimum" | the mirror images |
| "practically equivalent" | Holm p ≥ 0.05 and the bootstrap CI lies inside ±0.02 |
| "inconclusive" | otherwise |

**No pooling across cells.**

**Sample size:** 60 seeds. v0.6 measured paired SDs of 0.034–0.046 for E, giving a minimum detectable effect of about 0.015–0.020 at power 0.8 at the strictest Holm step of a 4-test family. With 12 primary tests the strictest step is α = 0.05/12, so the detectable effect is about 0.017–0.023. This is stated, not adjusted.

## 8. Runtime (measured v0.6 throughput: 2,940 runs in 391 s on 11 workers)

| Stage | Runs |
|---|---|
| Calibration | 60 static + 12,000 grid + 600 capped = 12,660 |
| Evaluation | 2,700 |

S3 (n = 80) is slower per run. Estimated wall time: about 25–40 min for calibration and about 8–12 min for evaluation.

## 9. Confounds and limitations (stated in advance)
- **Earliness (v0.6 C-1)** remains the main confound. A7 is included so it is measured, not hidden.
- **Counterfactual feedback assumes an exact model of the consensus dynamics,** plus a log of observed link states and inputs (`docs/MATH_SPEC_v0.7.md` §4). It is a centralised, model-based attribution.
- **R = λ₂ is provisional; M is a lexicographic ranking.** Both await the professor's definitions (`docs/MATH_SPEC_v0.7.md` §2–3).
- **Not modelled:** load, traffic, trust/uncertainty and adversarial attacks.
- **Scope:** only RGG topologies, at two sizes. Each cell is a separate condition.

## 10. Smoke test (development seeds only; `--smoke`)
- **Calibration:** seeds 300–301 with a 6-point grid, written to `results/v0.7/smoke/`. Arms that aren't calibratable are still written, so every code path runs.
- **Evaluation:** seeds 302–303.
- **Analysis:** with `--smoke`.

Smoke numbers are **not results** and are never reported as findings.
