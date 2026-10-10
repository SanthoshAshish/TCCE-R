# Key-paper verification, implementation comparison, and proposed experiment

Written 2026-10-10. No simulator code, configs or results were changed.

The code compared is tag `v0.5`. `tccer/` and `experiments/` are unchanged since then; HEAD `80ace87` only adds a scenario.

Labels used throughout:
- **[V]** verified from the full text, with page, section or equation;
- **[V-thesis]** verified from the author's thesis, not the journal article;
- **[M]** verified from metadata only;
- **[U]** unverified;
- **[I]** my interpretation;
- **[R]** recommendation.

---

## Task 1: verification of three papers

### 1.1 Ghosh & Boyd (2006): full text read

- **Source:** author-hosted PDF, <https://web.stanford.edu/~boyd/papers/pdf/growing_fast_graphs.pdf> (7 pages; proceedings pages 6605–6611). Read in full.
- **Bibliographic record [V]:**
  - title: *Growing Well-connected Graphs*
  - authors: Arpita Ghosh, Stephen Boyd (Stanford)
  - venue: *Proceedings of the 45th IEEE Conference on Decision & Control*, San Diego, 13–15 Dec 2006, session FrIP13.1, pp. 6605–6611
  - DOI: [10.1109/CDC.2006.377282](https://doi.org/10.1109/CDC.2006.377282) (title, authors and pages match Crossref)

| Item | What the paper states | Where |
|---|---|---|
| Graph model | Undirected, unweighted graph; Laplacian L = AAᵀ; λ₂ = algebraic connectivity; Fiedler vector = normalised λ₂ eigenvector | §I, eq. (1), p. 6605 |
| Objective | maximize λ₂(L(E_base ∪ E)) s.t. \|E\| = k, E ⊆ E_cand, with E_base ∩ E_cand = ∅ | §I-A, eq. (2), pp. 6605–6606 |
| Boolean form | maximize λ₂(L_base + Σ x_l a_l a_lᵀ) s.t. 1ᵀx = k, x ∈ {0,1}^mc | eq. (3), p. 6606 |
| Convex relaxation | x ∈ [0,1]^mc (eq. 5); SDP form (eq. 6); solvable up to about 1000 candidate edges; gives an upper bound | §II, p. 6606 |
| Greedy heuristic | Add k edges one at a time. Each step: (1) compute a unit Fiedler vector v of the **current** Laplacian; (2) add the remaining candidate (i, j) with the largest (vᵢ − vⱼ)² | §III, p. 6607 |
| Justification | If λ₂ is isolated (λ₁ < λ₂ < λ₃), ∂λ₂/∂x_l = (vᵢ − vⱼ)², i.e. the first-order predicted increase | eq. (7), p. 6607 |
| Key caveat | "When λ₂ is not isolated, adding a single edge cannot increase λ₂." With multiplicity r, exactly r edges are needed | p. 6607 |
| Disconnected graphs | Applied to a disconnected graph, the heuristic "always chooses an edge that connects two connected components" | §III-B-1, pp. 6607–6608 |
| Bounds | Lower and upper bounds on λ₂ after adding one edge, both increasing in (vᵢ − vⱼ)² (eqs. 8, 9); weaker bound λ₂ + (vᵢ − vⱼ)² (eq. 10) | §III-B-2, p. 6608 |
| Evaluation | Metric: λ₂(L) vs number of edges added k.<br>• 10 nodes / 14 edges / 11 candidates: heuristic vs exhaustive optimum and the SDP bound (Fig. 2)<br>• 28 nodes / 68 edges / 42 candidates: heuristic vs SDP bound (Fig. 4)<br>• 1000 nodes / 5517 edges / 2341 candidates: heuristic vs random addition (Fig. 6) | §IV, pp. 6609–6610 |
| Findings | The heuristic is "very close" to the optimum and to the upper bound. On the large graph, 150 well-chosen edges give λ₂ = 0.041, while adding all 2341 gives only 0.051 | §IV, p. 6609 |
| Edge costs | maximize λ₂ s.t. cᵀx ≤ k; greedy rule becomes the largest (vᵢ − vⱼ)²/c_l | §V, eq. (14), p. 6610 |
| Removing edges | "remove the k edges one at a time … choose the edge with the smallest (vᵢ − vⱼ)²"; also "we can construct an algorithm that adds and removes edges", with **no algorithm given** | §V, p. 6610 |
| Assumptions | Static graph; no failures, delays or dynamics; centralised eigenvector computation (Lanczos or multigrid suggested) | §III-A, p. 6607 [V]; "no failures/dynamics" is [I] from their absence |

### 1.2 Gençata & Mukherjee (2003): journal text not accessed; method verified from the first author's thesis

- **Bibliographic record [M]:** A. Gençata, B. Mukherjee, *Virtual-topology adaptation for WDM mesh networks under dynamic traffic*, IEEE/ACM Transactions on Networking 11(2):236–247, 2003, DOI [10.1109/TNET.2003.810319](https://doi.org/10.1109/TNET.2003.810319) (Crossref). Conference version: IEEE INFOCOM 2002.
- **Access:**
  - OpenAlex lists the journal paper as closed access.
  - Two CiteSeerX "submitted version" records exist, but their files could not be retrieved.
  - The method was verified instead from **A. Gençata, PhD thesis**, *Topology and Bandwidth Adaptation in Optical WDM Backbone Networks with Dynamic Traffic*, Istanbul Technical University, Institute of Science and Technology, April 2003. It is author-hosted at <https://web.itu.edu.tr/gencata/pubs/AGthesis.pdf> (139 PDF pages).
  - The thesis's publication list (thesis p. 119) names the ToN paper ("to appear in April 2003 issue") and the INFOCOM 2002 paper with the same title.
  - **It is not verified which parts of the thesis appear in the ToN paper** [U]. Page numbers below are the thesis's printed pages; PDF page = printed + 20.

| Item | What the thesis states | Where [V-thesis] |
|---|---|---|
| Network model | N nodes, bidirectional fibres with W wavelengths; transmitters and receivers per node; full wavelength conversion; unidirectional lightpaths; shortest-path routing | §3.2.1, pp. 37–38 |
| Control architecture | **Centralised manager** collects link usage at the end of every observation period; assumes the period (hundreds of seconds or more) is much longer than signalling delay | §3.2.1, p. 37 |
| Problem | Decide whether the virtual topology is efficient, whether to change it, and which lightpath to add or delete. Steps: monitor → trigger → modify | §3.2.2, pp. 38–39 |
| Trigger rule (adaptation cycle) | Every T seconds: find the highest and lowest lightpath loads L_H, L_L. **If L_H > W_H, add** a lightpath; **else if L_L < W_L, delete** one; else no change. Only **one lightpath** per step | §3.3, p. 39 |
| Watermarks | W_H, W_L ∈ (0, 1), W_L < W_H; overload means load > W_H · C | §3.3.1, p. 41 |
| Step objective (MILP-A) | **Minimise the maximum lightpath load L_max** | §3.3.1, p. 42 |
| Constraints | (3.1)–(3.5) lightpath routing and wavelength limits; (3.6)–(3.7) the new topology differs by at most one lightpath, with **addition prioritised over deletion**; (3.8)–(3.11) unsplit multicommodity flow, L_max ≤ C·W_H; (3.12)–(3.13) transceiver limits | §3.3.1, pp. 41–43 |
| Evaluation metrics | Number of lightpaths (resource cost) and **number of changes (operation cost)**; compared with an earlier optimal reconfiguration MILP ("MILP-B") solved in CPLEX | §3.3.2, p. 44 |
| Heuristic version | "Quasi-balanced" target W_L ≤ load ≤ W_H; studies of the watermarks, observation period, window size and load balancing; comparisons with local minimum, SMLTDA and GLTDA | Ch. 4, pp. 49–74 |
| **History-window variant** | The basic rule "may sometimes react very quickly". Averaging loads over a sliding window of 1, 2 or 4 periods is "useful to prevent the false alarms", but "would also delay some necessary changes" | §4.4.5, pp. 64–65 |
| Unlimited changes per step | "one change in one observation period was enough to maintain the loads to be balanced most of the time" | Ch. 4 conclusion, p. 75 |

### 1.3 Sydney, Scoglio & Gruenbacher (2013): not verifiable beyond metadata

- **Bibliographic record [M]:** *Optimizing algebraic connectivity by edge rewiring*, Applied Mathematics and Computation 219(10):5465–5479, 2013, DOI [10.1016/j.amc.2012.11.002](https://doi.org/10.1016/j.amc.2012.11.002). Authors: Ali Sydney, Caterina Scoglio, Don Gruenbacher (Crossref).
- **Access:** closed access (OpenAlex). No author-hosted, repository or thesis copy was found in four searches (journal title, Kansas State repository, the first author's dissertation, co-author pages). ScienceDirect blocked automated access.
- **[U] — everything about content is unverified:** the objective, algorithm, constraints, assumptions and metrics. The only available description is an indexed paraphrase of the abstract: which edge to rewire for the largest λ₂ increase, extended to several edges.
- **[R]** obtain the PDF through your university library before citing anything beyond the title and the stated question.

---

## Task 2: comparison with the TCCE-R code

### 2.1 What matches prior work [V]

| Our code | Prior work | Match |
|---|---|---|
| `core/coupling.py:49`, gain of adding (i, j) = `(fiedler[i] − fiedler[j])**2`; `metrics/resilience.py:19`, unit eigenvector from `np.linalg.eigh` | Ghosh & Boyd eq. (7) and the greedy step, p. 6607 | **Same formula**: first-order predicted λ₂ increase with a unit Fiedler vector |
| `core/mutations.py:79–82`, rewire removes the configured link with the **smallest** `(f_i − f_j)²` | Ghosh & Boyd §V, p. 6610: remove the edge with the smallest (vᵢ − vⱼ)² | **Same removal criterion** |
| One mutation per decision epoch, Fiedler vector recomputed each epoch (`core/selector.py:30`) | Greedy adds one edge at a time and recomputes v (p. 6607); Gençata changes one lightpath per period (p. 39) | Same "one change, then re-measure" structure |
| `core/debt.py:32`, `D = max(0, D + s − κ)` | One-sided CUSUM (Page 1954) | Standard modern form. **Page's original 1954 formulation was not read** [U] |
| `policies/baselines.py:37–40`, reactive fires when this epoch's E exceeds a fixed threshold | Gençata §3.3, p. 39: at the end of each observation period, change the topology only if a measured load is outside the watermarks | Same **trigger structure**: periodic measurement, a fixed threshold, one incremental change |

### 2.2 Our integration and design choices (not from these papers) [V: code read; attribution I]

1. **Rewire score.** `coupling.py:50–52` scores a rewire as add-gain − remove-loss using **one** Fiedler vector of the pre-change graph. Ghosh & Boyd recompute v after every single change and give no add-and-remove algorithm (§V).
2. **One removal per call.** `mutations.py:82` fixes a single removal r for all candidate additions.
3. **Removal restrictions:** only non-bridges, cooldown (`tabu`), and failed-link valuation `zero`/`if_up`, plus "only failed links when disconnected" (`mutations.py:72–80`).
4. **Lexicographic ranking** (`coupling.py:57–70`): fewer components first; candidates within 10% of the best gain are treated as tied and re-ordered by Δbridges, then link length. **This is not pure greedy**: it can choose an edge with up to 10% lower predicted gain. Ghosh & Boyd's published cost-aware variant uses the ratio (vᵢ − vⱼ)²/c_l instead (§V, eq. 14).
5. **Search limits:** a shortlist of 10 and at most 30 gate attempts.
6. **Safety gate** with an exact λ₂ floor, an interim-state check, degree limits and the budget.
7. **CUSUM stress** s = w·(E, C, V), the trigger D > Θ, adaptive Θ, the feedback success rule, and budget matching.

### 2.3 Where the implementation departs from the method it cites [V: code; consequences I]

| # | Departure | Evidence | Consequence |
|---|---|---|---|
| D-a | **Objective mismatch.** The selector maximises λ₂ of the unweighted Laplacian, but the consensus protocol uses Metropolis weights, and the measured outcome is E from that protocol. | Ghosh & Boyd optimise λ₂(L) (eq. 2) and link λ₂ to a unit-rate continuous-time chain (p. 6605); our consensus is `consensus/algorithm.py` (Metropolis) | [I] The selector optimises a proxy. This may explain cases where rewiring raised E, such as the v0.5 grid example. Untested. |
| D-b | **Disconnected case handled differently.** Ghosh & Boyd prove the Fiedler heuristic picks a cross-component edge by itself. Our code sets gain 0 when disconnected (`coupling.py:48`) and uses an explicit component count plus link length. | §III-B-1, pp. 6607–6608 vs `coupling.py:46–49` | Same intent, different tie-breaking among reconnecting edges. Not equivalent. |
| D-c | **Isolation of λ₂ is not checked** before using the first-order estimate. | p. 6607 vs `coupling.py` | Read-only diagnostic: λ₂ was never repeated in sampled static runs (0/567 connected epochs, v0.4 network, seeds 100–109; 0/115, grid example, seeds 0–4). Adaptive runs were not sampled. |
| D-d | **Rewire is not a published algorithm.** It combines Ghosh & Boyd's add and remove criteria with one Fiedler vector. | §V gives no combined algorithm | It must be described as our heuristic, not as Ghosh & Boyd's method. |
| D-e | **Lexicographic tolerance** departs from greedy maximum gain. | `coupling.py:66–69` | "Uses the Ghosh–Boyd perturbation score within a lexicographic rule", not "implements Ghosh & Boyd". |

### 2.4 Is the reactive baseline a faithful implementation of Gençata & Mukherjee? **No: a related heuristic.**

| Aspect | Gençata (thesis §3.3) | Our reactive | Same? |
|---|---|---|---|
| Measured signal | Per-lightpath traffic load (max and min) | One network-level consensus stress E | ✘ different domain and signal |
| Thresholds | Two (W_H for add, W_L for delete) | One (add or rewire on E > h) | ✘ no low watermark, no delete action |
| Action | Add or delete one lightpath | Add or rewire one link (strict budget: always rewire) | partial |
| Choice of change | MILP minimising maximum link load | Our lexicographic λ₂ selector | ✘ |
| Timing | Every observation period; one change per period | Every epoch; cooldown of 2 epochs; mutation cap | partial |
| Smoothing | Optional history window (§4.4.5) | None (window = 1) | matches the *basic* variant |

**[I] Suggested wording for the paper:** "Reactive follows the threshold-triggered, one-change-per-period pattern of Gençata & Mukherjee's adaptation cycle, applied to consensus stress." It must **not** be called an implementation of their method.

---

## Hypotheses (not verified; for the experiment below) [I]

- **H1.** CUSUM accumulation trades detection delay for fewer false alarms. This is the trade-off Gençata reports for history-window averaging (§4.4.5, p. 64). It can only pay off when acting on transient degradations is costly.
- **H2.** In v0.4, reactive's advantage came largely from **earliness**: its first mutation was at epoch 1.2 vs 11.3. A time-averaged E over 80 epochs rewards early, lasting improvements.
- **H3.** Part of TCCE-R's deficit may come from what its debt contains: C (nearly binary) and V (small). The v0.4 tuning already set w_C = w_V = 0, which suggests these terms did not help on tuning seeds. That is not evidence that accumulation itself is useless.

---

## Task 3: smallest fair experiment [R]

**Question:** at an equal number of reconfigurations, does an *accumulated* stress statistic decide *when* to act better than the *instantaneous* consensus-error threshold?

### Design principle
Change **only the trigger statistic**. Everything else stays identical across policies:
- the selector, safety gate, strict budget and setup delay;
- the failure trace (common random numbers);
- the measured signal E (except in the arms that deliberately add C and V).

### Policies (arms)

| Arm | Trigger | Purpose |
|---|---|---|
| A0 Static | never | floor |
| A1 Reactive | E_k > h | instantaneous baseline (window 1) |
| A2 Moving average | mean(E_{k−w+1..k}) > h, w = 4 | published smoothing precedent (Gençata §4.4.5) |
| A3 CUSUM-E | D_k > Θ, w = (1, 0, 0), **fixed** Θ | pure accumulation of E |
| A4 CUSUM-ECV | D_k > Θ, v0.1 weights (0.5, 0.3, 0.2), fixed Θ | do C and V add information? |
| A5 TCCE-R | A4 with adaptive Θ | the full mechanism, isolating the Θ effect vs A4 |
| A6 Random timing | fires at M epochs drawn from the policy RNG, independent of all state | does *any* state-based timing beat chance? |

### Budget matching
v0.2–v0.4 capped baselines at TCCE-R's count, which made the cap itself decide timing. Instead:
- Fix two target budgets, **M ∈ {3, 6}** mutations per run (about the v0.4 range).
- On tuning seeds, calibrate each arm's threshold (h, or Θ with κ fixed) to the value whose mean count is closest to M.
- Then apply a per-seed cap of M to every arm as a safety bound.
- Report the realised counts. Exact matching is not guaranteed; the calibration is.

### Environment and seeds
- v0.4 environment (bursty failures, strict budget, `if_up`, all audit fixes).
- Delays: **d = 2** (primary) and **d = 8** (secondary; costly reconfiguration).
- Tuning seeds 100–119; **fresh held-out seeds 6000–6029**.
- Size: 7 arms × 2 budgets × 2 delays × 30 seeds = 840 runs, plus calibration (about 1,000 short runs). Minutes on a laptop.

### Metrics

**Outcomes:**
- mean E;
- disconnected fraction;
- λ₂;
- recovery time;
- mutations and pending link-epochs.

**Timing quality (the new part; analysis only):** using the *static* run on the same seed as the counterfactual trace, label every epoch as part of
- a **persistent** degradation episode (E above the static-run median for ≥ 4 consecutive epochs), or
- a **transient** one (≤ 2 epochs).

Then measure:
- *precision*: the share of mutations made during persistent episodes;
- *detection delay*: epochs from the start of a persistent episode to the first mutation;
- *false-alarm rate*: mutations during transient episodes;
- *wasted releases*: rewires whose released failed link would have recovered within d + 3 epochs, computable from the deterministic failure trace.

### Hypotheses and decision rules (to pre-register before running)
- **Primary:**
  - A3 vs A1 on mean E, at each (M, d): 4 paired Wilcoxon tests, Holm-adjusted.
  - "Accumulation provides useful information" requires Holm p < 0.05, ΔE ≤ −0.02 **and** precision no worse.
- **Secondary (Holm-adjusted as one family):**
  - A2 vs A1: whether smoothing alone suffices;
  - A3 vs A2: CUSUM vs moving average;
  - A4 vs A3: whether C and V add information;
  - A5 vs A4: the Θ effect;
  - A1 and A3 vs A6: whether informed timing beats chance.
- **Interpretation guide:**
  - If A2 ≈ A3, any benefit comes from smoothing, not CUSUM specifically.
  - If A1 ≈ A6, timing information matters little in this environment.
  - A3 better than A1 only at d = 8 would support H1.

### Implementation needed later (nothing done now)
- two small policy classes (moving average; random timing);
- a calibration script that finds thresholds for target budgets;
- analysis code for episode labelling and the timing-quality metrics;
- tests for each;
- A3–A5 need only configuration (existing `tccer_fixed` / `tccer` with weights).

### Known limitations of the design
- One network model.
- The episode labels depend on the chosen persistence cut-offs. Pre-register them, and report sensitivity at 3 and 6 epochs.
- Precision describes timing, not causation. A branch-and-compare counterfactual (re-running from the same state without the mutation) would be stronger, but needs state cloning in the engine. It is not proposed for this smallest experiment.

---

## Sources
- Ghosh & Boyd full text: <https://web.stanford.edu/~boyd/papers/pdf/growing_fast_graphs.pdf>; abstract page <https://stanford.edu/~boyd/papers/growing_fast_graphs.html>.
- Gençata thesis: <https://web.itu.edu.tr/gencata/pubs/AGthesis.pdf>; thesis page <https://web.itu.edu.tr/gencata/pubs/phd.html>.
- Metadata: Crossref and OpenAlex records for all three DOIs; indexed abstract of Sydney et al. at <https://datalearner.com/academic/journal-papers/0096-3003/volumes-and-issues/583/paper-detail/65149>.
