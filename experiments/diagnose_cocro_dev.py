"""COCRO v2 development-seed DIAGNOSTICS (not an evaluation; descriptive only, no inference, nothing is tuned).
Seeds 8500-8519 only (the development range reserved in docs/COCRO_DESIGN.md); the held-out range 9300-9449 and every earlier range are refused.
Environments are the existing scenario definitions (read from configs/r2a/frozen, read-only). COCRO variants use CocroParams.fast() (reduced sampling).

  python -m experiments.diagnose_cocro_dev [--workers N] [--cells S1:3,S1:6,...] [--seeds 8500-8519]
Output (git-ignored): results/cocro/dev_diag/{epochs_<cell>_<arm>.csv, per_run.csv, summary.csv, decisions_summary.csv}
Arms: cocro (rollout price), cocro_m (spend whenever cooled down: A7-like timing, COCRO selection), cocro_l0 (Lambda = 0), A7M, A7C (A7 with exactly
COCRO's realised count on the same seed), A1, B8, C1 (frozen amended-calibration thresholds from OTHER seeds; reference only).
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from tccer.config import load_config, replace
from tccer.policies.cocro import CocroParams, register_variant

FAST = CocroParams.fast()
register_variant("cocro_f", base=FAST)                         # top-level so that spawned workers register the same variants
register_variant("cocro_m_f", base=FAST, price="none")
register_variant("cocro_l0_f", base=FAST, price="zero")

from tccer.sim.engine import simulate  # noqa: E402

OUT = "results/cocro/dev_diag"
CFG = "configs/r2a/frozen"
SCEN = {"S1": "S1_rgg40_bursty", "S2": "S2_rgg40_background", "S3": "S3_rgg80_bursty"}
POLICY = {"cocro": "cocro_f", "cocro_m": "cocro_m_f", "cocro_l0": "cocro_l0_f", "A7M": "v06_front", "A1": "v06_reactive", "B8": "v08_rcpr",
          "C1": "r2_causal"}


def cfg_path(arm, scen, M):
    return f"{CFG}/{'A7M' if arm == 'A7C' else arm}_{SCEN[scen]}_M{M}.yaml"


def run_one(task):
    cfg, seed, policy = task
    t = []
    t0 = time.perf_counter()
    rows = simulate(cfg, seed, policy, log_rounds=False, timing=t)[0]
    return rows, float(np.mean(t)) if t else float("nan"), time.perf_counter() - t0


def metrics(rows, arm, scen, M, seed, ms, secs):
    d = pd.DataFrame(rows)
    mut = d[d.mutation != ""]
    r = dict(cell=f"{scen}_M{M}", arm=arm, seed=seed, mutations=int(d.n_mutations.iloc[-1]), E=d.E_hat.mean(), E_second_half=d.E_hat.iloc[len(d) // 2:].mean(),
             disconnected=float((d.components > 1).mean()), first_mut=float(mut.epoch.iloc[0]) if len(mut) else np.nan,
             mean_mut_epoch=float(mut.epoch.mean()) if len(mut) else np.nan, ms_per_epoch=ms, seconds=secs,
             configured_end=int(d.configured_edges.iloc[-1]), budget=int(d.budget.iloc[-1]))
    if "cocro_evaluated" in d:
        ev = d[d.cocro_evaluated > 0]
        acted = d[d.cocro_decision == "act"]
        r.update(evaluated=len(ev), acted=len(acted), deferred=int((d.cocro_decision == "defer").sum()), no_gain=int((d.cocro_decision == "no_gain").sum()),
                 mean_adv_at_act=float(acted.cocro_adv.mean()) if len(acted) else np.nan, mean_lambda=float(ev.cocro_Lambda.mean()),
                 mean_G_sel=float(ev.cocro_G.mean()), mean_N=float(ev.cocro_N.mean()),
                 gap_G_minus_N=float((ev.cocro_G - ev.cocro_N).mean()), lift=float(d.cocro_lift.dropna().iloc[-1]) if d.cocro_lift.notna().any() else np.nan)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--cells", default="S1:3,S1:6,S2:3,S2:6")
    ap.add_argument("--seeds", default="8500-8519")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    assert 8500 <= lo <= hi <= 8539, "development seeds only (8500-8539)"
    seeds = list(range(lo, hi + 1))
    cells = [(c.split(":")[0], int(c.split(":")[1])) for c in a.cells.split(",")]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    tasks, keys = [], []
    for scen, M in cells:
        for arm, pol in POLICY.items():
            path = cfg_path(arm if arm in ("A7M", "A1", "B8", "C1") else "A7M", scen, M)
            if not os.path.exists(path):                      # arm-cell excluded at calibration (e.g. B8 in S2 M6): no run, as in the evaluation
                print(f"skipping {arm} in {scen} M={M}: no frozen config (infeasible at calibration)", flush=True)
                continue
            cfg = load_config(path)
            if arm.startswith("cocro"):
                cfg = replace(cfg, mutation_cap=M)
            for s in seeds:
                tasks.append((cfg, s, pol))
                keys.append((scen, M, arm, s))
    print(f"stage 1: {len(tasks)} runs on {a.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        res = list(ex.map(run_one, tasks, chunksize=1))
        out, store = [], {}
        for (scen, M, arm, s), (rows, ms, secs) in zip(keys, res):
            out.append(metrics(rows, arm, scen, M, s, ms, secs))
            store.setdefault((scen, M, arm), []).extend(dict(r, seed=s) for r in rows)
        # stage 2: A7C = A7 with exactly COCRO's realised count on the same seed (0 mutations -> no run needed: Static-like; recorded as count 0)
        t2, k2 = [], []
        for r in [x for x in out if x["arm"] == "cocro"]:
            scen, M = r["cell"].split("_M")[0], int(r["cell"].split("_M")[1])
            if r["mutations"] >= 1:
                cfg = replace(load_config(cfg_path("A7M", scen, M)), mutation_cap=r["mutations"])
                t2.append((cfg, r["seed"], "v06_front"))
                k2.append((scen, M, "A7C", r["seed"]))
        print(f"stage 2: {len(t2)} A7C runs", flush=True)
        for (scen, M, arm, s), (rows, ms, secs) in zip(k2, ex.map(run_one, t2, chunksize=1)):
            out.append(metrics(rows, arm, scen, M, s, ms, secs))
            store.setdefault((scen, M, arm), []).extend(dict(r, seed=s) for r in rows)
    per = pd.DataFrame(out)
    per.to_csv(f"{OUT}/per_run.csv", index=False)
    for (scen, M, arm), rows in store.items():
        pd.DataFrame(rows).to_csv(f"{OUT}/epochs_{scen}_M{M}_{arm}.csv", index=False)
    num = ["mutations", "E", "E_second_half", "disconnected", "first_mut", "mean_mut_epoch", "ms_per_epoch", "seconds"]
    summ = per.groupby(["cell", "arm"])[num].mean()
    summ.to_csv(f"{OUT}/summary.csv")
    dec = per[per.arm.str.startswith("cocro")].groupby(["cell", "arm"])[["evaluated", "acted", "deferred", "no_gain", "mean_adv_at_act", "mean_lambda",
                                                                         "mean_G_sel", "mean_N", "gap_G_minus_N", "lift"]].mean()
    dec.to_csv(f"{OUT}/decisions_summary.csv")
    pd.set_option("display.width", 230, "display.max_columns", 40)
    print(summ.round(3).to_string())
    print(dec.round(3).to_string())
    print(f"done in {round(time.time() - t0)} s")


if __name__ == "__main__":
    main()
