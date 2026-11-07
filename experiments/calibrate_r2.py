"""Revision 2 calibration of C1 (docs/R2_DESIGN_RULES.md section 3). Mutation counts only; no outcome metric.

  python -m experiments.calibrate_r2            # real: seeds 8300-8319 -> configs/r2/frozen (refuses if frozen)
  python -m experiments.calibrate_r2 --smoke    # dev seeds 8200-8201, 6-point grid -> results/r2/smoke (not frozen)

Calibrated by the identical rule and code path: A1, B8 (kappa_s from Static runs, as v0.8) and C1 (r2_causal). C1 fixed constants:
cd_tau = setup delay + 2, r2_retry = state, all other cd_* at their defaults. A grid-edge winner triggers ONE extension by a decade
(counts only). A7M = scenario + cap M; A7 = PMF of the capped counts of the three calibrated arms; A0 = Static.
"""
import argparse
import os
import time

import numpy as np
import pandas as pd
import yaml

from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.calibrate_v06 import static_constants
from experiments.v08_common import (CALIBRATION_RUN_CAP, CELLS, FEASIBILITY, SCENARIOS, TAU_QUANTILE, assert_seeds, choose,
                                    frozen_path, git_state, run_tasks, scenario_config, versions, write_json,
                                    write_manifest)
from tccer.config import replace, save_config
from tccer.core.causal_debt import setup_derived_tau

R2_SEEDS = tuple(range(8300, 8320))
SMOKE_SEEDS = (8200, 8201)
FROZEN_DIR = "configs/r2/frozen"
POLICY = {"A1": "v06_reactive", "B8": "v08_rcpr", "C1": "r2_causal"}
ARMS = tuple(POLICY)
GRID_POINTS, SMOKE_POINTS = 28, 6
KAPPA = {"B8": "kappa_s"}


def full_grid(arm, smoke):
    g = np.linspace(0.30, 0.98, GRID_POINTS) if arm == "A1" else np.geomspace(0.05, 20.0, GRID_POINTS)
    return g[np.linspace(0, len(g) - 1, SMOKE_POINTS).round().astype(int)] if smoke else g


def make_cfg(base, arm, thr, const, M, cap=None):
    cfg = replace(base, v06_threshold=float(thr), mutation_cap=M if cap is None else cap,
                  v06_kappa=const[KAPPA[arm]] if arm in KAPPA else None)
    if arm == "C1":
        cfg = replace(cfg, cd_tau=setup_derived_tau(cfg), r2_retry="state")
    return cfg


def means(d):
    return d.groupby(["scenario", "arm", "threshold"])["count"].mean().reset_index()


def grid_means(m, s, arm):
    return [(r.threshold, r["count"]) for _, r in m[(m.scenario == s) & (m.arm == arm)].iterrows()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = SMOKE_SEEDS if a.smoke else R2_SEEDS
    assert_seeds(seeds, range(8200, 8220) if a.smoke else range(8300, 8320), "R2 calibration")
    frozen = "results/r2/smoke/frozen" if a.smoke else FROZEN_DIR
    out = "results/r2/smoke/calibration" if a.smoke else "results/r2/calibration"
    manifest = os.path.join(frozen, "MANIFEST.sha256")
    if os.path.exists(manifest):
        raise SystemExit(f"{manifest} exists: already frozen; refusing to recalibrate")
    os.makedirs(frozen, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    const, srows = {}, []
    res = run_tasks([(scenario_config(s), seed, "static", "rows") for s in SCENARIOS for seed in seeds], a.workers)
    for i, s in enumerate(SCENARIOS):
        df = pd.DataFrame([r for rows in res[i * len(seeds):(i + 1) * len(seeds)] for r in rows])
        const[s] = static_constants(df)
        srows.append(df.assign(scenario=s))
    pd.concat(srows).to_csv(os.path.join(out, "static_calibration_epochs.csv"), index=False)

    def run_grid(pairs):
        tasks, keys = [], []
        for s, arm, thr in pairs:
            cfg = make_cfg(scenario_config(s), arm, thr, const[s], None, cap=CALIBRATION_RUN_CAP)
            for seed in seeds:
                tasks.append((cfg, seed, POLICY[arm], "count"))
                keys.append((s, arm, float(thr), seed))
        c = run_tasks(tasks, a.workers)
        return pd.DataFrame(keys, columns=["scenario", "arm", "threshold", "seed"]).assign(count=c)

    cdf = run_grid([(s, arm, t) for s in SCENARIOS for arm in ARMS for t in full_grid(arm, a.smoke)])
    cdf["extension"] = 0
    ext = []
    m = means(cdf)
    for s, M in CELLS:                      # one decade extension where the winner sits on a grid edge (counts only)
        for arm in ARMS:
            g = full_grid(arm, a.smoke)
            thr, _, _ = choose(grid_means(m, s, arm), M)
            if arm != "A1" and (np.isclose(thr, g.min()) or np.isclose(thr, g.max())):
                n = SMOKE_POINTS if a.smoke else 10
                if np.isclose(thr, g.min()):
                    e = np.geomspace(g.min() / 10, g.min(), n, endpoint=False)
                else:
                    e = np.geomspace(g.max(), g.max() * 10, n + 1)[1:]
                ext += [(s, arm, float(t)) for t in e]
    ext = sorted(set(ext))
    if ext:
        e = run_grid(ext)
        e["extension"] = 1
        cdf = pd.concat([cdf, e])
    cdf.to_csv(os.path.join(out, "calibration_counts.csv"), index=False)
    m = means(cdf)

    report, files, chosen = [], [], {}
    for s, M in CELLS:
        base = scenario_config(s)
        for arm in ARMS:
            thr, mean, ok = choose(grid_means(m, s, arm), M)
            report.append({"scenario": s, "M": M, "arm": arm, "threshold": thr, "calibration_mean_count": mean,
                           "calibratable": ok, "written": ok or a.smoke})
            if ok or a.smoke:
                cfg = make_cfg(base, arm, thr, const[s], M)
                p = frozen_path(frozen, arm, s, M)
                save_config(cfg, p)
                files.append(p)
                chosen[(s, M, arm)] = cfg
        p = frozen_path(frozen, "A7M", s, M)
        save_config(replace(base, mutation_cap=M), p)
        files.append(p)
    for s in SCENARIOS:
        p = frozen_path(frozen, "A0", s)
        save_config(scenario_config(s), p)
        files.append(p)

    keys = list(chosen)
    capped = run_tasks([(chosen[k], seed, POLICY[k[2]], "count") for k in keys for seed in seeds], a.workers)
    kdf = pd.DataFrame([(k[0], k[1], k[2], seed) for k in keys for seed in seeds],
                       columns=["scenario", "M", "arm", "seed"]).assign(count=capped)
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
    rep, pmfp, cpath = (os.path.join(frozen, n) for n in ("calibration_report.csv", "control_count_pmf.csv", "constants.yaml"))
    pd.DataFrame(report).to_csv(rep, index=False)
    pd.DataFrame(pmf_rows).to_csv(pmfp, index=False)
    with open(cpath, "w", encoding="utf-8") as f:
        yaml.safe_dump({"scenarios": {s: {k: round(v, 10) for k, v in c.items()} for s, c in const.items()},
                        "tau_quantile": TAU_QUANTILE, "calibration_seeds": list(seeds), "feasibility": FEASIBILITY,
                        "calibration_run_cap": CALIBRATION_RUN_CAP, "smoke": a.smoke, "git_commit": git_state()["commit"],
                        "c1_fixed": {"cd_tau": "setup_delay+2", "r2_retry": "state"}}, f, sort_keys=False)
    write_manifest(files + [rep, pmfp, cpath], manifest)
    write_json(os.path.join(out, "run_info.json"), {"seeds": list(seeds), "smoke": a.smoke, "git": git_state(),
                                                    "versions": versions(), "seconds": round(time.time() - t0, 1)})
    print(pd.DataFrame(report).to_string(index=False))
    print(f"frozen {len(files)} configs; manifest {manifest}; {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
