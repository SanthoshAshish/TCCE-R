"""Revision 2 main evaluation (docs/R2_DESIGN_RULES.md). Frozen configs in configs/r2/frozen only.

  python -m experiments.run_r2 --mode eval     # held-out seeds 9100-9159 -> results/r2/main/eval; runs EXACTLY ONCE
  python -m experiments.run_r2 --mode smoke    # dev seeds 8202-8203 with results/r2/smoke/frozen -> results/r2/smoke/run

Arms: A0 (Static), A1, A7, A7M, B8, C1 wherever a frozen config exists (infeasible arm-cells are excluded, never retuned).
Guards (eval): manifest verifies, tracked tree clean, output folder absent/empty, seeds 9100-9159 only.
Output: <out>/A0_<scenario>/epochs.csv, <out>/<scenario>_M<M>/epochs.csv, run_info.json, COMPLETE.
"""
import argparse
import os
import time

import pandas as pd

from experiments.run_v06 import check_eval_allowed
from experiments.v08_common import (ARM_POLICY, CELLS, SCENARIOS, assert_seeds, cell_name, frozen_path, git_state, run_tasks,
                                    sha256, verify_manifest, versions, write_json)
from tccer.config import load_config

EVAL_SEEDS = tuple(range(9100, 9160))
SMOKE_SEEDS = (8202, 8203)
FROZEN_DIR, SMOKE_FROZEN_DIR = "configs/r2/frozen", "results/r2/smoke/frozen"
EVAL_OUT, SMOKE_OUT = "results/r2/main/eval", "results/r2/smoke/run"
AM_SEEDS, AM_FROZEN, AM_OUT = tuple(range(9200, 9260)), "configs/r2a/frozen", "results/r2a/main/eval"   # Amendment 1
POLICY = {**{a: ARM_POLICY[a] for a in ("A0", "A1", "A7", "A7M", "B8")}, "C1": "r2_causal"}
ARMS = ("A1", "A7", "A7M", "B8", "C1")


def build_jobs(frozen, seeds):
    jobs = []
    for s in SCENARIOS:
        p = frozen_path(frozen, "A0", s)
        jobs += [(f"A0_{s}", "A0", load_config(p), seed, POLICY["A0"], p) for seed in seeds]
    for s, M in CELLS:
        for arm in ARMS:
            p = frozen_path(frozen, arm, s, M)
            if os.path.exists(p):
                cfg = load_config(p)
                jobs += [(cell_name(s, M), arm, cfg, seed, POLICY[arm], p) for seed in seeds]
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "eval"], required=True)
    ap.add_argument("--amended", action="store_true", help="Amendment 1: seeds 9200-9259, configs/r2a/frozen -> results/r2a/main/eval (eval only)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    smoke = a.mode == "smoke"
    if a.amended and smoke:
        raise SystemExit("--amended is for --mode eval only")
    seeds = SMOKE_SEEDS if smoke else (AM_SEEDS if a.amended else EVAL_SEEDS)
    assert_seeds(seeds, range(8200, 8220) if smoke else (range(9200, 9260) if a.amended else range(9100, 9160)), f"R2 {a.mode}")
    frozen = SMOKE_FROZEN_DIR if smoke else (AM_FROZEN if a.amended else FROZEN_DIR)
    out = SMOKE_OUT if smoke else (AM_OUT if a.amended else EVAL_OUT)
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
    print(f"R2 {a.mode}: {len(jobs)} runs on {a.workers} workers -> {out}", flush=True)
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
               {"mode": a.mode, "seeds": list(seeds), "n_runs": len(jobs), "runs_per_group": counts, "arm_policy": POLICY,
                "seconds": round(time.time() - t0, 1), "git": git, "versions": versions(), "manifest": listed,
                "config_sha256": cfg_hash, "complete": True})
    with open(os.path.join(out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {round(time.time() - t0, 1)} s; groups {counts}")


if __name__ == "__main__":
    main()
