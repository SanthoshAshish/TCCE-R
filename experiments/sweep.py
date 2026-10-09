"""Small, pre-specified sweep of debt weights and kappa, on TUNING seeds only.

Design (fixed before looking at results):
  * Tuning seeds 100-119. Final evaluation uses seeds 1000-1029 (never used here).
    Seeds 0-19 were used for v0.1 and diagnostics only.
  * Weights (w_E, w_C, w_V):
      W0_v01  (0.5, 0.3, 0.2)  v0.1 reference
      W1_E    (1.0, 0.0, 0.0)  consensus term only
      W2_EC   (0.7, 0.3, 0.0)  drop V (diagnosed as a near-constant offset)
  * kappa for each weighting = the 50th / 75th / 90th percentile of stress s under the STATIC policy
    in CONNECTED epochs (the "in-control" regime). CUSUM's allowance is conventionally set relative to
    the in-control distribution, so kappa is chosen from data rather than by hand. Plus v0.1's kappa = 0.30.
  * All other parameters (theta0, alpha, beta, cooldowns, gate, budget) unchanged from configs/default.yaml.
  * Selection rule for TCCE-R: lowest mean E_hat on tuning seeds, under per-seed mutation-budget matching
    against the reactive baseline (same procedure as experiments/run.py).
  * Equal tuning effort for reactive: its threshold is chosen from the 50/75/90th percentiles of static
    E_hat (connected epochs) plus v0.1's 0.5, by the same rule.
  * Uncapped runs of both policies are also reported (performance vs number of mutations).

Usage:  python -m experiments.sweep --out results/sweep
"""
import argparse
import itertools
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from experiments.analyze import per_seed
from tccer.config import load_config, replace, save_config
from tccer.sim.engine import simulate

TUNE_SEEDS = list(range(100, 120))
WEIGHTS = {"W0_v01": (0.5, 0.3, 0.2), "W1_E": (1.0, 0.0, 0.0), "W2_EC": (0.7, 0.3, 0.0)}
QUANTILES = [0.50, 0.75, 0.90]


def run(cfg, policy, seeds):
    rows = []
    for s in seeds:
        rows += simulate(cfg, s, policy, log_rounds=False)[0]
    return pd.DataFrame(rows)


def run_matched(cfg_t, cfg_r, seeds):
    """TCCE-R with cfg_t; reactive with cfg_r, capped per seed at TCCE-R's mutation count."""
    t_rows, r_rows = [], []
    for s in seeds:
        e = simulate(cfg_t, s, "tccer", log_rounds=False)[0]
        M = e[-1]["n_mutations"]
        t_rows += e
        r_rows += simulate(replace(cfg_r, mutation_cap=M), s, "reactive", log_rounds=False)[0]
    return pd.DataFrame(t_rows), pd.DataFrame(r_rows)


def agg(df, **tags):
    ps = per_seed(df)
    d = {k: ps[k].mean() for k in ["E_hat", "disconnected", "lambda2", "mutations", "first_mut_epoch", "live_edges"]}
    return {**tags, **d}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--out", default="results/sweep")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    base = load_config(args.config)

    # 1. static reference -> kappa and reactive-threshold candidates
    st = run(base, "static", TUNE_SEEDS)
    conn = st[st.components == 1]
    kappas, rows = {}, []
    for name, w in WEIGHTS.items():
        s = w[0] * conn.E_hat + w[1] * conn.C + w[2] * conn.V
        kappas[name] = {f"q{int(q * 100)}": round(float(s.quantile(q)), 4) for q in QUANTILES}
        kappas[name]["v01"] = 0.30
        rows.append({"weights": name, **kappas[name], "s_mean_connected": s.mean()})
    pd.DataFrame(rows).to_csv(os.path.join(args.out, "kappa_table.csv"), index=False)
    r_thresholds = {f"q{int(q * 100)}": round(float(conn.E_hat.quantile(q)), 4) for q in QUANTILES}
    r_thresholds["v01"] = 0.5
    print("kappa candidates:", kappas)
    print("reactive threshold candidates:", r_thresholds)

    # 2. uncapped runs (performance vs. number of mutations)
    unc = []
    for (wn, w), (kn, k) in ((wi, ki) for wi in WEIGHTS.items() for ki in kappas[wi[0]].items()):
        cfg = replace(base, w_E=w[0], w_C=w[1], w_V=w[2], kappa=k)
        unc.append(agg(run(cfg, "tccer", TUNE_SEEDS), policy="tccer", weights=wn, kappa_name=kn, param=k))
    for tn, th in r_thresholds.items():
        unc.append(agg(run(replace(base, reactive_threshold=th), "reactive", TUNE_SEEDS),
                       policy="reactive", weights="-", kappa_name=tn, param=th))
    unc = pd.DataFrame(unc)
    unc.to_csv(os.path.join(args.out, "uncapped.csv"), index=False)
    print("\nUNCAPPED (tuning seeds):\n", unc.round(3).to_string(index=False))

    # 3. budget-matched TCCE-R selection (reactive at v0.1 threshold as the reference opponent)
    matched = []
    for (wn, w), (kn, k) in ((wi, ki) for wi in WEIGHTS.items() for ki in kappas[wi[0]].items()):
        cfg = replace(base, w_E=w[0], w_C=w[1], w_V=w[2], kappa=k)
        t, r = run_matched(cfg, base, TUNE_SEEDS)
        matched.append(agg(t, policy="tccer", weights=wn, kappa_name=kn, param=k))
        matched.append(agg(r, policy="reactive(matched)", weights=wn, kappa_name=kn, param=base.reactive_threshold))
    matched = pd.DataFrame(matched)
    matched.to_csv(os.path.join(args.out, "matched_tccer_selection.csv"), index=False)
    tm = matched[matched.policy == "tccer"]
    best = tm.loc[tm.E_hat.idxmin()]
    w = WEIGHTS[best.weights]
    cfg_t = replace(base, w_E=w[0], w_C=w[1], w_V=w[2], kappa=float(best.param))
    print("\nMATCHED, TCCE-R selection (tuning seeds):\n", matched.round(3).to_string(index=False))
    print(f"\nselected TCCE-R: weights={best.weights} kappa={best.param} ({best.kappa_name})")

    # 4. equal-effort tuning of the reactive threshold against the selected TCCE-R
    rsel = []
    for tn, th in r_thresholds.items():
        t, r = run_matched(cfg_t, replace(cfg_t, reactive_threshold=th), TUNE_SEEDS)
        rsel.append(agg(r, policy="reactive(matched)", kappa_name=tn, param=th))
    rsel = pd.DataFrame(rsel)
    rsel.to_csv(os.path.join(args.out, "matched_reactive_selection.csv"), index=False)
    rbest = rsel.loc[rsel.E_hat.idxmin()]
    print("\nMATCHED, reactive threshold selection (tuning seeds):\n", rsel.round(3).to_string(index=False))
    print(f"selected reactive threshold: {rbest.param} ({rbest.kappa_name})")

    final = replace(cfg_t, reactive_threshold=float(rbest.param))
    save_config(final, os.path.join(args.out, "selected_config.yaml"))
    with open(os.path.join(args.out, "selection.yaml"), "w") as f:
        yaml.safe_dump({"tune_seeds": [TUNE_SEEDS[0], TUNE_SEEDS[-1]], "tccer_weights": best.weights,
                        "tccer_kappa": float(best.param), "tccer_kappa_rule": best.kappa_name,
                        "reactive_threshold": float(rbest.param), "reactive_rule": rbest.kappa_name}, f)

    # frontier plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, m in zip(axes, ["E_hat", "disconnected"]):
        for wn, mk in zip(WEIGHTS, "osD"):
            d = unc[(unc.policy == "tccer") & (unc.weights == wn)]
            ax.scatter(d.mutations, d[m], marker=mk, label=f"TCCE-R {wn}")
        d = unc[unc.policy == "reactive"]
        ax.scatter(d.mutations, d[m], marker="x", s=70, color="black", label="reactive")
        ax.set_xscale("symlog")
        ax.set_xlabel("mean mutations per run (uncapped)")
        ax.set_ylabel(m)
        ax.set_title(f"{m} vs mutation count, tuning seeds")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "frontier.png"), dpi=130)
    print(f"\nwrote {args.out}/")


if __name__ == "__main__":
    main()
