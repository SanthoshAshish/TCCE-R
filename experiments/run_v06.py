"""v0.6 runs from the frozen calibration (docs/PROTOCOL_v0.6.md sections 3.3-3.5, 6.1-6.2).

  python -m experiments.run_v06 --mode dry    # tuning seeds 100-119 (pipeline check + C-4 A2-reset sensitivity)
  python -m experiments.run_v06 --mode eval   # held-out seeds 6000-6059; runs EXACTLY ONCE

Guards:
  * the SHA-256 manifest of configs/v0.6/frozen must verify, else nothing runs;
  * eval mode requires a clean git tree for tracked files (protocol + code + frozen configs committed);
  * eval mode refuses to run if results/v0.6/eval already contains a COMPLETE marker (no second evaluation).
Outputs (raw, never overwritten):
  <out>/A0_static/epochs.csv                     A0 once per seed (reused in every cell; protocol 6.1)
  <out>/<cell>/epochs.csv                        A1-A7 under the cap M (primary)
  <out>/<cell>_uncapped/epochs.csv               A1-A5 uncapped, same thresholds (C-2, eval mode only)
  <out>/<cell>_A2reset/epochs.csv                A2-reset (C-4, dry mode only)
  <out>/run_info.json, <out>/COMPLETE
"""
import argparse
import os
import time

import pandas as pd

from experiments.v06_common import (ARM_POLICY, CALIBRATED_ARMS, CELLS, EVAL_ARMS, EVAL_SEEDS, TUNING_SEEDS,
                                    assert_seeds, cell_name, frozen_path, git_state, run_tasks, verify_manifest,
                                    versions, write_json)
from tccer.config import load_config, replace

OUTS = {"dry": "results/v0.6/dryrun", "eval": "results/v0.6/eval"}


def build_tasks(mode, seeds):
    """Return list of (group, arm, cfg, seed, policy). A0 once per seed; arms per cell."""
    jobs = []
    a0 = load_config(frozen_path("A0"))
    for s in seeds:
        jobs.append(("A0_static", "A0", a0, s, "static"))
    for d, M in CELLS:
        for arm in EVAL_ARMS:
            p = frozen_path(arm, d, M)
            if not os.path.exists(p):              # not calibratable: excluded by protocol 3.2
                continue
            cfg = load_config(p)
            for s in seeds:
                jobs.append((cell_name(d, M), arm, cfg, s, ARM_POLICY[arm]))
        if mode == "eval":                          # C-2: uncapped A1-A5, same frozen thresholds
            for arm in CALIBRATED_ARMS:
                p = frozen_path(arm, d, M)
                if os.path.exists(p):
                    cfg = replace(load_config(p), mutation_cap=None)
                    for s in seeds:
                        jobs.append((cell_name(d, M) + "_uncapped", arm, cfg, s, ARM_POLICY[arm]))
        if mode == "dry":                           # C-4: A2-reset with A2's frozen threshold, tuning seeds only
            p = frozen_path("A2", d, M)
            if os.path.exists(p):
                cfg = load_config(p)
                for s in seeds:
                    jobs.append((cell_name(d, M) + "_A2reset", "A2r", cfg, s, ARM_POLICY["A2r"]))
    return jobs


def check_eval_allowed(out, git):
    """Raise SystemExit unless the held-out evaluation may start: clean tracked tree, never run before, empty folder."""
    if git["dirty_files"]:
        raise SystemExit(f"eval refused: uncommitted tracked changes {git['dirty_files'][:5]}")
    if os.path.exists(os.path.join(out, "COMPLETE")):
        raise SystemExit(f"eval refused: {out} already complete; the held-out evaluation runs exactly once")
    if os.path.exists(out) and os.listdir(out):
        raise SystemExit(f"eval refused: {out} is not empty (partial earlier attempt?) - inspect manually")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dry", "eval"], required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = TUNING_SEEDS if a.mode == "dry" else EVAL_SEEDS
    assert_seeds(seeds, range(100, 120) if a.mode == "dry" else range(6000, 6060), f"{a.mode} run")
    listed = verify_manifest()                          # refuses if any frozen file changed
    out = OUTS[a.mode]
    git = git_state()
    if a.mode == "eval":
        check_eval_allowed(out, git)
    os.makedirs(out, exist_ok=True)

    jobs = build_tasks(a.mode, seeds)
    t0 = time.time()
    print(f"{a.mode}: {len(jobs)} runs on {a.workers} workers -> {out}", flush=True)
    results = run_tasks([(cfg, s, pol, "rows") for _, _, cfg, s, pol in jobs], a.workers)
    groups = {}
    for (group, arm, _, _, _), rows in zip(jobs, results):
        for r in rows:
            r["arm"] = arm
        groups.setdefault(group, []).extend(rows)
    counts = {}
    for group, _, _, _, _ in jobs:
        counts[group] = counts.get(group, 0) + 1
    for group, rows in groups.items():
        os.makedirs(os.path.join(out, group), exist_ok=True)
        pd.DataFrame(rows).to_csv(os.path.join(out, group, "epochs.csv"), index=False)
    info = {"mode": a.mode, "seeds": [seeds[0], seeds[-1]], "n_seeds": len(seeds), "n_runs": len(jobs),
            "runs_per_group": counts, "seconds": round(time.time() - t0, 1), "git": git, "versions": versions(),
            "manifest": listed, "workers": a.workers}
    write_json(os.path.join(out, "run_info.json"), info)
    with open(os.path.join(out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {info['seconds']} s; groups: {counts}")


if __name__ == "__main__":
    main()
