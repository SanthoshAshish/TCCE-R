"""Amendment 1 to the v0.8 E2 calibration (docs/PROTOCOL_v0.8.md section 9), made BEFORE any held-out run.

  python -m experiments.amend_calibration_v08

Why: pass 1 (`calibrate_v08`, 28-point grids) left 7 arm-cells uncalibratable, mostly because the count falls steeply between
adjacent thresholds, and put B8 in S2 at M = 6 on the grid minimum (Theta0 = 0.05). This script, using ONLY calibration seeds
8000-8019 and ONLY mutation counts:
  1. adds 11 equally spaced thresholds inside the bracket (adjacent pass-1 grid points whose counts straddle M) of each
     excluded arm-cell, and 13 geometric thresholds 0.005-0.045 below the pass-1 minimum for B8 in S2 at M = 6;
  2. re-chooses the threshold of exactly those 8 arm-cells (closest mean count, +-15% rule with the exact-limit fix);
     every other arm-cell keeps its pass-1 threshold;
  3. re-derives B5/B6/B7/H1 (from B8's config) in S2 M=6, runs capped counts for the 8 changed arm-cells, and rebuilds the A7
     count PMFs from the pooled capped counts of all calibratable arm-cells;
  4. re-freezes configs/v0.8/frozen with a new SHA-256 manifest. The pass-1 freeze is kept in configs/v0.8/frozen_pass1.
Refuses to run after any held-out output exists or after it has been applied once.
"""
import os
import shutil
import time

import pandas as pd
import yaml

from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.v08_common import (ARM_POLICY, CAL_OUT, CALIBRATED_ARMS, CALIBRATION_RUN_CAP, CELLS, E2_OUT, FEASIBILITY,
                                    FROZEN_DIR, TUNING_SEEDS, arm_config, assert_seeds, choose, derive_from_b8,
                                    frozen_path, git_state, run_tasks, scenario_config, verify_manifest, versions,
                                    write_json, write_manifest)
from tccer.config import load_config, replace, save_config

import numpy as np

N_INTERIOR = 11
B8_LOW = np.geomspace(0.005, 0.05, 14)[:-1]                  # 13 points below the pass-1 grid minimum 0.05
B8_CELL = ("S2_rgg40_background", 6, "B8")
BACKUP = "configs/v0.8/frozen_pass1"
MARKER = os.path.join(CAL_OUT, "AMENDMENT_1_APPLIED")


def bracket(points, M):
    """Adjacent (thr_lo, thr_hi) whose counts straddle M, nearest to M. points: sorted list of (thr, mean)."""
    best = None
    for (t0, c0), (t1, c1) in zip(points, points[1:]):
        if (c0 - M) * (c1 - M) <= 0 and c0 != c1:
            gap = min(abs(c0 - M), abs(c1 - M))
            if best is None or gap < best[0]:
                best = (gap, t0, t1)
    if best is None:
        raise SystemExit(f"no bracket around M={M} in the pass-1 curve; not amended")
    return best[1], best[2]


def main():
    assert_seeds(TUNING_SEEDS, range(8000, 8020), "v0.8 calibration amendment 1")
    if os.path.exists(E2_OUT):
        raise SystemExit("held-out E2 output exists: amendment refused")
    if os.path.exists(MARKER):
        raise SystemExit("amendment 1 already applied")
    verify_manifest(os.path.join(FROZEN_DIR, "MANIFEST.sha256"))        # pass-1 freeze must be intact
    t0 = time.time()
    seeds = TUNING_SEEDS
    rep1 = pd.read_csv(os.path.join(FROZEN_DIR, "calibration_report.csv"))
    cnt1 = pd.read_csv(os.path.join(CAL_OUT, "calibration_counts.csv"))
    cap1 = pd.read_csv(os.path.join(CAL_OUT, "capped_counts.csv"))
    const_rounded = yaml.safe_load(open(os.path.join(FROZEN_DIR, "constants.yaml"), encoding="utf-8"))["scenarios"]
    # exact (unrounded) kappa_s as used by the pass-1 configs; constants.yaml only stores it rounded to 10 decimals
    const = {s: {"kappa_s": load_config(frozen_path(FROZEN_DIR, "B8", s, 3)).v06_kappa} for s in const_rounded}
    assert set(cnt1.seed) == set(seeds) and set(cap1.seed) == set(seeds)
    means1 = cnt1.groupby(["scenario", "arm", "threshold"])["count"].mean().reset_index()

    # 1. supplementary grids
    targets = [(r.scenario, int(r.M), r.arm) for r in rep1.itertuples() if not r.calibratable] + [B8_CELL]
    supp = {}                                                     # (scenario, arm, M) -> list of new thresholds
    ranges = []
    for s, M, arm in targets:
        pts = sorted((float(r.threshold), float(r["count"])) for _, r in
                     means1[(means1.scenario == s) & (means1.arm == arm)].iterrows())
        if (s, M, arm) == B8_CELL:
            new = [float(x) for x in B8_LOW]
            ranges.append({"scenario": s, "M": M, "arm": arm, "kind": "extend-lower", "lo": new[0], "hi": new[-1], "n": len(new)})
        else:
            lo, hi = bracket(pts, M)
            new = [float(x) for x in np.linspace(lo, hi, N_INTERIOR + 2)[1:-1]]
            ranges.append({"scenario": s, "M": M, "arm": arm, "kind": "bracket", "lo": lo, "hi": hi, "n": len(new)})
        supp[(s, M, arm)] = new
    pd.DataFrame(ranges).to_csv(os.path.join(CAL_OUT, "amendment1_search_ranges.csv"), index=False)

    tasks, keys = [], []
    for (s, M, arm), thr_list in supp.items():
        base = scenario_config(s)
        for thr in thr_list:
            cfg = arm_config(base, arm, thr, const[s], None, cap=CALIBRATION_RUN_CAP)
            for seed in seeds:
                tasks.append((cfg, seed, ARM_POLICY[arm], "count")); keys.append((s, M, arm, thr, seed))
    print(f"amendment 1: {len(tasks)} supplementary calibration runs", flush=True)
    counts = run_tasks(tasks, max(1, (os.cpu_count() or 2) - 1))
    sdf = pd.DataFrame(keys, columns=["scenario", "M_target", "arm", "threshold", "seed"]).assign(count=counts)
    sdf.to_csv(os.path.join(CAL_OUT, "amendment1_counts.csv"), index=False)
    smeans = sdf.groupby(["scenario", "M_target", "arm", "threshold"])["count"].mean().reset_index()

    # 2. re-choose the 8 targets
    final, changed = {}, {}
    for s, M, arm in targets:
        pts = [(float(r.threshold), float(r["count"])) for _, r in
               means1[(means1.scenario == s) & (means1.arm == arm)].iterrows()]
        pts += [(float(r.threshold), float(r["count"])) for _, r in
                smeans[(smeans.scenario == s) & (smeans.arm == arm) & (smeans.M_target == M)].iterrows()]
        thr, mean, ok = choose(pts, M)
        final[(s, M, arm)] = (thr, mean, ok)
        old = rep1[(rep1.scenario == s) & (rep1.M == M) & (rep1.arm == arm)].iloc[0]
        changed[(s, M, arm)] = {"scenario": s, "M": M, "arm": arm, "pass1_threshold": old.threshold,
                                "pass1_mean_count": old.calibration_mean_count, "pass1_calibratable": bool(old.calibratable),
                                "final_threshold": thr, "final_mean_count": mean, "final_calibratable": ok}

    # 3. archive pass 1, rewrite configs
    if not os.path.exists(BACKUP):
        shutil.copytree(FROZEN_DIR, BACKUP)
    chosen = {}
    for r in rep1.itertuples():
        key = (r.scenario, int(r.M), r.arm)
        if key in final:
            thr, mean, ok = final[key]
            if ok:
                chosen[key] = arm_config(scenario_config(r.scenario), r.arm, thr, const[r.scenario], r.M)
        elif bool(r.calibratable):                        # untouched arm-cell: reuse the pass-1 config exactly
            chosen[key] = load_config(frozen_path(BACKUP, r.arm, r.scenario, r.M))
    files = []
    for (s, M, arm), cfg in chosen.items():
        p = frozen_path(FROZEN_DIR, arm, s, M)
        save_config(cfg, p); files.append(p)
    for s, M in CELLS:
        b8 = chosen.get((s, M, "B8"))
        for arm, cfg in derive_from_b8(b8, M).items():
            p = frozen_path(FROZEN_DIR, arm, s, M)
            save_config(cfg, p); files.append(p)
        p = frozen_path(FROZEN_DIR, "A7M", s, M)
        save_config(replace(scenario_config(s), mutation_cap=M), p); files.append(p)
    for s in {c[0] for c in CELLS}:
        files.append(frozen_path(FROZEN_DIR, "A0", s))

    # 4. capped counts for the arm-cells that are new or changed, then A7 PMFs from the pooled capped counts
    tasks, keys = [], []
    for key, row in changed.items():
        if row["final_calibratable"]:
            s, M, arm = key
            for seed in seeds:
                tasks.append((chosen[key], seed, ARM_POLICY[arm], "count")); keys.append((s, M, arm, seed))
    capped_new = run_tasks(tasks, max(1, (os.cpu_count() or 2) - 1))
    ndf = pd.DataFrame(keys, columns=["scenario", "M", "arm", "seed"]).assign(count=capped_new)
    ndf.to_csv(os.path.join(CAL_OUT, "amendment1_capped_counts.csv"), index=False)
    redo = {(s, M, arm) for (s, M, arm) in changed}
    kept = cap1[[(r.scenario, int(r.M), r.arm) not in redo for r in cap1.itertuples()]]
    allcap = pd.concat([kept, ndf], ignore_index=True)
    allcap.to_csv(os.path.join(CAL_OUT, "capped_counts_final.csv"), index=False)
    pmf_rows = []
    for s, M in CELLS:
        src = allcap[(allcap.scenario == s) & (allcap.M == M)]["count"].to_numpy()
        p, tally = empirical_pmf(src, M)
        pmf_rows += [{"scenario": s, "M": M, "count": n, "n_runs": tally[n], "probability": p[n]} for n in range(M + 1)]
        path = frozen_path(FROZEN_DIR, "A7", s, M)
        save_config(replace(scenario_config(s), mutation_cap=M, v06_count_pmf=pmf_string(p)), path); files.append(path)

    # 5. report, constants, manifest
    final_rep = []
    for r in rep1.itertuples():
        key = (r.scenario, int(r.M), r.arm)
        c = changed.get(key)
        final_rep.append({"scenario": r.scenario, "M": r.M, "arm": r.arm,
                          "threshold": c["final_threshold"] if c else r.threshold,
                          "calibration_mean_count": c["final_mean_count"] if c else r.calibration_mean_count,
                          "calibratable": c["final_calibratable"] if c else bool(r.calibratable),
                          "amended": bool(c), "pass1_threshold": r.threshold, "pass1_mean_count": r.calibration_mean_count,
                          "pass1_calibratable": bool(r.calibratable)})
    rep = os.path.join(FROZEN_DIR, "calibration_report.csv")
    pd.DataFrame(final_rep).to_csv(rep, index=False)
    pd.DataFrame(list(changed.values())).to_csv(os.path.join(CAL_OUT, "amendment1_changes.csv"), index=False)
    pmf_path = os.path.join(FROZEN_DIR, "control_count_pmf.csv")
    pd.DataFrame(pmf_rows).to_csv(pmf_path, index=False)
    cpath = os.path.join(FROZEN_DIR, "constants.yaml")
    with open(cpath, "w", encoding="utf-8") as f:
        yaml.safe_dump({"scenarios": const_rounded, "tau_quantile": 0.75, "calibration_seeds": list(seeds),
                        "feasibility": FEASIBILITY, "calibration_run_cap": CALIBRATION_RUN_CAP, "smoke": False,
                        "amendment": "1 (finer grids for 7 excluded arm-cells + B8 S2 M6 lower bound; seeds 8000-8019 only)",
                        "kappa_note": "values here are rounded to 10 decimals; configs carry the exact kappa",
                        "pass1_git_commit": "047d7c7", "amendment_git_commit": git_state()["commit"]}, f, sort_keys=False)
    manifest = os.path.join(FROZEN_DIR, "MANIFEST.sha256")
    os.remove(manifest)
    write_manifest(sorted(set(files)) + [rep, pmf_path, cpath], manifest)
    write_json(os.path.join(CAL_OUT, "amendment1_run_info.json"),
               {"seeds": list(seeds), "git": git_state(), "versions": versions(), "seconds": round(time.time() - t0, 1),
                "n_supplementary_runs": len(counts), "n_capped_runs": len(capped_new)})
    open(MARKER, "w").write("applied\n")
    print(pd.DataFrame(list(changed.values())).to_string(index=False))
    print(f"re-frozen {len(set(files)) + 3} files in {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
