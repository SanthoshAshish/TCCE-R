# v0.6 experiment protocol: does accumulated resilience debt add information beyond an instantaneous error threshold?

**Status: FINAL (revision 3, 2026-10-10).**
- Revision 2 was approved, with D-1 to D-6.
- Revision 3 makes two changes before freezing:
  - defines the backlog and retry semantics precisely (§2.1, §2.3);
  - pre-specifies the Wilcoxon all-zero-difference case (§6.4).
- This file is frozen when it is committed together with the implementation, before calibration.
- Existing tags `v0.1`–`v0.5`, `archive/`, `configs/` and `results/` stay untouched.
- Numbers marked *(measured)* come from read-only checks on the current code (`v0.5`) or on archived data.

**Freeze sequence.** The protocol becomes binding at step 1; nothing in it may change after step 4 begins.
1. This file → `docs/PROTOCOL_v0.6.md`, committed with the implementation, which is tested on tuning seeds only.
2. Calibration on tuning seeds 100–119 produces the frozen values in §3.4.
3. The calibration outputs and a SHA-256 manifest are committed.
4. **One** evaluation run on held-out seeds 6000–6059, then the analysis exactly as specified here.

The protocol is **not changed after evaluation outcomes have been seen**. Any later idea is reported separately as a labelled post-hoc analysis and never replaces the pre-specified one.

---

## 0. Question, scope and the meaning of conclusions

> At an **equal number of topology reconfigurations**, does an accumulated stress statistic (CUSUM debt) choose *when* to reconfigure better than an instantaneous consensus-error threshold?

Only the **trigger** varies between arms. These are identical for every arm:
- the candidate generator, the λ₂-based lexicographic selector, the safety gate;
- the strict edge budget, the setup delay and the cooldown;
- the failure trace and x(0).

**Conclusions are condition-specific.**
- Each delay × budget cell (d ∈ {2, 8} × M ∈ {3, 6}) is analysed and reported **on its own**.
- A result in one cell is not generalised to other cells, other delays or budgets, other network sizes or models, or other failure models.
- No pooled "overall" verdict is computed.

## 1. Fixed environment

| item | value |
|---|---|
| Base configuration | `configs/v0.4/selected_d2.yaml` with `link_setup_epochs` = d. Network: RGG, n = 40, `init_radius` 0.22, `radio_range` 0.32. 80 epochs × 60 rounds, ε = 0.01. |
| Failures | transient p = 0.05/round; background on/off p_fail = 0.005, p_repair = 0.10; bursts: rate 0.10/epoch, radius 0.15, duration U{2..6} |
| Budget and gate | `budget_on: configured`, `edge_budget_frac: 1.0` (every mutation is a rewire); `degree_fix`, `degree_basis: configured`, `feedback_after_setup`, `failed_link_value: if_up`; d_max = 10, λ₂ floor 0.05, edge cooldown 5 epochs |
| Cells | (d, M) ∈ {2, 8} × {3, 6}. d = 2 is primary; d = 8 is the costly-reconfiguration case. |
| RNG streams | `[seed,0]` graph, `[seed,1]` transient and background failures, `[seed,2]` x(0), `[seed,3]` policy randomness (A6), `[seed,4]` bursts. Identical across arms for a given seed (existing tests). |
| Software | Python 3.11.9, numpy 2.3.4, scipy 1.17.1, pandas 2.3.3 *(measured)*; recorded in every run folder together with the git commit hash |

## 2. The eight arms

### 2.1 Rules shared by all arms
- **Decision timing.** At the end of epoch k (after E_k, C_k, V_k are measured), an arm may *attempt* a mutation. A successful mutation takes effect from epoch k + 1; its new link is usable from k + 1 + d.
- **Cooldown.** An attempt is allowed only if k − (epoch of the last *successful* mutation) ≥ 2.
- **Hard cap.** At most **M** successful mutations per run. After M successes the arm makes no further attempts.
- **Selector and safety.** Every attempt calls the same `MutationPipeline.select` (same candidates, lexicographic rule, safety gate, budget, edge cooldown).
- **Attempt outcome.** An attempt either succeeds (one mutation applied) or fails (no valid mutation passed the gate). A failed attempt changes nothing: no reset, no cooldown, no count. All attempts and failures are logged per epoch.
- **At most one attempt per epoch, for every arm.** An arm never makes two attempts, and never applies two mutations, in the same epoch.
- **Order of checks at the end of epoch k, identical for all arms:**
  1. update the arm's statistic (A5: apply any feedback first);
  2. if realised = M, stop (cap);
  3. if the cooldown is not satisfied, no attempt;
  4. if the arm's attempt condition holds, make one attempt.

### 2.2 Definitions

| Arm | Statistic Sₖ | Attempt condition | Reset rule | Fixed parameters | Calibrated (§3) |
|---|---|---|---|---|---|
| **A0 Static** | — | never | — | — | — |
| **A1 Reactive** | E_k | S_k > h | none | — | h |
| **A2 Moving average** | mean(E_j for j = max(0, k−3)..k), i.e. window 4, shorter for k < 3 | S_k > h | none (window slides; Gençata thesis §4.4.5) | w = 4 | h |
| **A3 CUSUM-E** | D_k = max(0, D_{k−1} + E_k − κ_E), D₋₁ = 0 | D_k > Θ | D ← 0 after a **successful** mutation; unchanged after a failed attempt | κ_E (frozen, §3.1) | Θ |
| **A4 CUSUM-ECV** | D_k = max(0, D_{k−1} + s_k − κ_s), s_k = 0.5E_k + 0.3C_k + 0.2V_k | D_k > Θ | as A3 | κ_s (frozen, §3.1) | Θ |
| **A5 TCCE-R** | as A4 | D_k > Θ_k | as A4. Θ adaptation below | κ_s; α = 0.25, β = 0.10, H = 3; bounds factors (¼, 4) | Θ₀ |
| **A6 Random timing** | — | at scheduled epochs (§2.3) | — | schedule from stream `[seed,3]` | none |
| **A7 Front-loaded** | — | at scheduled epochs (§2.3) | — | schedule 0, 2, 4, …, 2(M−1) | none |

**A5 threshold adaptation (D-1).**
- Θ starts at the calibrated Θ₀ and stays within **[Θ₀/4, 4·Θ₀]**. These factors are frozen now; they are the same ratios as the v0.1 bounds [0.25, 4.0] around Θ = 1.
- For a mutation decided at epoch m, its "after" window is epochs m+1+d .. m+d+3 and its "before" window is m−2 .. m.
  - **Success** means mean E in the after window < mean E in the before window. Then Θ ← max(Θ₀/4, Θ·(1−β)).
  - **Failure:** Θ ← min(4Θ₀, Θ·(1+α)).
- An update is applied at epoch m+d+3. Windows that would extend past epoch 79 produce no update; this is logged.
- **Logged per epoch:** Θ_k, D_k, any update applied (S/F), and the mutation epoch it refers to. **Per run:** number of updates, successes and failures, and final Θ.

### 2.3 Intended vs realised mutations for A6 and A7 (D-3)

**Intended schedule** (independent of failures, x(0) and every observed quantity):
- **A6:** draw M distinct epochs uniformly from {0, …, 79} using the `[seed,3]` stream. Redraw the whole set until all pairwise gaps are ≥ 2, so the cooldown never blocks a scheduled epoch by construction. The schedule is logged.
- **A7:** epochs {0, 2, 4, …, 2(M−1)}, the earliest schedule the cooldown allows.

**Execution rule (backlog counter; precise definition):**
- The arm keeps a **backlog counter P** of owed attempts, starting at P = 0.
- At the end of each epoch k:
  1. If k is a scheduled epoch, P ← P + 1.
  2. The arm makes **one** attempt if and only if P > 0, realised < M and the cooldown is satisfied (k − last success ≥ 2).
  3. On **success**: P ← P − 1, realised ← realised + 1, last success ← k. On **failure**: P is unchanged and the arm tries again at the next eligible epoch.
- **A backlog can delay later mutations.**
  - When an attempt fails, its retries continue every epoch.
  - If a further scheduled epoch passes meanwhile, P = 2.
  - After the next success, the cooldown forces the following attempt to wait at least 2 epochs.
  - So realised mutation epochs are always **at or after** the scheduled ones, never earlier, and the arm never makes more than one attempt per epoch.
- This rule is chosen so that the intended budget M is still pursued after failures. Dropping missed attempts would lower realised counts and confound the budget comparison.
- **Lag:** for the j-th realised mutation, lag_j = (realised epoch) − (j-th scheduled epoch). Lags are logged and summarised per arm. Without any failed attempts the lag is 0 by construction: A6 gaps are ≥ 2, and A7's spacing equals the cooldown.
- Attempts in this rule depend only on the schedule, the cooldown and whether the selector found a valid move, **never on E, C or V**.
- The constraints are the same as for A1–A5: the same cooldown, cap, selector and safety gate, and one attempt per epoch. A1–A5 have no backlog because they re-evaluate their condition every epoch.

**Counts:** intended = M. **Realised** = successes by epoch 79, which is ≤ M. Unexecuted = intended − realised, reported per run together with the number of failed attempts and the epochs of realised mutations.

For **A1–A5**, "intended" means the calibration target M (§3.2), and realised is the per-seed count under the cap. Both are reported, together with how often the cap was hit.

## 3. Calibration on tuning seeds 100–119 and freezing (D-2, D-4)

### 3.1 Static-derived constants (A0 on seeds 100–119 only)
- **τ** = 75th percentile of E⁰_k pooled over all 80 epochs × 20 seeds, where E⁰ is static consensus stress (episode threshold, §4).
- **κ_E** = median of E⁰_k over **connected** epochs (in-control) × 20 seeds.
- **κ_s** = median of s⁰_k = 0.5E⁰ + 0.3C⁰ + 0.2V⁰ over connected epochs × 20 seeds.

All three are computed once, frozen and reported to 4 decimals. Static does not depend on d or M (see §6.1), so one set of 20 runs suffices.

### 3.2 Thresholds: matched activity, never matched outcome
- For each arm a ∈ {A1, …, A5} and delay d ∈ {2, 8}, run the arm **uncapped**, keeping the cooldown and every other rule, on seeds 100–119 over a fixed 40-point grid:
  - h (A1, A2): linear grid 0.30 → 0.98;
  - Θ (A3, A4) and Θ₀ (A5): geometric grid 0.05 → 20.
- For each M ∈ {3, 6}, select the grid value whose **mean uncapped count** over the 20 seeds is closest to M. Ties go to the larger threshold.
- **Only mutation counts are used.** E, λ₂, disconnection, precision and every other outcome are never consulted during calibration.
- **Why uncapped:** under a cap, the realised count saturates at M as the threshold falls, so "closest to M" would choose the lowest threshold and make every arm spend its budget as early as possible.
- **Feasibility:** if no grid value gives a mean within ±15% of M (2.55–3.45 for M = 3; 5.1–6.9 for M = 6), that (arm, d, M) is marked *not calibratable*. It is excluded from tests and reported as such. It is never re-tuned on evaluation seeds.
- A6 and A7 need no calibration.

### 3.3 Leakage guards
1. Tuning seeds 100–119 are used only for §3.1, §3.2 and the dry run (§3.5). Evaluation seeds 6000–6059 are used only in the single evaluation run.
2. No archived run has used seeds ≥ 6000 *(measured; archived ranges 0–19, 1000–1029, 2000–2029, 3000–3029, 4000–4029, 5000–5029)*.
3. The evaluation script reads only the frozen files and refuses to run if the manifest hash does not match.
4. The analysis code and its parameters (§4–§6) are frozen at step 1. The evaluation analysis runs them unchanged.

### 3.4 Frozen before evaluation (complete list)
- **Constants:** τ, κ_E, κ_s.
- **Calibrated thresholds:** h(A1), h(A2), Θ(A3), Θ(A4), Θ₀(A5) for each of the 4 cells, with their calibration means and the not-calibratable flags.
- **Fixed parameters:**
  - A5: bounds factors ¼ and 4; α = 0.25, β = 0.10, H = 3;
  - A2: w = 4;
  - all arms: cooldown 2, cap M.
- **A6/A7 schedule rules;** episode rules (§4); metric definitions (§5); tests, families, margins and decision rules (§6); bootstrap seed 20261010.
- **Evaluation seeds** 6000–6059.
- **Code:** the git commit hash of the implementation, and the per-cell config files `configs/v0.6/frozen/<arm>_d<d>_M<M>.yaml`.

### 3.5 Dry run
The full pipeline runs once on seeds 100–119 with the frozen values. Purpose: catch errors; its results are not reported as findings.

## 4. Episode labelling: policy-free (D-5)

**Source.** Labels come only from the A0 run on the same seed. A0 shares the failure trace and x(0) with every arm and never acts, so labels cannot depend on any evaluated arm's outcomes.

- **Degraded epoch:** E⁰_k > τ (τ frozen in §3.1).
- **Episode:** a maximal run of consecutive degraded epochs, with length L.

**Primary classification (used by the decision rule):**

| L | class |
|---|---|
| 1–2 | transient |
| 3 | intermediate (excluded from precision and false alarms; reported) |
| ≥ 4 | persistent |

**Sensitivity classifications (descriptive only; never used by the decision rule):**

| variant | transient | intermediate | persistent | effect compared with primary |
|---|---|---|---|---|
| S3 | L ≤ 2 | none | L ≥ 3 | episodes of length 3 move from intermediate to persistent |
| S6 | L ≤ 2 | 3 ≤ L ≤ 5 | L ≥ 6 | episodes of length 4–5 move from persistent to intermediate |
| Disconnection label | as primary, but "degraded" = the A0 network is disconnected (`components > 1`) instead of E⁰_k > τ | | | |

**Further rules:**
- **Censoring.** An episode still running at epoch 79 is classified by its observed length and flagged. If it has L ≤ 2 when censored, it is marked "transient (censored)" and included in the false-alarm count as transient.
- **Non-degraded epochs** (E⁰_k ≤ τ) form their own class, "calm".

## 5. Metrics (per seed; the seed is the unit of analysis)

A mutation "at epoch m" was decided at the end of epoch m. It takes the class of epoch m.

| Metric | Exact definition |
|---|---|
| **Consensus error E** (primary outcome; called "consensus stress" in the paper) | e_k(t) = ‖x(t) − x̄1‖ / ‖x(0) − x̄1‖ (defined as 0 if x(0) is constant). E_k = 1 − min(1, max(0, ln e_k(60) / ln 0.01)). Run value Ē = (1/80) Σ_{k=0..79} E_k. Range [0, 1]; **lower is better**. |
| Final disagreement | (1/80) Σ e_k(60) (secondary) |
| Disconnected fraction | (1/80) · #{k : arm's live graph has > 1 component} |
| λ₂ | (1/80) Σ λ₂ of the arm's live graph at epoch k (0 if disconnected) |
| Mutations | realised successes; attempts; failed attempts; cap hit (yes/no); intended (§2.3) |
| **Precision** | #(mutations at persistent epochs) ÷ #(all realised mutations). Undefined if the run made 0 mutations; that seed is dropped from this metric and n is reported. |
| **False-alarm share** | #(mutations at transient or calm epochs) ÷ #(all realised mutations). Also reported split into transient and calm. Precision + false-alarm share + intermediate share = 1. |
| **Detection rate** | #(persistent episodes containing ≥ 1 realised mutation at some m ∈ [s, s+L−1]) ÷ #(persistent episodes). Undefined if the seed has no persistent episodes. |
| **Detection delay** | For each detected persistent episode: (first mutation epoch in it) − s, in epochs. Per run: mean over detected episodes. Misses are counted in the detection rate, not given a delay. |
| **Wasted release** | A realised rewire at epoch m whose released link ℓ was failed at m (`removed_failed_link = true`), and for which some t ∈ [m+1, m+d+3] has ℓ **not down** in the failure trace (background ∪ bursts ∪ scripted). Per run: count, and rate = count ÷ #(failed-link releases), undefined if that is 0. The trace is rebuilt from (config, seed) and must reproduce the logged `n_down_potential` exactly, or the analysis aborts. |
| **Anchored recovery time** | For each start s of an A0 disconnection episode (policy-free anchor): r = min{t ≥ s : arm's graph connected at t} − s, or censored at 80 − s if none. Per run: mean r (censored values at their bound), number of anchors, number censored. |
| Own disconnection-episode length | descriptive; censoring flagged |
| Second-half error | (1/40) Σ_{k=40..79} E_k (secondary; earliness check) |
| Reconfiguration exposure | Σ_k (links in setup at epoch k) |
| A5 diagnostics | Θ trajectory, number of Θ updates, successes and failures |

## 6. Run count, runtime and statistics

### 6.1 Exact evaluation run count
**Static reuse.** A0 never mutates, so neither d (it only affects links being set up) nor M (it only caps mutations) can change it.
- *Measured:* archived v0.4 Static rows are identical across d ∈ {0, 2, 4, 8} on all 22 logged columns (30 seeds × 80 epochs).
- A0 is therefore run **once per seed** and its output is used in all 4 cells.
- A unit test confirms bit-identity between d = 2 and d = 8 before the evaluation run.

| Component | Formula | Runs |
|---|---|---|
| A0 Static | 1 per seed × 60 seeds | **60** |
| A1–A7 | 7 arms × 4 cells × 60 seeds | **1,680** |
| **Evaluation total** | 60 + 1,680 | **1,740** |
| (without Static reuse) | 8 × 4 × 60 | (1,920) |

**Reconciliation with the previous draft:** "1,500" was 25 runs per seed × 60 seeds, with **six** mutating arms (A1–A6). Adding A7 adds 4 runs per seed: 29 × 60 = **1,740**. The earlier "840" was 7 arms × 2 × 2 × 30 seeds *without* Static reuse and without A7.

### 6.2 Other runs

| Component | Formula | Runs |
|---|---|---|
| Static on tuning seeds (§3.1) | 20 | 20 |
| Calibration (§3.2) | 5 arms × 2 delays × 40 grid values × 20 seeds; uncapped runs reused for both M | 8,000 |
| Dry run (§3.5) | 20 + 7 × 4 × 20 | 580 |
| Static-identity unit test | 2 runs × 1 seed | 2 |
| C-2 uncapped sensitivity, part of the single evaluation run (seeds 6000–6059) | 5 arms (A1–A5) × 4 cells × 60 seeds | 1,200 |
| C-4 A2-reset sensitivity (tuning seeds 100–119 only) | 1 arm × 4 cells × 20 seeds | 80 |
| **Total, all stages** | | **11,622** |

*Revision 3 correction:* the C-2 and C-4 rows were specified in §7 but missing from this table in revision 2. They are secondary and descriptive and do not affect any confirmatory test. The single evaluation run therefore has **2,940 runs**: 1,740 primary plus 1,200 C-2.

### 6.3 Runtime
*Measured per-run time on this laptop with the current code: 0.38–0.57 s; mean of the six measured arm/delay combinations ≈ 0.44 s; slowest = reactive at d = 8, 0.57 s.*

| Stage | Runs | Typical (0.44 s) | Upper (0.57 s) |
|---|---|---|---|
| Evaluation, primary | 1,740 | 12.8 min | 16.5 min |
| Evaluation, C-2 uncapped | 1,200 | 8.8 min | 11.4 min |
| Calibration | 8,000 | 58.7 min | 76.0 min |
| Dry run + static + C-4 | 680 | 5.0 min | 6.5 min |
| **Total (sequential)** | 11,620 (+2) | **≈ 1 h 25 min** | **≈ 1 h 50 min** |

Runs are executed in parallel worker processes (12 cores available). Results are identical to sequential execution because every run is determined by (config, seed, arm) alone.

- The measurement used only 3 seeds × 3 arms. The upper column assumes every run is as slow as the slowest measured. Analysis time (seconds) is excluded.
- Seeds are independent, so parallel processes would reduce wall time; results are deterministic either way.

### 6.4 Tests and families
- **Pairing.** Within a cell, arms are paired by seed. Two-sided Wilcoxon signed-rank, scipy 1.17.1 `wilcoxon(x, y, zero_method="wilcox", method="auto")`. With n = 60 and no ties this uses the normal approximation; the method actually used is recorded.
  - **All-zero case (revision 3).** If every paired difference is exactly 0 (the test is undefined), p is set to 1.0, the comparison is flagged "identical", and the verdict is "practically equivalent".
  - **Partially zero differences** are handled by `zero_method="wilcox"`, which drops zeros. The number of non-zero pairs is reported.
- **Primary family (4 tests):** A3 vs A1 on Ē, one per cell. Holm-adjusted across the 4.
- **Confirmatory secondary family (28 tests):** on Ē only, per cell:
  - A2–A1 (smoothing alone);
  - A3–A2 (CUSUM vs moving average);
  - A4–A3 (do C and V add information?);
  - A5–A4 (Θ adaptation);
  - A1–A6 and A3–A6 (informed vs random timing);
  - A1–A7 (earliness control).

  7 × 4 tests, Holm-adjusted together.
- **Exploratory:** every other metric and comparison. Paired mean differences with CIs, no p-values in the main text.
- **Not-calibratable** arm–cells are dropped from their family, and m (the number of tests in the Holm family) is reduced accordingly, with this stated.

### 6.5 Effect sizes
For every comparison X − Y in a cell:
- the mean paired difference Δ̄ = (1/n) Σ_seeds (metric_X − metric_Y);
- its 95% bootstrap percentile CI (10,000 resamples of seeds, RNG seed 20261010) and its 95% t-interval;
- the matched-pairs rank-biserial correlation r = (W⁺ − W⁻)/(W⁺ + W⁻), where W± are the signed-rank sums.

### 6.6 Margins, signs and decision rules (D-6)
Throughout, **Δ = A3 − A1**, computed per seed and then averaged.
- **Error margin δ_E = 0.02**, absolute, on Ē (scale 0–1). Because lower Ē is better, **ΔĒ ≤ −0.02 means A3 is better by at least the minimum meaningful effect**, and ΔĒ ≥ +0.02 means A1 is better by at least that much.
- **Precision margin δ_P = 0.05**, absolute, on precision (scale 0–1). Higher precision is better. **Non-inferiority of A3** means the lower bound of the 95% bootstrap CI of Δprecision is > −0.05. Seeds where either arm's precision is undefined are excluded, and n is reported.

**Verdict in each cell** (Holm p from the primary family):

| Verdict | Condition |
|---|---|
| **"Accumulated debt adds meaningful timing information"** | Holm p < 0.05 **and** ΔĒ ≤ −0.02 **and** precision non-inferior |
| "A3 better, but below the minimum meaningful effect" | Holm p < 0.05 and −0.02 < ΔĒ < 0 |
| "A3 better on error, but precision not shown non-inferior" | Holm p < 0.05, ΔĒ ≤ −0.02, precision CI lower bound ≤ −0.05 |
| **"Instantaneous threshold meaningfully better"** | Holm p < 0.05 and ΔĒ ≥ +0.02 |
| "A1 better, but below the minimum meaningful effect" | Holm p < 0.05 and 0 < ΔĒ < +0.02 |
| "Practically equivalent" | Holm p ≥ 0.05 and the 95% bootstrap CI of ΔĒ lies entirely within (−0.02, +0.02) |
| "Inconclusive" | Holm p ≥ 0.05 and the CI extends beyond ±0.02 |

**Statistical significance is not practical importance.** A Holm p < 0.05 shows a detectable difference. Only a mean difference beyond the 0.02 margin counts as meaningful. Both are always reported.

**Secondary comparisons** use the same structure: secondary-family Holm p, ±0.02 on Ē, and "equivalent"/"inconclusive" by CI. Precision non-inferiority applies only to the primary comparison.

### 6.7 Sample-size justification (D-4)
Paired-difference SDs of Ē in archived v0.4 data (TCCE-R − reactive) *(measured)*: 0.034 at d = 2, 0.046 at d = 8. Minimum detectable effect at power 0.8 at the strictest Holm step of the primary family (α = 0.0125), with Wilcoxon efficiency 0.955:

| seeds | d = 2 | d = 8 |
|---|---|---|
| 30 | 0.021 | 0.029 |
| **60** | **0.015** | **0.020** |

With 60 seeds a 0.02 effect is detectable at roughly 80% power even in the d = 8 cells. The SDs are proxies from different arms; achieved precision is reported via the CIs.

## 7. Confounds and how they are handled

| # | Issue | Handling |
|---|---|---|
| C-1 | **Earliness**: mean error over 80 epochs rewards early, lasting changes regardless of timing quality (v0.4: reactive's first mutation at epoch 1.2 vs 11.3) | A7 (earliest legal schedule) and A6 (uninformed); second-half error; detection and anchored-recovery metrics |
| C-2 | Realised counts vary per seed; caps can truncate late actions | Report intended vs realised counts, cap-hit rate and calibration error. Secondary: uncapped evaluation with the same frozen thresholds (labelled secondary). |
| C-3 | **Proxy objective**: the selector maximises Laplacian λ₂, while consensus uses Metropolis weights | Identical for all arms; stated as a limitation. Low-value mutations shrink every timing effect. |
| C-4 | Reset asymmetry (A2 none; A3/A4 reset) | Each uses its standard form; A2-reset sensitivity on tuning seeds only (§3.5), descriptive |
| C-5 | Failed-attempt retries depend on the selector's feasibility | Same rule for all arms; attempts and failures logged |
| C-6 | Labels describe the unmodified network | Required for policy-free labels; the disconnection label and S3/S6 are descriptive sensitivity checks |
| C-7 | A5 at d = 8 gets few Θ updates (feedback lags 11 epochs) | Report the update count; interpret A5–A4 at d = 8 accordingly |
| C-8 | Different κ scales across CUSUM variants | κ from each arm's own static in-control median (D-2), frozen and reported |
| C-9 | A2 partial window for k < 3 | Mean of available values (stated) |
| C-10 | Episode cut-offs and τ are choices | Pre-specified primary plus S3, S6 and disconnection variants (descriptive) |
| C-11 | One network model and one failure model | Conclusions are condition-specific (§0) |

## 8. Implementation needed after final approval (none started)
1. **Policies:** A2, A3/A4 (CUSUM with configurable κ and fixed Θ), A5 bounds rule, A6, A7. Unit tests:
   - trigger, reset and cooldown rules;
   - the cap;
   - failed-attempt retry and queueing;
   - A6 gap constraint and stream independence;
   - A7 schedule;
   - A0 identity across d.
2. `experiments/calibrate_v06.py`: §3.1–3.2, writes the frozen configs and the manifest.
3. `experiments/run_v06.py`: manifest check; A0 once per seed; arms per cell.
4. `experiments/analyze_v06.py`: labels, trace rebuild and check, §5 metrics, §6 statistics and verdict table, figures. Unit-tested on synthetic sequences with known answers.
5. Results go to `results/v0.6/`, archived to `archive/v0.6/`, tagged `v0.6`. Nothing existing is modified.
