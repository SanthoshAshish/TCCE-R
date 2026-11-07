"""Revision 2, Amendment 1 calibration (docs/R2_AMENDMENT_1.md): thresholds chosen on the mean realised count under the ACTUAL cap M.

  python -m experiments.calibrate_r2a            # seeds 8400-8419 -> configs/r2a/frozen (refuses if frozen)
  python -m experiments.calibrate_r2a --smoke    # dev seeds 8200-8201, 6-point grid -> results/r2a/smoke (not frozen)

The grid is run once with cap 6; the count under cap M is min(count, M) (exact: a cap only stops mutations after the M-th). Every chosen
configuration is re-run under its actual cap and the script aborts if any count differs from the derived one. Counts only; no outcome metric.
"""
import argparse
import os
import time

import numpy as np
import pandas as pd
import yaml

from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.calibrate_r2 import ARMS, GRID_POINTS, POLICY, SMOKE_POINTS, full_grid, make_cfg  # noqa: F401
from experiments.calibrate_v06 import static_constants
from experiments.v08_common import (CELLS, FEASIBILITY, SCENARIOS, TAU_QUANTILE, assert_seeds, choose, frozen_path, git_state,
                                    run_tasks, scenario_config, versions, write_json, write_manifest)
from tccer.config import replace, save_config

SEEDS = tuple(range(8400, 8420))
SMOKE_SEEDS = (8200, 8201)
FROZEN_DIR = "configs/r2a/frozen"
GRID_CAP = 6                                   # = max M


def capped_means(cdf, M):
    d = cdf.assign(count=np.minimum(cdf["count"], M))
    return d.groupby(["scenario", "arm", "threshold"])["count"].mean().reset_index()


def gm(m, s, arm):
    return [(r.threshold, r["count"]) for _, r in m[(m.scenario == s) & (m.arm == arm)].iterrows()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = SMOKE_SEEDS if a.smoke else SEEDS
    assert_seeds(seeds, range(8200, 8220) if a.smoke else range(8400, 8420), "R2 amended calibration")
    frozen = "results/r2a/smoke/frozen" if a.smoke else FROZEN_DIR
    out = "results/r2a/smoke/calibration" if a.smoke else "results/r2a/calibration"
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
            cfg = make_cfg(scenario_config(s), arm, thr, const[s], None, cap=GRID_CAP)
            for seed in seeds:
                tasks.append((cfg, seed, POLICY[arm], "count"))
                keys.append((s, arm, float(thr), seed))
        c = run_tasks(tasks, a.workers)
        return pd.DataFrame(keys, columns=["scenario", "arm", "threshold", "seed"]).assign(count=c)

    cdf = run_grid([(s, arm, t) for s in SCENARIOS for arm in ARMS for t in full_grid(arm, a.smoke)])
    cdf["extension"] = 0
    ext = []
    for s, M in CELLS:                      # one decade extension where a B8/C1 winner sits on a grid edge (counts only)
        m = capped_means(cdf, M)
        for arm in ARMS:
            g = full_grid(arm, a.smoke)
            thr, _, _ = choose(gm(m, s, arm), M)
            if arm != "A1" and (np.isclose(thr, g.min()) or np.isclose(thr, g.max())):
                n = SMOKE_POINTS if a.smoke else 10
                e = (np.geomspace(g.min() / 10, g.min(), n, endpoint=False) if np.isclose(thr, g.min())
                     else np.geomspace(g.max(), g.max() * 10, n + 1)[1:])
                ext += [(s, arm, float(t)) for t in e]
    ext = sorted(set(ext))
    if ext:
        e = run_grid(ext)
        e["extension"] = 1
        cdf = pd.concat([cdf, e])
    cdf.to_csv(os.path.join(out, "calibration_counts_cap6.csv"), index=False)

    report, files, chosen, derived = [], [], {}, {}
    for s, M in CELLS:
        base = scenario_config(s)
        m = capped_means(cdf, M)
        for arm in ARMS:
            thr, mean, ok = choose(gm(m, s, arm), M)
            g = full_grid(arm, a.smoke)
            report.append({"scenario": s, "M": M, "arm": arm, "threshold": thr, "calibration_mean_count": mean, "calibratable": ok,
                           "written": ok or a.smoke, "at_grid_edge": bool(np.isclose(thr, g.min()) or np.isclose(thr, g.max()))})
            if ok or a.smoke:
                cfg = make_cfg(base, arm, thr, const[s], M)
                p = frozen_path(frozen, arm, s, M)
                save_config(cfg, p)
                files.append(p)
                chosen[(s, M, arm)] = cfg
                sel = cdf[(cdf.scenario == s) & (cdf.arm == arm) & np.isclose(cdf.threshold, thr)].sort_values("seed")
                derived[(s, M, arm)] = np.minimum(sel["count"].to_numpy(), M)
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
    bad = [(k, int((kdf[(kdf.scenario == k[0]) & (kdf.M == k[1]) & (kdf.arm == k[2])].sort_values("seed")["count"].to_numpy()
                    != derived[k]).sum())) for k in keys]
    bad = [b for b in bad if b[1]]
    if bad:
        raise SystemExit(f"EXACTNESS CHECK FAILED (count under cap M != min(count under cap 6, M)): {bad}; nothing frozen")
    print("exactness check passed: counts under the actual cap equal the derived counts in all chosen configurations")
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
                        "grid_cap": GRID_CAP, "amendment": "R2 Amendment 1: count under the actual cap M", "smoke": a.smoke,
                        "git_commit": git_state()["commit"], "c1_fixed": {"cd_tau": "setup_delay+2", "r2_retry": "state"}},
                       f, sort_keys=False)
    write_manifest(files + [rep, pmfp, cpath], manifest)
    write_json(os.path.join(out, "run_info.json"), {"seeds": list(seeds), "smoke": a.smoke, "git": git_state(),
                                                    "versions": versions(), "seconds": round(time.time() - t0, 1)})
    print(pd.DataFrame(report).to_string(index=False))
    print(f"frozen {len(files)} configs; manifest {manifest}; {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
