| Scenario | Graph | Radii | Background failures | Bursts / budget |
|---|---|---|---|---|
| S1 | RGG, n = 40 | initial radius 0.22, range 0.32 | p_fail 0.005, p_repair 0.10 | bursts: rate 0.10, radius 0.15, 2–6 epochs |
| S2 | RGG, n = 40 | as S1 | p_fail 0.01, p_repair 0.10 | none |
| S3 | RGG, n = 80 | radii × √(40/80): 0.1556, 0.2263 | as S1 | as S1 |
| all | 80 epochs × 60 rounds | ε = 0.01; p_transient 0.05 | setup delay d = 2; cooldown 2 | strict edge budget; budgets M ∈ {3, 6} |

| Parameter | Value (implemented defaults; not tuned) |
|---|---|
| stress weights (E, C, V) | 0.5, 0.3, 0.2 (A3: 1, 0, 0) |
| debt reference κ | median stress over connected Static epochs, calibration seeds |
| Θ adaptation | ×0.9 on success, ×1.25 on failure, bounds [Θ₀/4, 4Θ₀] |
| feedback window | d + 3 = 5 epochs |
| safety gate | cooldown 5, degree ≤ 10, λ₂ floor R_min = 0.05, components non-increasing |
| predictor | H = 5, hazard window 10 (priors 0.02, 0.10, weight 20), shortlist ≤ 10 of the first 30 |
| objective | (α, β, γ, δ) = (1, 0.5, 0.05, 1); costs 0.25 / +0.75; risk tolerance 0.20 |
