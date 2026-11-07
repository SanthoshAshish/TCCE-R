"""COCRO v2 toy study driver (no simulator). Evaluates the PRE-DECLARED criteria C1-C5 of tccer/toy/shadow_price.py on a fixed grid.

  python -m experiments.toy_shadow_price            -> results/cocro/toy/{per_config.csv, decisions.csv, criteria.json}
Grid: rho in {0, 0.5, 0.9, 0.97} x M in {1, 2, 3} x delta in {1.0, 0.7}; T = 40, d = 2, rare-spike chain (see ToyConfig). Seeds fixed.
"""
import itertools
import json
import os

import numpy as np
import pandas as pd

from tccer.toy.shadow_price import (ToyConfig, evaluate_policy, expectimax, policies, simulate_paths, solve_exact, solve_iid)

OUT = "results/cocro/toy"
RHO, MS, DELTA = (0.0, 0.5, 0.9, 0.97), (1, 2, 3), (1.0, 0.7)
EPISODES, ROLLOUTS = 4000, 2000


def c1_dp_vs_expectimax():
    worst = 0.0
    for cfg in (ToyConfig(T=6, M=2, rho=0.7, delta=0.7, b=(0.0, 0.1, 0.4), pi=(0.5, 0.3, 0.2)),
                ToyConfig(T=7, M=2, rho=0.0, delta=1.0, b=(0.0, 0.2), pi=(0.6, 0.4)),
                ToyConfig(T=6, M=3, rho=0.95, delta=0.5, b=(0.05, 0.3), pi=(0.7, 0.3))):
        V, _ = solve_exact(cfg)
        for m in range(cfg.M + 1):
            for z in range(cfg.Z):
                for cd in (0, 1):
                    worst = max(worst, abs(V[0, m, z, cd] - expectimax(cfg, 0, m, z, cd)))
    return worst


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, dec = [], []
    for rho, M, delta in itertools.product(RHO, MS, DELTA):
        cfg = ToyConfig(rho=rho, M=M, delta=delta)
        pol, tab = policies(cfg, rollout_seed=7, S=ROLLOUTS)
        paths = simulate_paths(cfg, N=EPISODES, seed=123)
        res = {k: evaluate_policy(cfg, paths, f) for k, f in pol.items()}
        base = res["GREEDY"][0]
        r = dict(rho=rho, M=M, delta=delta)
        for k, (tot, nact, dr) in res.items():
            r[f"value_{k}"], r[f"se_{k}"], r[f"acts_{k}"], r[f"defer_{k}"] = tot.mean(), tot.std(ddof=1) / np.sqrt(len(tot)), nact.mean(), dr
        diff = res["ROLLOUT"][0] - base
        r["roll_minus_greedy"], r["roll_minus_greedy_se"] = diff.mean(), diff.std(ddof=1) / np.sqrt(len(diff))
        _, lam_iid = solve_iid(cfg)
        # price comparison on the iid-vs-exact sanity (rho = 0): max |Lambda_exact(t, m, z) - Lambda_iid(t, m)| over feasible states with cd = 0
        feas = [(t, m) for t in range(cfg.T - cfg.d - 1) for m in range(1, M + 1)]
        r["max_price_diff_iid_vs_exact"] = max(abs(tab["exact"][t, m, z] - lam_iid[t, m]) for t, m in feas for z in range(cfg.Z))
        rows.append(r)
        # decision agreement rollout vs exact on non-marginal states
        for t, m, z in itertools.product(range(cfg.T - cfg.d - 1), range(1, M + 1), range(cfg.Z)):
            R = float(cfg.reward(t, z, M - m))
            ex, ro = tab["exact"][t, m, z], tab["roll"][t, m, z]
            dec.append(dict(rho=rho, M=M, delta=delta, t=t, m=m, z=z, R=R, lam_exact=ex, lam_roll=ro, act_exact=R >= ex, act_roll=R >= ro,
                            marginal=abs(R - ex) <= 0.05 * max(1.0, abs(ex))))
    df, dd = pd.DataFrame(rows), pd.DataFrame(dec)
    df.to_csv(f"{OUT}/per_config.csv", index=False)
    dd.to_csv(f"{OUT}/decisions.csv", index=False)

    c1 = c1_dp_vs_expectimax()
    c2_ok = bool((df.roll_minus_greedy >= -2 * df.roll_minus_greedy_se).all())
    ratio = (df.value_ROLLOUT / df.value_EXACT).mean()
    hi = df[(df.rho >= 0.9) & (df.delta == 1.0)]
    c4a = float((hi.defer_IID - hi.defer_EXACT).mean())
    c4b = float((hi.value_IID - hi.value_ROLLOUT).mean())
    c4c = float(df[df.rho == 0.0].max_price_diff_iid_vs_exact.max())
    nm = dd[~dd.marginal]
    agree = float((nm.act_exact == nm.act_roll).mean())
    crit = {"C1_dp_vs_expectimax_max_abs_diff": c1, "C1_pass": c1 < 1e-9,
            "C2_rollout_not_worse_than_greedy_all_configs": c2_ok, "C2_min_diff_over_se": float((df.roll_minus_greedy / df.roll_minus_greedy_se).min()),
            "C3_mean_value_ratio_rollout_over_exact": float(ratio), "C3_pass": bool(ratio >= 0.95),
            "C4_defer_rate_iid_minus_exact_(rho>=0.9,delta=1)": c4a, "C4_value_iid_minus_rollout_(same)": c4b,
            "C4_iid_price_diff_at_rho0": c4c, "C4_pass": bool(c4a > 0.02 and c4b <= 0 and c4c < 1e-9),
            "C5_decision_agreement_nonmarginal": agree, "C5_n_states": int(len(nm)), "C5_pass": bool(agree >= 0.90)}
    crit["ALL_PASS"] = bool(crit["C1_pass"] and c2_ok and crit["C3_pass"] and crit["C4_pass"] and crit["C5_pass"])
    json.dump(crit, open(f"{OUT}/criteria.json", "w"), indent=1)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(df[["rho", "M", "delta", "value_EXACT", "value_ROLLOUT", "value_IID", "value_OLD", "value_GREEDY", "value_FRONT",
              "defer_EXACT", "defer_IID", "defer_OLD"]].round(3).to_string(index=False))
    print(json.dumps(crit, indent=1))


if __name__ == "__main__":
    main()
