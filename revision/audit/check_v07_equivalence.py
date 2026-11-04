"""Does the current code with default options reproduce the stored frozen-v0.7 held-out outputs?

Re-simulates (frozen v0.7 config, arm policy, seed) for every evaluated arm-cell and compares with
results/v0.7/eval/<cell>/epochs.csv on every stored column. Read-only apart from the report files.
  python revision/audit/check_v07_equivalence.py --seeds 60
Classification per cell value: EXACT (identical after CSV round trip), TOLERANCE (not identical but
|a-b| <= ATOL + RTOL*|b|), FAIL (outside tolerance, or non-numeric/NaN mismatch).
Env: V07_RESULTS (stored dir), EQ_OUT (report prefix). Output: <prefix>.json and <prefix>_mismatches.csv
"""
import argparse, io, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.getcwd())
RTOL, ATOL = 1e-9, 1e-12


def main():
    from experiments.run_v07 import build_jobs
    from experiments.v07_common import EVAL_SEEDS, FROZEN_DIR, run_tasks
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=60)
    ap.add_argument("--suite", choices=["full", "focused"], default="full")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1)); a = ap.parse_args()
    if a.suite == "focused":                       # exploratory A1/A3/A5 run: frozen configs configs/v0.7_focused/frozen, seeds 500-559
        from experiments.v07_common import ARM_POLICY, CELLS, SCENARIOS, cell_name, frozen_path
        from tccer.config import load_config
        seeds = tuple(range(500, 560))[:a.seeds]
        fd = "configs/v0.7_focused/frozen"
        jobs = []
        for sc in SCENARIOS:
            jobs += [(f"A0_{sc}", "A0", load_config(frozen_path(fd, "A0", sc)), sd, "static", None) for sd in seeds]
        for sc, M in CELLS:
            for arm in ("A1", "A3", "A5"):
                pth = frozen_path(fd, arm, sc, M)
                if os.path.exists(pth):
                    jobs += [(cell_name(sc, M), arm, load_config(pth), sd, ARM_POLICY[arm], pth) for sd in seeds]
        os.environ.setdefault("V07_RESULTS", "results/v0.7_focused/eval")
        os.environ.setdefault("EQ_OUT", "revision/audit/focused_equivalence_%dseeds" % len(seeds))
    else:
        seeds = EVAL_SEEDS[:a.seeds]
        jobs = build_jobs(FROZEN_DIR, seeds)
    res = run_tasks([(cfg, s, pol, "rows") for _, _, cfg, s, pol, _ in jobs], a.workers)
    groups = {}
    for (group, arm, cfg, seed, _, _), rows in zip(jobs, res):
        for r in rows: r["arm"] = arm
        groups.setdefault(group, []).extend(rows)
    base = os.environ.get("V07_RESULTS", "results/v0.7/eval")
    prefix = os.environ.get("EQ_OUT", "revision/audit/v07_equivalence_60seeds")
    os.makedirs(os.path.dirname(prefix) or ".", exist_ok=True)
    key = ["arm", "seed", "epoch"]
    report, mm_all = {}, []
    for group, rows in groups.items():
        old = pd.read_csv(os.path.join(base, group, "epochs.csv"), low_memory=False)
        old = old[old.seed.isin(seeds)].sort_values(key).reset_index(drop=True)
        new = pd.DataFrame(rows).sort_values(key).reset_index(drop=True)
        cols = [c for c in old.columns if c in new.columns]
        rt = lambda d: pd.read_csv(io.StringIO(d[cols].to_csv(index=False)), low_memory=False)
        o, n = rt(old), rt(new)
        info = {"rows_old": len(old), "rows_new": len(new), "runs": int(old[["arm", "seed"]].drop_duplicates().shape[0]),
                "columns_compared": len(cols), "missing_in_new": [c for c in old.columns if c not in new.columns],
                "extra_in_new": [c for c in new.columns if c not in old.columns], "n_exact_cells": 0,
                "n_tolerance_cells": 0, "n_fail_cells": 0, "fields_not_exact": {}}
        if o.shape != n.shape or not (o[key].values == n[key].values).all():
            info["shape_or_key_mismatch"] = True; report[group] = info; continue
        for c in cols:
            ov, nv = o[c], n[c]
            same = (ov == nv) | (ov.isna() & nv.isna())
            info["n_exact_cells"] += int(same.sum())
            bad = ~same
            if not bad.any(): continue
            if ov.dtype.kind in "fi" and nv.dtype.kind in "fi":
                x, y = ov[bad].to_numpy(float), nv[bad].to_numpy(float)
                ok = np.isclose(x, y, rtol=RTOL, atol=ATOL) & ~(np.isnan(x) ^ np.isnan(y))
                d = np.abs(x - y)
            else:
                x, y, ok, d = ov[bad].astype(str).to_numpy(), nv[bad].astype(str).to_numpy(), np.zeros(int(bad.sum()), bool), np.full(int(bad.sum()), np.nan)
            info["n_tolerance_cells"] += int(ok.sum()); info["n_fail_cells"] += int((~ok).sum())
            info["fields_not_exact"][c] = {"cells": int(bad.sum()), "within_tolerance": int(ok.sum()),
                                           "max_abs_diff": float(np.nanmax(d)) if np.isfinite(d).any() else None}
            idx = np.flatnonzero(bad.to_numpy())
            for i, (xx, yy, oo, dd) in zip(idx, zip(x, y, ok, d)):
                mm_all.append({"group": group, "arm": o.arm[i], "seed": int(o.seed[i]), "epoch": int(o.epoch[i]),
                               "field": c, "stored": xx, "replay": yy, "abs_diff": dd,
                               "class": "TOLERANCE" if oo else "FAIL"})
        report[group] = info
        print(group, {k: info[k] for k in ("runs", "n_exact_cells", "n_tolerance_cells", "n_fail_cells")}, flush=True)
    tot = {k: sum(v.get(k, 0) for v in report.values()) for k in ("n_exact_cells", "n_tolerance_cells", "n_fail_cells", "runs")}
    structural = any(v.get("shape_or_key_mismatch") or v["missing_in_new"] for v in report.values())
    json.dump({"seeds": [seeds[0], seeds[-1]], "n_seeds": len(seeds), "n_runs": len(jobs), "rtol": RTOL, "atol": ATOL,
               "totals": tot, "structural_problem": structural, "groups": report}, open(prefix + ".json", "w"), indent=1)
    pd.DataFrame(mm_all, columns=["group", "arm", "seed", "epoch", "field", "stored", "replay", "abs_diff", "class"]).to_csv(prefix + "_mismatches.csv", index=False)
    print("TOTALS", tot, "structural_problem", structural)


if __name__ == "__main__":
    main()
