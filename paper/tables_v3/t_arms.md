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
