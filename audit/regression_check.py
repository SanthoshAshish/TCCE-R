"""Re-run every archived experiment with the CURRENT code and compare to archive/ (read-only).

  python -m audit.regression_check --out <scratch folder>

Outputs go to --out only; archive/ and results/ are never written. Exit code 1 if anything differs.
New log columns added after a version was archived are ignored (only archived columns are compared).
"""
import argparse
import os
import subprocess
import sys

import pandas as pd

CASES = [  # (label, config, seed_start, n_seeds, policies or None, archived epochs.csv)
    ("v0.1", "configs/default.yaml", 0, 20, None, "archive/v0.1/results_default/epochs.csv"),
    ("v0.2", "configs/v0.2_selected.yaml", 1000, 30, None, "archive/v0.2/eval_v0.2_selected/epochs.csv"),
    ("v0.3", "configs/v0.3_selected.yaml", 4000, 30, "static periodic reactive tccer tccer_fixed",
     "archive/v0.3/eval_v0.3_matched/epochs.csv"),
] + [(f"v0.4_d{d}", f"configs/v0.4/selected_d{d}.yaml", 5000, 30, "static periodic reactive tccer tccer_fixed",
      f"archive/v0.4/eval_d{d}/epochs.csv") for d in (0, 2, 4, 8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ok = True
    for label, cfg, s0, n, pols, arch in CASES:
        out = os.path.join(a.out, label)
        cmd = [sys.executable, "-m", "experiments.run", "--config", cfg, "--seed-start", str(s0), "--seeds", str(n),
               "--no-rounds", "--out", out] + (["--policies", *pols.split()] if pols else [])
        subprocess.run(cmd, check=True, capture_output=True)
        old, new = pd.read_csv(arch), pd.read_csv(os.path.join(out, "epochs.csv"))
        try:
            pd.testing.assert_frame_equal(old, new[old.columns])
            print(f"{label}: IDENTICAL ({len(old)} rows x {old.shape[1]} archived columns)", flush=True)
        except AssertionError as e:
            ok = False
            print(f"{label}: DIFFERS: {str(e)[:300]}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
