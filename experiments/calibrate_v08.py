"""v0.8 E2 calibration (docs/PROTOCOL_v0.8.md section 9). Calibration seeds 8000-8019 only; mutation counts only.

  python -m experiments.calibrate_v08            # real calibration -> configs/v0.8/frozen (refuses if frozen)
  python -m experiments.calibrate_v08 --smoke    # dev seeds 8100-8101, 6-point grid -> results/v0.8/smoke/

Per scenario: static constants (tau, kappa_E, kappa_s) -> uncapped-ish grid (cap 12) for A1, A5, B2, B3, B4, B8 ->
closest mean count to M (ties: larger threshold; feasible within +-15%) -> frozen configs. B5/B6/B7/H1 are *derived* from
B8's config (same threshold; one component differs by policy class), A7M = scenario + cap M, A7 = scenario + cap M +
count PMF from the capped realised counts of the calibrated arms. No outcome metric is used.
"""
import argparse
import os
import time

import pandas as pd
import yaml

from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.calibrate_v06 import choose, static_constants
from experiments.v08_common import (ARM_POLICY, CAL_OUT, CALIBRATED_ARMS, CALIBRATION_RUN_CAP, CELLS, FEASIBILITY,
                                    FROZEN_DIR, SCENARIOS, SMOKE_CAL_SEEDS, SMOKE_FROZEN_DIR, TAU_QUANTILE, TUNING_SEEDS,
                                    arm_config, assert_seeds, derive_from_b8, frozen_path, git_state, grid, run_tasks,
                                    scenario_config, versions, write_json, write_manifest)
from tccer.config import replace, save_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = SMOKE_CAL_SEEDS if a.smoke else TUNING_SEEDS
    assert_seeds(seeds, range(8100, 8120) if a.smoke else range(8000, 8020), "v0.8 calibration")
    frozen = SMOKE_FROZEN_DIR if a.smoke else FROZEN_DIR
    out = "results/v0.8/smoke/calibration" if a.smoke else CAL_OUT
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

    # 2. threshold grids (runs capped at CALIBRATION_RUN_CAP)
    tasks, keys = [], []
    for s in SCENARIOS:
        base = scenario_config(s)
        for arm in CALIBRATED_ARMS:
            for thr in grid(arm, a.smoke):
                cfg = arm_config(base, arm, thr, const[s], None, cap=CALIBRATION_RUN_CAP)
                for seed in seeds:
                    tasks.append((cfg, seed, ARM_POLICY[arm], "count"))
                    keys.append((s, arm, float(thr), seed))
    print(f"calibration grid: {len(tasks)} runs on {a.workers} workers", flush=True)
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
        b8 = chosen.get((s, M, "B8"))
        if b8 is not None:                              # derived arms exist only where B8 is calibratable
            for arm, cfg in derive_from_b8(b8, M).items():
                p = frozen_path(frozen, arm, s, M)
                save_config(cfg, p)
                files.append(p)
        p = frozen_path(frozen, "A7M", s, M)
        save_config(replace(base, mutation_cap=M), p)   # exactly M scheduled attempts, no PMF
        files.append(p)
    for s in SCENARIOS:
        p = frozen_path(frozen, "A0", s)
        save_config(scenario_config(s), p)
        files.append(p)

    # 3. A7 count distribution from the capped realised counts of the calibrated arms (same calibration seeds)
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
            raise SystemExit(f"{s}_M{M}: no calibratable arm; cannot build the A7 count distribution")
        p, tally = empirical_pmf(src, M)
        pmf_rows += [{"scenario": s, "M": M, "count": n, "n_runs": tally[n], "probability": p[n]} for n in range(M + 1)]
        path = frozen_path(frozen, "A7", s, M)
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
                        "calibration_run_cap": CALIBRATION_RUN_CAP, "smoke": a.smoke,
                        "git_commit": git_state()["commit"]}, f, sort_keys=False)
    write_manifest(files + [rep, pmf_path, cpath], manifest)
    write_json(os.path.join(out, "run_info.json"), {"seeds": list(seeds), "smoke": a.smoke, "git": git_state(),
                                                    "versions": versions(), "seconds": round(time.time() - t0, 1),
                                                    "n_runs": len(res) + len(counts) + len(capped)})
    print(pd.DataFrame(report).to_string(index=False))
    print(f"frozen {len(files)} configs; manifest {manifest}; {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
