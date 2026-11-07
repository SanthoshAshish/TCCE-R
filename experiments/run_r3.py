"""R3 held-out evaluation runner (docs/PROTOCOL_R3.md sections 3, 6, 7 and the addendum). COCRO-final = r3_cocro_m (selection-only COCRO, frozen in docs/R3_FREEZE.md).

  python -m experiments.run_r3 --write-configs               # writes configs/r3/frozen (Tier B/C environments + manifest); commit before evaluating
  python -m experiments.run_r3 --tier A|B|C --mode eval      # held-out run, EXACTLY ONCE per tier (guards: clean tracked tree, manifests verify, folder absent)
  python -m experiments.run_r3 --tier A|B|C --mode smoke     # smoke seeds 8540-8541, one cell, results/r3/smoke (pipeline check only)
Tier A: RGG cells S1/S2/S3 x M in {3, 6}, frozen configs in configs/r2a/frozen. Tier B: ER/BA/WS/scale-free n = 100, M in {6, 12}. Tier C: RGG-40 (S1 geometry) with
extended failure models (cascade, node, regime, mixed), M in {3, 6}. Output: <out>/<cell>/epochs.csv (all arms, column `arm`), timing.csv, run_info.json, COMPLETE.
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.diagnose_cocro_dev import run_one
from experiments.run_v06 import check_eval_allowed
from experiments.v08_common import assert_seeds, git_state, sha256, verify_manifest, versions, write_json, write_manifest
from tccer.config import load_config, replace, save_config
from tccer.policies.cocro import CocroParams, register_variant

FAST = CocroParams.fast()
VARIANTS = {"cocro_m": dict(price="none"), "cocro_mfg": dict(price="none", shortlist=3), "cocro": {}, "cocro_r": dict(reserve_factors=(1.0, 2.0)),
            "cocro_m_plug": dict(price="none", plug_in=True), "cocro_m_k1": dict(price="none", Kr=1), "cocro_m_nb1": dict(price="none", nb=1),
            "cocro_m_s1": dict(price="none", S_sel=1), "cocro_m_lap": dict(price="none", estimator="laplacian")}
for _n, _kw in VARIANTS.items():                      # top level: spawned workers register the same variants
    register_variant("r3_" + _n, base=FAST, **_kw)
BASE_POL = {"A0": "static", "A1": "v06_reactive", "A7": "v06_front", "A7M": "v06_front", "B8": "v08_rcpr", "C1": "r2_causal"}
R2A, R3 = "configs/r2a/frozen", "configs/r3/frozen"
SEEDS = {"A": tuple(range(9300, 9450)), "B": tuple(range(9450, 9550)), "C": tuple(range(9450, 9550))}
RANGE = {"A": range(9300, 9450), "B": range(9450, 9550), "C": range(9450, 9550)}
SMOKE_SEEDS = (8540, 8541)
SCEN = {"S1": "S1_rgg40_bursty", "S2": "S2_rgg40_background", "S3": "S3_rgg80_bursty"}
ABL = ["cocro_m_plug", "cocro_m_k1", "cocro_m_nb1", "cocro_m_s1", "cocro_m_lap", "cocro_mfg"]
# Tier B/C environment definitions (frozen by the protocol addendum; overrides of the S1 geometry/failure configuration)
TIER_B = {"ER100": dict(graph_family="er", n_nodes=100, er_p_init=0.06, er_p_pot=0.10),
          "BA100": dict(graph_family="ba", n_nodes=100, ba_m=3, er_p_pot=0.08),
          "WS100": dict(graph_family="ws", n_nodes=100, ws_k=6, ws_p=0.1, er_p_pot=0.08),
          "SF100": dict(graph_family="sf", n_nodes=100, ba_m=3, sf_p=0.3, er_p_pot=0.08)}
TIER_C = {"cascade": dict(failure_model="extended", casc_gain=6.0), "node": dict(failure_model="extended", node_rate=0.01, node_repair=0.3),
          "regime": dict(failure_model="extended", regime_epoch=40, regime_mult=4.0),
          "mixed": dict(failure_model="extended", casc_gain=4.0, node_rate=0.005, node_repair=0.3, regime_epoch=40, regime_mult=3.0)}
M_B, M_C = (6, 12), (3, 6)


def tier_cells(tier):
    """[(cell_name, {arm: config_path}, M)] for the tier; arms use policy names resolved by `policy_of`."""
    cells = []
    if tier == "A":
        for s in ("S1", "S2", "S3"):
            for M in (3, 6):
                files = {"A0": f"{R2A}/A0_{SCEN[s]}.yaml"}
                for a in ("A1", "A7", "A7M", "B8", "C1"):
                    p = f"{R2A}/{a}_{SCEN[s]}_M{M}.yaml"
                    if os.path.exists(p):
                        files[a] = p
                for v in ["cocro_m"] + ABL + (["cocro"] if s != "S3" else []):
                    files[v] = files["A7M"]
                cells.append((f"{s}_M{M}", files, M))
        return cells
    envs, Ms = (TIER_B, M_B) if tier == "B" else (TIER_C, M_C)
    for env in envs:
        for M in Ms:
            d = f"{R3}/{tier}/{env}_M{M}"
            files = {a: f"{d}/{a}.yaml" for a in (["A0", "A7M"] + (["A1", "B8", "C1"] if tier == "C" else []))}
            for v in ["cocro_m", "cocro_m_plug", "cocro_m_k1", "cocro_m_nb1", "cocro_m_s1", "cocro_m_lap", "cocro_mfg"] + (["cocro"] if tier == "C" else []):
                files[v] = files["A7M"]
            cells.append((f"{env}_M{M}", files, M))
    return cells


def policy_of(arm):
    return BASE_POL[arm] if arm in BASE_POL else "r3_" + arm


def write_configs():
    manifest = os.path.join(R3, "MANIFEST.sha256")
    if os.path.exists(manifest):
        raise SystemExit(f"{manifest} exists: configs already frozen; refusing to rewrite")
    files = []
    for tier, envs, Ms in (("B", TIER_B, M_B), ("C", TIER_C, M_C)):
        for env, over in envs.items():
            for M in Ms:
                d = f"{R3}/{tier}/{env}_M{M}"
                os.makedirs(d, exist_ok=True)
                src = {"A0": f"{R2A}/A0_{SCEN['S1']}.yaml", "A7M": f"{R2A}/A7M_{SCEN['S1']}_M6.yaml"}
                if tier == "C":
                    src.update({a: f"{R2A}/{a}_{SCEN['S1']}_M{M}.yaml" for a in ("A1", "B8", "C1")})
                for arm, p in src.items():
                    cfg = replace(load_config(p), **over)
                    if arm != "A0":
                        cfg = replace(cfg, mutation_cap=M)
                    out = f"{d}/{arm}.yaml"
                    save_config(cfg, out)
                    files.append(out)
    write_manifest(files, manifest)
    print(f"wrote {len(files)} configs and {manifest}")


def build_jobs(cells, seeds):
    jobs = []
    for cell, files, M in cells:
        for arm, path in files.items():
            cfg = load_config(path)
            for s in seeds:
                jobs.append((cell, arm, cfg, s))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-configs", action="store_true")
    ap.add_argument("--tier", choices=list(SEEDS))
    ap.add_argument("--mode", choices=["smoke", "eval"])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    if a.write_configs:
        return write_configs()
    if not (a.tier and a.mode):
        raise SystemExit("need --tier and --mode (or --write-configs)")
    smoke = a.mode == "smoke"
    seeds = SMOKE_SEEDS if smoke else SEEDS[a.tier]
    assert_seeds(seeds, range(8540, 8560) if smoke else RANGE[a.tier], f"R3 tier {a.tier} {a.mode}")
    out = f"results/r3/smoke/{a.tier}" if smoke else f"results/r3/{a.tier}"
    cells = tier_cells(a.tier)
    if a.tier in ("B", "C"):
        verify_manifest(os.path.join(R3, "MANIFEST.sha256"))
    verify_manifest(os.path.join(R2A, "MANIFEST.sha256"))
    git = git_state()
    if smoke:
        cells = cells[:1]
        if os.path.exists(os.path.join(out, "COMPLETE")):
            raise SystemExit(f"{out} already complete")
    else:
        check_eval_allowed(out, git)
    os.makedirs(out, exist_ok=True)
    jobs = build_jobs(cells, seeds)
    cost = {"cocro": 6, "cocro_r": 6, "cocro_mfg": 3, "cocro_m_lap": 2, "cocro_m": 2, "cocro_m_plug": 2, "cocro_m_k1": 2, "cocro_m_nb1": 2, "cocro_m_s1": 1}
    order = sorted(range(len(jobs)), key=lambda i: -cost.get(jobs[i][1], 0))
    print(f"tier {a.tier} {a.mode}: {len(jobs)} runs on {a.workers} workers -> {out}", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        res = dict(zip(order, ex.map(run_one, [(jobs[i][2], jobs[i][3], policy_of(jobs[i][1])) for i in order], chunksize=1)))
    groups, timing, problems = {}, [], []
    for i, (cell, arm, cfg, s) in enumerate(jobs):
        rows, ms, secs = res[i]
        if len(rows) != cfg.epochs:
            problems.append((cell, arm, s, len(rows)))
        for r in rows:
            r["arm"] = arm
        groups.setdefault(cell, []).extend(rows)
        timing.append(dict(cell=cell, arm=arm, seed=s, ms_per_epoch=ms, seconds=secs))
    if problems:
        raise SystemExit(f"incomplete runs: {problems[:5]}")
    for cell, rows in groups.items():
        os.makedirs(os.path.join(out, cell), exist_ok=True)
        pd.DataFrame(rows).to_csv(os.path.join(out, cell, "epochs.csv"), index=False)
    pd.DataFrame(timing).to_csv(os.path.join(out, "timing.csv"), index=False)
    cfg_hash = {f"{c}/{arm}": sha256(path) for c, files, _ in cells for arm, path in files.items()}
    write_json(os.path.join(out, "run_info.json"), {"tier": a.tier, "mode": a.mode, "seeds": list(seeds), "n_runs": len(jobs), "cells": [c for c, _, _ in cells],
                                                    "arms": sorted({arm for _, f, _ in cells for arm in f}), "seconds": round(time.time() - t0, 1), "git": git,
                                                    "versions": versions(), "config_sha256": cfg_hash, "cocro_params": {k: str(v) for k, v in FAST.__dict__.items()},
                                                    "variants": {k: {kk: str(vv) for kk, vv in v.items()} for k, v in VARIANTS.items()}, "complete": True})
    with open(os.path.join(out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {round(time.time() - t0, 1)} s")


if __name__ == "__main__":
    main()
