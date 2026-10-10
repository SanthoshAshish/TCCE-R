# TCCE-R architecture compliance (code vs the professor's specification)

**Specification:** the professor's TCCE-R architecture diagram, shared at the start of the project. It names nine stages, the variables E, C, V, D, Θ and M, an R_min constraint, and a threshold-update feedback loop. **It gives no formulas.** Every equation below is therefore our own design (or a cited standard method) and is labelled as such.

**Basis:** current code. **Verified by:** `tests/test_architecture.py` (full nine-stage chain on `configs/v0.5/custom_4node.yaml`) and the rest of the 135-test suite.

## 1. Compliance table

| # | Stage (diagram) | Diagram item | Status | Implementation | Notes |
|---|---|---|---|---|---|
| 1 | Dynamic Network State | Topology (links, weights) | **simplified** | `network/state.py`: configured / failed / in-setup / live links | Unweighted links; the consensus weights (Metropolis) are derived from the topology |
| | | Node states | **implemented** | x(t) per node, fresh each epoch or from a scenario file | |
| | | Node **load** | **missing** | — | Not defined in the diagram; deferred |
| | | **Traffic** conditions | **missing** | — | Not defined in the diagram; deferred |
| | | Failures / attacks | failures **implemented**; attacks **partial** | transient, background on/off, spatial bursts, scripted events (`network/events.py`, `scenario.py`) | No adversarial attack model; attacks can only be scripted by hand |
| 2 | Distributed Consensus Monitor | Local disagreement | **implemented** (v0.6.1) | `consensus/algorithm.py: local_disagreement`; logged as `local_disagreement_total`, `local_disagreement_max` | Standard Laplacian disagreement; monitoring only, does not feed D |
| | | Convergence rate | **implemented** | `rate` = e(T)^(1/T), `conv_round` | |
| | | Trust / uncertainty | **missing** | — | Not defined in the diagram; deferred |
| | | "Distributed" | **simplified** | consensus is distributed (local Metropolis updates); the *monitor* computes global quantities centrally | |
| 3 | Resilience Debt Estimator | E, C, V, D | **implemented** (our equations, §2) | `consensus/monitor.py`, `metrics/resilience.py`, `core/debt.py` | C is nearly binary in practice; V is small |
| 4 | Adaptive Mutation Trigger | D > Θ? | **implemented** | `core/trigger.py` | Adds a cooldown (our choice) |
| 5 | Consensus–Resilience Coupling Evaluator | "Consensus improvement per resilience cost (M)" | **deviation (approved design D7)** | `core/coupling.py`: lexicographic vector (Δcomponents, Δλ₂ estimate, Δbridges, length); logged as `M_*` | M is a **ranking**, not a scalar ratio. A ratio cannot be formed without a definition of "resilience cost", which the diagram does not give. |
| | | Rank candidate mutations | **implemented** | `rank_lexicographic` | |
| 6 | Constraint / Safety Gate | Connectivity constraint | **implemented** | `core/safety.py` | Components may not increase, in the final and in the interim (setup) state |
| | | Stability constraint | **implemented (interpretation)** | edge cooldown, trigger cooldown, interim-state check | The diagram does not define stability |
| | | Resilience minimum R_min | **implemented, with R ≡ λ₂ (unverified)** | λ₂ ≥ min(R_min, λ₂ before) | **R is never defined in the diagram.** The code uses algebraic connectivity λ₂ as R. No separate R exists. |
| 7 | Topology Mutation Selector | Choose best mutation; apply | **implemented** | `core/selector.py`, `core/mutations.py` | Add, or rewire under a full budget |
| 8 | Reconfigured Network | Updated topology; new consensus state | **implemented** | `NetworkState.apply`; break-before-make setup delay | |
| | | "Improved resilience" | **not guaranteed** | outcome, measured (λ₂, C, disconnection) | v0.4–v0.6 show it is not always improved |
| 9 | Adaptive Debt Threshold Update / feedback loop | Success/failure feedback; update Θ | **implemented** | `core/feedback.py`, `core/threshold.py`, `policies/tccer.py` | Success criterion is ours (§2) |
| | | Feedback of new state to monitor and estimator | **implemented** | next epoch's measurements | |

## 2. Equations actually implemented (our design unless cited)

| Symbol | Definition | Code |
|---|---|---|
| e_k(t) | ‖x(t) − x̄1‖ / ‖x(0) − x̄1‖ (0 if x(0) is constant) | `consensus/algorithm.py` |
| **E** | E_k = 1 − min(1, max(0, ln e_k(T) / ln ε)); T = `rounds_per_epoch`, ε = `eps` | `consensus/monitor.py` |
| local disagreement | δᵢ = Σ_{j∈N(i)} (xᵢ(T) − xⱼ(T))² over live links; total = ½Σδᵢ = x(T)ᵀ L x(T) | `consensus/algorithm.py` |
| **C** | 1 if the live graph is disconnected, otherwise #bridges / #live links | `metrics/resilience.py` |
| **V** | min(1, Σ over the last `vol_window` epochs of environmental link-state flips among configured links ÷ #configured links); own mutations excluded | `core/debt.py` |
| **D** | s_k = w_E E_k + w_C C_k + w_V V_k; D_k = max(0, D_{k−1} + s_k − κ). Page's CUSUM recursion (1954). D ← 0 after a successful mutation; unchanged after a failed attempt. | `core/debt.py`, `policies/tccer.py` |
| **Θ** | Trigger: D_k > Θ_k and k − (last mutation) ≥ `trigger_cooldown`. Success: Θ ← max(θ_min, Θ(1−β)). Failure: Θ ← min(θ_max, Θ(1+α)). | `core/trigger.py`, `core/threshold.py` |
| success | mean E over epochs m+1+o..m+o+H < mean E over m−H+1..m, where o = d if `feedback_after_setup` else 0 | `core/feedback.py` |
| **M** | Candidates sorted by (Δcomponents, −Δλ₂ estimate, length); among the shortlist, candidates within `gain_tolerance` of the best estimate are re-sorted by (Δbridges, length). Δλ₂ estimate for adding (i,j) = (fᵢ − fⱼ)², f = unit Fiedler vector (Ghosh & Boyd 2006, eq. 7). Rewire = add estimate − remove estimate. | `core/coupling.py` |
| **R** | R ≡ λ₂ of the live-graph Laplacian; R_min = `lambda2_min` | `metrics/resilience.py`, `core/safety.py` |

## 3. Ambiguities documented, not guessed
1. **M as a scalar ratio.** "Consensus improvement per resilience cost" needs a definition of resilience cost, which the diagram does not give. The lexicographic M (design decision D7) stays.
2. **R vs λ₂.** The diagram uses R_min and "improved resilience" without defining R. The code uses λ₂, and that is stated wherever R appears.
3. **Load, traffic, trust/uncertainty.** These are named in the diagram with no model. They are deferred rather than invented.
4. **Stability constraint.** Interpreted as anti-flapping: cooldowns plus the interim check.
5. **Mutation success.** Interpreted as lower mean E after the change than before.

## 4. Changes in v0.6.1 (this compliance pass)
- **Local disagreement monitor.** Logged columns `local_disagreement_total` and `local_disagreement_max`. The existing logic and outputs are unchanged.
- **Duplicate-key warning in the config loader.** YAML silently keeps the last value. `configs/v0.5/custom_4node.yaml` repeats `epochs`, `rounds_per_epoch` and `burst_rate`; it still loads as before and now warns.
- **Integration tests** for the whole chain, including the no-candidate path and the cooldown interaction, plus reproduction checks against the archived v0.6 tuning-seed dry run.
