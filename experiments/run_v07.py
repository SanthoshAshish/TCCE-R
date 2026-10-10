"""v0.7 eight-method runs (docs/PROTOCOL_v0.7.md section 5).

  python -m experiments.run_v07 --mode smoke   # dev seeds 302-303 with the smoke calibration
  python -m experiments.run_v07 --mode eval    # held-out seeds 7000-7059; runs EXACTLY ONCE

Guards (eval): manifest must verify; clean tracked tree; output folder must not exist; seeds must be 7000-7059.
Outputs: <out>/A0_<scenario>/epochs.csv, <out>/<scenario>_M<M>/epochs.csv, run_info.json (commit, versions,
manifest hashes, config hashes per group, run counts, completeness check), COMPLETE.
"""
import argparse
import os
import time

import pandas as pd

from experiments.run_v06 import check_eval_allowed
from experiments.v07_common import (ARM_POLICY, CELLS, EVAL_ARMS, EVAL_SEEDS, FROZEN_DIR, SCENARIOS, SMOKE_EVAL_SEEDS,
                                    assert_seeds, cell_name, frozen_path, git_state, run_tasks, sha256,
                                    verify_manifest, versions, write_json)
from tccer.config import load_config


def build_jobs(frozen, seeds):
    jobs = []
    for s in SCENARIOS:
        cfg = load_config(frozen_path(frozen, "A0", s))
        jobs += [(f"A0_{s}", "A0", cfg, seed, "static", frozen_path(frozen, "A0", s)) for seed in seeds]
    for s, M in CELLS:
        for arm in EVAL_ARMS:
            p = frozen_path(frozen, arm, s, M)
            if os.path.exists(p):                         # not calibratable -> excluded (protocol 4.3)
                cfg = load_config(p)
                jobs += [(cell_name(s, M), arm, cfg, seed, ARM_POLICY[arm], p) for seed in seeds]
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "eval"], required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    smoke = a.mode == "smoke"
    seeds = SMOKE_EVAL_SEEDS if smoke else EVAL_SEEDS
    assert_seeds(seeds, range(300, 320) if smoke else range(7000, 7060), f"v0.7 {a.mode}")
    frozen = "results/v0.7/smoke/frozen" if smoke else FROZEN_DIR
    out = "results/v0.7/smoke/run" if smoke else "results/v0.7/eval"
    listed = verify_manifest(os.path.join(frozen, "MANIFEST.sha256"))
    git = git_state()
    if smoke:
        if os.path.exists(os.path.join(out, "COMPLETE")):
            raise SystemExit(f"{out} already complete; outputs are never overwritten")
    else:
        check_eval_allowed(out, git)
    os.makedirs(out, exist_ok=True)

    jobs = build_jobs(frozen, seeds)
    t0 = time.time()
    print(f"v0.7 {a.mode}: {len(jobs)} runs on {a.workers} workers -> {out}", flush=True)
    results = run_tasks([(cfg, s, pol, "rows") for _, _, cfg, s, pol, _ in jobs], a.workers)
    groups, cfg_hash = {}, {}
    for (group, arm, cfg, seed, _, path), rows in zip(jobs, results):
        for r in rows:
            r["arm"] = arm
        groups.setdefault(group, []).extend(rows)
        cfg_hash[f"{group}/{arm}"] = sha256(path)
    # completeness: every (group, arm, seed) present with the configured number of epochs
    problems = []
    for (group, arm, cfg, seed, _, _), rows in zip(jobs, results):
        if len(rows) != cfg.epochs:
            problems.append((group, arm, seed, len(rows)))
    if problems:
        raise SystemExit(f"incomplete runs: {problems[:5]}")
    for group, rows in groups.items():
        os.makedirs(os.path.join(out, group), exist_ok=True)
        pd.DataFrame(rows).to_csv(os.path.join(out, group, "epochs.csv"), index=False)
    counts = {}
    for group, *_ in jobs:
        counts[group] = counts.get(group, 0) + 1
    write_json(os.path.join(out, "run_info.json"),
               {"mode": a.mode, "seeds": list(seeds), "n_runs": len(jobs), "runs_per_group": counts,
                "seconds": round(time.time() - t0, 1), "git": git, "versions": versions(), "manifest": listed,
                "config_sha256": cfg_hash, "complete": True})
    with open(os.path.join(out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {round(time.time() - t0, 1)} s; groups {counts}")


if __name__ == "__main__":
    main()
