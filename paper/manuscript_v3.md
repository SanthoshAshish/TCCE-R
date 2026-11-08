**Highlights**

- Posterior failure scenarios choose which link to rewire under a fixed budget
- Pre-registered test on 150 unseen seeds; frozen algorithm, no retuning
- Lower consensus error than three baselines in all 17 primary tests
- Gains are small to moderate; connectivity and recovery gains are limited
- Rollout timing gave no reliable benefit at about 12 times the decision cost

[[PAGEBREAK]]

# Posterior-Scenario Selection of Link Rewirings for Consensus under a Mutation Budget: A Pre-Registered Simulation Study

**Y. Santhosh Ashish, E. Kishan Kumar, P. Navyambika, Vinay Gupta**

[Affiliations — AUTHOR INPUT REQUIRED]

Corresponding author: [name and e-mail — AUTHOR INPUT REQUIRED]

## Abstract

When only a few link rewirings may be spent on a network that suffers correlated link failures, the question is which link to swap. Earlier controllers in this line of work, a reactive threshold and predictive and debt-based triggers, did not beat a simple front-loaded schedule. We propose COCRO-M, a centralised controller that fits a Bayesian failure model (lagged-neighbour hazards and a two-component repair-time mixture), draws failure scenarios from its posterior, and spends each rewiring on the candidate with the highest expected gain in a spectral surrogate of consensus error, subject to an unchanged safety gate. The algorithm and its analysis plan were frozen before the evaluation: a rollout-based timing rule was developed and then dropped by a pre-declared rule on development seeds. On 150 held-out seeds (12,150 runs) in six random-geometric-graph conditions, COCRO-M had lower mean error than the exact-budget front-loaded schedule, the predictive controller and the debt controller in all 17 primary tests (Holm p ≤ 0.0005); 15 differences exceeded a 0.01 margin and 10 exceeded 0.02. Against the front-loaded schedule the reduction was 1.4% to 8.0%, and it was below the margin in the 80-node conditions. Candidate-set breadth and the spectral surrogate mattered; the propagation term, posterior sampling and a full-horizon rerank showed no measurable benefit. Disconnection and recovery were close to the front-loaded schedule and worse than the predictive controller. Other graph families and failure models were not evaluated.

**Keywords:** distributed consensus; topology adaptation; link rewiring; mutation budget; failure model; pre-registered evaluation

## 1. Introduction

Distributed averaging and consensus let nodes agree on a common value using local exchanges, and their convergence speed depends on the connectivity of the communication graph, in particular its algebraic connectivity λ₂ [1, 2, 3]. When links fail, are repaired, or are lost in correlated bursts, the effective graph changes and consensus degrades. A large literature designs the consensus law to tolerate such conditions, through adaptive and event-triggered protocols [4, 5, 6] and through protocols analysed under switching topologies and random link failures [7, 8, 9]. A complementary line changes the *topology*: connectivity-aware reconfiguration, rewiring and robustness-oriented design [10, 11, 12, 13].

This paper concerns the second line under a constraint that is often implicit in practice: only a small number M of rewirings may be spent per run. The controller must decide *when* to spend each rewiring and *which* link to remove and add. Earlier versions of this study (v0.7, v0.8 and Revision 2) compared reactive, predictive and debt-based triggers against a state-blind front-loaded schedule; none of the state-triggered designs beat the front-loaded schedule in the matched-budget evaluations (Section 6.7). That outcome suggests that the state-blind schedule was already close to the best *timing*, and that the open opportunity lies in the *selection* of the link swap.

**Contributions.** (i) COCRO-M, a controller that selects rewirings by their expected gain under failure scenarios drawn from a fitted Bayesian failure model (Section 4); (ii) a numerical study showing when deferring a rewiring is worth its cost in a correlated-failure world, which motivated and then, on development data, rejected a rollout-based timing rule (Sections 4.6, 5.3); (iii) a protocol that fixed the algorithm, the arms, the statistics and the seeds before the evaluation, a held-out evaluation of 12,150 runs, and the report of both favourable and unfavourable results (Section 6); (iv) a theory note that separates what is proved about the implementation from what is only measured (Section 4.7).

**What is not claimed.** The evaluation is on one graph family (random geometric graphs, 40 and 80 nodes) and one failure model. The controller is centralised. A pre-registered evaluation on other graph families and on a cascade, node-failure and regime-shift failure model was planned and implemented but has *not* been run (Section 8); no statement is made about those settings.

## 2. Related work

**Consensus under unreliable links.** Work on event-triggered, adaptive and fault-tolerant consensus [14, 15, 16, 17, 18] and on consensus over random or failing links [7, 8, 19] adapts the *protocol* to a given topology process. The standard analysis of consensus with random link outages is the randomized-gossip bound [20], which we use to relate our metric to the spectrum of the expected weight matrix (Section 4.7).

**Connectivity-aware topology control.** Model-predictive and barrier-function approaches preserve connectivity of multi-agent systems [21, 22, 23], and budget-limited rewiring has been studied for information flow in networks [10, 11, 24]. Cascading-failure and recovery models [25, 26] motivate our use of lagged neighbour failures as a hazard covariate. These works typically assume a known failure model or optimise a static robustness objective; they do not compare rewiring *selection* against state-blind schedules under a hard mutation cap, which is the question here.

**Sequential decision tools.** The deferral question is an optimal-stopping and restless-allocation problem [27, 28]; rollout is a standard way to improve a base policy [29]; scenario selection with a posterior is in the spirit of Thompson sampling [30, 31]; and the repair-time mixture is fitted by expectation–maximisation [32]. We use these as components, not as claims of novelty. Table 1 summarises how the mechanisms differ.

**Table 1** Mechanism comparison of the controller families discussed (qualitative; no performance comparison is implied).

| Family | Decision addressed | Failure/objective model | Adaptation | Note |
|---|---|---|---|---|
| Consensus-law design (event-triggered, adaptive, fault-tolerant) | Protocol | Given or switching topology | No topology change | — |
| Connectivity-preserving control (MPC, barrier functions) | Motion or links, constraint-based | Known model, connectivity constraint | Continuous control | No hard rewiring cap |
| Budget-limited rewiring for information flow | Which links to add | Static objective | Offline or one-shot | No failure process |
| Reactive threshold (A1); front-loaded schedules (A7, A7M) | When to spend | State-blind or error threshold | Fixed rule | Earlier controllers of this study |
| Predictive and debt-based triggers (B8, C1) | When and which | Hand-built risk or debt scores | Calibrated thresholds | Earlier controllers of this study |
| COCRO-M (this paper) | Which link to swap | Fitted posterior failure model; scenario-averaged spectral gain | Timing fixed (front-loaded), selection by expected gain | Centralised; tested on random geometric graphs only |

## 3. System model

A network of n nodes has a set of potential links with geometric positions; a subset (the configured links) forms the initial topology, subject to a strict budget B on the number of configured links. Time is divided into K = 80 epochs. Within an epoch, T consensus rounds are run with Metropolis weights on the links that survive the round; links fail through a bursty, background or transient process (scenarios S1–S3 of Section 5). In every epoch the initial values are redrawn, so the error does not accumulate across epochs. The per-epoch consensus error is

$$e_k(T)=\frac{\lVert x(T)-\bar x\mathbf 1\rVert}{\lVert x(0)-\bar x\mathbf 1\rVert},\qquad E_k = 1-\min\Bigl(1,\max\Bigl(0,\frac{\ln e_k(T)}{\ln\varepsilon}\Bigr)\Bigr),\quad \varepsilon=0.01 ,\tag{1}$$

and the primary outcome is the mean E over the run (lower is better). A *mutation* removes one configured link and adds another; a new link is usable only after a setup delay of d = 2 epochs (break-before-make), at most one mutation is made per epoch with a cooldown of 2 epochs, a link touched once is unavailable for a tabu period, and at most M mutations are allowed per run (M = 3 or 6). Every proposed mutation passes the *safety gate* of the earlier studies: it must not increase the number of components in either the final or the interim graph, must respect degree and budget limits, and must not reduce λ₂ below a floor. The controller is centralised and observes the up/down state of all potential links. Secondary outcomes are the share of epochs in which the live graph is disconnected, the longest disconnection, the anchored recovery time, the worst-case E, the reconfiguration overhead and the decision time.

## 4. Method

### 4.1. Overview

At each epoch the controller (a) updates a failure model from the observed link states, (b) builds a small set of safe candidate mutations, (c) draws failure scenarios from the model's posterior, (d) scores each candidate by the expected gain in a spectral surrogate of E over the scenarios, and (e) applies the best candidate if the cooldown, cap and gate allow it. Fig. 1 shows the procedure.

![Fig. 1. COCRO-M decision procedure at one epoch.](figures_v3/fig_procedure.png)

### 4.2. Causal failure posterior estimator (CFPE)

For each potential link the estimator tracks whether it failed, with a hazard that depends on the number N of its neighbouring links (sharing an endpoint) that were down in the previous epoch, bucketed as N = 0, 1, 2, 3+ with empirical-Bayes pooling across links and forgetting factor φ = 0.98. Down-times are modelled by a two-component geometric mixture fitted by expectation–maximisation [32] on censored episodes; posterior draws of its parameters are obtained by the Bayesian bootstrap. A failure that coincides with many failed links at one node is attributed to the node rather than to individual links. The model is a *model*, not the truth: statements about it are statements about the estimator.

### 4.3. Scenario sampling

For each decision, S_sel = 8 failure scenarios of length d + H (H = 3 is the benefit window) are simulated forward from the current state, each with its own posterior parameter draw. Scenarios are generated from controller-owned random streams, independent of the environment's streams, so the controller cannot read the environment's future randomness. The same scenarios are shared by all candidates, so comparisons between candidates are paired.

### 4.4. Gain estimator and selection

The surrogate of E for a graph is obtained from the spectrum of the expected-weight matrix, Ê = 1 − min(1, −½ ln(Σ_{i≥2} λᵢ^{2T}/(n−1)) / ln(1/ε)). For a candidate a, the gain in scenario s is G_s(a) = S_setup + b·(τ − d), where S_setup is the improvement during the setup window, b the per-epoch improvement after the link becomes usable, and τ the remaining epochs. The controller selects

$$a^{*}=\arg\max_{a\in\mathcal A}\ \frac1{S_{\mathrm{sel}}}\sum_{s=1}^{S_{\mathrm{sel}}} G_s(a),\tag{2}$$

over the candidate set 𝒜 of the top K_r = 2 removals and K_a = 5 additions that pass the gate (up to 10 candidates). Candidates come from the shared candidate generator of the earlier controllers, and every one is filtered by the unchanged safety gate.

### 4.5. Timing and variants

COCRO-M spends a rewiring whenever the cooldown has elapsed and the cap M is not reached (the timing of the front-loaded schedule A7M), and uses eq. (2) only to choose *what* to swap. Table 2 lists the arms. The ablations remove one component each: a single removal candidate (k1), a Laplacian instead of the spectral surrogate (lap), a single scenario (s1), the posterior mean instead of posterior draws (plug), and no lagged-neighbour term (nb1). Two exploratory variants were developed and not adopted: a full-horizon rerank of a shortlist by simulated gain (mfg), and a rollout shadow-price rule that defers a rewiring when the expected value of waiting exceeds acting (cocro).

**Table 2** Arms. Thresholds of A1, B8, C1 and the A7 count distribution are the frozen earlier calibrations.

| Arm | Name | Rule | Origin |
|---|---|---|---|
| A0 | Static | No mutations | earlier |
| A1 | Reactive | Spend when error exceeds a calibrated threshold | earlier |
| A7 / A7M | Front-loaded | Spend at the first eligible epochs (A7: count from a calibrated distribution; A7M: exactly M) | earlier |
| B8 | Predictive | Risk-filtered predictive score and calibrated trigger | earlier |
| C1 | Causal debt | Resilience debt with causal attribution of stress to failure episodes | earlier |
| COCRO-M | Selection only | Front-loaded timing; swap chosen by expected gain over 8 posterior scenarios (K_r = 2, K_a = 5) | this paper (final) |
| k1 / lap / s1 / plug / nb1 | Ablations | One removal; Laplacian surrogate; one scenario; posterior mean; no lagged-neighbour term | this paper |
| mfg | Full-horizon rerank | COCRO-M with a shortlist reranked by full-horizon simulated gain | this paper (exploratory) |
| cocro | Rollout timing | COCRO with a rollout shadow price deciding when to act | this paper (exploratory) |

### 4.6. Why rollout timing was tested and then dropped

A numerical study (exact dynamic programming against the rollout rule and an i.i.d. baseline in a correlated-failure toy world; `docs/COCRO_TOY_STUDY.md`) showed that deferral can pay off when failures are correlated: the rollout rule reached 99.2% of the exact optimum while the i.i.d. rule over-deferred. In the simulator, however, the pre-declared adoption rule (Section 5.3) evaluated on development seeds did not support adopting the rollout: its mean ΔE against selection-only COCRO-M was −0.0011 (mean z = −0.10), far from the −0.010 threshold and from the z criterion. The final algorithm is therefore selection-only. The rollout base policy also ignores links still being set up, which biases it against acting when two or more rewirings remain; this limitation is documented and was not fixed.

### 4.7. Theoretical properties of the implementation

`docs/COCRO_THEORY.md` states seven propositions, each with a code location and a numerical test. (P1) Cap, cooldown, budget and tabu constraints hold in every run. (P2) A gate-accepted mutation does not increase the number of components in the final or interim graph at decision time; exogenous failures during setup can still disconnect the network. (P3) For constant symmetric doubly stochastic W and i.i.d. initial values, the expected mean-square contraction over T rounds is exactly (1/(n−1)) Σ_{i≥2} λᵢ^{2T}, and with random link outages it is bounded by λ₂(E[W²])^T [20]; the surrogate in eq. (2) evaluates the metric's formula at the first quantity and is **not** a bound on E_k, because E_k uses a realised ratio inside a logarithm and is clipped. (P4) The sample-average selection is consistent as S_sel grows, with a Hoeffding bound on the probability of a wrong selection under the model. (P5) The per-decision cost is O(S (d+H) K n³). (P6) The one-step rollout is at least as good as its base policy in the model (an established result [29]), which is not claimed for the simulator. (P7) The debt ledger of the earlier controller C1 is bounded under recoverable disturbances. Nothing in this section proves that COCRO-M lowers E_k; that is the empirical question of Section 6.

## 5. Experimental protocol

### 5.1. Conditions and arms

Three scenarios are crossed with two budgets: S1 (40-node random geometric graph, bursty failures), S2 (40 nodes, background failures) and S3 (80 nodes, bursty failures), each with M = 3 and M = 6, giving six conditions. The comparison arms and their frozen thresholds are those of the earlier studies and were not retuned: A0 (static), A1 (reactive threshold), A7 (front-loaded with a count distribution), A7M (exactly M front-loaded attempts), B8 (predictive, risk-filtered) and C1 (causal resilience debt). B8 was not calibrated for S2 with M = 6 and is therefore absent from that condition. All arms see identical failure traces within a seed.

### 5.2. Pre-registration and seeds

The protocol (`docs/PROTOCOL_R3.md`), the research questions, the primary comparisons, the statistics and the frozen configurations (56 files with a checksum manifest; `docs/R3_FREEZE.md`) were committed before the held-out run. Seed blocks do not overlap: consumed development seeds 8500–8519, ablation seeds 8520–8539, smoke seeds 8540–8559, and held-out Tier A seeds 9300–9449 (150 seeds). The held-out evaluation ran at commit d4238a1; the analysis script refuses to run on a modified source tree. The primary family has 17 tests: COCRO-M against A7M (6 conditions), B8 (5) and C1 (6). Statistics are paired per seed: Wilcoxon signed-rank tests with Holm correction within the family, 95% bootstrap intervals (10,000 resamples), standardised paired effect sizes, and two minimum practically meaningful margins, 0.01 (primary) and 0.02, on the difference in mean E.

### 5.3. Development-stage adoption rules

The choice between the rollout and the selection-only variants was fixed before the held-out run by a mechanical rule on the development ablation (seeds 8520–8539): a component was to be adopted only if all of the following held across the four development cells: the mean paired ΔE was at most a threshold (−0.010 for the rollout timing, −0.005 for the full-horizon rerank and the reservation variants), ΔE was non-positive in at least three of the four cells, and the mean of ΔE divided by its standard error was at most −1.5. Table 3 shows the outcome. No rule passed, so the simpler variant was kept and the final algorithm is `cocro_m` (final decision: cocro_m).

Fig. 2 shows the same comparison graphically.

![Fig. 2. Development-stage adoption rules: mean paired ΔE per rule (bars) against the adoption threshold (orange marks). No rule reaches its threshold.](figures_v3/fig_step2.png)

**Table 3** Development-stage adoption rules (seeds 8520–8539, four cells). Mean ΔE is the second-named variant minus the first-named; a rule passes only if mean ΔE is at most the threshold, ΔE ≤ 0 in at least 3 of 4 cells, and mean z ≤ −1.5. No rule passed.

| Rule | Comparison | Mean ΔE over 4 cells | Cells with ΔE ≤ 0 | Mean z | Adopted |
|---|---|---|---|---|---|
| R-sel:m-family | cocro_mfg vs cocro_m | −0.0040 | 4/4 | −0.74 | no |
| R-sel:roll-family | cocro_fg vs cocro | 0.0011 | 1/4 | 0.03 | no |
| R-roll:plain | cocro vs cocro_m | −0.0011 | 3/4 | −0.10 | no |
| R-roll:fg | cocro_fg vs cocro_mfg | 0.0039 | 1/4 | 0.55 | no |
| R-res:plain | cocro_r vs cocro | 0.0019 | 1/4 | 0.16 | no |
| R-res:fg | cocro_fgr vs cocro_fg | −0.0031 | 3/4 | −0.30 | no |

### 5.4. What was and was not run

Tier A (the six random-geometric-graph conditions above) was run in full. Tier B (Erdős–Rényi, Barabási–Albert, Watts–Strogatz and scale-free graphs with 100 nodes) and Tier C (a cascade, node-failure and regime-shift failure model on 40-node graphs) were implemented, tested for inertness of the defaults and pre-registered, but **not run**: Tier B was started and then stopped by the authors before any output was read, and Tier C was not started. All claims below are therefore restricted to Tier A.

## 6. Results

### 6.1. Overall error

Table 4 gives mean E per arm and condition and Fig. 3 the corresponding intervals. COCRO-M had the lowest mean error among the non-exploratory arms in every condition.

**Table 4** Mean consensus error E (SD over 150 seeds) per arm and condition; lower is better. Static has no mutations; B8 was not calibrated for S2, M = 6; the rollout variant was run in S1 and S2 only.

| Arm | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|
| A0 Static | 0.475 (0.073) | 0.475 (0.073) | 0.440 (0.085) | 0.440 (0.085) | 0.556 (0.041) | 0.556 (0.041) |
| A1 Reactive | 0.413 (0.076) | 0.364 (0.073) | 0.322 (0.091) | 0.266 (0.090) | 0.542 (0.041) | 0.528 (0.042) |
| A7 Front-loaded | 0.376 (0.087) | 0.329 (0.092) | 0.322 (0.093) | 0.269 (0.096) | 0.521 (0.048) | 0.500 (0.049) |
| A7M Front-loaded (exactly M) | 0.376 (0.087) | 0.328 (0.092) | 0.321 (0.093) | 0.266 (0.095) | 0.521 (0.048) | 0.498 (0.048) |
| B8 Predictive (earlier) | 0.402 (0.070) | 0.351 (0.069) | 0.318 (0.078) | not run | 0.526 (0.042) | 0.511 (0.040) |
| C1 Causal debt (earlier) | 0.383 (0.083) | 0.343 (0.080) | 0.351 (0.096) | 0.303 (0.100) | 0.529 (0.042) | 0.511 (0.041) |
| COCRO-M | 0.359 (0.084) | 0.306 (0.085) | 0.307 (0.097) | 0.245 (0.095) | 0.513 (0.047) | 0.489 (0.049) |
| COCRO + rollout timing (exploratory) | 0.352 (0.079) | 0.294 (0.079) | 0.301 (0.090) | 0.235 (0.086) | not run | not run |

![Fig. 3. Mean consensus error by arm and condition with 95% intervals over 150 seeds; the dashed line is Static. COCRO + rollout was run in S1 and S2 only.](figures_v3/fig_E_by_cell.png)

### 6.2. Primary comparisons

COCRO-M had lower mean error than the comparator in all 17 primary tests (Holm p ≤ 0.0005). Against A7M the paired differences were −0.022 to −0.007 (ΔE, COCRO-M minus comparator), against B8 −0.045 to −0.012 and against C1 −0.058 to −0.015. Of the 17 differences, 15 exceeded the 0.01 margin and 10 the 0.02 margin. Against A7M the margin 0.01 was exceeded in 4 of 6 conditions and the margin 0.02 in 2; in the two 80-node conditions the difference was statistically detectable but below the margin. Relative to A7M the reduction in mean E was 1.4% to 8.0% (4.5% to 8.0% in the 40-node conditions). Table 5 and Fig. 5 give the differences with intervals; Fig. 4 shows the per-seed distribution of the differences, which is wide: COCRO-M is lower on average, but not on every seed; the full test table (dz, both verdicts) is in Appendix A.

![Fig. 4. Per-seed paired differences (COCRO-M minus comparator) by condition; violins show the distribution over 150 seeds, with the median and range marked.](figures_v3/fig_perseed.png)

**Table 5** Primary family (17 tests, Holm within the family). ΔE = COCRO-M minus comparator, mean [95% bootstrap CI]; negative: COCRO-M has lower error. * Holm p < 0.05; ** also |ΔE| ≥ 0.01.

| Condition | COCRO-M − A7M | COCRO-M − B8 | COCRO-M − C1 |
|---|---|---|---|
| S1, M = 3 | −0.017 [−0.022, −0.012]** | −0.043 [−0.050, −0.036]** | −0.024 [−0.031, −0.017]** |
| S1, M = 6 | −0.022 [−0.027, −0.018]** | −0.045 [−0.053, −0.038]** | −0.037 [−0.045, −0.029]** |
| S2, M = 3 | −0.015 [−0.021, −0.008]** | −0.012 [−0.019, −0.004]** | −0.044 [−0.053, −0.036]** |
| S2, M = 6 | −0.021 [−0.028, −0.014]** | not evaluated | −0.058 [−0.069, −0.047]** |
| S3, M = 3 | −0.007 [−0.009, −0.006]* | −0.013 [−0.016, −0.010]** | −0.015 [−0.019, −0.012]** |
| S3, M = 6 | −0.009 [−0.011, −0.007]* | −0.023 [−0.026, −0.019]** | −0.022 [−0.026, −0.018]** |

![Fig. 5. Paired differences in mean E (COCRO-M minus comparator) with 95% bootstrap intervals; the band is the 0.01 margin.](figures_v3/fig_primary_forest.png)

### 6.3. Component ablations

Table 6 gives the ablation differences relative to COCRO-M (positive: the ablated variant has higher error). Removing the multi-candidate removal set (k1) or replacing the spectral with the Laplacian surrogate (lap) increased error in 6 and 6 of 6 conditions respectively (Holm p < 0.05); the increase exceeded 0.01 in 2 and 3 conditions. Posterior sampling (plug) and the propagation term (nb1) showed no Holm-significant effect in any condition (ranges −0.005 to 0.001 and −0.005 to 0.000), and a single scenario (s1) a small, significant increase in 2 conditions (range −0.000 to 0.005). The full-horizon rerank did not improve on COCRO-M (−0.011 to −0.001; no significant effect). The data therefore support the candidate breadth and the spectral surrogate as useful components and do **not** support the propagation term or posterior sampling as measurably useful in this environment; they remain part of the model for generality, not for demonstrated benefit.

![Fig. 6. Ablations relative to COCRO-M: paired ΔE with 95% bootstrap intervals (blue: Holm p < 0.05; grey: not significant); the band is the 0.01 margin.](figures_v3/fig_ablation.png)

**Table 6** Ablations relative to COCRO-M (ΔE = variant minus COCRO-M; positive: the variant has higher error), mean [95% bootstrap CI]. * Holm p < 0.05 within the 36-test family; ** also |ΔE| ≥ 0.01.

| Condition | single removal candidate | Laplacian surrogate | one scenario | no posterior sampling | no propagation term | + full-horizon rerank |
|---|---|---|---|---|---|---|
| S1, M = 3 | 0.007 [0.003, 0.011]* | 0.007 [0.004, 0.010]* | 0.003 [−0.002, 0.008] | −0.002 [−0.005, 0.002] | −0.001 [−0.005, 0.003] | −0.003 [−0.007, 0.000] |
| S1, M = 6 | 0.007 [0.004, 0.010]* | 0.010 [0.006, 0.014]** | 0.005 [−0.000, 0.010] | −0.002 [−0.006, 0.003] | −0.004 [−0.008, 0.001] | −0.005 [−0.009, −0.001] |
| S2, M = 3 | 0.010 [0.006, 0.015]** | 0.010 [0.006, 0.015]** | 0.002 [−0.002, 0.007] | −0.000 [−0.005, 0.006] | −0.003 [−0.008, 0.001] | −0.004 [−0.008, 0.000] |
| S2, M = 6 | 0.013 [0.009, 0.018]** | 0.012 [0.007, 0.018]** | −0.000 [−0.007, 0.006] | −0.005 [−0.012, 0.002] | −0.005 [−0.011, 0.002] | −0.011 [−0.018, −0.005] |
| S3, M = 3 | 0.002 [0.001, 0.003]* | 0.003 [0.002, 0.004]* | 0.002 [0.000, 0.003]* | 0.001 [−0.001, 0.002] | −0.000 [−0.001, 0.001] | −0.001 [−0.002, 0.000] |
| S3, M = 6 | 0.002 [0.001, 0.003]* | 0.005 [0.004, 0.007]* | 0.003 [0.002, 0.005]* | 0.001 [−0.000, 0.003] | 0.000 [−0.001, 0.002] | −0.001 [−0.002, −0.000] |

### 6.4. Rollout timing (exploratory)

The rollout variant was run in S1 and S2 for cost reasons and is exploratory. Against COCRO-M its error difference ranged over −0.012 to −0.005 with 1 of 4 tests Holm-significant (smallest Holm p = 0.0023). It cost 10 to 14 times COCRO-M's decision time (Table 9). Given the development outcome in Section 5.3, the rollout is reported but not recommended.

### 6.5. Connectivity, recovery and overhead

COCRO-M's gains in error did not come with comparable gains in connectivity. Tables 7 and 8 give the disconnected share, longest disconnection, anchored recovery, worst-case E, overhead and realised mutations. COCRO-M had a slightly smaller disconnected share than A7M in 6 of 6 conditions, but the difference is small, and the predictive controller B8 had a smaller disconnected share and shorter recovery than COCRO-M in all five conditions in which it was run, at a higher error. The debt controller C1 and the rollout variant were also better than COCRO-M on disconnection or recovery in several conditions (see the tables). COCRO-M therefore resembles the front-loaded schedule in these measures and does not match the more conservative controllers. COCRO-M realised exactly M mutations in all conditions (budget utilisation 100%), whereas B8 and C1 left a small part of the budget unspent.

Figs. 7–9 show the same measures graphically.

![Fig. 7. Disconnected share, longest disconnection and anchored recovery by arm and condition (means over 150 seeds; B8 absent in S2, M = 6; the rollout variant run in S1 and S2 only).](figures_v3/fig_connectivity.png)

![Fig. 8. Mean E against realised mutations per run (left) and against reconfiguration overhead (right); one point per arm and condition.](figures_v3/fig_tradeoff.png)

![Fig. 9. Worst-case E (mean over seeds of the per-run maximum) by arm and condition.](figures_v3/fig_worst.png)

**Table 7** Secondary measures, M = 6 (means over 150 seeds; descriptive, no tests). Disconnected share: fraction of epochs with a disconnected live graph; longest disconnection and anchored recovery in epochs; overhead: pending link-epochs plus live-link releases.

| Condition | Arm | Disconnected share | Longest disconnection (epochs) | Anchored recovery (epochs) | Worst-case E | Overhead | Mutations |
|---|---|---|---|---|---|---|---|
| S1, M = 6 | A7M Front-loaded (exactly M) | 0.260 | 9.1 | 4.23 | 0.780 | 16.5 | 6.00 |
| S1, M = 6 | B8 Predictive (earlier) | 0.234 | 7.2 | 3.47 | 0.785 | 13.6 | 5.90 |
| S1, M = 6 | C1 Causal debt (earlier) | 0.239 | 7.6 | 3.65 | 0.787 | 14.8 | 5.95 |
| S1, M = 6 | COCRO-M | 0.254 | 9.0 | 4.16 | 0.779 | 16.6 | 6.00 |
| S1, M = 6 | COCRO + rollout timing (expl.) | 0.234 | 7.9 | 3.67 | 0.777 | 16.8 | 6.00 |
| S2, M = 6 | A7M Front-loaded (exactly M) | 0.139 | 8.1 | 3.25 | 0.679 | 17.5 | 6.00 |
| S2, M = 6 | C1 Causal debt (earlier) | 0.106 | 5.7 | 2.66 | 0.692 | 15.2 | 5.75 |
| S2, M = 6 | COCRO-M | 0.122 | 7.4 | 3.18 | 0.665 | 17.4 | 6.00 |
| S2, M = 6 | COCRO + rollout timing (expl.) | 0.083 | 5.0 | 2.22 | 0.655 | 17.4 | 6.00 |
| S3, M = 6 | A7M Front-loaded (exactly M) | 0.372 | 11.8 | 5.19 | 0.779 | 16.1 | 6.00 |
| S3, M = 6 | B8 Predictive (earlier) | 0.348 | 9.8 | 4.57 | 0.783 | 12.7 | 5.67 |
| S3, M = 6 | C1 Causal debt (earlier) | 0.354 | 9.9 | 4.92 | 0.783 | 13.0 | 5.69 |
| S3, M = 6 | COCRO-M | 0.370 | 11.9 | 5.26 | 0.777 | 16.1 | 6.00 |

**Table 8** Secondary measures, M = 3 (means over 150 seeds; descriptive, no tests).

| Condition | Arm | Disconnected share | Longest disconnection (epochs) | Anchored recovery (epochs) | Worst-case E | Overhead | Mutations |
|---|---|---|---|---|---|---|---|
| S1, M = 3 | A7M Front-loaded (exactly M) | 0.290 | 10.9 | 5.25 | 0.791 | 8.4 | 3.00 |
| S1, M = 3 | B8 Predictive (earlier) | 0.268 | 8.4 | 4.17 | 0.796 | 6.5 | 2.99 |
| S1, M = 3 | C1 Causal debt (earlier) | 0.265 | 8.9 | 4.34 | 0.793 | 7.5 | 3.00 |
| S1, M = 3 | COCRO-M | 0.278 | 10.2 | 4.98 | 0.789 | 8.4 | 3.00 |
| S1, M = 3 | COCRO + rollout timing (expl.) | 0.254 | 8.4 | 4.06 | 0.786 | 8.4 | 3.00 |
| S2, M = 3 | A7M Front-loaded (exactly M) | 0.158 | 9.1 | 4.14 | 0.695 | 8.7 | 3.00 |
| S2, M = 3 | B8 Predictive (earlier) | 0.100 | 5.7 | 2.31 | 0.685 | 7.8 | 2.91 |
| S2, M = 3 | C1 Causal debt (earlier) | 0.147 | 8.2 | 3.96 | 0.709 | 7.6 | 2.91 |
| S2, M = 3 | COCRO-M | 0.145 | 8.3 | 4.15 | 0.687 | 8.8 | 3.00 |
| S2, M = 3 | COCRO + rollout timing (expl.) | 0.113 | 6.7 | 3.37 | 0.680 | 8.7 | 3.00 |
| S3, M = 3 | A7M Front-loaded (exactly M) | 0.398 | 13.9 | 6.24 | 0.785 | 8.2 | 3.00 |
| S3, M = 3 | B8 Predictive (earlier) | 0.377 | 11.9 | 5.27 | 0.787 | 6.6 | 2.97 |
| S3, M = 3 | C1 Causal debt (earlier) | 0.388 | 12.2 | 5.72 | 0.787 | 6.7 | 2.95 |
| S3, M = 3 | COCRO-M | 0.387 | 12.8 | 5.85 | 0.784 | 8.2 | 3.00 |

### 6.6. Cost and per-mutation efficiency

Table 9 reports decision time. COCRO-M's per-epoch decision time was 2.5 to 6.7 times that of A7M and below B8 and C1 in the conditions where those were run. Times were measured with parallel workers on one machine and under load, so they are indicative only. Table 10 gives the error reduction per mutation relative to Static; COCRO-M had the highest value in all six conditions. Fig. 10 shows the efficiency, Fig. 11 error against decision time and Fig. 12 decision time in all conditions.

**Table 9** Mean decision time per epoch (ms) and run time per run (s), M = 6; measured with parallel workers under load, indicative only. n/a: arm not run in that condition.

| Arm | S1: ms/epoch | S2: ms/epoch | S3: ms/epoch | S1: s/run | S2: s/run | S3: s/run |
|---|---|---|---|---|---|---|
| A7M Front-loaded (exactly M) | 2.6 | 2.6 | 5.0 | 1.3 | 1.0 | 10.4 |
| B8 Predictive (earlier) | 13.5 | n/a | 52.8 | 2.0 | n/a | 6.0 |
| C1 Causal debt (earlier) | 20.3 | 21.4 | 67.0 | 2.6 | 2.5 | 7.1 |
| COCRO-M | 8.2 | 9.3 | 27.7 | 1.5 | 1.4 | 4.2 |
| COCRO-M + full-horizon rerank | 20.8 | 22.3 | 55.5 | 2.5 | 2.4 | 6.3 |
| COCRO + rollout timing (exploratory) | 86.7 | 92.2 | n/a | 7.8 | 8.0 | n/a |

![Fig. 10. Error reduction per realised mutation relative to Static, by arm and condition.](figures_v3/fig_efficiency.png)

**Table 10** Error reduction per realised mutation relative to Static (higher is better; descriptive).

| Arm | S1, M = 3 | S1, M = 6 | S2, M = 3 | S2, M = 6 | S3, M = 3 | S3, M = 6 |
|---|---|---|---|---|---|---|
| A7M Front-loaded (exactly M) | 0.0328 | 0.0245 | 0.0395 | 0.0290 | 0.0119 | 0.0097 |
| B8 Predictive (earlier) | 0.0243 | 0.0212 | 0.0420 | n/a | 0.0103 | 0.0080 |
| C1 Causal debt (earlier) | 0.0305 | 0.0223 | 0.0303 | 0.0236 | 0.0094 | 0.0081 |
| COCRO-M | 0.0385 | 0.0282 | 0.0443 | 0.0325 | 0.0143 | 0.0112 |

![Fig. 11. Mean E against decision time per epoch (log scale), M = 6.](figures_v3/fig_cost_error.png)

![Fig. 12. Decision time per epoch (log scale) by arm and condition; measured under load, indicative only.](figures_v3/fig_time.png)

### 6.7. Earlier studies (context)

The earlier controllers were evaluated in v0.8 (60 held-out seeds) and Revision 2 (60 seeds, original and budget-matched calibrations). Table 11 summarises them. The predictive controller B8 beat the reactive controller A1 in all six conditions but not the front-loaded schedules; the debt controller C1 did not beat the front-loaded schedule A7 in any condition under budget-matched calibration. Those studies used the same conditions and metrics but different seeds and 60 rather than 150 seeds.

**Table 11** Earlier studies (60 held-out seeds each): number of conditions in which the first-named or the second-named arm had significantly lower error (Holm p < 0.05) and in which neither did.

| Study | Comparison (first vs second) | Conditions evaluated | First arm lower error (Holm p < 0.05) | Second arm lower error (Holm p < 0.05) | No significant difference |
|---|---|---|---|---|---|
| v0.8 held-out (60 seeds) | B8 vs A1 (reactive) | 6 | 6 | 0 | 0 |
| v0.8 held-out (60 seeds) | B8 vs A7 (front-loaded) | 6 | 0 | 5 | 1 |
| v0.8 held-out (60 seeds) | B8 vs A7M | 6 | 0 | 6 | 0 |
| R2 original (60 seeds) | C1 vs A7 | 6 | 0 | 6 | 0 |
| R2 original (60 seeds) | C1 vs B8 | 6 | 0 | 6 | 0 |
| R2 amended, matched budgets (60 seeds) | C1 vs A7 | 6 | 0 | 3 | 3 |
| R2 amended, matched budgets (60 seeds) | C1 vs B8 | 5 | 1 | 2 | 2 |

## 7. Discussion

**What the evidence supports.** On the six random-geometric-graph conditions, with an algorithm and an analysis plan frozen in advance, selecting the swap by expected gain under posterior failure scenarios lowered the mean consensus error relative to three baselines at matched mutation budgets. The effects are small to moderate: against the strongest and cheapest baseline, the exact-budget front-loaded schedule, the reduction is 1.4% to 8.0%, with a margin-exceeding effect in the four 40-node conditions only.

**What the ablations suggest about the mechanism.** The benefit appears to come from evaluating several removal candidates with a spectral objective rather than from the probabilistic machinery: the posterior-sampling and propagation components, which motivated the design, show no measurable benefit here. A plausible reading is that, in a random-geometric environment whose failure process is close to what the earlier controllers already summarised, the candidate ordering is robust to the failure-model details. This reading is untested; an environment with strong cascades, which Tier C would provide, is where the propagation term could matter.

**Timing.** The toy study shows a regime in which deferring a rewiring is valuable, but in the simulator the rollout timing gave at most small exploratory gains at about 10 to 14 times the cost, and the pre-declared rule dropped it. We interpret this as a negative result for state-dependent timing under a fixed budget in these environments, consistent with the earlier studies.

**Trade-offs.** COCRO-M uses the whole budget at the front-loaded times and therefore inherits the connectivity and recovery profile of the front-loaded schedule. If disconnection and recovery are the operational priority, B8 or C1 are preferable in several conditions despite their higher error.

## 8. Limitations

* **Tiers B and C were not run.** Only random geometric graphs with 40 and 80 nodes and the original burst/background failure models were tested. The performance on Erdős–Rényi, Barabási–Albert, Watts–Strogatz and scale-free graphs and under cascading, node and regime-shift failures is unknown. Tier B was started and stopped by the authors before any output was read.
* The propagation term, posterior sampling and the full-horizon rerank showed no measurable benefit in Tier A; their inclusion in the model is not justified by these data.
* Not implemented: delayed credit assignment, persistence-aware removal, per-link hazard models, the debt ledger inside COCRO, mobility, link-observation noise, scalability beyond 80 nodes and parameter-sensitivity grids.
* The thresholds of A1, B8 and C1 were calibrated on other seeds and under a different mutation-count rule; they are not tuned for the new seeds, which may disadvantage them. B8 is absent from S2 with M = 6.
* Decision times were measured with parallel workers under load. COCRO-M's absolute times are small, but the ratios are indicative.
* Connectivity and recovery gains over the front-loaded schedule are small, and B8 and C1 do better on several of these measures.
* The surrogate of E is biased upward (by 0.04–0.09 at mid-range) and saturates at the floor for small graphs; it orders candidates, it does not predict E. The consensus metric is evaluated with redrawn initial values and a fixed tolerance.
* The controller is centralised; no distributed or decentralised guarantee is claimed.
* The 150-seed minimum detectable effect is about 0.011 at 80% power for the observed paired SD; effects below the 0.01 margin are reported as such.
* The reference list was verified for existence and metadata against Crossref, not for the support of each individual statement.

## 9. Reproducibility

All results are produced by scripts from fixed configurations and seeds. The held-out run is `experiments/run_r3.py` (tier A), the analysis `experiments/analyze_r3.py`, and the manuscript tables and figures `paper/tools/make_v3_sections.py`; the claims of the text are checked against the analysis files by `paper/tools/check_claims_v3.py`. The test suite covers the failure model, scenario sampler, gain estimator, policy, environments, pipeline and the numerical checks of the theory note. The run used 12,150 runs on seeds 9300–9449 at commit d4238a1.

## 10. Conclusion

Under a hard cap on rewirings, choosing which link to swap by its expected gain under failure scenarios drawn from a fitted posterior lowered consensus error compared with the exact-budget front-loaded schedule, the predictive controller and the debt controller in all 17 primary tests of a pre-registered, 150-seed evaluation on random geometric graphs. The improvements are small to moderate, they come mainly from the candidate breadth and the spectral objective, rollout-based timing did not help, and connectivity and recovery are not better than those of more conservative controllers. The generality of the result to other graph families and failure processes remains to be tested; the corresponding evaluation is implemented and pre-registered but not run.

**Funding:** [AUTHOR CONFIRMATION REQUIRED: state the funding source(s), grant number(s), or “This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors,” if accurate.]

**Declaration of competing interests:** [AUTHOR CONFIRMATION REQUIRED: confirm whether any financial or personal relationships could have influenced the work; use the target journal’s required wording. See also the Declaration of interests form at the end of the document.]

**CRediT authorship contribution statement:** [AUTHOR CONFIRMATION REQUIRED: assign each CRediT role to the appropriate author(s), with every author’s approval.]

**Ethics approval and consent:** Not applicable (simulation only; no human or animal data).

**Data availability statement:** The code, frozen configurations, analysis scripts, audit materials and analysis manifests are available at https://github.com/SanthoshAshish/TCCE-R/tree/revision-v0.8. Raw per-run evaluation logs are not included in the tracked repository; they may be made available by the authors on reasonable request or deposited in a suitable repository before submission, subject to the target journal’s policy. No DOI is currently assigned.

**Code availability:** Source code, experiment scripts and manuscript tools are available at https://github.com/SanthoshAshish/TCCE-R/tree/revision-v0.8. The Revision 3 held-out evaluation (Tier A) ran at commit d4238a1; the v0.8 held-out evaluation corresponds to commit e16a208, the Revision 2 original evaluation to commit d7f6a40 and the amended evaluation to commit 14b7359; the branch also contains the manuscript and analysis/audit updates.

**Declaration of generative AI and AI-assisted technologies in the manuscript preparation process:** The research design, experimentation, interpretation of results, and scientific conclusions presented in this manuscript were primarily carried out by the authors. Claude (Anthropic) was used as an assistive tool for selected tasks, including manuscript drafting, code development, and analysis scripting. The authors retained responsibility for the research methodology, evaluation of experimental results, interpretation of findings, and final manuscript content. All AI-assisted material was reviewed and edited by the authors, who take responsibility for the accuracy and integrity of the submitted work. All figures were generated programmatically from experimental result files, without the use of generative-AI image-generation tools.

**Acknowledgements:** The authors would like to express their sincere gratitude to Professor Deethi G for her valuable guidance, constructive feedback, and encouragement throughout this research. Her support and suggestions contributed to the development and refinement of this work. The authors also acknowledge their institution for providing an academic environment that supported this research.

## References

*32 references are cited; 21 (66%) are from 2022-2026. Reference metadata were checked against Crossref (existence, title, year); claims attached to citations are supported at the level of title and venue only. Holm (1979) has no DOI.*

[1] Fiedler, M., 1973. Algebraic connectivity of graphs. Czechoslovak Mathematical Journal, 23(2), pp.298–305. https://doi.org/10.21136/cmj.1973.101168
[2] Xiao, L. and Boyd, S., 2004. Fast linear iterations for distributed averaging. Systems & Control Letters, 53(1), pp.65–78. https://doi.org/10.1016/j.sysconle.2004.02.022
[3] Olfati-Saber, R. and Murray, R.M., 2004. Consensus Problems in Networks of Agents With Switching Topology and Time-Delays. IEEE Transactions on Automatic Control, 49(9), pp.1520–1533. https://doi.org/10.1109/tac.2004.834113
[4] Zhang, S., Liu, J., Wang, W. and Zhang, Z., 2023. Topology-based dynamic event-triggered leader-following consensus of multi-agent systems under switching topologies. ISA Transactions, 142, pp.299-309. https://doi.org/10.1016/j.isatra.2023.08.010
[5] Xiao, P. and Gu, Z., 2022. Adaptive Event-Triggered Consensus of Fractional-Order Nonlinear Multi-Agent Systems. IEEE Access, 10, pp.213-220. https://doi.org/10.1109/access.2021.3136892
[6] Wang, Y., Yang, Y. and Wu, L., 2023. Adaptive fault-tolerant consensus control of multi-agent systems with event-triggered inputs. Information Sciences, 650, p.119594. https://doi.org/10.1016/j.ins.2023.119594
[7] Battilotti, S., Cacace, F. and d'Angelo, M., 2024. Consensus Analysis of Random Subgraphs for Distributed Filtering With Link Failures. IEEE Transactions on Automatic Control, 69(4), pp.2476-2483. https://doi.org/10.1109/tac.2023.3311709
[8] Liu, Y., Fan, H., Liu, L. and Wang, B., 2024. Adaptive output consensus of heterogeneous nonlinear multi‐agent system under random link failures with partially unknown transition rates. International Journal of Robust and Nonlinear Control, 34(12), pp.7799-7820. https://doi.org/10.1002/rnc.7367
[9] Fu, Y., Wen, G., Zhao, D. and Lv, Y., 2026. Resilient consensus of multi-agent systems with time-varying topologies and unmodeled dynamics. Systems & Control Letters, 218, p.106579. https://doi.org/10.1016/j.sysconle.2026.106579
[10] Muthirayan, D. and Khargonekar, P.P., 2022. Online Algorithms for Network Robustness Under Connectivity Constraints. IEEE Transactions on Network Science and Engineering, 9(4), pp.2266-2277. https://doi.org/10.1109/tnse.2022.3160073
[11] Chujyo, M. and Toriumi, F., 2024. Link-limited bypass rewiring for enhancing the robustness of complex networks. Applied Network Science, 9(1), p.17. https://doi.org/10.1007/s41109-024-00624-4
[12] Feng, Y., Wang, F., Liu, Z. and Chen, Z., 2024. An Online Topology Control Method for Multi-Agent Systems: Distributed Topology Reconfiguration. IEEE Transactions on Network Science and Engineering, 11(5), pp.4358-4370. https://doi.org/10.1109/tnse.2024.3417478
[13] Estrada, J., Djemai, M., Castillo-Toledo, B. and Defoort, M., 2026. Topology Reconfiguration of Multiagent Systems under Link Failures. IEEE Control Systems Letters, pp.1-1. https://doi.org/10.1109/lcsys.2026.3742141
[14] Perez-Salesa, I., Aldana-Lopez, R. and Sagues, C., 2023. Precise Dynamic Consensus under Event-Triggered Communication. Machines, 11(2), p.128. https://doi.org/10.3390/machines11020128
[15] Kim, H.J. and Yoo, S.J., 2023. Dynamic Event-Triggered Communication-Based Adaptive Consensus Tracking of Uncertain Nonlinear Multiagent Systems in Pure-Feedback Form. IEEE Access, 11, pp.21092-21103. https://doi.org/10.1109/access.2023.3250440
[16] Wang, Y., Yu, S. and Zhao, Y., 2024. Switching adaptive dynamic event-triggered consensus of nonlinear multi-agent systems under DoS attacks and communication delay. Information Sciences, 682, p.121257. https://doi.org/10.1016/j.ins.2024.121257
[17] Dong, Z., Shi, S., Ouyang, Q. and Jiang, J., 2026. Event-triggered adaptive predefined-time consensus for multi-agent systems under switching topologies. ISA Transactions, 178, pp.72-84. https://doi.org/10.1016/j.isatra.2026.08.015
[18] Tian, Y., Tian, S., Li, H., Han, Q. and Wang, X., 2022. Event-Triggered Security Consensus for Multi-Agent Systems with Markov Switching Topologies under DoS Attacks. Energies, 15(15), p.5353. https://doi.org/10.3390/en15155353
[19] Ghosh, A. and Boyd, S., 2006. Growing Well-connected Graphs. In: Proceedings of the 45th IEEE Conference on Decision and Control, pp 6605–6611. https://doi.org/10.1109/cdc.2006.377282
[20] Boyd, S., Ghosh, A., Prabhakar, B. and Shah, D., 2006. Randomized gossip algorithms. IEEE Transactions on Information Theory, 52(6), pp.2508-2530. https://doi.org/10.1109/TIT.2006.874516
[21] Carron, A., Saccani, D., Fagiano, L. and Zeilinger, M.N., 2023. Multi-agent Distributed Model Predictive Control with Connectivity Constraint. IFAC-PapersOnLine, 56(2), pp.3806-3811. https://doi.org/10.1016/j.ifacol.2023.10.1310
[22] Wang, J. and Li, S., 2024. Distributed Model Predictive Control for Consensus of Multi-Agent Systems With Connectivity Maintenance. IEEE Transactions on Circuits and Systems I: Regular Papers, 71(3), pp.1299-1310. https://doi.org/10.1109/tcsi.2023.3334869
[23] Nguyen, T.S., Cao, H.N., Thai, N.H. and Pham, M.T., 2026. C-CBF: Communication-Aware Control Barrier Functions for Resilient Multi-Robot Connectivity. IEEE Transactions on Automation Science and Engineering, 23, pp.5596-5614. https://doi.org/10.1109/tase.2026.3667964
[24] Kumari, S., Kumar, R., Muhuri, S. and Namasudra, S., 2025. A Novel Budget-Constrained Rewiring Strategy for Information Flow in Social Networks. IEEE Transactions on Computational Social Systems, 12(5), pp.2242-2253. https://doi.org/10.1109/tcss.2024.3519566
[25] Zhang, Y., Ren, W., Feng, J., Zhao, J., Chen, Y. and Mi, Y., 2024. A cascading failure propagation model for a network with a node emergency recovery function. Applied Energy, 371, p.123655. https://doi.org/10.1016/j.apenergy.2024.123655
[26] Li, J., Wang, Y. and Zhong, J., 2022. An Exceeding Recovery Model for Enhancing Network Resilience Against Cascading Failures. IEEE Access, 10, pp.71035-71043. https://doi.org/10.1109/access.2022.3188659
[27] Freeman, P.R., 1983. The Secretary Problem and Its Extensions: A Review. International Statistical Review / Revue Internationale de Statistique, 51(2), p.189. https://doi.org/10.2307/1402748
[28] Whittle, P., 1988. Restless bandits: activity allocation in a changing world. Journal of Applied Probability, 25(A), pp.287-298. https://doi.org/10.2307/3214163
[29] Bertsekas, D.P., Tsitsiklis, J.N. and Wu, C., 1997. Rollout Algorithms for Combinatorial Optimization. Journal of Heuristics, 3(3), pp.245-262. https://doi.org/10.1023/a:1009635226865
[30] THOMPSON, W.R., 1933. ON THE LIKELIHOOD THAT ONE UNKNOWN PROBABILITY EXCEEDS ANOTHER IN VIEW OF THE EVIDENCE OF TWO SAMPLES. Biometrika, 25(3-4), pp.285-294. https://doi.org/10.1093/biomet/25.3-4.285
[31] Russo, D.J., Roy, B.V., Kazerouni, A., Osband, I. and Wen, Z., 2018. A Tutorial on Thompson Sampling. Foundations and Trends® in Machine Learning, 11(1), pp.1-96. https://doi.org/10.1561/2200000070
[32] Dempster, A.P., Laird, N.M. and Rubin, D.B., 1977. Maximum Likelihood from Incomplete Data Via the EM Algorithm. Journal of the Royal Statistical Society Series B: Statistical Methodology, 39(1), pp.1-22. https://doi.org/10.1111/j.2517-6161.1977.tb01600.x

## Appendices

### Appendix A. Full primary test table

**Table A1** All primary tests: ΔE = COCRO-M minus comparator; dz: standardised paired effect size; verdicts at the 0.01 and 0.02 margins.

| Condition | Comparison | n | ΔE | 95% CI | dz | Holm p | Verdict (margin 0.01) | Verdict (margin 0.02) |
|---|---|---|---|---|---|---|---|---|
| S1, M = 3 | COCRO − M − A7M | 150 | −0.0171 | [−0.0224, −0.0122] | −0.54 | 2.0e-14 | first arm better (meaningful) | first arm better, below margin |
| S1, M = 3 | COCRO − M − B8 | 150 | −0.0430 | [−0.0502, −0.0358] | −0.96 | 1.4e-17 | first arm better (meaningful) | first arm better (meaningful) |
| S1, M = 3 | COCRO − M − C1 | 150 | −0.0238 | [−0.0308, −0.0169] | −0.56 | 1.5e-11 | first arm better (meaningful) | first arm better (meaningful) |
| S1, M = 6 | COCRO − M − A7M | 150 | −0.0222 | [−0.0269, −0.0178] | −0.78 | 1.5e-15 | first arm better (meaningful) | first arm better (meaningful) |
| S1, M = 6 | COCRO − M − B8 | 150 | −0.0454 | [−0.0527, −0.0378] | −0.96 | 2.3e-16 | first arm better (meaningful) | first arm better (meaningful) |
| S1, M = 6 | COCRO − M − C1 | 150 | −0.0372 | [−0.0454, −0.0292] | −0.75 | 2.7e-14 | first arm better (meaningful) | first arm better (meaningful) |
| S2, M = 3 | COCRO − M − A7M | 150 | −0.0146 | [−0.0209, −0.0084] | −0.38 | 2.3e-07 | first arm better (meaningful) | first arm better, below margin |
| S2, M = 3 | COCRO − M − B8 | 150 | −0.0115 | [−0.0186, −0.0044] | −0.26 | 4.7e-04 | first arm better (meaningful) | first arm better, below margin |
| S2, M = 3 | COCRO − M − C1 | 150 | −0.0442 | [−0.0525, −0.0357] | −0.84 | 1.6e-15 | first arm better (meaningful) | first arm better (meaningful) |
| S2, M = 6 | COCRO − M − A7M | 150 | −0.0212 | [−0.0280, −0.0143] | −0.50 | 3.4e-11 | first arm better (meaningful) | first arm better (meaningful) |
| S2, M = 6 | COCRO − M − C1 | 150 | −0.0583 | [−0.0694, −0.0468] | −0.83 | 1.8e-15 | first arm better (meaningful) | first arm better (meaningful) |
| S3, M = 3 | COCRO − M − A7M | 150 | −0.0073 | [−0.0090, −0.0056] | −0.68 | 1.2e-15 | first arm better, below margin | first arm better, below margin |
| S3, M = 3 | COCRO − M − B8 | 150 | −0.0128 | [−0.0158, −0.0097] | −0.67 | 1.3e-12 | first arm better (meaningful) | first arm better, below margin |
| S3, M = 3 | COCRO − M − C1 | 150 | −0.0155 | [−0.0186, −0.0124] | −0.79 | 1.8e-14 | first arm better (meaningful) | first arm better, below margin |
| S3, M = 6 | COCRO − M − A7M | 150 | −0.0093 | [−0.0114, −0.0072] | −0.72 | 1.8e-14 | first arm better, below margin | first arm better, below margin |
| S3, M = 6 | COCRO − M − B8 | 150 | −0.0225 | [−0.0263, −0.0188] | −0.97 | 3.6e-18 | first arm better (meaningful) | first arm better (meaningful) |
| S3, M = 6 | COCRO − M − C1 | 150 | −0.0222 | [−0.0259, −0.0183] | −0.94 | 2.0e-17 | first arm better (meaningful) | first arm better (meaningful) |
