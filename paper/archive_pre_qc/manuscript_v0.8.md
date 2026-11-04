# When Does Resilience-Aware Topology Adaptation Help Consensus? A Budget-Constrained Comparison of Reactive, Front-Loaded and Predictive Rewiring

**Authors:** [AUTHOR NAMES — TO BE COMPLETED] · **Affiliations:** [TO BE COMPLETED] · **Corresponding author:** [TO BE COMPLETED]

> Revised manuscript (v0.8). Every result-dependent number in the Abstract, Results, Tables and Discussion is generated from `revision/analysis/E2/` (held-out evaluation, seeds 9000–9059) or `results/v0.8/E1/` (development seeds) by `paper/tools/build_manuscript_v08.py`; the qualitative claims are asserted against those files by `paper/tools/check_claims_v08.py`. Items that could not be verified are marked **[UNRESOLVED]**. The previous (v0.7) manuscript is preserved unchanged in `paper/manuscript.md`.

## Abstract

**Purpose.** Networks that rewire links to survive failures can keep distributed consensus working, but it is unclear when a resilience-aware rewiring controller is worth its complexity compared with simple reactive or timing-based rules. We ask when a controller that accumulates a "resilience debt" and selects rewirings by a predictive, risk-filtered score reduces consensus error under a fixed rewiring budget, relative to a reactive threshold (A1) and to state-blind front-loaded schedules (A7, A7M).

**Methods.** We simulate random geometric networks with 40 and 80 nodes under transient, background and spatially correlated burst failures, with rewiring budgets of 3 and 6 per run (six conditions). Twelve arms share one candidate generator, safety gate and edge budget and differ in when and which link is rewired. Thresholds were calibrated on separate seeds using mutation counts only, frozen, and the arms were evaluated once on 60 held-out seeds (4,500 runs). Comparisons are paired by seed (Wilcoxon signed-rank, Holm correction within pre-specified families, bootstrap confidence intervals) against a practical-effect margin of 0.02 in consensus error.

**Results.** The predictive controller B8 had lower error than the reactive threshold A1 in all six conditions (ΔE −0.041 to −0.014; Holm p ≤ 0.025), beyond the margin in 3 of the six. The front-loaded schedule A7 had lower error than B8 in all six point estimates (ΔE B8 − A7 = 0.010 to 0.056, i.e. A7 lower), Holm-significant in five and inconclusive in S2, M = 6; the exact-budget variant A7M had lower error than B8 in all six conditions. A hybrid that front-loads before adapting (H1) was not distinguishable from A7. Adding bridge or volatility signals (B2–B4) did not improve on A1, accumulation into a debt (B5 vs B4) gave small differences confounded with threshold and count, and adaptive thresholds and counterfactual feedback (B8 vs B6, B7) changed mean error by at most 0.0055. A comparison of B6 with B5 is consistent with the predictive selector contributing to B8's advantage over A1, but a separate validation on development seeds found little selector headroom, a discrepancy we did not resolve. Against A1, B8 reduced disconnection in the bursty conditions at the price of more live-link releases; against A7 it showed lower disconnection but higher error.

**Conclusion.** In these simulated conditions, a predictive, risk-filtered selector helped relative to a reactive threshold, yet no resilience-aware controller beat simple front-loaded timing, and the adaptive threshold and counterfactual feedback showed no measurable benefit. We offer a framework and a controlled, reproducible evaluation with explicit calibration limitations (notably S2, M = 6), not a claim of superiority.

**Keywords:** distributed consensus; topology adaptation; link rewiring; network resilience; budget-constrained control; negative results

---

## 1 Introduction

Distributed averaging and consensus let nodes agree on a common value using local exchanges, and their convergence speed depends on the connectivity of the communication graph, in particular its algebraic connectivity λ₂ [1, 2, 3]. When links fail, are repaired, or are lost in correlated bursts, the effective graph changes and consensus degrades. A large literature designs the consensus law itself to tolerate such conditions, through adaptive and event-triggered protocols [4, 5, 6] and through protocols analysed under switching topologies and random link failures [7, 8, 9]. A complementary line changes the *topology*: connectivity-aware reconfiguration and rewiring [10, 11, 12, 13].

This paper concerns the second line under an explicit constraint that is often implicit in practice: only a small number M of rewirings may be spent per run. The question is then not only *which* link to add or remove but *when* to spend each rewiring. TCCE-R (Topology–Consensus Co-Evolution with Resilience debt) was designed on the intuition that a controller aware of how much consensus-error stress has accumulated, how fragile the graph is (bridge fraction) and how volatile the links are, should decide when and where to rewire better than one reacting to an instantaneous error. An earlier, pre-registered evaluation (v0.7) did not support this intuition for the original design: it was practically equivalent to a reactive threshold and worse than a state-blind front-loaded schedule. This revision asks a more specific question: **when, if ever, does resilience-aware adaptation help, and which of its components is responsible?**

**Research gap and positioning.** In the literature we reviewed (a non-systematic review, `docs/LITERATURE_REVIEW.md`), consensus work mostly designs the control law for a given or switching topology, and reconfiguration work mostly designs *where* to add links; we found few controlled comparisons of *rewiring timing* under a matched mutation budget against simple state-blind baselines. The individual ingredients we use are established: CUSUM statistics [14] (including on network structure [15]), bridge detection, algebraic connectivity and its first-order gain estimate [1, 16], hazard-based failure estimates and counterfactual replay. We do **not** claim novelty for any of them. Whatever novelty exists lies in their integration in a budget-constrained controller, in the resilience-debt formulation, and above all in the systematic evaluation, including baselines that expose the importance of timing.

**Research questions.**
- **RQ1.** Does the predictive controller B8 reduce consensus error relative to a reactive threshold (A1)?
- **RQ2.** Does B8, or a hybrid that front-loads then adapts (H1), match or beat a front-loaded schedule (A7, A7M)?
- **RQ3.** Which components (extra signals, accumulation, predictive selection, adaptive threshold, counterfactual feedback) are associated with changes in error?
- **RQ4.** What trade-offs appear among consensus error, disconnection and recovery, and reconfiguration overhead?

**Contributions.** (i) A fully specified, reproducible protocol with separate calibration, development and held-out seed ranges, a frozen calibration and a single held-out evaluation. (ii) A controlled comparison of twelve arms that share the candidate generator, safety gate and edge budget, including front-loaded baselines (A7, A7M) and one-component-at-a-time ablations. (iii) A predictive, risk-filtered selector (B8) whose objective follows the form J = αE + βR + γC + δS (no uncertainty term, because uncertainty is not modelled) and an honest account of what it does and does not achieve. (iv) A report of negative and mixed results with the diagnostics, calibration limitations and scripts needed to audit them. These are a framework and an evaluation, not a proven algorithmic advance.

## 2 Related Work

**Adaptive and event-triggered consensus.** Recent work proposes adaptive, dynamic and predefined-time event-triggered consensus protocols for nonlinear, fractional-order, fault-prone and attacked multi-agent systems, often under switching topologies [4, 5, 6, 17, 18, 19, 20, 21]. These works design the triggering and control law for the *states*; the topology is given. Our controller instead triggers *topology mutations*, and its trigger (a CUSUM on a stress signal) is a different object from the event-triggered communication rules above.

**Time-varying topology and link failures.** Consensus and related algorithms have been analysed under random link failures, random subgraphs, time-varying topologies and adversarial behaviour [7, 8, 9, 22, 23, 24]; predictive control has been applied to consensus in switching networks [25]. Our failures are benign (transient outages, background on–off failures, spatially correlated bursts), nodes are honest, and we do not modify the consensus law, which is Metropolis-weight averaging [2].

**Connectivity-aware topology control and rewiring.** Connectivity can be preserved or restored by edge addition, rewiring or reconfiguration, using algebraic connectivity, k-connectivity or model-predictive formulations, in multi-robot, multi-vehicle and complex-network settings [10, 11, 12, 13, 26, 27, 28, 29, 30, 31]. The first-order gain in λ₂ from adding a link is classical [16] and is what our shared candidate ranking uses.

**Resilience and recovery.** Resilience has been studied through reconfiguration after disasters, self-healing, recovery models and augmentation against geographically correlated failures [32, 33, 34, 35, 36, 37, 38]. Our burst model is motivated by geographically correlated failures; our recovery measures (longest disconnection, anchored recovery time) are simple descriptive statistics, not an optimisation target.

**Predictive and counterfactual control.** Model-predictive control has been used for connectivity preservation [30, 31], learning-based methods for link prediction and topology optimisation [39, 40, 41], and CUSUM-type statistics for detecting changes in network structure [15]. Our predictor is deliberately simple: a hazard-based, expected-Metropolis surrogate with a union-bound risk proxy (Section 4.5), not a learned model; our counterfactual feedback is a model-based replay inside the simulator and requires an exact model of the consensus dynamics. We do not compare with learned or model-predictive controllers.

**Mutation-budget constraints.** Link-limited rewiring and online robustness under connectivity constraints [10, 11] are close in spirit to our per-run cap M and strict edge budget; our setting adds a setup delay and failures during operation.

**Statistical methodology.** Paired nonparametric testing [42], Holm's sequentially rejective correction [43], the bootstrap [44] and equivalence reasoning with a smallest effect size of interest [45] underlie the analysis. Citations in this section are supported at the level of titles and bibliographic metadata verified against Crossref (abstracts and full texts were not read for this revision); we have not re-derived any cited result (`revision/literature/LITERATURE_AUDIT_v08.md`).

## 3 System Model

**Network and failures.** A network has n nodes in the unit square (n = 40 or 80) and a set of *candidate* links between node pairs within radio range; a subset is *configured* initially (links within an initial radius). Time is divided into epochs k = 0,…,79 of T = 60 consensus rounds. A configured link is *live* in an epoch if it is not failed and not in setup. Three failure processes act: (a) transient outages (each configured link unusable in each round independently with probability 0.05); (b) background on–off failures per epoch (fail probability p_fail, repair probability 0.1); (c) spatially correlated bursts (S1, S3): a burst starts with probability 0.1 per epoch, and fails every potential link whose midpoint lies within radius 0.15 of a uniformly random centre for 2–6 epochs. S2 has no bursts and a higher background failure rate. A new link becomes usable after a setup delay of d = 2 epochs; a removed link disappears immediately.

**Consensus error.** At the start of every epoch each node draws fresh initial values x(0). Over T rounds nodes apply Metropolis averaging on the live graph of the round: for live neighbours i, j, W_ij = 1/(1 + max(d_i, d_j)), W_ii = 1 − Σ_j W_ij. With x̄ the mean of x(0),

$$e(t)=\frac{\lVert x(t)-\bar x\mathbf 1\rVert}{\lVert x(0)-\bar x\mathbf 1\rVert},\qquad E_k = 1-\min\Bigl(1,\max\Bigl(0,\frac{\ln e_k(T)}{\ln\varepsilon}\Bigr)\Bigr),\quad \varepsilon=0.01 .$$

E_k ∈ [0, 1] (0: the error fell to ε or below within the epoch; 1: no progress). **Lower E is better.** The primary outcome of a run is the mean of E_k over its 80 epochs.

**Control problem.** A logically centralised controller observes the graph and the history of E_k, C_k and V_k and may *mutate* the topology at most once per epoch and at most M times per run. Every mutation is a *rewire*: it removes one configured link and adds one candidate link (strict edge budget). The question is *when* to attempt a mutation and, for some arms, *which* candidate to choose; the candidate generator and the safety gate are identical across arms.

**Scope.** The controller is centralised (global graph information, exact-model counterfactual replay). Node load, traffic, trust and adversarial attacks are not modelled. The simulator contains options for non-geometric graphs, an abrupt-outage shock and controller-side observation noise or delay, but **none of them is used in any experiment reported here**, and they would perturb only the controller's trigger statistics, not its feedback, candidate scoring or safety gate (`revision/audit/V08_CODE_REVIEW.md`). No claim about distributed operation, partial observation or other graph families is made.

## 4 Mathematical Formulation and Method

### 4.1 Signals, stress and resilience debt

Let L_k be the live links and Q_k the configured links in epoch k. The three measured signals are the consensus error E_k (Section 3), the structural fragility C_k = 1 if the live graph is disconnected, otherwise C_k = (number of bridges)/|L_k|, and the link volatility V_k = min(1, (1/|Q_k|) Σ_{w=k−2}^{k} flips_w), where flips_w counts up/down changes of configured links in epoch w (own mutations excluded). All three lie in [0, 1]. The stress is s_k = w_E E_k + w_C C_k + w_V V_k with weights ≥ 0 fixed in code: A3 uses (1, 0, 0); the arms with the full stress (A4, A5, B5–B8, H1) use (0.5, 0.3, 0.2), which sum to one; no weight tuning was performed. The **resilience debt** is Page's one-sided CUSUM [14],

$$D_k=\max\bigl(0,\ D_{k-1}+s_k-\kappa\bigr),\qquad D_{-1}=0,$$

with reference value κ ≥ 0 equal to the median of the corresponding stress over connected epochs of the static arm A0 on calibration seeds (the κ values are listed in Appendix B). The debt is reset to 0 only after a successful mutation (exception: phase 1 of H1, Section 4.6). It is unbounded above while the controller cannot act.

### 4.2 Trigger and adaptive threshold

A mutation is attempted when D_k > Θ_k, at least 2 epochs have passed since the last successful mutation, and fewer than M mutations have been made. For A5, B7, B8 and H1 the threshold adapts within [Θ₀/4, 4Θ₀]: Θ ← 0.9Θ after a successful mutation, Θ ← 1.25Θ after a failed one, unchanged if neutral (factors hard-coded). B5, B6 use a fixed Θ = Θ₀. The instantaneous arms (A1, B2–B4) attempt when the instantaneous statistic exceeds a fixed h (E for A1; (0.5E + 0.3C)/0.8, (0.5E + 0.2V)/0.7 and 0.5E + 0.3C + 0.2V for B2, B3, B4).

### 4.3 Counterfactual and legacy feedback

For a mutation at epoch m, the **counterfactual** rule replays the window {m + 1,…,m + d + H} (d = 2, H = 3) from the pre-mutation snapshot with and without the mutation under the identical observed failures, outages and initial values; with Δ the mean E with minus the mean E without, the outcome is success if Δ < 0, failure if Δ > 0 and neutral (no update) if Δ = 0. Each mutation is replayed alone and no future information is used. The replay assumes an exact model of the consensus dynamics. The **legacy** before/after rule (B7) declares success when the mean E over the H epochs after setup is lower than over the H epochs up to the mutation; it is biased towards success by regression to the mean (on archived v0.6 data it labelled 67–73% of no-op placebo mutations as successes).

### 4.4 Shared candidate generation and safety gate

Under a full strict budget every candidate removes the same configured link r (the one with the smallest first-order λ₂ loss, never a bridge while connected) and adds one candidate link a. Candidates are ranked lexicographically by (i) change in the number of components, (ii) the first-order gain (f_i − f_j)² of λ₂ with f the Fiedler vector [16], (iii) change in the number of bridges, (iv) link length; at most 30 are examined. A candidate is accepted only if: no touched edge is in its 5-epoch cooldown; the added link is not currently failed; the edge budget holds; both endpoints keep degree ≤ 10; the number of components does not increase (final and interim state); and λ₂(after) ≥ min(R_min, λ₂(before)) with R_min = 0.05. These are implementation constraints evaluated on the *current* failure state; they are **not** guarantees about the future.

### 4.5 Predictive, risk-filtered selection (B6, B7, B8, H1)

From the shared generator and gate, the feasible shortlist 𝒜 (at most 10 candidates) is scored together with the null action a₀. With horizon H = d + 3 = 5 and per-epoch link failure/repair hazards h, r estimated online from the last 10 epochs (priors 0.02 and 0.10 with weight 20), each configured link gets a survival weight q_e = (1 − h)^{H/2}(1 − p_tr) if it is up and (1 − (1 − r)^{H/2})(1 − p_tr) if it is down (the added link counts as up). The expected Metropolis matrix uses edge weights q_e/(1 + max(d_u, d_v)) with expected degrees d; with ρ its second-largest eigenvalue, the **predicted error** is E(a) = 1 − clip(T·(−ln ρ)/ln(1/ε), 0, 1) (a spectral-gap surrogate; the Jensen gap is ignored). The **risk proxy** is R(a) = min(1, (c − 1)(1 − r)^H + (#bridges)(1 − (1 − h)^H)) on the graph of configured links that are not down (union bound; links still in setup are counted as up). The **rewiring cost** is C(a) = 0.25 + 0.75·[a releases a working link], C(a₀) = 0, and the **setup penalty** is S(a) = max(0, E_int(a) − E(a₀))·d/H, with E_int the predicted error on the break-before-make graph. The objective is

$$J(a)=\alpha E(a)+\beta R(a)+\gamma C(a)+\delta S(a),\qquad (\alpha,\beta,\gamma,\delta)=(1,\,0.5,\,0.05,\,1),$$

with an *empirical* risk constraint R(a) ≤ max(0.20, R(a₀)). The controller acts on a* = argmin J over the candidates that satisfy it iff J(a₀) − J(a*) > 0; otherwise the attempt fails (a deferral) and may repeat next epoch. This is the form suggested for the formal objective, **without an uncertainty term U (uncertainty is not modelled)**; the cap |A_k| ≤ M and the safety gate are the constraints; the weights are untuned defaults. There is **no mathematical guarantee** that the risk constraint bounds the probability of disconnection: R is an empirical proxy whose rank agreement with replayed outcomes we assess on development seeds (Section 6.9).

### 4.6 Arms

Table 1 lists the twelve arms, Figure 1 shows the architecture of the v0.7 design from which they derive and Figure 2 the per-epoch procedure of B8. A1 is the reactive baseline (B1). A5 is the TCCE-R of the v0.7 study. A7 attempts at epochs 0, 2, 4, … with a per-seed intended count drawn from the empirical distribution of calibrated arms' counts; A7M attempts at the same epochs with exactly M intended attempts. B2–B4 add bridge and volatility signals to an *instantaneous* trigger: the protocol's list of signal sets does not state whether B1–B4 accumulate, and accumulating them would make B4 identical to B5, so we adopted the instantaneous reading as a **design assumption**; debt-based variants are not evaluated. B5 is the accumulated debt with fixed Θ (= A4) at B8's Θ₀; B6 adds the predictive selector; B7 is B8 with the legacy feedback rule; B8 is the complete predictive controller. **H1 (Hybrid-FrontRisk)** first makes F = ⌈M/2⌉ state-blind front-loaded rewirings (F = 2 for M = 3, F = 3 for M = 6; an attempt is owed from epoch 2·n_front on, selected by the lexicographic rule as in A7; phase 1 ends after F successes or at epoch 4F), which count against M but neither reset the debt nor feed the threshold adaptation (a design choice, not a tuned one), and is then exactly B8. Static (A0) never mutates and defines κ, τ and the recovery anchors.

| Arm | Code policy | Attempt when | Candidate selection | Threshold | Feedback | Calibrated |
|---|---|---|---|---|---|---|
| A0 Static | static | never | - | - | - | no (reference) |
| A1 Reactive (B1) | v06_reactive | E_k > h | lexicographic first choice | fixed h | - | yes (h) |
| A5 TCCE-R (v0.7) | v06_tccer | D_k > Θ (E, C, V debt) | lexicographic first choice | adaptive Θ | counterfactual | yes (Θ₀) |
| A7 Front-loaded | v06_front | epochs 0, 2, 4, … until the intended count | lexicographic first choice | - | - | count PMF from calibrated arms |
| A7M Front-loaded, exact M | v06_front (no PMF) | epochs 0, 2, …, 2(M−1) | lexicographic first choice | - | - | no |
| B2 E + C | v08_b2 | (0.5E + 0.3C)/0.8 > h | lexicographic first choice | fixed h | - | yes (h) |
| B3 E + V | v08_b3 | (0.5E + 0.2V)/0.7 > h | lexicographic first choice | fixed h | - | yes (h) |
| B4 E + C + V | v08_b4 | 0.5E + 0.3C + 0.2V > h | lexicographic first choice | fixed h | - | yes (h) |
| B5 debt (= A4) | v06_cusum_ecv | D_k > Θ (E, C, V debt) | lexicographic first choice | fixed Θ = B8's Θ₀ | - | no (inherits B8) |
| B6 debt + predictive | v08_rcpr_fixed | D_k > Θ | predictive, risk-filtered (Sec. 4.5) | fixed Θ = B8's Θ₀ | - | no (inherits B8) |
| B7 B8, legacy feedback | v08_rcpr_legacy | D_k > Θ | predictive | adaptive Θ | legacy before/after | no (inherits B8) |
| B8 predictive controller | v08_rcpr | D_k > Θ | predictive | adaptive Θ | counterfactual | yes (Θ₀) |
| H1 Hybrid-FrontRisk | v08_hybrid | phase 1: A7-style, F = ⌈M/2⌉; then as B8 | lexicographic (phase 1), predictive (phase 2) | adaptive Θ (phase 2) | counterfactual (phase 2) | no (inherits B8) |


*Table 1. Arms. "Calibrated" means the threshold was chosen on calibration seeds from mean mutation counts; B5–B7 and H1 inherit B8's Θ₀ and κ so that each step differs in one component. All arms share the cooldown of 2 epochs, the cap M, one attempt per epoch, the candidate generator, the safety gate, the strict edge budget and the setup delay.*

**Algorithm 1 (one epoch of B8; Figure 2 gives the same procedure graphically).**

```
inputs: E_k, C_k, V_k measured; state: D, Θ, n_mutations, last_success, pending feedback
 1  feedback: for every mutation whose window {m+1..m+d+3} has closed, replay with/without;
            Θ ← max(Θ0/4, 0.9Θ) if Δ<0;  min(4Θ0, 1.25Θ) if Δ>0;  unchanged if Δ=0
 2  D ← max(0, D + (0.5E_k + 0.3C_k + 0.2V_k) − κ)
 3  if n_mutations = M or k − last_success < 2 or D ≤ Θ: return no mutation
 4  generate candidates (one removed link r; added links), keep the first 30 by lexicographic rank
 5  𝒜 ← feasible candidates (safety gate), at most 10
 6  if 𝒜 empty: return no mutation (failed attempt)
 7  estimate hazards (h, r); score a0 and every a ∈ 𝒜: E, R, C, S, J
 8  discard a with R(a) > max(0.20, R(a0));  a* ← argmin J over the rest
 9  if none or J(a0) − J(a*) ≤ 0: return no mutation (deferral; D unchanged)
10  apply rewire (remove r, add a*); D ← 0; last_success ← k; n_mutations += 1; register for feedback
```

![Figure 1. TCCE-R architecture of the v0.7 study (arm A5), unchanged from that study. The logically centralised controller has nine stages. In B6–B8 and H1 the selection stage (7) is replaced by the predictive, risk-filtered scoring of Section 4.5 and in B7 the feedback stage (9) uses the legacy rule; Figure 2 shows the B8 procedure. Not implemented as mechanisms: load, traffic, trust/uncertainty, attack model; R = λ₂ is provisional.](figures_v0.8/fig1_architecture.png)

![Figure 2. Per-epoch procedure of B8 and the variants derived from it. The risk filter is an empirical criterion, not a guarantee.](figures_v0.8/fig_b8_procedure.png)

## 5 Experimental Setup

The study workflow is summarised in Figure 3.

![Figure 3. Study workflow. Calibration and development seeds are separate from the held-out seeds; Amendment 1 was made before any held-out run; the analysis does not modify raw outputs.](figures_v0.8/fig_workflow_v08.png)

**Scenarios and budgets.** Three synthetic scenarios, each with 80 epochs of 60 rounds, ε = 0.01, setup delay 2 and strict edge budget, at budgets M ∈ {3, 6} (six conditions, analysed separately; Table 2): S1 (random geometric graph, n = 40, initial radius 0.22, range 0.32, background p_fail 0.005, bursts), S2 (as S1 with p_fail 0.01 and no bursts), S3 (n = 80, radii scaled by √(40/80) to keep the expected degree, as S1). No real traces were used.

| Scenario | Graph | Radii | Background failures | Bursts / budget |
|---|---|---|---|---|
| S1 | RGG, n = 40 | initial radius 0.22, range 0.32 | p_fail 0.005, p_repair 0.10 | bursts: rate 0.10, radius 0.15, 2–6 epochs |
| S2 | RGG, n = 40 | as S1 | p_fail 0.01, p_repair 0.10 | none |
| S3 | RGG, n = 80 | radii × √(40/80): 0.1556, 0.2263 | as S1 | as S1 |
| all | 80 epochs × 60 rounds | ε = 0.01; p_transient 0.05 | setup delay d = 2; cooldown 2 | strict edge budget; budgets M ∈ {3, 6} |

*Table 2. Scenarios and implemented parameters.*

| Parameter | Value (implemented defaults; not tuned) |
|---|---|
| stress weights (E, C, V) | 0.5, 0.3, 0.2 (A3: 1, 0, 0) |
| debt reference κ | median stress over connected Static epochs, calibration seeds |
| Θ adaptation | ×0.9 on success, ×1.25 on failure, bounds [Θ₀/4, 4Θ₀] |
| feedback window | d + 3 = 5 epochs |
| safety gate | cooldown 5, degree ≤ 10, λ₂ floor R_min = 0.05, components non-increasing |
| predictor | H = 5, hazard window 10 (priors 0.02, 0.10, weight 20), shortlist ≤ 10 of the first 30 |
| objective | (α, β, γ, δ) = (1, 0.5, 0.05, 1); costs 0.25 / +0.75; risk tolerance 0.20 |


**Seeds and separation.** Calibration seeds 8000–8019 (20), development seeds 8100–8119 (20; E1 predictor validation, tests and smoke runs, never reported as results and never used to set a threshold) and held-out seeds 9000–9059 (60). All are disjoint from each other and from the seed ranges of the earlier v0.7 study (calibration 200–219, held-out 7000–7059). Common random numbers are used: the graph, failure trace and initial values are generated from the seed alone and are identical across arms (checked in the validation of the analysis inputs).

**Calibration and its amendment.** Thresholds (h for A1, B2–B4; Θ₀ for A5 and B8) were chosen per condition on the calibration seeds from a 28-point grid as the value whose *mean mutation count* was closest to M, feasible within ±15% of M; no error metric was used, and calibration runs were capped at 12 mutations (the evaluation cap is M). B5–B7 and H1 inherit B8's Θ₀ and κ and were not calibrated. A7's per-seed intended counts are drawn from the pooled capped counts of the calibrated arms on the calibration seeds; A7M needs no calibration. **Amendment 1**, made before any held-out run and using the same calibration seeds and counts only: pass 1 left seven arm-cells uncalibratable (B3, B4 in S1; B4, A1 in S3 with M = 3; B2 in S3 with M = 6; one of them, B3 in S1 with M = 3, by a floating-point rounding at the exact ±15% limit), mostly because the mean count falls steeply between adjacent thresholds, and B8 in S2 with M = 6 sat on the grid minimum. We fixed the boundary comparison, added 11 finer thresholds inside the bracket of each excluded cell and 13 lower thresholds for B8 in S2 with M = 6, and re-chose only those eight arm-cells; every other arm-cell kept its pass-1 configuration byte for byte, and the pass-1 freeze is retained. All 36 calibrated arm-cells were then feasible (Appendix B). Configurations, constants, PMFs and the calibration report (78 files) were frozen with a SHA-256 manifest and committed (commit e16a208) before the held-out evaluation. (In the earlier v0.7 study, A1 in S3 with M = 3 could not be calibrated and was excluded; that historical exclusion does not apply to the present evaluation, where A1 is calibrated in all six conditions.)

**Calibration limitation (S2, M = 6).** B8's calibrated threshold in this condition is **Θ₀ = 0.0145**, the lowest threshold of all conditions and obtained only after the amendment; with θ_min = Θ₀/4 the trigger fires whenever the cooldown allows, so B5–B8 and H1 tend to act as soon as permitted there. Because calibration counts were measured with a cap of 12 but evaluation is capped at M, realised counts in the held-out run are lower than the calibration means (for B8 in S2 with M = 6, 5.03 against a calibration mean of 6.00; Table 7). **We therefore do not interpret S2, M = 6 as evidence that B5–B8 or H1 is superior**, and all conclusions are conditional on this limitation.

**Evaluation.** The 12 arms were run once on seeds 9000–9059 in each of the six conditions (4,320 runs) plus Static for each scenario (180 runs): 4,500 runs, from a clean tracked tree at commit e16a208 (Python 3.11.9, numpy 2.3.4, scipy 1.17.1, pandas 2.3.3; 615 s). No run failed or was excluded; the analysis validated arms, conditions, seeds, 80 epochs per run, completion markers, configuration hashes, caps, strict budget, rewire-only mutations and common random numbers before any statistics were computed.

**Statistical analysis.** Within each condition arms are paired by seed (n = 60). For a comparison X − Y the difference is ΔE = E_X − E_Y (negative: X has lower error). We use two-sided Wilcoxon signed-rank tests [42] (p = 1 if all differences are zero), Holm correction [43] within pre-specified families, 95% bootstrap confidence intervals [44] (10,000 resamples, seed 20261010), rank-biserial effect sizes, and a practical-effect margin of |ΔE| = 0.02 retained from the v0.7 study (fixed before those runs; the same scale as the A5 − A7 differences observed there). Families: **primary** (18 tests): B8 − A1, B8 − A7, H1 − A7 in each condition; **ablation** (48): B2 − A1, B3 − A1, B4 − B2, B4 − B3, B5 − B4, B6 − B5, B8 − B6, B8 − B7; **matched-budget** (12): B8 − A7M, H1 − A7M. An assessment is "lower error, beyond margin" (Holm p < 0.05 and |ΔE| ≥ 0.02), "lower error, below margin" (Holm p < 0.05, |ΔE| < 0.02), **"practically equivalent" only if Holm p ≥ 0.05 and the 95% bootstrap CI lies inside ±0.02**, and otherwise "inconclusive"; a non-significant result is never called equivalent on its own. Conditions are never pooled. Everything else (disconnection, recovery, worst-case error, overhead, equal-count subsets, comparisons outside the families) is **exploratory**: paired mean differences with bootstrap CIs and no p-values (the continuity comparisons in Appendix D list unadjusted p-values, labelled as such). With a paired SD of about 0.04, 60 seeds detect differences of roughly 0.02–0.025 at the strictest Holm step, so smaller effects can be missed.

**Metrics.** *Consensus error* E (mean over 80 epochs), second-half E, *worst-case error* (per-seed maximum of E_k), *disconnection* (fraction of epochs with more than one component; number of maximal disconnection episodes; longest episode), *anchored recovery* (for each start s of a disconnection episode of the static arm with the same seed, the number of epochs until the arm's own live graph is first connected, right-censored at the end of the run, averaged over the run's anchors; runs without anchors are missing), *mutation count*, *reconfiguration overhead* (pending link-epochs: link-epochs spent in setup; live-link releases: mutations whose removed link was working; reported separately and as their sum), *adaptation success rate* (successes over successes plus failures of Θ updates, adaptive arms only) and *time to consensus* (see Section 6.8). **Not computed:** wasted releases and the precision/false-alarm/detection rates of the v0.7 study (they need an episode-labelling and trace-rebuild step outside this analysis).

## 6 Results

### 6.1 Overall error

| Arm | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|
| A1 | 0.458 [0.437, 0.479] | 0.435 [0.417, 0.454] | 0.386 [0.365, 0.406] | 0.299 [0.282, 0.316] | 0.554 [0.545, 0.562] | 0.546 [0.538, 0.555] |
| A5 | 0.452 [0.433, 0.471] | 0.430 [0.411, 0.449] | 0.390 [0.369, 0.411] | 0.320 [0.305, 0.335] | 0.551 [0.542, 0.559] | 0.543 [0.534, 0.552] |
| A7 | 0.386 [0.362, 0.411] | 0.339 [0.315, 0.362] | 0.326 [0.298, 0.353] | 0.265 [0.239, 0.292] | 0.530 [0.519, 0.541] | 0.513 [0.501, 0.525] |
| A7M | 0.376 [0.352, 0.400] | 0.323 [0.300, 0.346] | 0.306 [0.281, 0.331] | 0.243 [0.219, 0.268] | 0.525 [0.514, 0.535] | 0.505 [0.494, 0.517] |
| B2 | 0.456 [0.436, 0.476] | 0.439 [0.420, 0.459] | 0.396 [0.374, 0.418] | 0.318 [0.304, 0.333] | 0.552 [0.544, 0.561] | 0.546 [0.538, 0.555] |
| B3 | 0.459 [0.438, 0.480] | 0.439 [0.421, 0.457] | 0.386 [0.365, 0.406] | 0.306 [0.290, 0.322] | 0.554 [0.545, 0.563] | 0.547 [0.539, 0.556] |
| B4 | 0.459 [0.438, 0.480] | 0.442 [0.423, 0.461] | 0.395 [0.374, 0.417] | 0.315 [0.300, 0.330] | 0.554 [0.545, 0.562] | 0.547 [0.539, 0.556] |
| B5 | 0.452 [0.433, 0.472] | 0.429 [0.411, 0.448] | 0.381 [0.361, 0.401] | 0.281 [0.265, 0.298] | 0.549 [0.540, 0.557] | 0.539 [0.531, 0.548] |
| B6 | 0.433 [0.416, 0.449] | 0.400 [0.383, 0.416] | 0.370 [0.351, 0.389] | 0.286 [0.267, 0.304] | 0.540 [0.532, 0.547] | 0.524 [0.515, 0.532] |
| B7 | 0.432 [0.416, 0.449] | 0.395 [0.378, 0.412] | 0.367 [0.349, 0.385] | 0.286 [0.267, 0.304] | 0.540 [0.532, 0.548] | 0.524 [0.515, 0.532] |
| B8 | 0.433 [0.417, 0.450] | 0.394 [0.378, 0.411] | 0.367 [0.349, 0.386] | 0.285 [0.267, 0.303] | 0.539 [0.532, 0.547] | 0.523 [0.515, 0.532] |
| H1 | 0.388 [0.366, 0.409] | 0.340 [0.319, 0.362] | 0.327 [0.304, 0.350] | 0.256 [0.235, 0.277] | 0.523 [0.513, 0.534] | 0.510 [0.500, 0.520] |
| A0 Static | 0.475 | 0.475 | 0.432 | 0.432 | 0.559 | 0.559 |


*Table 3. Mean consensus error E per arm and condition (95% t-interval over 60 seeds); lower is better. Static: no mutations.*

Figure 4 shows the same data.

![Figure 4. Mean consensus error by arm and condition with 95% t-intervals; the dashed line is Static.](figures_v0.8/fig_E_by_cell.png)

### 6.2 Primary comparisons (RQ1, RQ2)

Table 4 and Figure 5 give the primary comparisons.

| Cell | Comparison (first − second) | ΔE [95% bootstrap CI] | r (rank-biserial) | Holm p | Assessment (margin 0.02) |
|---|---|---|---|---|---|
| S1, M = 3 | B8 − A1 | −0.0248 [−0.0330, −0.0166] | −0.74 | < 0.0001 | first lower, beyond margin |
| S1, M = 3 | B8 − A7 | 0.0470 [0.0317, 0.0623] | 0.76 | < 0.0001 | second lower, beyond margin |
| S1, M = 3 | H1 − A7 | 0.0012 [−0.0090, 0.0108] | 0.08 | 1.0000 | practically equivalent |
| S1, M = 6 | B8 − A1 | −0.0412 [−0.0497, −0.0324] | −0.91 | < 0.0001 | first lower, beyond margin |
| S1, M = 6 | B8 − A7 | 0.0555 [0.0383, 0.0729] | 0.77 | < 0.0001 | second lower, beyond margin |
| S1, M = 6 | H1 − A7 | 0.0018 [−0.0096, 0.0125] | 0.09 | 1.0000 | practically equivalent |
| S2, M = 3 | B8 − A1 | −0.0183 [−0.0275, −0.0101] | −0.67 | 0.0001 | first lower, below margin |
| S2, M = 3 | B8 − A7 | 0.0418 [0.0242, 0.0588] | 0.61 | 0.0005 | second lower, beyond margin |
| S2, M = 3 | H1 − A7 | 0.0016 [−0.0133, 0.0162] | 0.04 | 1.0000 | practically equivalent |
| S2, M = 6 | B8 − A1 | −0.0140 [−0.0231, −0.0044] | −0.44 | 0.0246 | first lower, below margin |
| S2, M = 6 | B8 − A7 | 0.0195 [0.0027, 0.0358] | 0.34 | 0.1574 | inconclusive |
| S2, M = 6 | H1 − A7 | −0.0095 [−0.0241, 0.0043] | −0.08 | 1.0000 | inconclusive |
| S3, M = 3 | B8 − A1 | −0.0144 [−0.0178, −0.0111] | −0.90 | < 0.0001 | first lower, below margin |
| S3, M = 3 | B8 − A7 | 0.0096 [0.0041, 0.0152] | 0.44 | 0.0246 | second lower, below margin |
| S3, M = 3 | H1 − A7 | −0.0061 [−0.0103, −0.0022] | −0.33 | 0.1574 | practically equivalent |
| S3, M = 6 | B8 − A1 | −0.0227 [−0.0269, −0.0186] | −0.97 | < 0.0001 | first lower, beyond margin |
| S3, M = 6 | B8 − A7 | 0.0104 [0.0041, 0.0168] | 0.48 | 0.0130 | second lower, below margin |
| S3, M = 6 | H1 − A7 | −0.0031 [−0.0080, 0.0017] | −0.29 | 0.2734 | practically equivalent |


*Table 4. Primary family (18 tests, Holm over 18). ΔE = first − second; negative means the first arm has lower error. 95% bootstrap CIs; r is the rank-biserial effect size.*

![Figure 5. Primary and matched-budget paired differences with 95% bootstrap CIs; the band is the ±0.02 margin. Blue: Holm p < 0.05. Negative values favour the first arm.](figures_v0.8/fig_primary_forest.png)

**B8 vs A1 (RQ1).** B8 had lower error than A1 in all six conditions (ΔE −0.041 to −0.014), every Holm-adjusted p ≤ 0.025. Three conditions exceed the 0.02 margin (S1, M = 3: −0.0248 [−0.0330, −0.0166]; S1, M = 6: −0.0412 [−0.0497, −0.0324]; S3, M = 6: −0.0227 [−0.0269, −0.0186]) and three are below it (S2, M = 3: −0.0183 [−0.0275, −0.0101]; S2, M = 6: −0.0140 [−0.0231, −0.0044]; S3, M = 3: −0.0144 [−0.0178, −0.0111]). Statistical significance is therefore established in all six conditions, practical significance (by the 0.02 margin) in three. The S2, M = 6 estimate comes with the calibration limitation above.

**B8 vs A7 (RQ2).** The front-loaded schedule A7 had lower error than B8 in all six point estimates (ΔE B8 − A7 0.010 to 0.056). The difference is Holm-significant in five conditions and beyond the margin in 3 of them (S1, M = 3: 0.0470 [0.0317, 0.0623]; S1, M = 6: 0.0555 [0.0383, 0.0729]; S2, M = 3: 0.0418 [0.0242, 0.0588]); in S3 it is below the margin (M = 3: 0.0096 [0.0041, 0.0152]; M = 6: 0.0104 [0.0041, 0.0168]); in S2 with M = 6 it is **inconclusive** (0.0195 [0.0027, 0.0358], Holm p = 0.1574). **We do not claim that B8 outperforms A7; in this evaluation it does not.**

### 6.3 Hybrid H1 (RQ2)

H1 − A7 ranges −0.009 to 0.002 (S1, M = 3: 0.0012 [−0.0090, 0.0108]; S2, M = 6: −0.0095 [−0.0241, 0.0043]). H1 is assessed as practically equivalent to A7 in 5 conditions and inconclusive in 1; in none is it better than A7 by a Holm-significant amount. **H1 therefore does not establish superiority over A7.** H1 is clearly better than B8 (exploratory, Appendix D: for example S1, M = 6, H1 − B8 −0.0537 [−0.0663, −0.0417]). These results are consistent with the front-loaded phase being important, but they do not establish a causal mechanism: H1 also differs from B8 in how many mutations it spends (Table 7) and in when.

### 6.4 Matched-budget comparison with A7M

| Cell | Comparison (first − second) | ΔE [95% bootstrap CI] | r (rank-biserial) | Holm p | Assessment (margin 0.02) |
|---|---|---|---|---|---|
| S1, M = 3 | B8 − A7M | 0.0575 [0.0435, 0.0720] | 0.87 | < 0.0001 | second lower, beyond margin |
| S1, M = 3 | H1 − A7M | 0.0117 [0.0039, 0.0195] | 0.41 | 0.0226 | second lower, below margin |
| S1, M = 6 | B8 − A7M | 0.0714 [0.0552, 0.0881] | 0.88 | < 0.0001 | second lower, beyond margin |
| S1, M = 6 | H1 − A7M | 0.0176 [0.0069, 0.0277] | 0.52 | 0.0020 | second lower, below margin |
| S2, M = 3 | B8 − A7M | 0.0615 [0.0474, 0.0752] | 0.87 | < 0.0001 | second lower, beyond margin |
| S2, M = 3 | H1 − A7M | 0.0213 [0.0104, 0.0324] | 0.55 | 0.0014 | second lower, beyond margin |
| S2, M = 6 | B8 − A7M | 0.0415 [0.0262, 0.0563] | 0.67 | < 0.0001 | second lower, beyond margin |
| S2, M = 6 | H1 − A7M | 0.0125 [−0.0007, 0.0252] | 0.37 | 0.0410 | second lower, below margin |
| S3, M = 3 | B8 − A7M | 0.0146 [0.0093, 0.0199] | 0.69 | < 0.0001 | second lower, below margin |
| S3, M = 3 | H1 − A7M | −0.0011 [−0.0053, 0.0026] | 0.09 | 0.5315 | practically equivalent |
| S3, M = 6 | B8 − A7M | 0.0179 [0.0125, 0.0237] | 0.78 | < 0.0001 | second lower, below margin |
| S3, M = 6 | H1 − A7M | 0.0045 [0.0002, 0.0089] | 0.24 | 0.2107 | practically equivalent |


*Table 5. Matched-budget family (12 tests, Holm over 12): B8 and H1 against A7M, which makes exactly M front-loaded attempts.*

A7M had lower error than B8 in all six conditions (ΔE B8 − A7M 0.015 to 0.071; all Holm p < 0.05). Against H1, A7M is lower in four conditions (all below the margin except S2, M = 3: 0.0213 [0.0104, 0.0324]), and practically equivalent in two. **Fixed attempt budgets are not realised mutations.** A7M always spends M (3.00 and 6.00 mutations) whereas the calibrated arms realise fewer (B8: 2.30 to 5.08 depending on the condition; Table 7), so the B8 − A7M comparison matches the *cap*, not the number of mutations, and may favour A7M through its larger realised budget (not isolated here). Restricting to seeds with equal realised counts (exploratory, Appendix C) gives differences in the same direction for B8 − A7M in all six conditions, with smaller samples (32–36 seeds). The A7 arm, whose intended counts follow the calibrated arms' count distribution, realises counts close to B8's (Table 7), and is the closer count-matched comparator.

### 6.5 Component ablations (RQ3)

| Step (first − second) | Component changed | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|---|
| B2 − A1 | adding C (bridge fraction) to E, instantaneous | −0.0023 | 0.0041 | 0.0100 | 0.0195* | −0.0014* | 0.0001 |
| B3 − A1 | adding V (volatility) to E, instantaneous | 0.0007 | 0.0036 | −0.0001 | 0.0069* | 0.0002 | 0.0011 |
| B4 − B2 | adding V to E + C | 0.0031 | 0.0026 | −0.0003 | −0.0037 | 0.0013 | 0.0009 |
| B4 − B3 | adding C to E + V | 0.0001 | 0.0031 | 0.0097 | 0.0089* | −0.0003 | −0.0001 |
| B5 − B4 | accumulation (debt) instead of instantaneous trigger; B5 uses B8's Θ₀ | −0.0066 | −0.0126 | −0.0140 | −0.0337** | −0.0049 | −0.0079* |
| B6 − B5 | predictive selector instead of lexicographic first choice (same Θ₀) | −0.0196* | −0.0298** | −0.0111* | 0.0046 | −0.0091* | −0.0155* |
| B8 − B6 | adaptive Θ with counterfactual feedback (same Θ₀) | 0.0007 | −0.0055 | −0.0029* | −0.0007 | −0.0004 | −0.0003 |
| B8 − B7 | counterfactual instead of legacy before/after feedback (same Θ₀) | 0.0011 | −0.0011 | 0.0004 | −0.0005 | −0.0007 | −0.0001 |


*Table 6. Ablation steps (ΔE, first − second; * Holm p < 0.05 within the 48-test family; ** also |ΔE| ≥ 0.02). Full results with CIs in Appendix A.*

![Figure 6. Paired differences of the ablation steps with 95% bootstrap CIs; the band is the ±0.02 margin; blue: Holm p < 0.05.](figures_v0.8/fig_ablation_forest.png)

Figure 6 shows the same steps with their confidence intervals.

- **Extra signals (B2–B4 vs A1).** No step reaches the 0.02 margin in favour of the added signals. B2 is worse than A1 by 0.0195 in S2 with M = 6 (below the margin, Holm-significant); the other differences are small and mostly practically equivalent. We found no benefit from the bridge or volatility signals under an instantaneous trigger.
- **Accumulation (B5 vs B4).** Negative in all six conditions, beyond the margin only in S2 with M = 6 (−0.0337 [−0.0417, −0.0257]), the condition with the calibration limitation; B5 also uses B8's threshold and realises more mutations there (Table 7), so this step is confounded with the threshold and the count and we draw no conclusion.
- **Predictive selector (B6 vs B5).** Negative in five conditions and Holm-significant in five (beyond the margin in S1, M = 6: −0.0298 [−0.0374, −0.0220]), practically equivalent in S2 with M = 6. This is consistent with the predictive selector contributing to B8's lower error than A1, but see Section 6.9: the selector headroom found on development seeds was small, and we did not establish the mechanism.
- **Adaptive threshold (B8 vs B6) and feedback rule (B8 vs B7).** No difference reaches the margin; the largest is 0.0055 in mean error, and only one B8 − B6 comparison (S2, M = 3: −0.0029 [−0.0060, −0.0006]) and none of the B8 − B7 comparisons is Holm-significant (B8 − B7 is practically equivalent in all six conditions). Within the tested conditions we found **no measurable benefit attributable to the adaptive threshold or to counterfactual rather than legacy feedback**.

### 6.6 Trade-offs among error, disconnection, recovery and overhead (RQ4; exploratory)

| Comparison | Cell | Δ disconnected fraction | Δ longest disconnection (epochs) | Δ anchored recovery (epochs) | Δ worst-case E | Δ live-link releases | Δ pending link-epochs + live releases |
|---|---|---|---|---|---|---|---|
| B8 − A1 | S1, M = 3 | −0.045 [−0.071, −0.023] | −3.43 [−5.52, −1.68] | −1.28 [−2.09, −0.62] | −0.005 [−0.008, −0.002] | 0.30 [0.15, 0.47] | 0.35 [−0.07, 0.77] |
| B8 − A1 | S1, M = 6 | −0.031 [−0.048, −0.017] | −1.70 [−2.57, −0.95] | −0.71 [−1.12, −0.35] | −0.009 [−0.014, −0.005] | 0.47 [0.25, 0.68] | 0.10 [−0.62, 0.73] |
| B8 − A1 | S2, M = 3 | −0.031 [−0.056, −0.010] | −1.40 [−2.85, −0.18] | −0.70 [−1.36, −0.07] | −0.011 [−0.022, −0.001] | −0.13 [−0.28, 0.00] | 0.37 [0.02, 0.73] |
| B8 − A1 | S2, M = 6 | −0.001 [−0.015, 0.014] | 0.18 [−0.63, 1.08] | −0.03 [−0.38, 0.33] | 0.001 [−0.013, 0.014] | −0.08 [−0.45, 0.27] | 0.28 [−0.60, 1.10] |
| B8 − A1 | S3, M = 3 | −0.040 [−0.060, −0.021] | −3.23 [−5.57, −1.37] | −1.50 [−2.58, −0.64] | −0.003 [−0.006, 0.000] | 0.67 [0.50, 0.85] | 1.40 [0.93, 1.88] |
| B8 − A1 | S3, M = 6 | −0.045 [−0.066, −0.026] | −2.63 [−4.13, −1.35] | −1.14 [−1.67, −0.66] | −0.004 [−0.007, −0.002] | 1.00 [0.77, 1.25] | 2.12 [1.20, 3.05] |
| B8 − A7 | S1, M = 3 | −0.013 [−0.049, 0.017] | −2.17 [−5.32, 0.02] | −0.41 [−2.09, 0.61] | 0.010 [0.004, 0.017] | −1.65 [−1.92, −1.35] | −1.97 [−2.77, −1.13] |
| B8 − A7 | S1, M = 6 | −0.007 [−0.032, 0.015] | −1.18 [−2.43, −0.20] | 0.09 [−0.29, 0.45] | 0.002 [−0.003, 0.008] | −3.15 [−3.57, −2.72] | −3.88 [−5.10, −2.65] |
| B8 − A7 | S2, M = 3 | −0.057 [−0.089, −0.027] | −3.32 [−5.18, −1.62] | −2.19 [−3.73, −0.83] | 0.020 [0.002, 0.039] | −1.65 [−1.95, −1.32] | −1.72 [−2.63, −0.75] |
| B8 − A7 | S2, M = 6 | −0.064 [−0.101, −0.030] | −2.80 [−4.62, −1.08] | −1.90 [−3.34, −0.70] | 0.003 [−0.017, 0.026] | −1.28 [−1.72, −0.85] | −1.10 [−2.22, 0.02] |
| B8 − A7 | S3, M = 3 | −0.012 [−0.030, 0.005] | −1.80 [−3.47, −0.35] | −0.64 [−1.57, 0.08] | 0.003 [0.001, 0.005] | −1.12 [−1.48, −0.75] | −1.15 [−2.03, −0.22] |
| B8 − A7 | S3, M = 6 | −0.031 [−0.052, −0.014] | −3.07 [−4.93, −1.48] | −1.19 [−2.14, −0.41] | 0.002 [0.000, 0.005] | −2.20 [−2.75, −1.63] | −2.22 [−3.62, −0.78] |
| H1 − A7 | S1, M = 3 | −0.017 [−0.042, 0.004] | −1.70 [−4.53, 0.10] | −0.66 [−2.22, 0.26] | 0.002 [−0.001, 0.005] | −0.22 [−0.42, 0.00] | 0.55 [−0.05, 1.22] |
| H1 − A7 | S1, M = 6 | −0.017 [−0.040, 0.002] | −1.20 [−2.48, −0.03] | −0.30 [−0.66, 0.04] | −0.002 [−0.005, 0.001] | −1.02 [−1.32, −0.70] | −0.05 [−0.93, 0.92] |
| H1 − A7 | S2, M = 3 | −0.033 [−0.064, 0.000] | −1.93 [−3.90, 0.38] | −1.82 [−3.65, 0.06] | 0.003 [−0.013, 0.021] | −0.12 [−0.37, 0.17] | 0.78 [0.00, 1.67] |
| H1 − A7 | S2, M = 6 | −0.056 [−0.094, −0.020] | −2.67 [−4.47, −1.02] | −1.97 [−3.39, −0.83] | −0.017 [−0.032, −0.001] | −0.40 [−0.78, 0.02] | 0.53 [−0.52, 1.68] |
| H1 − A7 | S3, M = 3 | −0.018 [−0.034, −0.004] | −0.98 [−2.43, 0.23] | −0.53 [−1.07, −0.09] | 0.000 [−0.002, 0.001] | 0.12 [−0.15, 0.40] | 1.28 [0.60, 2.05] |
| H1 − A7 | S3, M = 6 | −0.021 [−0.034, −0.008] | −1.62 [−2.97, −0.33] | −0.61 [−1.12, −0.12] | −0.002 [−0.004, 0.000] | −0.47 [−0.88, −0.03] | 1.18 [0.05, 2.45] |


*Table 8. Exploratory paired differences (mean [95% bootstrap CI]; no p-values), first − second; negative disconnection, recovery and error values favour the first arm.*

Against A1, B8 had a smaller disconnected fraction in the five conditions other than S2 with M = 6 (e.g. S1, M = 3: −0.045 [−0.071, −0.023]), shorter longest disconnections (−3.433 [−5.517, −1.683] in S1, M = 3) and shorter anchored recovery (−1.277 [−2.091, −0.623]), with intervals excluding zero in those five; at the price of more live-link releases in the bursty conditions (S3, M = 6: 1.000 [0.767, 1.250]) and, in S3, more overhead (S3, M = 6: 2.117 [1.200, 3.050]). Against A7 the picture is a **trade-off**: B8 has fewer live-link releases (intervals exclude zero in all six conditions) and lower overhead (negative in all six, interval excluding zero in five), a smaller disconnected fraction in three conditions with intervals excluding zero (S2, both budgets, and S3 with M = 6; S2, M = 3: −0.057 [−0.089, −0.027]), yet a higher consensus error (Section 6.2) and a higher worst-case error in all six point estimates (interval excluding zero in three). Better continuity-related measures therefore do not imply lower error or overall superiority. Figures 7–9 show the same data by arm.

![Figure 7. Error versus realised mutations per run, by condition.](figures_v0.8/fig_tradeoff_mutations.png)

![Figure 8. Error versus reconfiguration overhead (pending link-epochs plus live-link releases), by condition.](figures_v0.8/fig_tradeoff_overhead.png)

![Figure 9. Resilience measures by arm and condition (means; uncertainty in Table 8 and the repository tables).](figures_v0.8/fig_resilience.png)

### 6.7 Realised mutation counts and the calibration limitation

| Arm | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|
| A1 | 2.32 | 5.02 | 2.03 | 4.85 | 2.02 | 4.45 |
| A5 | 2.38 | 4.82 | 2.20 | 4.63 | 2.32 | 4.70 |
| A7 | 2.48 | 5.17 | 2.32 | 4.93 | 2.38 | 5.00 |
| A7M | 3.00 | 6.00 | 3.00 | 6.00 | 3.00 | 6.00 |
| B2 | 2.10 | 4.85 | 2.08 | 4.55 | 2.13 | 4.60 |
| B3 | 2.07 | 4.62 | 2.03 | 4.63 | 2.10 | 4.48 |
| B4 | 2.07 | 4.55 | 2.10 | 4.75 | 2.18 | 4.58 |
| B5 | 2.35 | 5.18 | 2.35 | 5.47 | 2.57 | 5.77 |
| B6 | 2.25 | 4.68 | 2.28 | 5.05 | 2.23 | 4.85 |
| B7 | 2.32 | 4.83 | 2.30 | 5.03 | 2.33 | 4.92 |
| B8 | 2.33 | 4.87 | 2.30 | 5.03 | 2.43 | 5.08 |
| H1 | 2.87 | 5.65 | 2.77 | 5.40 | 2.97 | 5.83 |


*Table 7. Mean realised mutations per run (cap M in the condition label; A7M is fixed at M). Counts differ between arms; B5–B7 and H1 inherit B8's threshold.*

![Figure 10. Realised mutations per run (dot: mean; bar: minimum to maximum; dotted line: the cap M). The S2, M = 6 panel carries the calibration limitation.](figures_v0.8/fig_realised_counts.png)

Figure 10 shows the realised counts. Realised counts are below the cap on average for every calibrated arm, because the calibration targeted the mean count under a cap of 12. B5 realises more mutations than B6–B8 in S2 and S3 with M = 6 (for example S3, M = 6: 5.77 vs 5.08), and H1 uses nearly the whole budget by design. Differences in error between arms are therefore partly differences in reconfiguration activity.

### 6.8 Time to consensus

The consensus tolerance ε = 0.01 is rarely reached within the 60 rounds of an epoch: the share of epochs in which an arm never reached it ranges from 0.859 (A7M, S2, M = 6) to 1.000 (Table 9), and is at least 0.998 for every arm in S3. Time to consensus (rounds until the error falls below ε) is therefore censored at 60 in most epochs; we report its mean in the repository tables (`ttc_mean`) but it carries little information, and E, which measures progress towards ε within the epoch, is the primary outcome.

| Arm | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|
| A1 | 0.977 | 0.970 | 0.976 | 0.943 | 1.000 | 1.000 |
| A5 | 0.976 | 0.970 | 0.973 | 0.956 | 1.000 | 1.000 |
| A7 | 0.948 | 0.910 | 0.939 | 0.884 | 0.999 | 0.999 |
| A7M | 0.944 | 0.896 | 0.930 | 0.859 | 0.999 | 0.999 |
| B8 | 0.973 | 0.953 | 0.969 | 0.927 | 1.000 | 1.000 |
| H1 | 0.953 | 0.914 | 0.948 | 0.901 | 0.999 | 0.999 |
| A0 Static | 0.983 | 0.983 | 0.984 | 0.984 | 1.000 | 1.000 |


*Table 9. Share of epochs in which the consensus tolerance was not reached (non-converged share).*

### 6.9 Predictor validation on development seeds (E1) and an unexplained discrepancy

On development seeds 8100–8119 (not held-out) a passive probe scored 11,390 candidates in 1,139 decisions with the predictor and replayed each from the pre-decision snapshot. The window-matched predicted change in error correlated with the replayed change (Spearman 0.57, 95% seed-cluster bootstrap [0.51, 0.62]; direction agreement 85%). The predictive choice had lower window-level error than the average candidate (difference −0.0127) but only marginally lower than the lexicographic first choice, the rule of A4/A5/B5 (difference −0.0016, CI [−0.0030, −0.0002]), far below the 0.02 margin; the absolute predicted error was poorly calibrated, and the rule would act in 85% of decisions while, among the decisions it would defer, the best candidate would still have helped in 80%, so the deferral rule did not reliably screen out harmful moves. An exploratory within-decision analysis (post hoc) gave a mean Spearman of 0.41 (median 0.54, positive in 80% of decisions). We make **no claim of demonstrated predictive superiority**.

**Discrepancy.** E1 suggests little headroom for the selector in a single decision, yet in the held-out run B6 − B5 (the selector step) is negative in five conditions, by up to 0.030. E1 measured the window effect of one move from unadapted states, whereas B6 differs from B5 over a whole closed-loop run (including risk filtering, deferral and the resulting states); we have not analysed which of these produces the gap, so the mechanism is **not causally established**.

### 6.10 Historical v0.7 evaluation (context)

The earlier pre-registered evaluation (seeds 7000–7059; commit 7a81352; 2,640 of 2,700 planned runs because A1 in S3 with M = 3 could not be calibrated) found A5 practically equivalent to A1 in four of the five evaluable conditions and slightly worse in one, and A7 lower than A5 in all six conditions by 0.024 to 0.076 (Appendix E). Those results are unchanged and were not re-analysed here; the present B8 − A1 results differ from A5 − A1 because B8 differs from A5 by the predictive selector, and the A5 − A1 and B8 − A5 continuity comparisons are exploratory (Appendix D).

## 7 Discussion

**What the evidence supports.** (i) Statistically, B8 had lower consensus error than the reactive threshold in all six conditions, and by more than the practical margin in three. (ii) No resilience-aware arm beat front-loaded timing: A7 and A7M had lower error than B8 throughout (inconclusive for A7 in S2, M = 6), and the hybrid H1 matched but did not beat A7. (iii) The bridge and volatility signals (B2–B4), the adaptive threshold and the counterfactual feedback showed no measurable benefit; accumulation into a debt (B5 vs B4) was associated with small reductions, beyond the margin only in the calibration-limited S2, M = 6 condition where it is confounded with threshold and count. (iv) The predictive selector is the component associated with B8's advantage over A1.

**Measured findings versus hypotheses.** What we measured is the list above. Why they occurred is conjecture: front-loaded timing may help because early rewirings improve the baseline connectivity for the whole run, whereas debt-triggered rewirings often occur while the network is already disconnected (in the v0.7 mechanism check, 47–98% of A5's mutations) and may be spent repairing failures that would heal; the predictive selector may help because it avoids moves that the lexicographic rule would take; and adaptive thresholds may add little because the trigger rarely fires more than a handful of times per run. None of these was tested here.

**Novelty and significance.** The contribution is a controlled evaluation and a reproducible framework, not a new algorithmic principle: the components are established, and the best-performing simple rule (A7) uses no state at all. The practical message is that, under a small rewiring budget, *when* the budget is spent can matter more than how sophisticated the trigger is, and that a predictive selector may add value on top.

**Statistical versus practical significance.** Several differences are strongly significant but below the margin (e.g. B8 − A1 in S2 and S3 with M = 3); we report confidence intervals with the margin rather than p-values alone.

## 8 Limitations

1. **Scope.** Three synthetic scenarios, graph sizes 40 and 80, random geometric graphs only, two budgets, one failure family. No claim of generalisation to other graph families, larger networks, other failure distributions or real traces. No sensitivity analysis of the weights, κ, thresholds, horizon, cost terms, setup delay or failure intensity was performed, and no experiment with observation noise, delay or other graph families was run; the simulator options for them are untested beyond smoke tests.
2. **Controller.** Logically centralised, with an exact-model counterfactual replay; no distributed operation, partial observation or uncertainty is modelled. The predictive objective has no uncertainty term, the risk constraint is an empirical proxy that ignores link setup in its disconnection estimate, the predictor's absolute error is not calibrated, and its constants (hazard priors, cost terms, weights) are untuned defaults.
3. **Calibration.** Mean-count matching with a calibration cap of 12 and an evaluation cap of M leaves realised counts below M and different across arms; B5–B7 and H1 inherit B8's threshold; **B8's threshold in S2 with M = 6 is very low (0.0145)**; thresholds in several cells were obtained only after Amendment 1 (made before the held-out run, counts only).
4. **Design assumptions.** B1–B4 are instantaneous triggers (an interpretation, Section 4.6); H1's phase-1 handling of the debt and feedback and F = ⌈M/2⌉ are design choices; A7M uses a larger realised budget than the calibrated arms.
5. **Statistics.** 60 seeds give limited power for effects below about 0.02; conditions are not pooled, so no overall significance is claimed; several exploratory comparisons carry no multiplicity control.
6. **Metrics.** Time to consensus is heavily censored; wasted releases and detection metrics were not computed; recovery is anchored to the static arm's disconnections.
7. **Mechanisms.** The B6 − B5 effect and its tension with E1 are unexplained; no ablation of the predictive model's internal terms was run.
8. **Provenance.** Raw outputs and results are git-ignored; their integrity is recorded by SHA-256 hashes; the analysis script was not yet committed when this manuscript was drafted.

## 9 Reproducibility

Code: `tccer/`, `experiments/`; calibration seeds 8000–8019, development seeds 8100–8119, held-out seeds 9000–9059. Pass-1 calibration ran at commit 047d7c7, Amendment 1 and the frozen configuration are commit e16a208 (`configs/v0.8/frozen`, manifest of 78 entries; pass 1 kept in `configs/v0.8/frozen_pass1`); the held-out evaluation ran once at e16a208 on a clean tracked tree (`results/v0.8/E2/eval/run_info.json`). Commands: `python -m experiments.calibrate_v08`; `python -m experiments.amend_calibration_v08`; `python -m experiments.run_v08 --mode eval`; `python -m experiments.validate_predictor_v08` (E1, development seeds); `python -m experiments.analyze_v08` (analysis, outputs in `revision/analysis/E2/` with input hashes in `run_manifest.json`); `python paper/tools/build_manuscript_v08.py`; `python paper/tools/check_claims_v08.py`. The earlier v0.7 evidence is preserved (`results/v0.7`, a read-only backup with SHA-256 checksums, and `configs/v0.7`). Environment: Python 3.11.9, numpy 2.3.4, scipy 1.17.1, pandas 2.3.3. No DOI or public release exists yet **[UNRESOLVED]**. Re-running reproduces results up to floating-point round-off (a replay of the v0.7 held-out data matched all decision-bearing fields exactly and derived diagnostics to within 3.6e-15).

## 10 Conclusion

In six simulated conditions, a predictive, risk-filtered rewiring controller (B8) had lower consensus error than a reactive threshold in every condition (beyond the 0.02 margin in three), but a front-loaded schedule (A7, and the exact-budget A7M) had lower error than B8 in every point estimate, and a hybrid that front-loads before adapting (H1) only matched A7. The bridge and volatility signals, the adaptive threshold and the counterfactual feedback showed no measurable benefit, and accumulation into a debt gave only small, confounded differences; the predictive selector is associated with B8's gain over A1, but the selector's mechanism and its tension with a development-seed validation are unresolved. The results are bounded by a small simulated scope, a centralised controller, mean-count calibration (with a very low threshold in S2, M = 6) and 60 seeds per condition. We therefore present a framework and a controlled evaluation, not evidence of superiority, together with the protocol and diagnostics needed to audit and extend it.

## Declarations

- **Funding:** [TO BE COMPLETED]
- **Competing interests:** [TO BE COMPLETED]
- **Ethics approval and consent:** Not applicable (simulation only).
- **Data availability:** Per-run logs and analysis outputs: `results/v0.8/E2/eval/` (git-ignored; hashes in `revision/analysis/E2/run_manifest.json`), `revision/analysis/E2/`; v0.7: `results/v0.7/`. [Repository URL / DOI — TO BE COMPLETED]
- **Code availability:** `tccer/`, `experiments/`, `paper/tools/` in the project repository, commit e16a208 for the evaluation. [Public link — TO BE COMPLETED]
- **Author contributions:** [TO BE COMPLETED]
- **Use of AI assistance:** Drafting, code and analysis scripting were assisted by an AI model (Claude); the authors remain responsible for verifying all content. [Confirm against the target journal's policy]

## References

*45 references are cited; 36 (80%) are from 2022-2026. Reference metadata were checked against Crossref (existence, title, year); claims attached to citations are supported at the level of titles/abstract metadata only. Holm (1979): DOI not verified. Wilcoxon (1945): attribution of the signed-rank test to be checked. See `revision/literature/LITERATURE_AUDIT_v08.md`.*

1. Fiedler M (1973) Algebraic connectivity of graphs. Czechoslovak Mathematical Journal 23(2):298–305. https://doi.org/10.21136/cmj.1973.101168 [Crossref metadata verified]
2. Xiao L, Boyd S (2004) Fast linear iterations for distributed averaging. Systems & Control Letters 53(1):65–78. https://doi.org/10.1016/j.sysconle.2004.02.022 [Crossref metadata verified]
3. Olfati-Saber R, Murray RM (2004) Consensus Problems in Networks of Agents With Switching Topology and Time-Delays. IEEE Transactions on Automatic Control 49(9):1520–1533. https://doi.org/10.1109/tac.2004.834113 [Crossref metadata verified]
4. Zhang S, Liu J, Wang W, Zhang Z (2023) Topology-based dynamic event-triggered leader-following consensus of multi-agent systems under switching topologies. ISA Transactions 142:299-309. https://doi.org/10.1016/j.isatra.2023.08.010 [Crossref metadata verified]
5. Xiao P, Gu Z (2022) Adaptive Event-Triggered Consensus of Fractional-Order Nonlinear Multi-Agent Systems. IEEE Access 10:213-220. https://doi.org/10.1109/access.2021.3136892 [Crossref metadata verified]
6. Wang Y, Yang Y, Wu L (2023) Adaptive fault-tolerant consensus control of multi-agent systems with event-triggered inputs. Information Sciences 650:119594. https://doi.org/10.1016/j.ins.2023.119594 [Crossref metadata verified]
7. Battilotti S, Cacace F, d'Angelo M (2024) Consensus Analysis of Random Subgraphs for Distributed Filtering With Link Failures. IEEE Transactions on Automatic Control 69(4):2476-2483. https://doi.org/10.1109/tac.2023.3311709 [Crossref metadata verified]
8. Liu Y, Fan H, Liu L, Wang B (2024) Adaptive output consensus of heterogeneous nonlinear multi‐agent system under random link failures with partially unknown transition rates. International Journal of Robust and Nonlinear Control 34(12):7799-7820. https://doi.org/10.1002/rnc.7367 [Crossref metadata verified]
9. Fu Y, Wen G, Zhao D, Lv Y (2026) Resilient consensus of multi-agent systems with time-varying topologies and unmodeled dynamics. Systems & Control Letters 218:106579. https://doi.org/10.1016/j.sysconle.2026.106579 [Crossref metadata verified]
10. Muthirayan D, Khargonekar PP (2022) Online Algorithms for Network Robustness Under Connectivity Constraints. IEEE Transactions on Network Science and Engineering 9(4):2266-2277. https://doi.org/10.1109/tnse.2022.3160073 [Crossref metadata verified]
11. Chujyo M, Toriumi F (2024) Link-limited bypass rewiring for enhancing the robustness of complex networks. Applied Network Science 9(1):17. https://doi.org/10.1007/s41109-024-00624-4 [Crossref metadata verified]
12. Feng Y, Wang F, Liu Z, Chen Z (2024) An Online Topology Control Method for Multi-Agent Systems: Distributed Topology Reconfiguration. IEEE Transactions on Network Science and Engineering 11(5):4358-4370. https://doi.org/10.1109/tnse.2024.3417478 [Crossref metadata verified]
13. Estrada J, Djemai M, Castillo-Toledo B, Defoort M (2026) Topology Reconfiguration of Multiagent Systems under Link Failures. IEEE Control Systems Letters :1-1. https://doi.org/10.1109/lcsys.2026.3742141 [Crossref metadata verified]
14. Page ES (1954) Continuous inspection schemes. Biometrika 41(1-2):100–115. https://doi.org/10.1093/biomet/41.1-2.100 [Crossref metadata verified]
15. Zhang M, Xie L, Xie Y (2023) Spectral CUSUM for Online Network Structure Change Detection. IEEE Transactions on Information Theory 69(7):4691-4707. https://doi.org/10.1109/tit.2023.3259185 [Crossref metadata verified]
16. Ghosh A, Boyd S (2006) Growing Well-connected Graphs. In: Proceedings of the 45th IEEE Conference on Decision and Control, pp 6605–6611. https://doi.org/10.1109/cdc.2006.377282 [Crossref metadata verified]
17. Perez-Salesa I, Aldana-Lopez R, Sagues C (2023) Precise Dynamic Consensus under Event-Triggered Communication. Machines 11(2):128. https://doi.org/10.3390/machines11020128 [Crossref metadata verified]
18. Kim HJ, Yoo SJ (2023) Dynamic Event-Triggered Communication-Based Adaptive Consensus Tracking of Uncertain Nonlinear Multiagent Systems in Pure-Feedback Form. IEEE Access 11:21092-21103. https://doi.org/10.1109/access.2023.3250440 [Crossref metadata verified]
19. Wang Y, Yu S, Zhao Y (2024) Switching adaptive dynamic event-triggered consensus of nonlinear multi-agent systems under DoS attacks and communication delay. Information Sciences 682:121257. https://doi.org/10.1016/j.ins.2024.121257 [Crossref metadata verified]
20. Dong Z, Shi S, Ouyang Q, Jiang J (2026) Event-triggered adaptive predefined-time consensus for multi-agent systems under switching topologies. ISA Transactions . https://doi.org/10.1016/j.isatra.2026.08.015 [Crossref metadata verified]
21. Tian Y, Tian S, Li H, Han Q, Wang X (2022) Event-Triggered Security Consensus for Multi-Agent Systems with Markov Switching Topologies under DoS Attacks. Energies 15(15):5353. https://doi.org/10.3390/en15155353 [Crossref metadata verified]
22. Li S, Zhang S, He G, Jiang T (2024) Discrete-Time Flocking Control in Multi-Robot Systems With Random Link Failures. IEEE Transactions on Vehicular Technology 73(9):12290-12304. https://doi.org/10.1109/tvt.2024.3382617 [Crossref metadata verified]
23. Yan W, Cao X (2024) Decentralized Multitask Online Convex Optimization Under Random Link Failures. IEEE Transactions on Signal Processing 72:622-635. https://doi.org/10.1109/tsp.2023.3348954 [Crossref metadata verified]
24. Gao R, Yang G (2024) Resilient cluster consensus for discrete-time high-order multi-agent systems against malicious adversaries. Automatica 159:111382. https://doi.org/10.1016/j.automatica.2023.111382 [Crossref metadata verified]
25. Han S, Ong CJ (2025) Consensus of heterogeneous multi-agent system in switching network using model predictive control. Systems & Control Letters 204:106187. https://doi.org/10.1016/j.sysconle.2025.106187 [Crossref metadata verified]
26. Wang J, Shan Q, Zhu J, Cheng X, Wei B (2023) Algebraic-Connectivity-Based Multi-USV Distributed Formation Method via Adding a Reverse Edge. Mathematics 11(13):2942. https://doi.org/10.3390/math11132942 [Crossref metadata verified]
27. Shan Q, Liu W, Li T, Zhang H (2025) A Topology Reconfiguration Strategy for Containment Control of the Multi-USV System Based on Algebraic Connectivity. IEEE Transactions on Industrial Electronics 72(5):5322-5332. https://doi.org/10.1109/tie.2024.3472272 [Crossref metadata verified]
28. Shi G, Ishat-E-Rabban M, Bonner G, Tokekar P (2025) Fast k-connectivity restoration in multi-robot systems for robust communication maintenance: algorithmic and learning-based solutions. Autonomous Robots 49(4):34. https://doi.org/10.1007/s10514-025-10224-5 [Crossref metadata verified]
29. Shetty A, Hussain, T, Gao G (2023) Decentralized Connectivity Maintenance for Multi-Robot Systems Under Motion and Sensing Uncertainties. NAVIGATION: Journal of the Institute of Navigation 70(1):navi.552. https://doi.org/10.33012/navi.552 [Crossref metadata verified]
30. ElHamamsy A, Aghili F, Aghdam AG (2023) Connectivity Preservation and Collision Avoidance in Multi-Agent Systems Using Model Predictive Control. IEEE Transactions on Network Science and Engineering 10(3):1779-1791. https://doi.org/10.1109/tnse.2023.3234720 [Crossref metadata verified]
31. Du Z, Zhang H, Wang Z, Yan H (2025) Estimator-Based Dual-Model Predictive Control for Multi-AAVs With Connectivity-Preserving. IEEE Transactions on Network Science and Engineering 12(3):1482-1496. https://doi.org/10.1109/tnse.2025.3532475 [Crossref metadata verified]
32. Imteaj A, Akbari V, Amini MH (2023) A Novel Scalable Reconfiguration Model for the Postdisaster Network Connectivity of Resilient Power Distribution Systems. Sensors 23(3):1200. https://doi.org/10.3390/s23031200 [Crossref metadata verified]
33. Jo S, Oh J, Yoon YT, Jin YG (2024) Self-healing radial distribution network reconfiguration based on deep reinforcement learning. Results in Engineering 22:102026. https://doi.org/10.1016/j.rineng.2024.102026 [Crossref metadata verified]
34. Jiménez D, Barrera J, Cancela H (2023) Communication Network Reliability Under Geographically Correlated Failures Using Probabilistic Seismic Hazard Analysis. IEEE Access 11:31341-31354. https://doi.org/10.1109/access.2023.3255794 [Crossref metadata verified]
35. Andrés‐Thió N, Brazil M, Ras C, Thomas D (2022) Network augmentation for disaster‐resilience against geographically correlated failure. Networks 81(4):419-444. https://doi.org/10.1002/net.22138 [Crossref metadata verified]
36. Li J, Wang Y, Zhong J (2022) An Exceeding Recovery Model for Enhancing Network Resilience Against Cascading Failures. IEEE Access 10:71035-71043. https://doi.org/10.1109/access.2022.3188659 [Crossref metadata verified]
37. Awoyemi BS, Maharaj BT (2022) Improving link failure restoration in next-generation wireless sensor networks. Array 14:100147. https://doi.org/10.1016/j.array.2022.100147 [Crossref metadata verified]
38. Hafaiedh IB, Slimane MB (2022) A distributed formal-based model for self-healing behaviors in autonomous systems: from failure detection to self-recovery. The Journal of Supercomputing 78(17):18725-18753. https://doi.org/10.1007/s11227-022-04614-0 [Crossref metadata verified]
39. Mei P, Zhao Yh (2024) Dynamic network link prediction with node representation learning from graph convolutional networks. Scientific Reports 14(1):538. https://doi.org/10.1038/s41598-023-50977-6 [Crossref metadata verified]
40. Tang Q, Sun W, Liu Z, Li Q, Yuan X (2025) Multi-agent reinforcement learning based dynamic self-coordinated topology optimization for wireless mesh networks. Journal of Network and Computer Applications 239:104177. https://doi.org/10.1016/j.jnca.2025.104177 [Crossref metadata verified]
41. Binh LH, Duong TT, Le DH (2026) FRLTC: A new topology control algorithm using federated reinforcement learning for software-defined wireless sensor network in IoT. PLOS One 21(8):e0355604. https://doi.org/10.1371/journal.pone.0355604 [Crossref metadata verified]
42. Wilcoxon F (1945) Individual Comparisons by Ranking Methods. Biometrics Bulletin 1(6):80–83. https://doi.org/10.2307/3001968 [attribution of the signed-rank test to be checked; see audit]
43. Holm S (1979) A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics 6(2):65–70. https://www.jstor.org/stable/4615733  [DOI NOT VERIFIED] [DOI not verified; see audit]
44. Efron B (1979) Bootstrap Methods: Another Look at the Jackknife. The Annals of Statistics 7(1):1–26. https://doi.org/10.1214/aos/1176344552 [Crossref metadata verified]
45. Lakens D (2017) Equivalence Tests. Social Psychological and Personality Science 8(4):355–362. https://doi.org/10.1177/1948550617697177 [Crossref metadata verified]

## Appendices

### Appendix A. Full ablation family

| Cell | Comparison (first − second) | ΔE [95% bootstrap CI] | r (rank-biserial) | Holm p | Assessment (margin 0.02) |
|---|---|---|---|---|---|
| S1, M = 3 | B2 − A1 | −0.0023 [−0.0071, 0.0015] | −0.05 | 1.0000 | practically equivalent |
| S1, M = 3 | B3 − A1 | 0.0007 [−0.0039, 0.0055] | 0.05 | 1.0000 | practically equivalent |
| S1, M = 3 | B4 − B2 | 0.0031 [−0.0019, 0.0088] | 0.17 | 1.0000 | practically equivalent |
| S1, M = 3 | B4 − B3 | 0.0001 [0.0000, 0.0002] | 1.00 | 1.0000 | practically equivalent |
| S1, M = 3 | B5 − B4 | −0.0066 [−0.0171, 0.0034] | −0.21 | 1.0000 | practically equivalent |
| S1, M = 3 | B6 − B5 | −0.0196 [−0.0262, −0.0135] | −0.89 | < 0.0001 | first lower, below margin |
| S1, M = 3 | B8 − B6 | 0.0007 [−0.0027, 0.0048] | −0.13 | 1.0000 | practically equivalent |
| S1, M = 3 | B8 − B7 | 0.0011 [−0.0018, 0.0049] | −0.20 | 1.0000 | practically equivalent |
| S1, M = 6 | B2 − A1 | 0.0041 [0.0013, 0.0074] | 0.76 | 0.1307 | practically equivalent |
| S1, M = 6 | B3 − A1 | 0.0036 [−0.0018, 0.0095] | 0.19 | 1.0000 | practically equivalent |
| S1, M = 6 | B4 − B2 | 0.0026 [−0.0024, 0.0082] | 0.13 | 1.0000 | practically equivalent |
| S1, M = 6 | B4 − B3 | 0.0031 [0.0006, 0.0062] | 0.82 | 0.5469 | practically equivalent |
| S1, M = 6 | B5 − B4 | −0.0126 [−0.0218, −0.0039] | −0.37 | 0.4097 | inconclusive |
| S1, M = 6 | B6 − B5 | −0.0298 [−0.0374, −0.0220] | −0.87 | < 0.0001 | first lower, beyond margin |
| S1, M = 6 | B8 − B6 | −0.0055 [−0.0087, −0.0026] | −0.52 | 0.0625 | practically equivalent |
| S1, M = 6 | B8 − B7 | −0.0011 [−0.0037, 0.0016] | −0.26 | 1.0000 | practically equivalent |
| S2, M = 3 | B2 − A1 | 0.0100 [0.0023, 0.0179] | 0.38 | 0.4818 | practically equivalent |
| S2, M = 3 | B3 − A1 | −0.0001 [−0.0021, 0.0020] | 0.00 | 1.0000 | practically equivalent |
| S2, M = 3 | B4 − B2 | −0.0003 [−0.0015, 0.0005] | −0.40 | 1.0000 | practically equivalent |
| S2, M = 3 | B4 − B3 | 0.0097 [0.0023, 0.0174] | 0.43 | 0.2709 | practically equivalent |
| S2, M = 3 | B5 − B4 | −0.0140 [−0.0224, −0.0064] | −0.49 | 0.0692 | inconclusive |
| S2, M = 3 | B6 − B5 | −0.0111 [−0.0174, −0.0052] | −0.56 | 0.0249 | first lower, below margin |
| S2, M = 3 | B8 − B6 | −0.0029 [−0.0060, −0.0006] | −0.97 | 0.0371 | first lower, below margin |
| S2, M = 3 | B8 − B7 | 0.0004 [−0.0001, 0.0013] | 0.40 | 1.0000 | practically equivalent |
| S2, M = 6 | B2 − A1 | 0.0195 [0.0125, 0.0270] | 0.76 | < 0.0001 | second lower, below margin |
| S2, M = 6 | B3 − A1 | 0.0069 [0.0031, 0.0113] | 0.70 | 0.0138 | second lower, below margin |
| S2, M = 6 | B4 − B2 | −0.0037 [−0.0064, −0.0012] | −0.66 | 0.2709 | practically equivalent |
| S2, M = 6 | B4 − B3 | 0.0089 [0.0034, 0.0151] | 0.57 | 0.0398 | second lower, below margin |
| S2, M = 6 | B5 − B4 | −0.0337 [−0.0417, −0.0257] | −0.89 | < 0.0001 | first lower, beyond margin |
| S2, M = 6 | B6 − B5 | 0.0046 [−0.0045, 0.0138] | 0.06 | 1.0000 | practically equivalent |
| S2, M = 6 | B8 − B6 | −0.0007 [−0.0017, 0.0003] | −0.52 | 1.0000 | practically equivalent |
| S2, M = 6 | B8 − B7 | −0.0005 [−0.0011, 0.0000] | −0.87 | 1.0000 | practically equivalent |
| S3, M = 3 | B2 − A1 | −0.0014 [−0.0027, −0.0004] | −1.00 | 0.0100 | first lower, below margin |
| S3, M = 3 | B3 − A1 | 0.0002 [−0.0008, 0.0014] | −0.18 | 1.0000 | practically equivalent |
| S3, M = 3 | B4 − B2 | 0.0013 [−0.0001, 0.0029] | 0.10 | 1.0000 | practically equivalent |
| S3, M = 3 | B4 − B3 | −0.0003 [−0.0008, 0.0000] | −0.49 | 1.0000 | practically equivalent |
| S3, M = 3 | B5 − B4 | −0.0049 [−0.0080, −0.0019] | −0.38 | 0.3627 | practically equivalent |
| S3, M = 3 | B6 − B5 | −0.0091 [−0.0120, −0.0063] | −0.80 | < 0.0001 | first lower, below margin |
| S3, M = 3 | B8 − B6 | −0.0004 [−0.0010, 0.0003] | −0.40 | 0.6993 | practically equivalent |
| S3, M = 3 | B8 − B7 | −0.0007 [−0.0017, 0.0002] | −0.40 | 1.0000 | practically equivalent |
| S3, M = 6 | B2 − A1 | 0.0001 [−0.0011, 0.0014] | −0.24 | 1.0000 | practically equivalent |
| S3, M = 6 | B3 − A1 | 0.0011 [−0.0008, 0.0030] | 0.19 | 1.0000 | practically equivalent |
| S3, M = 6 | B4 − B2 | 0.0009 [−0.0009, 0.0028] | 0.20 | 1.0000 | practically equivalent |
| S3, M = 6 | B4 − B3 | −0.0001 [−0.0010, 0.0010] | −0.22 | 1.0000 | practically equivalent |
| S3, M = 6 | B5 − B4 | −0.0079 [−0.0113, −0.0047] | −0.62 | 0.0014 | first lower, below margin |
| S3, M = 6 | B6 − B5 | −0.0155 [−0.0196, −0.0117] | −0.90 | < 0.0001 | first lower, below margin |
| S3, M = 6 | B8 − B6 | −0.0003 [−0.0014, 0.0009] | −0.09 | 1.0000 | practically equivalent |
| S3, M = 6 | B8 − B7 | −0.0001 [−0.0012, 0.0010] | −0.05 | 1.0000 | practically equivalent |


### Appendix B. Frozen calibration (final thresholds and Amendment 1)

| Scenario | M | Arm | Final threshold (h or Θ₀) | Calibration mean count | Amendment 1 | Pass 1 threshold (count) |
|---|---|---|---|---|---|---|
| S1 | 3 | A1 | 0.7533 | 3.20 |  |  |
| S1 | 3 | A5 | 2.7144 | 2.95 |  |  |
| S1 | 3 | B2 | 0.8500 | 2.90 |  |  |
| S1 | 3 | B3 | 0.5750 | 3.05 | amended | 0.5833 (2.55, excluded) |
| S1 | 3 | B4 | 0.7028 | 3.00 | amended | 0.7167 (1.85, excluded) |
| S1 | 3 | B8 | 2.7144 | 2.65 |  |  |
| S1 | 6 | A1 | 0.7030 | 5.75 |  |  |
| S1 | 6 | A5 | 1.3950 | 5.80 |  |  |
| S1 | 6 | B2 | 0.8167 | 5.60 |  |  |
| S1 | 6 | B3 | 0.5306 | 6.05 | amended | 0.5167 (7.00, excluded) |
| S1 | 6 | B4 | 0.6722 | 5.90 | amended | 0.6833 (4.70, excluded) |
| S1 | 6 | B8 | 1.1173 | 6.40 |  |  |
| S2 | 3 | A1 | 0.6526 | 2.75 |  |  |
| S2 | 3 | A5 | 0.7169 | 3.15 |  |  |
| S2 | 3 | B2 | 0.7167 | 3.10 |  |  |
| S2 | 3 | B3 | 0.4833 | 2.80 |  |  |
| S2 | 3 | B4 | 0.5833 | 3.10 |  |  |
| S2 | 3 | B8 | 0.4599 | 3.00 |  |  |
| S2 | 6 | A1 | 0.5015 | 5.85 |  |  |
| S2 | 6 | A5 | 0.0779 | 5.90 |  |  |
| S2 | 6 | B2 | 0.3500 | 5.40 |  |  |
| S2 | 6 | B3 | 0.3833 | 5.70 |  |  |
| S2 | 6 | B4 | 0.2833 | 5.90 |  |  |
| S2 | 6 | B8 | 0.0145 | 6.00 | amended | 0.0500 (5.60) |
| S3 | 3 | A1 | 0.7638 | 2.95 | amended | 0.7533 (3.75, excluded) |
| S3 | 3 | A5 | 4.2308 | 2.65 |  |  |
| S3 | 3 | B2 | 0.8500 | 3.15 |  |  |
| S3 | 3 | B3 | 0.5833 | 2.70 |  |  |
| S3 | 3 | B4 | 0.7056 | 3.15 | amended | 0.7167 (2.10, excluded) |
| S3 | 3 | B8 | 3.3888 | 2.90 |  |  |
| S3 | 6 | A1 | 0.7281 | 5.60 |  |  |
| S3 | 6 | A5 | 2.1742 | 5.40 |  |  |
| S3 | 6 | B2 | 0.8278 | 5.95 | amended | 0.8167 (7.55, excluded) |
| S3 | 6 | B3 | 0.5500 | 5.75 |  |  |
| S3 | 6 | B4 | 0.6833 | 6.00 |  |  |
| S3 | 6 | B8 | 1.1173 | 5.80 |  |  |


*Table B1. Final thresholds and calibration mean mutation counts (Amendment 1 changes shown with their pass-1 values). κ_s = 0.2287 (S1), 0.2327 (S2), 0.2685 (S3); κ_E = 0.4196, 0.4217, 0.5018; τ = 0.6267, 0.5646, 0.6686 (from Static runs on seeds 8000–8019). B5, B6, B7 and H1 inherit B8's Θ₀ and κ.*

### Appendix C. Matched-budget and equal-count comparisons (exploratory)

| Cell | Comparison | Seeds with equal realised counts | ΔE [95% bootstrap CI] (exploratory) |
|---|---|---|---|
| S1, M = 3 | B8 − A1 | 38 | −0.0291 [−0.0381, −0.0200] |
| S1, M = 3 | B8 − A7 | 28 | 0.0371 [0.0194, 0.0551] |
| S1, M = 3 | H1 − A7 | 33 | 0.0124 [0.0023, 0.0222] |
| S1, M = 3 | B8 − A7M | 36 | 0.0391 [0.0224, 0.0565] |
| S1, M = 3 | H1 − A7M | 52 | 0.0084 [0.0003, 0.0163] |
| S1, M = 6 | B8 − A1 | 34 | −0.0535 [−0.0640, −0.0428] |
| S1, M = 6 | B8 − A7 | 22 | 0.0593 [0.0377, 0.0795] |
| S1, M = 6 | H1 − A7 | 24 | 0.0059 [−0.0131, 0.0236] |
| S1, M = 6 | B8 − A7M | 32 | 0.0515 [0.0335, 0.0694] |
| S1, M = 6 | H1 − A7M | 46 | 0.0150 [0.0021, 0.0269] |
| S2, M = 3 | B8 − A1 | 44 | −0.0210 [−0.0325, −0.0108] |
| S2, M = 3 | B8 − A7 | 25 | 0.0469 [0.0252, 0.0674] |
| S2, M = 3 | H1 − A7 | 29 | 0.0257 [0.0094, 0.0439] |
| S2, M = 3 | B8 − A7M | 36 | 0.0422 [0.0253, 0.0588] |
| S2, M = 3 | H1 − A7M | 46 | 0.0142 [0.0016, 0.0276] |
| S2, M = 6 | B8 − A1 | 33 | −0.0198 [−0.0306, −0.0086] |
| S2, M = 6 | B8 − A7 | 23 | 0.0198 [−0.0092, 0.0488] |
| S2, M = 6 | H1 − A7 | 22 | −0.0033 [−0.0230, 0.0151] |
| S2, M = 6 | B8 − A7M | 33 | 0.0283 [0.0078, 0.0485] |
| S2, M = 6 | H1 − A7M | 38 | 0.0034 [−0.0147, 0.0206] |
| S3, M = 3 | B8 − A1 | 30 | −0.0163 [−0.0213, −0.0113] |
| S3, M = 3 | B8 − A7 | 20 | 0.0111 [0.0040, 0.0180] |
| S3, M = 3 | H1 − A7 | 38 | −0.0027 [−0.0082, 0.0022] |
| S3, M = 3 | B8 − A7M | 32 | 0.0077 [0.0015, 0.0134] |
| S3, M = 3 | H1 − A7M | 58 | −0.0018 [−0.0060, 0.0021] |
| S3, M = 6 | B8 − A1 | 22 | −0.0189 [−0.0245, −0.0136] |
| S3, M = 6 | B8 − A7 | 22 | 0.0128 [0.0058, 0.0201] |
| S3, M = 6 | H1 − A7 | 34 | 0.0004 [−0.0047, 0.0057] |
| S3, M = 6 | B8 − A7M | 32 | 0.0146 [0.0090, 0.0203] |
| S3, M = 6 | H1 − A7M | 53 | 0.0027 [−0.0014, 0.0068] |


### Appendix D. Continuity comparisons (exploratory; unadjusted p-values, no claims)

| Cell | Comparison | ΔE [95% bootstrap CI] | Wilcoxon p (unadjusted, exploratory) |
|---|---|---|---|
| S1, M = 3 | A5 − A1 | −0.0061 [−0.0138, 0.0013] | 0.1836 |
| S1, M = 3 | A5 − A7 | 0.0657 [0.0517, 0.0797] | < 0.0001 |
| S1, M = 3 | B8 − A5 | −0.0187 [−0.0248, −0.0130] | < 0.0001 |
| S1, M = 3 | H1 − B8 | −0.0458 [−0.0568, −0.0349] | < 0.0001 |
| S1, M = 3 | A7 − A1 | −0.0718 [−0.0864, −0.0568] | < 0.0001 |
| S1, M = 3 | A7M − A7 | −0.0105 [−0.0166, −0.0055] | < 0.0001 |
| S1, M = 3 | B5 − A1 | −0.0059 [−0.0149, 0.0029] | 0.2003 |
| S1, M = 6 | A5 − A1 | −0.0053 [−0.0125, 0.0017] | 0.1686 |
| S1, M = 6 | A5 − A7 | 0.0914 [0.0771, 0.1057] | < 0.0001 |
| S1, M = 6 | B8 − A5 | −0.0359 [−0.0445, −0.0271] | < 0.0001 |
| S1, M = 6 | H1 − B8 | −0.0537 [−0.0663, −0.0417] | < 0.0001 |
| S1, M = 6 | A7 − A1 | −0.0967 [−0.1122, −0.0814] | < 0.0001 |
| S1, M = 6 | A7M − A7 | −0.0158 [−0.0243, −0.0089] | < 0.0001 |
| S1, M = 6 | B5 − A1 | −0.0059 [−0.0126, 0.0003] | 0.1351 |
| S2, M = 3 | A5 − A1 | 0.0043 [−0.0031, 0.0113] | 0.0838 |
| S2, M = 3 | A5 − A7 | 0.0643 [0.0472, 0.0814] | < 0.0001 |
| S2, M = 3 | B8 − A5 | −0.0226 [−0.0298, −0.0157] | < 0.0001 |
| S2, M = 3 | H1 − B8 | −0.0401 [−0.0524, −0.0273] | < 0.0001 |
| S2, M = 3 | A7 − A1 | −0.0601 [−0.0774, −0.0427] | < 0.0001 |
| S2, M = 3 | A7M − A7 | −0.0197 [−0.0299, −0.0112] | < 0.0001 |
| S2, M = 3 | B5 − A1 | −0.0044 [−0.0116, 0.0025] | 0.2915 |
| S2, M = 6 | A5 − A1 | 0.0208 [0.0141, 0.0280] | < 0.0001 |
| S2, M = 6 | A5 − A7 | 0.0543 [0.0363, 0.0714] | < 0.0001 |
| S2, M = 6 | B8 − A5 | −0.0348 [−0.0453, −0.0235] | < 0.0001 |
| S2, M = 6 | H1 − B8 | −0.0290 [−0.0391, −0.0195] | < 0.0001 |
| S2, M = 6 | A7 − A1 | −0.0335 [−0.0494, −0.0169] | 0.0003 |
| S2, M = 6 | A7M − A7 | −0.0220 [−0.0316, −0.0138] | < 0.0001 |
| S2, M = 6 | B5 − A1 | −0.0179 [−0.0243, −0.0113] | < 0.0001 |
| S3, M = 3 | A5 − A1 | −0.0031 [−0.0063, −0.0001] | 0.1224 |
| S3, M = 3 | A5 − A7 | 0.0210 [0.0154, 0.0264] | < 0.0001 |
| S3, M = 3 | B8 − A5 | −0.0113 [−0.0138, −0.0089] | < 0.0001 |
| S3, M = 3 | H1 − B8 | −0.0157 [−0.0197, −0.0119] | < 0.0001 |
| S3, M = 3 | A7 − A1 | −0.0240 [−0.0295, −0.0189] | < 0.0001 |
| S3, M = 3 | A7M − A7 | −0.0050 [−0.0077, −0.0026] | 0.0001 |
| S3, M = 3 | B5 − A1 | −0.0050 [−0.0079, −0.0021] | 0.0057 |
| S3, M = 6 | A5 − A1 | −0.0031 [−0.0059, −0.0003] | 0.0393 |
| S3, M = 6 | A5 − A7 | 0.0300 [0.0239, 0.0363] | < 0.0001 |
| S3, M = 6 | B8 − A5 | −0.0196 [−0.0233, −0.0161] | < 0.0001 |
| S3, M = 6 | H1 − B8 | −0.0135 [−0.0176, −0.0094] | < 0.0001 |
| S3, M = 6 | A7 − A1 | −0.0331 [−0.0400, −0.0265] | < 0.0001 |
| S3, M = 6 | A7M − A7 | −0.0076 [−0.0115, −0.0043] | < 0.0001 |
| S3, M = 6 | B5 − A1 | −0.0069 [−0.0099, −0.0041] | < 0.0001 |


### Appendix E. Historical v0.7 primary comparisons (seeds 7000–7059; unchanged)

| Condition | Comparison (E_X − E_Y) | n | ΔE | 95% bootstrap CI | Holm p | Reading |
|---|---|---|---|---|---|---|
| S1, M=3 | A5 − A1 | 60 | -0.0053 | [-0.0131, +0.0019] | 0.865 | practically equivalent |
| S1, M=3 | A5 − A7 | 60 | +0.0448 | [+0.0286, +0.0600] | 1.27×10⁻⁵ | A7 lower E, ≥ margin |
| S1, M=6 | A5 − A1 | 60 | -0.0046 | [-0.0103, +0.0012] | 0.513 | practically equivalent |
| S1, M=6 | A5 − A7 | 60 | +0.0756 | [+0.0597, +0.0912] | 5.45×10⁻⁹ | A7 lower E, ≥ margin |
| S2, M=3 | A5 − A1 | 60 | +0.0105 | [+0.0027, +0.0182] | 0.033 | A1 lower E, < margin |
| S2, M=3 | A5 − A7 | 60 | +0.0461 | [+0.0291, +0.0627] | 4.04×10⁻⁵ | A7 lower E, ≥ margin |
| S2, M=6 | A5 − A1 | 60 | +0.0080 | [+0.0008, +0.0151] | 0.213 | practically equivalent |
| S2, M=6 | A5 − A7 | 60 | +0.0381 | [+0.0184, +0.0570] | 0.003 | A7 lower E, ≥ margin |
| S3, M=3 | A5 − A7 | 60 | +0.0244 | [+0.0188, +0.0298] | 4.76×10⁻⁸ | A7 lower E, ≥ margin |
| S3, M=6 | A5 − A1 | 60 | +0.0002 | [-0.0035, +0.0036] | 0.865 | practically equivalent |
| S3, M=6 | A5 − A7 | 60 | +0.0321 | [+0.0255, +0.0382] | 1.04×10⁻⁸ | A7 lower E, ≥ margin |

