"""Post-calibration diagnostics for E2 (read-only w.r.t. the frozen configs). Calibration seeds 8000-8019 only.

  python revision/audit/check_calibration_v08.py [--run-derived]

1. verifies the frozen manifest and that every config is what calibrate_v08 would write (derived arms == B8's config);
2. lists thresholds / kappa / PMF / H1 F per cell and which arm-cells exist (and the exact E2 job count);
3. with --run-derived: runs B5/B6/B7/H1 (which inherit B8's threshold and were NOT calibrated) on the calibration seeds and
   reports their mean realised mutation counts, as a diagnostic only. Nothing is changed or re-tuned from these numbers.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())


def main():
    from experiments.run_v08 import build_jobs
    from experiments.v08_common import (ARM_POLICY, CELLS, EVAL_ARMS, FROZEN_DIR, SCENARIOS, TUNING_SEEDS, assert_seeds,
                                        cell_name, frozen_path, run_tasks, verify_manifest)
    from tccer.config import load_config
    ap = argparse.ArgumentParser(); ap.add_argument("--run-derived", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1)); a = ap.parse_args()
    assert_seeds(TUNING_SEEDS, range(8000, 8020), "calibration diagnostics")
    verify_manifest(os.path.join(FROZEN_DIR, "MANIFEST.sha256"))
    print("manifest verifies")
    rows = []
    for s, M in CELLS:
        b8 = load_config(frozen_path(FROZEN_DIR, "B8", s, M))
        for arm in EVAL_ARMS:
            p = frozen_path(FROZEN_DIR, arm, s, M)
            if not os.path.exists(p):
                rows.append({"cell": cell_name(s, M), "arm": arm, "exists": False}); continue
            c = load_config(p)
            rows.append({"cell": cell_name(s, M), "arm": arm, "exists": True, "policy": ARM_POLICY[arm],
                         "threshold": c.v06_threshold, "kappa": c.v06_kappa, "cap": c.mutation_cap, "v08_front": c.v08_front,
                         "has_pmf": c.v06_count_pmf is not None,
                         "same_as_B8": (c == b8) if arm in ("B5", "B6", "B7") else None})
    df = pd.DataFrame(rows)
    ok = df[df.arm.isin(["B5", "B6", "B7"]) & df.exists].same_as_B8.all()
    print("B5/B6/B7 configs identical to B8 in every cell:", bool(ok))
    print(df.to_string(index=False))
    print("E2 evaluation jobs for 60 seeds:", len(build_jobs(FROZEN_DIR, tuple(range(9000, 9060)))), "(seeds not run)")
    if a.run_derived:
        tasks, keys = [], []
        for s, M in CELLS:
            for arm in ("B5", "B6", "B7", "H1"):
                p = frozen_path(FROZEN_DIR, arm, s, M)
                if os.path.exists(p):
                    for seed in TUNING_SEEDS:
                        tasks.append((load_config(p), seed, ARM_POLICY[arm], "count")); keys.append((cell_name(s, M), arm, seed))
        counts = run_tasks(tasks, a.workers)
        d = pd.DataFrame(keys, columns=["cell", "arm", "seed"]).assign(count=counts)
        piv = d.groupby(["cell", "arm"])["count"].agg(["mean", "min", "max"]).round(2)
        print(piv.to_string())
        piv.to_csv("revision/audit/calibration_v08_derived_arm_counts.csv")


if __name__ == "__main__":
    main()
