# PROTOCOL R3 — COCRO evaluation (PRE-REGISTRATION; binding once committed, before any run on the seeds it names)

Status: written 2026-11-08 on branch `cocro-dev`. Inputs: `docs/COCRO_DESIGN.md` (sections 0–12), `docs/COCRO_TOY_STUDY.md`. Nothing in this protocol was chosen after seeing held-out results. The held-out seeds named below have never been used. Seeds 8500–8519 were used once for descriptive diagnostics (`results/cocro/dev_diag`) and are **consumed**: no decision below is justified by them.

## 1. Questions and hypotheses
* **Q1 (selection).** Does choosing the rewiring by expected future gain (joint removal x addition search, CFPE scenarios, spectral surrogate) lower consensus error relative to the lexicographic first-order selector at the **same timing** (COCRO-M vs A7M)?
* **Q2 (timing).** Does opportunity-cost timing (rollout shadow price, optionally with reservation) add to Q1 (COCRO vs COCRO-M)?
* **Q3 (state-triggered baselines).** Does the final COCRO beat B8 and C1 at matched budgets?
* **Q4 (robustness).** Do the conclusions hold on other graph families, failure models and sizes (Tiers B–E)?
Hypotheses H1–H6 of `COCRO_DESIGN.md` section 8 are exploratory. Negative and inconclusive results will be reported in full.

## 2. Arms (all share the candidate generator limits, SafetyGate, strict edge budget, setup delay d = 2, cooldown 2, cap M, and identical failure traces)
Baselines, frozen and unchanged: A0 Static; A1 reactive; A7 (front-loaded, count PMF); A7M (exactly M front-loaded attempts); **A7C** (A7M with exactly COCRO's realised count on the same seed, two-stage); B8; C1. Thresholds of A1, B8, C1 and the A7 PMF are the frozen amended-calibration values in `configs/r2a/frozen` (seeds 8400-8419, counts under the actual cap); they are not retuned for the new seeds.
COCRO family (`tccer/policies/cocro.py`; sampling parameters fixed in section 4): `cocro_m` (A7 timing, COCRO selection), `cocro_mfg` (same + Fix 1 full-horizon rerank of a shortlist of 3), `cocro_l0` (act iff the net gain is positive), `cocro` (rollout shadow price), `cocro_fg` (+ Fix 1), `cocro_r` (+ Fix 2 reservation), `cocro_fgr` (both).

## 3. Seeds (disjoint from every earlier range)
| Use | Seeds |
|---|---|
| consumed diagnostics (not used for any decision) | 8500–8519 |
| **Step-2 ablation / component selection (used once, section 5)** | **8520–8539** |
| Tier A held-out (main) | 9300–9449 (150) |
| Tiers B and C held-out (topology and failure sweeps) | 9450–9549 (100 per cell) |
| Tier D scalability (timing, memory) | 9600–9619 (20) |
| Tier E noise/delay robustness | 9620–9719 (100) |
Run guards (to be implemented in `experiments/run_r3.py` following `run_r2.py`): clean tracked tree, frozen manifest verifies, output folder absent, seed range enforced; each held-out block runs exactly once.

## 4. Fixed parameters (declared now; varied only in the sensitivity analysis on development seeds)
S_sel = S_test = 8 scenarios, benefit window H = 3, K_r = 2 removals x K_a = 5 additions, slot/stride 4, forgetting phi = 0.98, c_op = 0, spectral surrogate (Laplacian surrogate only in Tier D beyond n = 200), identity calibration map, shortlist 3 where Fix 1 is on, reserve factors (1, 2) where Fix 2 is on, CFPE priors as in the code. These are the "fast" settings of the development diagnostics; the design defaults (16, 5, 3, 8) are a sensitivity point.

## 5. Step-2 component-selection rule (development seeds 8520–8539, 4 cells: S1 and S2 x M in {3, 6}; paired by seed; metric = mean consensus error E per run)
Compute for each comparison the mean paired difference per cell, d_c, and its standard error s_c over the 20 seeds. A comparison "adopts" a component only if **all** hold: (a) mean over the 4 cells of d_c <= the threshold below; (b) d_c <= 0 in at least 3 of 4 cells; (c) mean over cells of d_c / s_c <= -1.5. Otherwise the simpler/cheaper arm is kept.
* **Rule R-sel (Fix 1):** `cocro_mfg` vs `cocro_m`, and `cocro_fg` vs `cocro`; threshold -0.005. Adopt Fix 1 for a family if its rule passes in that family; if only one passes, adopt it for that family only.
* **Rule R-roll (rollout timing):** best of {`cocro`, `cocro_fg`} vs its selection-only counterpart (`cocro_m`, `cocro_mfg`); threshold **-0.010**. If the rule fails, the **proposed algorithm is the selection-only COCRO-M(fg)** and the rollout is reported as a negative ablation (it costs roughly two orders of magnitude more decision time).
* **Rule R-res (Fix 2):** `cocro_r` vs `cocro` (and `cocro_fgr` vs `cocro_fg`); threshold -0.005; evaluated only if R-roll passed.
The adopted combination is **COCRO-final**. It is frozen (code commit hash and parameters recorded in `docs/R3_FREEZE.md`) before any held-out run. After the freeze only bug fixes with accompanying tests are allowed, each documented; any other change is a protocol amendment written before the affected run.

## 6. Tier A held-out evaluation (seeds 9300–9449; cells S1, S2, S3 x M in {3, 6}; B8 excluded in S2 M6 as at calibration)
Primary family (Holm over its tests): COCRO-final vs A7M; vs B8; vs C1; and vs COCRO-M if the rollout was adopted. Margin 0.01 (150 seeds: with paired SD about 0.05 the minimum detectable effect is about 0.011 at 80% power; the analysis reports the observed SD) and 0.02. Secondary (labelled exploratory): vs A1, A0, A7C; every component ablation; per-mutation efficiency. Always reported: mean, SD, 95% bootstrap CI (10,000 resamples), rank-biserial and standardised effect sizes, realised mutation counts and budget utilisation, disconnection, recovery, worst-case E, overhead, decision time, memory. Paired Wilcoxon, Holm within family, Benjamini-Hochberg across tiers.

## 7. Further tiers (parameters frozen in an addendum BEFORE any run on them)
Tier B: Erdos-Renyi, Barabasi-Albert, Watts-Strogatz (generator to be implemented), scale-free; sizes 100, 200 (500 if compute allows). Tier C: cascading, node, correlated/repeated-burst, regime-switching and mobility-driven failures on RGG-80 (models to be implemented; each model's parameters declared in the addendum). Tier D: sizes up to the largest that fits the compute budget, decision time and memory with CIs. Tier E: observation noise and delay. Anything not implemented by the time of the final analysis is reported as not done, never simulated.

## 8. Fairness
Identical failure traces; same gate/budget/delay; A7C (matched count) and budget-sweep curves; an oracle-headroom analysis (best fixed-offset schedule per seed with hindsight) bounds what any adaptive policy could gain over A7; disclosed asymmetries: COCRO uses the consensus model, link adjacency and a posterior over failure parameters that A1/A7 do not, and its decision time is about two orders of magnitude larger (no compute-matched comparison is made).

## 9. Known limitations carried into the evaluation (not fixed before it)
Persistence-valued link removal, delayed credit and the debt ledger update are not implemented; per-link heterogeneous hazards are not implemented; the base policy cannot see links still being set up (biases the one-step rule toward waiting when >= 2 units remain, `COCRO_DESIGN.md` section 12); the failure model assumes lagged-adjacency propagation and a short/long downtime mixture; theory is assumption-dependent and covers only what the code implements.

## 10. Compute plan
Measured (n = 40, 80 epochs, one core): COCRO about 13 s, with Fix 1 about 26 s, both fixes about 28 s per run (decision about 145-340 ms per epoch against about 2 ms for A7M), after exact (bit-identical) speed-ups. Tier A at 150 seeds x 6 cells x 3-4 COCRO arms is a few hours on 11 workers; Tier B-E sizes are limited by this budget and will be stated.

## 11. Raw-result preservation
Per-run per-epoch CSVs written once with a SHA-256 manifest, never overwritten; analysis reads them and writes only to its own folder; archive prepared for deposit by the authors.

## 12. Addendum 1 (written after Step 2 and the environment work, BEFORE any held-out run)
**12.1 Outcome of the pre-declared Step-2 rule (development seeds 8520-8539; `results/cocro/step2`, git-ignored).** None of the six adoption rules passed (rollout timing: mean dE -0.0011, z -0.10 against the -0.010 threshold; Fix 1 selection-only: -0.0040, z -0.74; Fix 2: +0.0019 / -0.0031). By section 5 the proposed algorithm is the selection-only **COCRO-M (`cocro_m`)** with the section-4 parameters. The rollout and its fixes are retained only as labelled exploratory arms, and the rollout is reported as a negative result for timing in these scenarios. Frozen in `docs/R3_FREEZE.md`.
**12.2 Arms per tier (all arms see identical failure traces).** Tier A (cells S1, S2, S3 x M in {3, 6}): A0, A1, A7, A7M, B8 (not in S2 M6), C1, `cocro_m`, ablations of `cocro_m` (`cocro_m_plug` posterior mean instead of posterior draws; `cocro_m_k1` a single removal candidate; `cocro_m_nb1` no lagged-adjacency term; `cocro_m_s1` one scenario; `cocro_m_lap` Laplacian surrogate), `cocro_mfg` (Fix 1), and `cocro` (rollout; S1 and S2 only for cost). Tier B (ER, BA, WS, scale-free, n = 100, M in {6, 12}): A0, A7M, `cocro_m` and the same ablations; A1, B8, C1 are excluded because their thresholds are not calibrated for these environments and calibration is out of scope (reported as a limitation). Tier C (RGG-40 with extended failures, M in {3, 6}): A0, A7M, `cocro_m`, ablations (plug, k1, nb1), `cocro` (rollout), and A1, B8, C1 at their frozen S1 thresholds (calibrated for the original failure model, NOT re-tuned; exploratory).
**12.3 Tier B and C environments (frozen in `configs/r3/frozen`, manifest verified before every run).** Template: the S1 configuration (40-node geometry replaced where stated; 80 epochs, 60 rounds, p_fail 0.005, p_repair 0.1, p_transient 0.05, spatial bursts rate 0.1, setup delay 2, strict edge budget). B: ER (n 100, p_init 0.06, p_pot 0.10); BA (m 3, p_pot 0.08); WS (k 6, p 0.1, p_pot 0.08); scale-free power-law cluster (m 3, p 0.3, p_pot 0.08). C (n 40): cascade (hazard x6 for links adjacent to a link down in the previous epoch); node (rate 0.01 per epoch, repair 0.3); regime (from epoch 40 the link failure probability x4); mixed (cascade x4, node 0.005, regime x3 from epoch 40). Mobility-driven change, link-observation noise/delay (COCRO reads link states directly; the engine's noise option perturbs only the E/C/V signals COCRO does not use) and Tier D/E are NOT run unless an addendum is written before they are.
**12.4 Confirmatory families (Holm within family; margins 0.01 and 0.02; declared in `experiments/analyze_r3.py`).** Tier A primary: `cocro_m` vs A7M, vs B8, vs C1 (17 tests). Tier B primary: `cocro_m` vs A7M (8 tests). Tier C primary: `cocro_m` vs A7M (8 tests). **H2** (pre-declared, Tier C only): the rollout (`cocro`) has lower E than `cocro_m` in the regime and mixed cells (4 tests); an exploratory comparison of the rollout in the cascade and node cells is labelled as such. Ablation families (Tier A: 6 ablations x 6 cells; Tier B: 6 x 8; Tier C: 3 x 8) are confirmatory-for-components but not used to change the algorithm. Everything else is exploratory.
**12.5 Compute (measured on smoke runs, one core per run).** Per (cell, seed) across all arms: about 30 s (tier A, S1/S2), 60 s (tier B), 33 s (tier C): roughly 25-40 minutes of wall-clock per tier on 11 workers. Decision time per epoch (mean over a run, n = 40): A7M about 1.4-2 ms, `cocro_m` about 5 ms, `cocro_mfg` about 17 ms, `cocro` (rollout) about 41-52 ms in these smoke runs; at n = 100 `cocro_m` about 68 ms.
**12.6 Known limitations unchanged from section 9, plus:** the Step-2 decision used 20 seeds x 4 cells of two scenarios only; the rollout may matter under conditions not covered there (tested by H2); Tier B/C baselines other than A7M are not calibrated for the new environments.
