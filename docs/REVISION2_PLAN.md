# Revision 2 plan (COCRO) - status log

Components are PROPOSALS to be validated; no novelty claim is made until the literature check is done.

| Step | Component | Status |
|---|---|---|
| 1 | TRDE: causality-aware debt ledger (`tccer/core/causal_debt.py`), arm `r2_causal` (C1 = B8 with ledger debt) | implemented, unit-tested; cd_tau = setup delay + 2 and exact-state retry rule ACCEPTED 2026-11-07; calibration protocol (docs/R2_DESIGN_RULES.md s.3) FINAL; NOT yet calibrated, NOT evaluated |
| 2 | CFPE/UABR: calibrated, uncertainty-aware failure prediction | not started |
| 3 | CMVE: delayed mutation-credit assignment | not started |
| 4 | MOCO: rewire / defer / reserve decision | not started |
| 5 | LHTA: long-horizon marginal-gain selector | not started |
| 6 | Theory, extra graph families and failure laws, scalability, sensitivity, manuscript | not started |

Seed policy (Revision 2 uses NEW seeds; v0.8 held-out seeds 9000-9059 were consumed by the v0.8 E2 evaluation and must not be used to tune or select R2 designs):
development 8200-8219, calibration 8300-8319, held-out 9100-9159. Baselines A1/A7/A7M/B8 are re-run on the same R2 seeds for paired comparison.

Preserved unchanged: v0.7/v0.8 policies, frozen configs, E1/E2 results.
