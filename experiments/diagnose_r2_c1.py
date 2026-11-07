"""Revision 2 diagnostic of C1 (policy r2_causal) against B8 (v08_rcpr) on identical environments.

DEVELOPMENT seeds 8200-8219 only. No parameter is changed or tuned: both arms use the frozen v0.8 B8 configuration of
each cell (including the CUSUM-scale threshold theta0), and C1's cd_* fields keep their defaults. This is a behaviour
diagnostic, not an evaluation.

  python -m experiments.diagnose_r2_c1 [--workers N]
Output: results/r2/diag_c1/{epochs_<cell>_<arm>.csv, per_run.csv, summary_by_cell.csv, debt_quantiles.csv}
"""
import argparse
import os

import numpy as np
import pandas as pd

from experiments.v06_common import run_tasks
from tccer.config import load_config

SEEDS = list(range(8200, 8220))
CELLS = [("S1_rgg40_bursty", 3), ("S1_rgg40_bursty", 6), ("S2_rgg40_background", 3), ("S2_rgg40_background", 6),
         ("S3_rgg80_bursty", 3), ("S3_rgg80_bursty", 6)]
ARMS = {"B8": "v08_rcpr", "C1": "r2_causal"}
OUT = "results/r2/diag_c1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    assert min(SEEDS) >= 8200 and max(SEEDS) <= 8219            # development seeds only
    os.makedirs(OUT, exist_ok=True)
    jobs = [(sc, M, arm, load_config(f"configs/v0.8/frozen/B8_{sc}_M{M}.yaml"), seed)
            for sc, M in CELLS for arm in ARMS for seed in SEEDS]
    res = run_tasks([(cfg, seed, ARMS[arm], "rows") for _, _, arm, cfg, seed in jobs], a.workers)
    runs, qrows, dfs = [], [], {}
    for (sc, M, arm, cfg, seed), rows in zip(jobs, res):
        dfs.setdefault((sc, M, arm), []).append(pd.DataFrame(rows))
    for (sc, M, arm), lst in dfs.items():
        pd.concat(lst).to_csv(f"{OUT}/epochs_{sc}_M{M}_{arm}.csv", index=False)
    for (sc, M, arm), lst in dfs.items():
        for df in lst:
            seed, last, th0 = int(df.seed.iloc[0]), df.iloc[-1], df.theta.iloc[0]
            d = df.debt if "debt" in df else pd.Series(np.nan, index=df.index)
            rec = dict(cell=f"{sc}_M{M}", arm=arm, seed=seed, theta0=th0, n_mut=int(last.n_mutations),
                       attempts=int(last.v06_attempts_total), failed_attempts=int(last.v06_failed_attempts_total),
                       cap_epoch=int(df.index[df.n_mutations >= M][0]) if (df.n_mutations >= M).any() else np.nan,
                       first_mut=int(df.index[df.n_mutations >= 1][0]) if (df.n_mutations >= 1).any() else np.nan,
                       debt_mean=d.mean(), debt_max=d.max(), frac_debt_gt_theta0=float((d > th0).mean()),
                       frac_debt_gt_theta=float((d > df.theta).mean()), theta_final=last.theta,
                       E_mean=df.E_hat.mean(), E_max=df.E_hat.max(), frac_E_gt_half=float((df.E_hat > 0.5).mean()),
                       lambda2_mean=df.lambda2.mean(), frac_disconnected=float((df.components > 1).mean()),
                       conf_edges_end=int(last.configured_edges), conf_edges_start=int(df.configured_edges.iloc[0]),
                       n_deferred=int(last.get("rcpr_deferred", 0)), n_risk_filtered=int(last.get("rcpr_risk_filtered", 0)),
                       theta_updates=int(last.theta_updates_total), theta_success=int(last.theta_success_total),
                       theta_failure=int(last.theta_failure_total))
            if arm == "C1":
                rec.update({k: int(last[k]) for k in ("cd_persistent", "cd_temporary", "cd_cascaded", "cd_recovered",
                                                      "cd_compensated", "cd_open")}, scar_max=df.cd_scar.max(),
                           open_debt_max=df.cd_open_debt.max())
            runs.append(rec)
            if arm in ARMS:
                qrows.append(dict(cell=f"{sc}_M{M}", arm=arm, seed=seed, **{f"q{int(q*100)}": d.quantile(q)
                                                                         for q in (.5, .75, .9, .95, .99)}))
    per = pd.DataFrame(runs)
    per.to_csv(f"{OUT}/per_run.csv", index=False)
    pd.DataFrame(qrows).to_csv(f"{OUT}/debt_quantiles.csv", index=False)
    per["hit_cap"] = per.cap_epoch.notna().astype(float)
    per.to_csv(f"{OUT}/per_run.csv", index=False)
    pv = per.pivot_table(index=["cell", "seed"], columns="arm",
                         values=["n_mut", "E_mean", "frac_disconnected", "lambda2_mean", "attempts"])
    dl = pd.DataFrame({m: pv[m]["C1"] - pv[m]["B8"] for m in pv.columns.levels[0]})
    pd_ = dl.groupby("cell").agg(["mean", "std"]).round(4)
    pd_.to_csv(f"{OUT}/paired_C1_minus_B8_descriptive.csv")
    print("paired C1 - B8, mean / sd over 20 dev seeds (descriptive only, no inference):")
    print(pd_.to_string())
    num = per.drop(columns=["seed"]).groupby(["cell", "arm"]).mean(numeric_only=True)
    num.to_csv(f"{OUT}/summary_by_cell.csv")
    # environment identity check: before either arm's first mutation the two arms must see identical dynamics
    chk = []
    for sc, M in CELLS:
        for i, seed in enumerate(SEEDS):
            b, c = dfs[(sc, M, "B8")][i], dfs[(sc, M, "C1")][i]
            fm = [x.index[x.n_mutations >= 1][0] if (x.n_mutations >= 1).any() else len(x) for x in (b, c)]
            k = min(fm)
            same = np.array_equal(b.E_hat.values[:k + 1], c.E_hat.values[:k + 1]) and \
                np.array_equal(b.n_down_potential.values[:k + 1], c.n_down_potential.values[:k + 1])
            # link-failure environment is policy-independent for configured links only; compare burst/scripted counts
            same &= np.array_equal(b.n_burst_down.values, c.n_burst_down.values)
            chk.append(same)
    print("environment identical up to first divergence-allowed epoch (all runs):", all(chk), f"({sum(chk)}/{len(chk)})")
    pd.set_option("display.width", 250, "display.max_columns", 60)
    print(num.round(3).T.to_string())


if __name__ == "__main__":
    main()
