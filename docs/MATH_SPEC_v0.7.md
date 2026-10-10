# TCCE-R mathematical specification (v0.7)

**Source of truth:** the code. Every row names the function that implements it.

**Labels:**
- **(A)** specified by the professor's architecture diagram (names and roles only; the diagram contains **no formulas**);
- **(B)** an approved design decision;
- **(C)** our implementation interpretation;
- **(D)** unresolved, needing the professor's clarification.

## 1. Update order within one epoch k (`tccer/sim/engine.py: simulate`)

1. **Environment.** background_down ← Markov update; down_k = background ∪ bursts_k ∪ scripted_k. The flips of configured links feed V. The observed state is recorded for counterfactual feedback (v0.7).
2. **Consensus.** 60 rounds of x ← W(t)x over live links minus per-round transient outages, from a fresh x(0). Outputs: e(t), final states x(T), local disagreement.
3. **Metrics.** E, C, V, λ₂ (= R), components.
4. **Policy (TCCE-R, `policies/tccer.py: decide`):**
   1. feedback on earlier mutations whose windows have closed → Θ updates;
   2. D update;
   3. trigger test;
   4. if it fires: candidates → M ranking → safety gate → first accepted candidate.
   5. On success: D ← 0 and the mutation is registered for feedback.
5. **Apply.** The removed link is gone from epoch k+1. The added link is configured now and usable from epoch k+1+d.

## 2. Variables

| Symbol | Exact definition | Code | Label |
|---|---|---|---|
| **e(t)** | ‖x(t) − x̄1‖ / ‖x(0) − x̄1‖, x̄ = mean x(0); e ≡ 0 if x(0) is constant | `consensus/algorithm.py: run_epoch_state` | (C) |
| **E** | E_k = 1 − min(1, max(0, ln e_k(T) / ln ε)), T = `rounds_per_epoch`, 0 < ε < 1 (validated) | `consensus/monitor.py: summarize` | name (A); fresh x(0) per epoch (B); log-progress normalisation (C) |
| local disagreement | δᵢ = Σ_{j∈N(i)} (xᵢ(T) − xⱼ(T))²; total = ½Σᵢδᵢ = x(T)ᵀ L x(T). **Logged only; used by no decision.** | `consensus/algorithm.py: local_disagreement` | name (A); formula (C, standard Laplacian disagreement) |
| **C** | 1 if the live graph is disconnected; otherwise #bridges / #live links (1 if there are none) | `metrics/resilience.py: vulnerability` | name (A); formula (C) |
| **V** | min(1, Σ_{j=k−w+1..k} f_j / #configured links), f_j = number of configured links whose up/down state flipped at the start of epoch j; own mutations excluded; w = `vol_window` ≥ 1 | `core/debt.py: volatility`, engine | name (A); formula (C) |
| **D** | s_k = w_E E_k + w_C C_k + w_V V_k (weights ≥ 0); D_k = max(0, D_{k−1} + s_k − κ), κ ≥ 0 (Page's one-sided CUSUM). Reset D ← 0 only after a **successful** mutation. Unbounded above while the arm cannot act. | `core/debt.py: CusumDebt`; reset in `policies/tccer.py` | name (A); CUSUM (B); weights, κ, reset (C) |
| **Θ, trigger** | fire ⇔ D_k > Θ_k and k − (last successful mutation) ≥ `trigger_cooldown` | `core/trigger.py` | D > Θ (A); cooldown (C) |
| **Θ update** | success: Θ ← max(θ_min, Θ(1−β)); failure: Θ ← min(θ_max, Θ(1+α)); neutral (counterfactual rule only): unchanged. Validated: 0 < θ_min ≤ Θ₀ ≤ θ_max, α ≥ 0, 0 ≤ β < 1 | `core/threshold.py` | "update Θ from success/failure feedback" (A); form, bounds, direction (C) |
| **success** | see §4 | `core/feedback.py` (legacy), `core/counterfactual.py` (v0.7) | (C) |
| **R** | **R ≡ λ₂ of the unweighted Laplacian of the live graph** (0 when disconnected) | `metrics/resilience.py: lambda2` | **(D): provisional operational definition.** The diagram mentions R_min and "improved resilience" but never defines R mathematically. |
| **R_min** | the gate requires λ₂(after) ≥ min(R_min, λ₂(before)) − 10⁻¹² whenever the result is connected; λ₂(before) := 0 if disconnected before | `core/safety.py: SafetyGate.check` | R_min named (A); rule (C) |
| **M** | see §3 | `core/coupling.py` | see §3 |

## 3. M: decision and justification

**Diagram (A):** "Consensus improvement per resilience cost (M)" and "rank candidate mutations". This is a benefit-to-cost ratio, but no formula is given for either part.

**Implemented and retained (B, design decision D7):** a lexicographic ranking. For each candidate:

| Quantity | Definition | Notes |
|---|---|---|
| Δcomponents | −1 if the added link joins two live components, else 0 | exact |
| gain | (fᵢ − fⱼ)² for an addition (minus the same quantity for the removed link in a rewire); f = unit Fiedler vector of the live graph; **0 when disconnected** | first-order Δλ₂ estimate, Ghosh & Boyd (2006) eq. 7, p. 6607 |
| Δbridges | change in the number of bridges after the mutation | exact; computed for the first `shortlist` candidates |
| length | Euclidean link length | — |

**Ranking procedure:**
1. Sort by (Δcomponents, −gain, length).
2. Shortlist the first 10.
3. "Tied" = the shortlisted candidates with the best Δcomponents and gain ≥ best − `gain_tolerance`·|best|.
4. Re-sort the tied candidates by (Δbridges, length).
5. Then the rest of the shortlist, then the remaining candidates.
6. Any remaining ties are broken by candidate index (stable sort).
7. The gate checks candidates in this order, up to 30 attempts.

**Why the ranking is retained rather than replaced by a ratio:**
1. "Resilience cost" is undefined. Any formula (λ₂ loss, link length, outage time, Δbridges, or a weighted sum) would be an invented cost, which the brief forbids.
2. A ratio is ill-posed in the common cases. Reconnecting moves have zero first-order gain, because λ₂ = 0 when disconnected; they made up 66% of chosen mutations in v0.6. Additions have zero or negative "cost" when λ₂ increases, making the denominator ≤ 0.
3. The lexicographic order already encodes a defensible priority without a cost scale: restore connectivity first, then maximise the λ₂ estimate, then minimise new bridges, then link length.

**What the gain is, and is not:**
- It is a **first-order estimate of the change in Laplacian λ₂**, not measured consensus improvement.
- Consensus actually runs on Metropolis weights, and E is measured separately.
- Verified properties:
  - Ghosh & Boyd's bounds (eq. 8 lower, eq. 10 upper, p. 6608) hold on all 100+ tested candidate additions (`tests/test_math_v07.py`);
  - across 40 development graphs (n = 40, seeds 300–339), the estimate's top pick reaches a median **99.3%** of the best exact λ₂ gain (minimum 42.5%; exactly the best in 47% of graphs);
  - the median Spearman correlation between estimate and exact gain is 0.99.

**Unresolved (D):** the professor's intended cost term and whether a scalar M is required.

## 4. Feedback rules

**Legacy before/after rule** (`feedback_rule: before_after`, the default; used by v0.1–v0.6, kept unchanged):
- Success ⇔ mean E over m+1+o … m+o+H < mean E over m−H+1 … m, where o = d if `feedback_after_setup` else 0. A tie counts as failure.
- **Known bias:** the before window contains the triggering high-stress epoch. On archived v0.6 held-out data the rule declared success in **67–73% of Static placebo cases**, where nothing was mutated (audit at `95a1512`).

**Counterfactual rule** (`feedback_rule: counterfactual`, v0.7, `core/counterfactual.py`):
- **Window:** W = {m+1, …, m+d+H}, which includes the setup outage.
- **Evaluation:** at the end of epoch m+d+H, replay W from the pre-mutation snapshot **with** this mutation only and **without** any mutation, both under the identical *observed* exogenous record (link states, per-round outages, x(0)).
- **Δ** = mean E_with − mean E_without.
  - **Success** if Δ < 0; **failure** if Δ > 0; **neutral, no Θ update**, if Δ = 0 (the live graphs coincide throughout W).
- **Isolation:** each mutation is replayed alone, so overlapping windows cannot share attribution.
- **Invalid window:** a window that extends past the last epoch is never evaluated, and this is logged.
- **Assumptions (C):**
  - the controller holds an exact model of the consensus dynamics;
  - it logs observed link states and inputs;
  - it uses no future information (enforced: a replay requesting an unobserved epoch raises an error).
- **Tests** (`tests/test_feedback_v07.py`):
  - the replay reproduces the factual run and the Static run exactly;
  - beneficial → success, harmful → failure, ineffective → neutral;
  - the null-mutation placebo is never a success (0 of n), while the legacy rule calls most of the same placebo cases successes;
  - overlap isolation; the no-future-information guard.

## 5. Safety gate (`core/safety.py`): accept only if every check passes, in this order
1. No touched link is in edge cooldown (`edge_cooldown` epochs).
2. The added link is not currently failed.
3. Pure additions: the edge count after is within the budget (configured or live links per `budget_on`).
4. Degree: with `degree_fix`, the endpoints of the new link have degree ≤ d_max (configured or live per `degree_basis`). Without it (legacy), every node does.
5. The number of components does not increase, in the final and (with setup delay and a removal) in the interim state.
6. If connected: λ₂ ≥ min(R_min, λ₂ before), in the final and the interim state.

Labels: connectivity, stability and R_min are named in the diagram (A); the strict budget is (B); everything else is (C). The gate judges the *current* failure state, not future failures (C).

## 6. Deferred inputs named in the diagram (no model given)
- **Node load** and **traffic conditions:** not modelled.
- **Trust/uncertainty:** not modelled.
- **Adversarial attacks:** only hand-scripted removals (scenario files); no adversary model.
- **Link weights:** unweighted topology; consensus weights are derived (Metropolis).

These require the professor's specification and are not invented here.
