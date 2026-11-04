"""v0.8 E2 runs (docs/PROTOCOL_v0.8.md sections 6, 9, 10).

  python -m experiments.run_v08 --mode smoke   # dev seeds 8102-8103 with the smoke calibration -> results/v0.8/smoke/run
  python -m experiments.run_v08 --mode eval    # held-out seeds 9000-9059; runs EXACTLY ONCE

Guards (eval): the frozen manifest must verify; the tracked tree must be clean; the output folder must not exist;
seeds must be 9000-9059 only. Output: <out>/A0_<scenario>/epochs.csv, <out>/<scenario>_M<M>/epochs.csv, run_info.json.
"""
import argparse
import os
import time

import pandas as pd

from experiments.run_v06 import check_eval_allowed
from experiments.v08_common import (ARM_POLICY, CELLS, E2_OUT, EVAL_ARMS, EVAL_SEEDS, FROZEN_DIR, SCENARIOS,
                                    SMOKE_EVAL_SEEDS, SMOKE_FROZEN_DIR, assert_seeds, cell_name, frozen_path, git_state,
                                    run_tasks, sha256, verify_manifest, versions, write_json)
from tccer.config import load_config


def build_jobs(frozen, seeds):
    jobs = []
    for s in SCENARIOS:
        p = frozen_path(frozen, "A0", s)
        jobs += [(f"A0_{s}", "A0", load_config(p), seed, ARM_POLICY["A0"], p) for seed in seeds]
    for s, M in CELLS:
        for arm in EVAL_ARMS:
            p = frozen_path(frozen, arm, s, M)
            if os.path.exists(p):                         # not calibratable -> excluded and reported, never retuned
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
    assert_seeds(seeds, range(8100, 8120) if smoke else range(9000, 9060), f"v0.8 {a.mode}")
    frozen = SMOKE_FROZEN_DIR if smoke else FROZEN_DIR
    out = "results/v0.8/smoke/run" if smoke else E2_OUT
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
    print(f"v0.8 {a.mode}: {len(jobs)} runs on {a.workers} workers -> {out}", flush=True)
    results = run_tasks([(cfg, s, pol, "rows") for _, _, cfg, s, pol, _ in jobs], a.workers)
    groups, cfg_hash, problems = {}, {}, []
    for (group, arm, cfg, seed, _, path), rows in zip(jobs, results):
        if len(rows) != cfg.epochs:
            problems.append((group, arm, seed, len(rows)))
        for r in rows:
            r["arm"] = arm
        groups.setdefault(group, []).extend(rows)
        cfg_hash[f"{group}/{arm}"] = sha256(path)
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
                "arm_policy": ARM_POLICY, "seconds": round(time.time() - t0, 1), "git": git, "versions": versions(),
                "manifest": listed, "config_sha256": cfg_hash, "complete": True})
    with open(os.path.join(out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {round(time.time() - t0, 1)} s; groups {counts}")


if __name__ == "__main__":
    main()
