# R3 design freeze (COCRO-final)

Frozen on 2026-11-08 after Step 2 (`docs/PROTOCOL_R3.md` section 12.1). After this file is committed only bug fixes with tests are allowed; any other change is a protocol amendment written before the affected run.

**COCRO-final = `cocro_m`**: A7-like timing (spend whenever cooled down, from epoch 0, cap M) with COCRO's candidate selection:
candidates = top K_r = 2 removals x K_a = 5 additions (cocro_ops, failed-link valuation `failed_link_value`, SafetyGate unchanged); selection by the extrapolated expected gain
G = S_setup + b (tau - d) (spectral surrogate, H = 3, S_sel = 8 posterior scenarios from the CFPE failure model, forgetting 0.98, plug_in = False, cross-fit scenario streams);
`price = none` (no shadow price), `shortlist = 0` (no Fix 1), `reserve_factors = ()` (no Fix 2), c_op = 0.
Policy name `r3_cocro_m` (experiments/run_r3.py; parameters `CocroParams.fast()` with `price='none'`). Registered in `tccer/policies/cocro.py` as `cocro_m`.

Code commit: recorded in `results/r3/*/run_info.json` at run time (the run guard refuses a dirty tracked tree). Frozen configurations: `configs/r2a/frozen` (tier A, baselines) and `configs/r3/frozen` (tiers B and C), each with a SHA-256 manifest verified before every run.
Seeds: `docs/PROTOCOL_R3.md` section 3. Held-out blocks have never been used.

Components NOT in COCRO-final (retained as exploratory arms): rollout shadow price (`cocro`), Fix 1 full-horizon rerank (`cocro_mfg`, `cocro_fg`), Fix 2 reservation (`cocro_r`, `cocro_fgr`).
Not implemented at all: debt-ledger update inside COCRO, delayed credit assignment, persistence-aware removal value, per-link heterogeneous hazards, mobility, link-observation noise.
