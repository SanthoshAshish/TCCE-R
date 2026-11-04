# Baseline manifest (Phase 1)

The v0.7 evidence is the immutable reference for the revision. Machine-readable version with per-file SHA-256: `baseline_manifest.json` (regenerate with `python revision/baseline/make_manifest.py`; it is read-only with respect to the repo).

- **Git:** branch `master`, HEAD `4fa6f2a308f0bf032f12ce59a6266fe20f0b7e9c` (2026-10-11). Working tree **dirty** (v0.8 draft code + untracked `paper/`), see REPOSITORY_AUDIT section 0. Baseline results were generated at clean commits: v0.7 full at `7a81352`, focused at `ec0fb75` (from each `run_info.json`).
- **Environment (revision session):** Python 3.11.9, numpy 2.3.4, scipy 1.17.1, pandas 2.3.3, networkx 3.6.1, matplotlib 3.10.8, PyYAML 6.0.3, pytest 9.1.1, Windows 11. The original runs recorded identical python/numpy/scipy/pandas versions.
- **Baseline result sets (not to be edited):**
  - `results/v0.7/eval/`: 6 cell folders + 3 A0 folders, `run_info.json`, `COMPLETE`, `analysis/`. Seeds 7000-7059, 2,640 runs, 272 s.
  - `results/v0.7_focused/eval/`: seeds 500-559, 1,140 runs, 189 s.
  - Frozen configs: `configs/v0.7/frozen/` (47 manifest entries), `configs/v0.7_focused/frozen/` (21). Calibration seeds 200-219 / 400-419.
  - Older: `archive/` (v0.1-v0.6); `results/v0.6` is empty (the archive holds it).
- **Generation commands (from docs; flags per `docs/PROTOCOL_v0.7.md` sections 4-5 and `docs/FOCUSED_v0.7_PLAN.md`):**
  ```
  python -m experiments.calibrate_v07
  python -m experiments.run_v07 --mode eval      # seeds 7000-7059, once
  python -m experiments.analyze_v07
  python -m experiments.focused_v07 --stage all
  ```
  I have **not** re-run these. Revision outputs will go under `revision/` and new `results/v0.8*` folders, never into baseline folders.
- **Integrity checks done:** both frozen `MANIFEST.sha256` files verify; baseline file hashes are in the JSON (results, frozen configs, archive/v0.6, `tccer/`, `experiments/`, `docs/`). `paper/` (52 files) is hashed too.
- **Git (done 2026-11-04):** tag `baseline-v0.7` -> `4fa6f2a` (verified: `tccer/` identical to the `7a81352` code that produced the v0.7 held-out results; the focused run's `ec0fb75` also has identical `tccer/`). Branch `revision-v0.8` created from it with the uncommitted work carried over (nothing discarded). Nothing committed yet.
- **`results/` is gitignored**, so the result files are protected only by the SHA-256 list (`baseline_manifest.json`, which now also records tree hashes of the tag and hashes of `paper/`). **Backup made 2026-11-04** at `E:\SEM5\CN\CN LAB PROJECT	cce_r_baseline_backup_v0.7\` (238 files, 94.5 MB, read-only, `SHA256SUMS.txt` verified 238/238; same drive as the repo, so not protection against disk failure).
- Default-equivalence of the v0.8-draft code to these results: see `revision/audit/REPRODUCIBILITY_REPORT.md`, Update 2.
