"""v0.7 calibration (docs/PROTOCOL_v0.7.md section 4). Tuning seeds 200-219 only; mutation counts only.

  python -m experiments.calibrate_v07            # real calibration -> configs/v0.7/frozen (refuses if frozen)
  python -m experiments.calibrate_v07 --smoke    # dev seeds 300-301, 6-point grid -> results/v0.7/smoke/

Steps per scenario:
  1. A0 static on calibration seeds -> tau (75th pct of E), kappa_E, kappa_s (medians over connected epochs)
  2. A1-A5 uncapped over the threshold grid -> mean count -> threshold closest to M (ties: larger), +-15% feasibility
  3. capped A1-A5 with the chosen thresholds -> realised counts -> per-cell pmf for A6/A7 (v0.6 rev. 4 procedure)
  4. frozen configs + constants + calibration report + pmf table + SHA-256 manifest
"""
import argparse
import os
import time

import pandas as pd
import yaml

from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.calibrate_v06 import choose, static_constants
from experiments.v07_common import (ARM_KAPPA, ARM_POLICY, BUDGETS, CALIBRATED_ARMS, CELLS, FEASIBILITY, FROZEN_DIR,
                                    SCENARIOS, SMOKE_CAL_SEEDS, TAU_QUANTILE, TUNING_SEEDS, assert_seeds, cell_name,
                                    frozen_path, git_state, grid, run_tasks, scenario_config, versions, write_json,
                                    write_manifest)
from tccer.config import replace, save_config


def arm_config(base, arm, thr, kappa, M):
    return replace(base, v06_threshold=float(thr), mutation_cap=M,
                   v06_kappa=kappa[ARM_KAPPA[arm]] if arm in ARM_KAPPA else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = SMOKE_CAL_SEEDS if a.smoke else TUNING_SEEDS
    assert_seeds(seeds, range(300, 320) if a.smoke else range(200, 220), "v0.7 calibration")
    frozen = "results/v0.7/smoke/frozen" if a.smoke else FROZEN_DIR
    out = "results/v0.7/smoke/calibration" if a.smoke else "results/v0.7/calibration"
    manifest = os.path.join(frozen, "MANIFEST.sha256")
    if os.path.exists(manifest):
        raise SystemExit(f"{manifest} exists: calibration already frozen; refusing to recalibrate")
    os.makedirs(frozen, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    # 1. static constants per scenario
    const, static_rows = {}, []
    res = run_tasks([(scenario_config(s), seed, "static", "rows") for s in SCENARIOS for seed in seeds], a.workers)
    for i, s in enumerate(SCENARIOS):
        df = pd.DataFrame([r for rows in res[i * len(seeds):(i + 1) * len(seeds)] for r in rows])
        const[s] = static_constants(df)
        static_rows.append(df.assign(scenario=s))
    pd.concat(static_rows).to_csv(os.path.join(out, "static_calibration_epochs.csv"), index=False)

    # 2. uncapped grid
    tasks, keys = [], []
    for s in SCENARIOS:
        base = scenario_config(s)
        for arm in CALIBRATED_ARMS:
            for thr in grid(arm, a.smoke):
                cfg = arm_config(base, arm, thr, const[s], None)
                for seed in seeds:
                    tasks.append((cfg, seed, ARM_POLICY[arm], "count"))
                    keys.append((s, arm, float(thr), seed))
    print(f"calibration grid: {len(tasks)} uncapped runs on {a.workers} workers", flush=True)
    counts = run_tasks(tasks, a.workers)
    cdf = pd.DataFrame(keys, columns=["scenario", "arm", "threshold", "seed"]).assign(count=counts)
    cdf.to_csv(os.path.join(out, "calibration_counts.csv"), index=False)
    means = cdf.groupby(["scenario", "arm", "threshold"])["count"].mean().reset_index()

    report, files, chosen = [], [], {}
    for s, M in CELLS:
        base = scenario_config(s)
        for arm in CALIBRATED_ARMS:
            gm = [(r.threshold, r["count"]) for _, r in means[(means.scenario == s) & (means.arm == arm)].iterrows()]
            thr, mean, ok = choose(gm, M)
            write = ok or a.smoke                       # smoke: exercise the pipeline even if not calibratable
            report.append({"scenario": s, "M": M, "arm": arm, "threshold": thr, "calibration_mean_count": mean,
                           "calibratable": ok, "written": write})
            if write:
                cfg = arm_config(base, arm, thr, const[s], M)
                p = frozen_path(frozen, arm, s, M)
                save_config(cfg, p)
                files.append(p)
                chosen[(s, M, arm)] = cfg
    for s in SCENARIOS:
        p = frozen_path(frozen, "A0", s)
        save_config(scenario_config(s), p)
        files.append(p)

    # 3. A6/A7 count distributions from capped A1-A5 on the same calibration seeds
    tasks, keys = [], []
    for (s, M, arm), cfg in chosen.items():
        for seed in seeds:
            tasks.append((cfg, seed, ARM_POLICY[arm], "count"))
            keys.append((s, M, arm, seed))
    capped = run_tasks(tasks, a.workers)
    kdf = pd.DataFrame(keys, columns=["scenario", "M", "arm", "seed"]).assign(count=capped)
    kdf.to_csv(os.path.join(out, "capped_counts.csv"), index=False)
    pmf_rows = []
    for s, M in CELLS:
        src = kdf[(kdf.scenario == s) & (kdf.M == M)]["count"].to_numpy()
        if len(src) == 0:
            raise SystemExit(f"{cell_name(s, M)}: no calibratable A1-A5 arm; cannot build A6/A7 count distribution")
        p, tally = empirical_pmf(src, M)
        pmf_rows += [{"scenario": s, "M": M, "count": n, "n_runs": tally[n], "probability": p[n]} for n in range(M + 1)]
        for arm in ("A6", "A7"):
            path = frozen_path(frozen, arm, s, M)
            save_config(replace(scenario_config(s), mutation_cap=M, v06_count_pmf=pmf_string(p)), path)
            files.append(path)

    rep = os.path.join(frozen, "calibration_report.csv")
    pd.DataFrame(report).to_csv(rep, index=False)
    pmf_path = os.path.join(frozen, "control_count_pmf.csv")
    pd.DataFrame(pmf_rows).to_csv(pmf_path, index=False)
    cpath = os.path.join(frozen, "constants.yaml")
    with open(cpath, "w", encoding="utf-8") as f:
        yaml.safe_dump({"scenarios": {s: {k: round(v, 10) for k, v in c.items()} for s, c in const.items()},
                        "tau_quantile": TAU_QUANTILE, "calibration_seeds": list(seeds), "feasibility": FEASIBILITY,
                        "smoke": a.smoke, "git_commit": git_state()["commit"]}, f, sort_keys=False)
    write_manifest(files + [rep, pmf_path, cpath], manifest)
    write_json(os.path.join(out, "run_info.json"), {"seeds": list(seeds), "smoke": a.smoke, "git": git_state(),
                                                    "versions": versions(), "seconds": round(time.time() - t0, 1),
                                                    "n_runs": len(res) + len(counts) + len(capped)})
    print(pd.DataFrame(report).to_string(index=False))
    print(f"frozen {len(files)} configs; manifest {manifest}; {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
