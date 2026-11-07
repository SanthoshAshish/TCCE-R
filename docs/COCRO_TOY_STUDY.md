# COCRO v2 toy study: shadow price of a mutation unit (no simulator)

Code: `tccer/toy/shadow_price.py`, driver `experiments/toy_shadow_price.py` (`python -m experiments.toy_shadow_price`, about 80 s), tests `tests/test_cocro_toy.py`.
Raw outputs (git-ignored): `results/cocro/toy/{per_config.csv, decisions.csv, criteria.json}`. Pass criteria C1-C5 were declared in the module docstring BEFORE the first run.

## Result: all five pre-declared criteria hold
| Criterion | Value | Pass |
|---|---|---|
| C1 vectorised DP equals explicit expectimax tree search (tiny instances) | max abs difference 0.0e+00 | yes |
| C2 rollout policy not worse than its greedy base policy (2 SE) in every one of 24 configurations | min (diff / SE) = -0.42 | yes |
| C3 mean value(ROLLOUT)/value(EXACT) >= 0.95 | 0.992 | yes |
| C4 i.i.d. method over-defers under persistence (rho >= 0.9, delta = 1): deferral rate IID minus EXACT > 0.02 and value(IID) <= value(ROLLOUT); equal to EXACT at rho = 0 | 0.216; value difference -0.295; price difference at rho = 0: 3.6e-15 | yes |
| C5 rollout act/wait agrees with exact on non-marginal states >= 90% | 0.987 (7263 states) | yes |

Mean total reward (M = 3, delta = 1, 4,000 common episodes, T = 40; deferral = share of feasible, positive-reward slot visits at which the policy waits):

| rho | EXACT | ROLLOUT | IID | OLD (v1) | GREEDY | FRONT | deferral EXACT | deferral IID |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 6.757 | 6.727 | 6.757 | 6.233 | 3.588 | 1.820 | 0.76 | 0.76 |
| 0.50 | 5.064 | 4.997 | 4.963 | 4.366 | 3.419 | 1.789 | 0.75 | 0.80 |
| 0.90 | 2.991 | 2.988 | 2.694 | 2.156 | 2.746 | 1.757 | 0.73 | 0.88 |
| 0.97 | 2.237 | 2.234 | 1.848 | 1.420 | 2.237 | 1.769 | 0.46 | 0.92 |

## What this does and does not show
* The i.i.d. dynamic programme over-defers as persistence rises (deferral 0.92 vs 0.46 at rho = 0.97, M = 3) and loses value; the v1 method (truncated one-shot gain) is worse still. At rho = 0 the i.i.d. method is exact, as it must be.
* Rollout is within about 1% of the exact optimum on average. At rho = 0 it is a little below exact (for example 3.30 vs 3.37) because the greedy base policy undervalues waiting; it still never fell below the greedy base policy beyond Monte-Carlo error (C2).
* At high persistence the greedy policy is almost as good as optimal (rho = 0.97: 2.237 vs 2.237 at M = 3): when damage persists, acting at the first positive opportunity is nearly optimal. This is the toy-model counterpart of the design's expectation that COCRO reduces to early action under stationary damage. State-blind front-loading (FRONT) is clearly worse in this toy because it spends units when nothing is wrong.
* **Limits:** the toy chain is exogenous and its transition matrix is known to every method (the simulator's must be estimated); rewards are exactly persistent flows with a fixed setup loss; there is no graph structure, no model misspecification and no sampling noise in the opportunity values. Passing here shows the rollout *method* is sound under correct model assumptions. It is not evidence about COCRO's performance in the simulator, and it does not show any advantage over A7.
