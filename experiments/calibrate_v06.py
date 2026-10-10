"""v0.6 calibration (docs/PROTOCOL_v0.6.md section 3). Uses ONLY tuning seeds 100-119 and ONLY mutation counts.

  python -m experiments.calibrate_v06 [--workers 11]

Writes (frozen, checksummed):
  configs/v0.6/frozen/constants.yaml            tau, kappa_E, kappa_s
  configs/v0.6/frozen/A0_static.yaml
  configs/v0.6/frozen/<arm>_d<d>_M<M>.yaml      A1-A7 per cell (A1-A5 only if calibratable)
  configs/v0.6/frozen/calibration_report.csv    chosen thresholds, calibration means, feasibility flags
  configs/v0.6/frozen/MANIFEST.sha256
Raw calibration data: results/v0.6/calibration/{static_tuning_epochs.csv, calibration_counts.csv, run_info.json}
"""
import argparse
import os
import time

import numpy as np
import pandas as pd
import yaml

from experiments.v06_common import (ARM_KAPPA, ARM_POLICY, BUDGETS, CALIBRATED_ARMS, CELLS, DELAYS, ECV,
                                    FEASIBILITY, FROZEN_DIR, GRID, MANIFEST, TAU_QUANTILE, TUNING_SEEDS, assert_seeds,
                                    base_config, frozen_path, git_state, run_tasks, versions, write_json,
                                    write_manifest)
from tccer.config import replace, save_config

OUT = "results/v0.6/calibration"


def static_constants(static_df):
    """tau: 75th pct of static E over all epochs; kappas: medians over connected epochs (protocol 3.1)."""
    conn = static_df[static_df.components == 1]
    s = ECV[0] * conn.E_hat + ECV[1] * conn.C + ECV[2] * conn.V
    return {"tau": float(static_df.E_hat.quantile(TAU_QUANTILE)), "kappa_E": float(conn.E_hat.median()),
            "kappa_s": float(s.median())}


def choose(grid_means, M):
    """Closest mean count to M; ties -> larger threshold. grid_means: list of (threshold, mean). Returns (thr, mean, ok)."""
    best = min(grid_means, key=lambda tm: (abs(tm[1] - M), -tm[0]))
    return best[0], best[1], abs(best[1] - M) <= FEASIBILITY * M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    assert_seeds(TUNING_SEEDS, range(100, 120), "calibration")
    if os.path.exists(MANIFEST):
        raise SystemExit(f"{MANIFEST} exists: calibration is already frozen. Refusing to recalibrate.")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FROZEN_DIR, exist_ok=True)
    t0 = time.time()
    info = {"stage": "calibration", "seeds": list(TUNING_SEEDS), "git": git_state(), "versions": versions(),
            "workers": a.workers}

    # 3.1 static constants (static is independent of d and M; d=2 config used)
    static_rows = run_tasks([(base_config(2), s, "static", "rows") for s in TUNING_SEEDS], a.workers)
    static_df = pd.DataFrame([r for rows in static_rows for r in rows])
    static_df.to_csv(os.path.join(OUT, "static_tuning_epochs.csv"), index=False)
    const = static_constants(static_df)
    print("constants:", {k: round(v, 4) for k, v in const.items()}, flush=True)

    # 3.2 uncapped grid runs: counts only
    tasks, keys = [], []
    for arm in CALIBRATED_ARMS:
        for d in DELAYS:
            for gi, thr in enumerate(GRID[arm]):
                cfg = replace(base_config(d), v06_threshold=float(thr), mutation_cap=None,
                              v06_kappa=const[ARM_KAPPA[arm]] if arm in ARM_KAPPA else None)
                for s in TUNING_SEEDS:
                    tasks.append((cfg, s, ARM_POLICY[arm], "count"))
                    keys.append((arm, d, gi, float(thr), s))
    print(f"running {len(tasks)} uncapped calibration runs on {a.workers} workers ...", flush=True)
    counts = run_tasks(tasks, a.workers)
    cdf = pd.DataFrame(keys, columns=["arm", "delay", "grid_index", "threshold", "seed"]).assign(count=counts)
    cdf.to_csv(os.path.join(OUT, "calibration_counts.csv"), index=False)
    means = cdf.groupby(["arm", "delay", "threshold"])["count"].mean().reset_index()

    # selection + frozen configs
    report, frozen = [], []
    for arm in CALIBRATED_ARMS:
        for d in DELAYS:
            gm = [(r.threshold, r["count"]) for _, r in means[(means.arm == arm) & (means.delay == d)].iterrows()]
            for M in BUDGETS:
                thr, mean, ok = choose(gm, M)
                report.append({"arm": arm, "delay": d, "M": M, "threshold": thr, "calibration_mean_count": mean,
                               "abs_error": abs(mean - M), "calibratable": ok,
                               "kappa": const[ARM_KAPPA[arm]] if arm in ARM_KAPPA else None})
                if ok:
                    cfg = replace(base_config(d), v06_threshold=float(thr), mutation_cap=M,
                                  v06_kappa=const[ARM_KAPPA[arm]] if arm in ARM_KAPPA else None)
                    p = frozen_path(arm, d, M)
                    save_config(cfg, p)
                    frozen.append(p)
    for d, M in CELLS:
        for arm in ("A6", "A7"):
            p = frozen_path(arm, d, M)
            save_config(replace(base_config(d), mutation_cap=M), p)
            frozen.append(p)
            report.append({"arm": arm, "delay": d, "M": M, "threshold": None, "calibration_mean_count": None,
                           "abs_error": None, "calibratable": True, "kappa": None})
    p = frozen_path("A0")
    save_config(base_config(2), p)
    frozen.append(p)
    rep = os.path.join(FROZEN_DIR, "calibration_report.csv")
    pd.DataFrame(report).to_csv(rep, index=False)
    cpath = os.path.join(FROZEN_DIR, "constants.yaml")
    with open(cpath, "w", encoding="utf-8") as f:
        yaml.safe_dump({**{k: round(v, 10) for k, v in const.items()}, "tau_quantile": TAU_QUANTILE,
                        "tuning_seeds": [TUNING_SEEDS[0], TUNING_SEEDS[-1]], "grid_points": 40,
                        "feasibility": FEASIBILITY, "calibration_git_commit": info["git"]["commit"]}, f, sort_keys=False)
    write_manifest(frozen + [rep, cpath])
    info.update({"constants": const, "n_runs": len(tasks) + len(TUNING_SEEDS), "seconds": round(time.time() - t0, 1),
                 "frozen_files": sorted(frozen + [rep, cpath])})
    write_json(os.path.join(OUT, "run_info.json"), info)
    print(pd.DataFrame(report).to_string(index=False))
    print(f"\nfrozen {len(frozen)} configs + report + constants; manifest {MANIFEST}; {info['seconds']} s")


if __name__ == "__main__":
    main()
