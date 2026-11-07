"""Step 2 of docs/PROTOCOL_R3.md: COCRO component ablation on FRESH development seeds 8520-8539 (used once), applying the pre-declared adoption rules
of protocol section 5 mechanically (thresholds and conditions are coded exactly as written there).

  python -m experiments.ablate_r3_dev [--workers N] [--cells S1:3,S1:6,S2:3,S2:6]
Output (git-ignored): results/cocro/step2/{per_run.csv, summary.csv, paired.csv, rules.json, epochs_*.csv}
Arms: COCRO family with CocroParams.fast() (cocro_m, cocro_mfg, cocro_l0, cocro, cocro_fg, cocro_r, cocro_fgr) and references A7M, A1, B8, C1 (frozen thresholds).
Rules (all on mean E per seed, paired, 4 cells): adopt a component iff (a) mean over cells of d_c <= threshold, (b) d_c <= 0 in >= 3 of 4 cells,
(c) mean over cells of d_c / s_c <= -1.5.  R-sel (Fix 1): mfg vs m and fg vs plain, threshold -0.005.  R-roll (rollout timing): plain vs m and fg vs mfg, threshold -0.010
(the better pair decides).  R-res (Fix 2): r vs plain and fgr vs fg, threshold -0.005, applicable only if R-roll adopts.
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.diagnose_cocro_dev import cfg_path, metrics, run_one
from tccer.config import load_config, replace
from tccer.policies.cocro import CocroParams, register_variant

FAST = CocroParams.fast()
VARIANTS = {"cocro_m": dict(price="none"), "cocro_mfg": dict(price="none", shortlist=3), "cocro_l0": dict(price="zero"), "cocro": {},
            "cocro_fg": dict(shortlist=3), "cocro_r": dict(reserve_factors=(1.0, 2.0)), "cocro_fgr": dict(shortlist=3, reserve_factors=(1.0, 2.0))}
for _n, _kw in VARIANTS.items():                       # top level, so that spawned workers register the same variants
    register_variant(_n + "_a", base=FAST, **_kw)
REFS = {"A7M": "v06_front", "A1": "v06_reactive", "B8": "v08_rcpr", "C1": "r2_causal"}
OUT = "results/cocro/step2"
THR = {"sel": -0.005, "roll": -0.010, "res": -0.005}


def paired(per, a, b, col="E"):
    out = {}
    for cell, g in per.groupby("cell"):
        x, y = g[g.arm == a].set_index("seed")[col], g[g.arm == b].set_index("seed")[col]
        j = x.index.intersection(y.index)
        d = (x[j] - y[j]).to_numpy(float)
        out[cell] = (float(d.mean()), float(d.std(ddof=1) / np.sqrt(len(d))), len(d))
    return out


def judge(pairs, thr):
    d = np.array([v[0] for v in pairs.values()])
    s = np.array([v[1] for v in pairs.values()])
    a, b, c = bool(d.mean() <= thr), bool((d <= 0).sum() >= 3), bool((d / s).mean() <= -1.5)
    return dict(mean_d=float(d.mean()), cells_nonpositive=int((d <= 0).sum()), n_cells=len(d), mean_z=float((d / s).mean()), cond_a=a, cond_b=b, cond_c=c,
                adopt=bool(a and b and c), per_cell={k: [round(v[0], 4), round(v[1], 4)] for k, v in pairs.items()})


def apply_rules(per):
    P = lambda a, b: paired(per, a, b)
    r = {"R-sel:m-family (cocro_mfg vs cocro_m)": judge(P("cocro_mfg", "cocro_m"), THR["sel"]),
         "R-sel:roll-family (cocro_fg vs cocro)": judge(P("cocro_fg", "cocro"), THR["sel"]),
         "R-roll:plain (cocro vs cocro_m)": judge(P("cocro", "cocro_m"), THR["roll"]),
         "R-roll:fg (cocro_fg vs cocro_mfg)": judge(P("cocro_fg", "cocro_mfg"), THR["roll"]),
         "R-res:plain (cocro_r vs cocro)": judge(P("cocro_r", "cocro"), THR["res"]),
         "R-res:fg (cocro_fgr vs cocro_fg)": judge(P("cocro_fgr", "cocro_fg"), THR["res"])}
    rp, rf = r["R-roll:plain (cocro vs cocro_m)"], r["R-roll:fg (cocro_fg vs cocro_mfg)"]
    adopting = [(n, x) for n, x in (("plain", rp), ("fg", rf)) if x["adopt"]]
    if adopting:
        fam = min(adopting, key=lambda t: t[1]["mean_d"])[0]
        final = "cocro_fg" if fam == "fg" else "cocro"
        res = r["R-res:fg (cocro_fgr vs cocro_fg)"] if fam == "fg" else r["R-res:plain (cocro_r vs cocro)"]
        if res["adopt"]:
            final = "cocro_fgr" if fam == "fg" else "cocro_r"
        decision = dict(rollout_adopted=True, family=fam, reservation_adopted=bool(res["adopt"]), final=final)
    else:
        fix1 = r["R-sel:m-family (cocro_mfg vs cocro_m)"]["adopt"]
        decision = dict(rollout_adopted=False, family="selection-only", reservation_adopted=False, final="cocro_mfg" if fix1 else "cocro_m")
    return r, decision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--cells", default="S1:3,S1:6,S2:3,S2:6")
    a = ap.parse_args()
    seeds = list(range(8520, 8540))                        # fixed by the protocol; no other seed may be used here
    cells = [(c.split(":")[0], int(c.split(":")[1])) for c in a.cells.split(",")]
    os.makedirs(OUT, exist_ok=True)
    tasks, keys = [], []
    for scen, M in cells:
        for arm in list(VARIANTS) + list(REFS):
            pol = arm + "_a" if arm in VARIANTS else REFS[arm]
            path = cfg_path(arm if arm in REFS else "A7M", scen, M)
            if not os.path.exists(path):
                print(f"skipping {arm} in {scen} M={M}: no frozen config", flush=True)
                continue
            cfg = load_config(path)
            if arm in VARIANTS:
                cfg = replace(cfg, mutation_cap=M)
            for s in seeds:
                tasks.append((cfg, s, pol)); keys.append((scen, M, arm, s))
    cost = {"cocro_fgr": 5, "cocro_fg": 4, "cocro_r": 3, "cocro": 3, "cocro_mfg": 2, "cocro_l0": 2, "cocro_m": 1}
    order = sorted(range(len(tasks)), key=lambda i: -cost.get(keys[i][2], 0))
    print(f"{len(tasks)} runs on {a.workers} workers (seeds 8520-8539)", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        res = dict(zip(order, ex.map(run_one, [tasks[i] for i in order], chunksize=1)))
    out, store = [], {}
    for i, (scen, M, arm, s) in enumerate(keys):
        rows, ms, secs = res[i]
        out.append(metrics(rows, arm, scen, M, s, ms, secs))
        store.setdefault((scen, M, arm), []).extend(dict(r, seed=s) for r in rows)
    per = pd.DataFrame(out)
    per.to_csv(f"{OUT}/per_run.csv", index=False)
    for (scen, M, arm), rows in store.items():
        pd.DataFrame(rows).to_csv(f"{OUT}/epochs_{scen}_M{M}_{arm}.csv", index=False)
    summ = per.groupby(["cell", "arm"])[["mutations", "E", "E_second_half", "disconnected", "first_mut", "mean_mut_epoch", "ms_per_epoch", "seconds"]].mean()
    summ.to_csv(f"{OUT}/summary.csv")
    rules, decision = apply_rules(per)
    pairs = [(x, "A7M") for x in VARIANTS] + [("cocro", "cocro_m"), ("cocro_fg", "cocro_mfg"), ("cocro_r", "cocro"), ("cocro_fgr", "cocro_fg"), ("cocro_fg", "cocro"), ("cocro_mfg", "cocro_m")]
    rows_p = []
    for x, y in pairs:
        for cell, (d, se, n) in paired(per, x, y).items():
            rows_p.append(dict(arm=x, vs=y, cell=cell, mean_diff=d, se=se, n=n))
    pd.DataFrame(rows_p).to_csv(f"{OUT}/paired.csv", index=False)
    json.dump({"rules": rules, "decision": decision, "thresholds": THR, "seeds": "8520-8539", "seconds": round(time.time() - t0)}, open(f"{OUT}/rules.json", "w"), indent=1)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(summ.round(3).to_string())
    for k, v in rules.items():
        print(f"{k:42s} mean_d={v['mean_d']:+.4f} cells<=0: {v['cells_nonpositive']}/{v['n_cells']} mean_z={v['mean_z']:+.2f} -> adopt={v['adopt']}")
    print("DECISION:", decision, f"| {round(time.time() - t0)} s")


if __name__ == "__main__":
    main()
