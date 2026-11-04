# Repository audit (Phase 0)

Audited: 2026-11-04, working copy `E:\SEM5\CN\CN LAB PROJECT\tcce_r - Copy`, branch `master`, HEAD `4fa6f2a`.
No scientific logic was modified. Everything below was read from files or measured by running them; items I could not verify are marked **(unverified)**.

## 0. Repository state that matters before anything else
1. **The working tree is not at a clean commit.** Six tracked files are modified and three paths are untracked:
   - modified: `tccer/config.py`, `network/events.py`, `network/generators.py`, `policies/__init__.py`, `policies/v06.py`, `sim/engine.py` (87 insertions);
   - untracked: `tccer/core/predict.py`, `tccer/policies/v08.py` (a "v0.8" RCPR controller plus ablation arms B2-B4, B6-B8, P1, H1), and the whole `paper/` directory.
   - These are pre-existing, unreviewed, **unrun** v0.8 work (no `results/` or `configs/` for v0.8, no `PROTOCOL_v0.8.md` even though `config.py` cites it). They are *not* part of the v0.7 baseline. I treat them as draft code to be reviewed in Phase 6/8, not as evidence.
2. **`paper/` (manuscript, figures, tables, references, build tools) is untracked**: no git history, not protected by the baseline commit. Hashing it is planned (not yet in the manifest).
3. `engine.py` now writes a wall-clock column `decide_ms` into every epoch row; this breaks two determinism tests (see REPRODUCIBILITY_REPORT.md).

## A. What is actually implemented (committed code, `tccer/`)
- **Network** (`network/`): random geometric graph (RGG) generator; potential-link set; Bernoulli transient link loss per round; Markov (p_fail/p_repair) background failures; spatially correlated bursts; scripted scenario files. Uncommitted: Erdos-Renyi / Barabasi-Albert generators, abrupt "shock" outage.
- **Consensus** (`consensus/`): Metropolis-Hastings average consensus, 60 rounds/epoch, fresh x(0) each epoch; E = 1 - min(1, ln e(T)/ln eps).
- **Controller core** (`core/`): CUSUM resilience debt D_k = max(0, D_{k-1}+s_k-kappa); trigger D > Theta with cooldown; adaptive Theta (multiplicative, bounded); first-order delta-lambda2 gain (Fiedler vector); lexicographic mutation ranking; safety gate (connectivity, lambda2 floor, degree, strict edge budget, edge cooldown); legacy before/after feedback and v0.7 counterfactual-replay feedback.
- **Engine** (`sim/engine.py`): common-random-number design; graph, failure trace and x(0) pre-generated per seed, identical across policies.
- **Controller is centralised** (global lambda2/Fiedler, exact-model counterfactual replay). Not distributed.
- Not modelled: load, traffic, trust/uncertainty, adversaries, link weights, partial observation.

## B. Experiments actually run (with saved outputs)
| Version | What | Seeds | Where |
|---|---|---|---|
| v0.1 | prototype, 6 policies | 0-19 | `archive/v0.1` |
| v0.2 | kappa/weight sweep (tuning) then held-out | 100-119, 1000-1029 | `archive/v0.2` |
| v0.3 | binding budget; **two invalid seed ranges (2000s, 3000s) archived and disclosed** | 4000-4029 | `archive/v0.3*` |
| v0.4 | bursty failures x setup delay {0,2,4,8} | held-out | `archive/v0.4` |
| v0.6 | pre-registered 8-arm trigger comparison, d in {2,8} x M in {3,6} | cal 100-119, **eval 6000-6059** | `archive/v0.6` |
| **v0.7 full** | 8 methods x 3 scenarios x M in {3,6} | cal 200-219, **eval 7000-7059** | `results/v0.7/eval` (commit `7a81352`) |
| **v0.7 focused** | A1/A3/A5 only, exploratory | cal 400-419, **eval 500-559** | `results/v0.7_focused/eval` (run recorded at `ec0fb75`) |

The two v0.7 evaluations are the **baseline evidence** for this revision. Nothing for the revised study (ablations, ER/BA graphs, hybrid, sensitivity, imperfect info) has been run.

## C. Exact number of policies
- 22 registered in `POLICIES` in the working tree: 6 legacy (static, random, periodic, reactive, tccer, tccer_fixed), 8 v0.6 arms (A1-A7 plus the A2r reset variant; A0 = static), and **8 uncommitted v0.8** (v08_b2, b3, b4, hybrid, pred_only, rcpr, rcpr_fixed, rcpr_legacy).
- Committed (HEAD): 14. v0.7 evaluates **8 methods**: A0 Static, A1 Reactive, A2 Moving average, A3 CUSUM-E, A4 CUSUM-ECV, A5 full TCCE-R, A6 Random timing, A7 Front-loaded.
- The professor's B1-B8 labels do **not** match the repo's A-labels. B1 (E-only) is approximately A1/A3 but has no dedicated arm; B2-B4 and B6-B8 exist only as uncommitted code.

## D. Exact scenarios (v0.7)
| Scenario | Graph | Failures |
|---|---|---|
| S1_rgg40_bursty | RGG n=40, init radius 0.22, range 0.32 | transient 0.05; background p_fail 0.005 / p_repair 0.10; bursts rate 0.10, radius 0.15, 2-6 epochs |
| S2_rgg40_background | as S1 | transient 0.05; p_fail 0.01 / p_repair 0.10; no bursts |
| S3_rgg80_bursty | RGG n=80, radii x sqrt(40/80) | as S1 |

Common: 80 epochs x 60 rounds, eps=0.01, setup delay d=2, strict edge budget (all mutations are rewires), cooldown 2, counterfactual feedback.

## E. Graph sizes
n = 40 and n = 80, RGG only. No ER / scale-free results exist.

## F. Mutation budgets
M in {3, 6} per run (v0.6 also used delay 8; v0.2-v0.4 used uncapped / matched budgets).

## G. Seed ranges
0-19; 100-119; 200-219; 300-319 (dev only); 400-419; 500-559; 1000-1029; 4000-4029; 6000-6059; 7000-7059. (2000s/3000s ranges invalidated.) Each held-out set was used once.

## H. Metrics (v0.7)
Primary: mean E over 80 epochs. Secondary: disconnected fraction, lambda2 (provisional R), anchored recovery time, realised/intended mutations, pending link-epochs, live-link releases, wasted releases, precision / false-alarm / detection, second-half E, A5 feedback success/failure/neutral and mean delta.
**Not present as defined metrics:** time-to-consensus (only per-epoch `conv_round` in the raw log), disconnection *duration*, worst-case error, a single reconfiguration-overhead number, "adaptation success rate" (the feedback success share is the closest).

## I. Statistics
Seed-paired two-sided Wilcoxon; Holm within pre-declared families (primary 12 tests; secondary 42 in full v0.7, 6 in focused); 10,000-resample bootstrap CI (seed 20261010) plus t-CI; rank-biserial r; margin |dE| = 0.02; "practically equivalent" only when Holm p >= 0.05 **and** the bootstrap CI lies inside +-0.02. Power is stated (min detectable about 0.017-0.023).

## J. Existing limitations (documented by the authors)
RGG-only, two sizes; earliness confound; A5 differs from A1 in several components at once; counts matched on average, not per seed; counterfactual feedback needs an exact model; R = lambda2 and M are provisional; load/traffic/trust/attacks absent; centralised.

## K. Existing failed tests
Full suite (working tree): **176 passed, 2 failed, 0 skipped**, 62 warnings (300 s). Failures: `test_engine.py::test_same_seed_same_result` and `test_v06.py::test_static_invariant_to_delay_and_budget`, both caused by the uncommitted `decide_ms` timing column. The previously reported `test_v06_dry_run_rows_reproduce[A6-v06_random]` **passes** (see REPRODUCIBILITY_REPORT.md). README says "85 tests"; the actual count is 178 (stale doc).

## L. Missing experiments requested by the professor
Systematic component ablation (B1-B8); direct matched-budget TCCE-R vs A7 analysis incl. disconnection duration / recovery / worst case; hybrid front-loaded + risk-aware; ER and scale-free graphs; n > 80; additional failure distributions (sustained outages, correlated bursts, abrupt change); imperfect-information robustness; parameter sensitivity (alpha, beta, gamma, delta, eta, Theta, kappa, M, d, safety threshold, failure intensity); formal objective J_k; trade-off plots; literature rewrite.

## M. Existing results that already answer some comments
- **Gap TCCE-R vs reactive:** v0.7 A5-A1 on E ranges -0.005 to +0.010 across evaluable cells: 4 "practically equivalent", 1 "reactive better, below minimum" (S2 M3, Holm p=0.033), no cell where A5 is better. No superiority. (`results/v0.7/eval/analysis/REPORT.md`)
- **A7:** A5-A7 = +0.024 to +0.076 in all 6 cells (A5-A1 has only 5 evaluable cells), A7 "meaningfully better" (Holm p <= 3e-3). A7 also beats A1 in every cell tested. Already in the data and unfavourable to TCCE-R; must be reported.
- **Component effects** (accumulation, C/V terms, adaptive Theta): A3-A1, A4-A3, A5-A4 in `secondary_tests.csv`; A5-A4 is about 0 in all cells.
- **Missing/excluded runs:** v0.7 ran 2,640 not 2,700 runs. Arm-cells that failed the +-15% calibration feasibility check (e.g. A1 and A2 in S3 M=3, hence no A5-A1 test there) were excluded by rule, recorded in `calibration_report.csv`.
- **Bias in legacy feedback:** placebo audit (legacy rule calls 67-73% of no-op cases "success") motivated counterfactual feedback, implemented and tested.
- **Larger size (n=80) and a second environment (no bursts):** partially present.
- **References:** 28 verified Crossref entries (`paper/references/references_verified.json`), **all dated 2017 or earlier (0 from 2022-2026)**; 34 candidate 2022-2026 entries in `refs_v2_recent.json` have DOIs but **no verification status**, so they are not yet usable.

## Status update (2026-11-04, after step-wise cleanup)
- Branch `revision-v0.8` created from `master` HEAD `4fa6f2a`; tag `baseline-v0.7` = `4fa6f2a` (its `tccer/` is byte-identical to the code that produced the v0.7 held-out run at `7a81352`; the later commits add only focused-run configs, `experiments/focused_v07.py` and its test). A pre-existing tag `v0.7` (`f874ad7`) is the pre-calibration code freeze and was left untouched.
- `results/` is **gitignored**: the baseline result files (v0.7 65 MB, focused 27 MB) are *not* under version control; their integrity record is the SHA-256 list in `revision/baseline/baseline_manifest.json`. They have not been copied or modified.
- Staged (not committed): `paper/`, `revision/`, `tccer/core/predict.py`, `tccer/policies/v08.py`, `tests/test_timing_isolation.py`. The 6 modified tracked files remain unstaged for review.
- Test suite now 180 passed / 0 failed (item K superseded). Default-equivalence: see REPRODUCIBILITY_REPORT Update 2.

## Status update 2 (Phase 1 verification)
- Test suite: 211 passed, 0 failed (31 new v0.8 smoke tests). Full 60-seed replay of v0.7 held-out and of the focused run: 0 FAIL; 99.986% / 99.97% of cells bit-identical, the rest float round-off <= 3.6e-15 (see REPRODUCIBILITY_REPORT, Update 3).
- Baseline results backed up read-only and checksum-verified outside the repo; v0.8 draft code reviewed (`V08_CODE_REVIEW.md`); README corrected.
- Item C/L corrections: the v0.8 arms are reviewed but still have no protocol, calibration or runner.

## Other observations
- Focused-run provenance: `run_info.json` records commit `ec0fb75`, but the frozen configs were committed later in `4fa6f2a`. The SHA manifests do verify against current files (checked), so contents are consistent; only commit ordering is awkward.
- Both frozen manifests verify with `sha256sum -c` (47 and 21 entries, 0 mismatches).
- `analysis_zip.zip` artifacts and `archive/v0.3_INVALID_*` are retained as-is.
