"""Summarise an experiment directory: summary.csv, paired tests, plots.

Usage:  python -m experiments.analyze results/default
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

METRICS = {
    "E_hat": "consensus stress E (lower better)",
    "final_error": "final disagreement e(T) (lower better)",
    "lambda2": "algebraic connectivity (higher better)",
    "disconnected": "fraction of epochs disconnected (lower better)",
    "live_edges": "live links (cost)",
}


def per_seed(df):
    df = df.assign(disconnected=(df.components > 1).astype(float))
    g = df.groupby(["policy", "seed"])
    out = g[list(METRICS)].mean()
    out["mutations"] = g.n_mutations.last()
    # epoch of first mutation (= n_epochs if none): exposes timing differences between policies
    muts = df[df.mutation.fillna("") != ""]
    first = muts.groupby(["policy", "seed"]).epoch.min()
    out["first_mut_epoch"] = first.reindex(out.index).fillna(df.epoch.max() + 1)
    return out.reset_index()


def ci95(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return np.nan
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    args = ap.parse_args()
    df = pd.read_csv(os.path.join(args.dir, "epochs.csv"))
    ps = per_seed(df)
    cols = list(METRICS) + ["mutations", "first_mut_epoch"]

    summary = ps.groupby("policy")[cols].agg(["mean", ci95])
    summary.columns = [f"{m}_{s}" for m, s in summary.columns]
    summary.to_csv(os.path.join(args.dir, "summary.csv"))
    print("\nMean over seeds (+/- 95% CI half-width):")
    for pol, row in summary.iterrows():
        print(f"  {pol:12s} " + "  ".join(f"{m}={row[m + '_mean']:.3f}+/-{row[m + '_ci95']:.3f}" for m in cols))

    # Paired Wilcoxon signed-rank: TCCE-R vs each baseline, per-seed means
    rows = []
    base = ps[ps.policy == "tccer"].set_index("seed")
    for pol in sorted(set(ps.policy) - {"tccer"}):
        other = ps[ps.policy == pol].set_index("seed").loc[base.index]
        for m in ["E_hat", "disconnected", "lambda2"]:
            d = base[m] - other[m]
            p = stats.wilcoxon(base[m], other[m]).pvalue if (d != 0).any() and len(d) >= 5 else np.nan
            rows.append({"baseline": pol, "metric": m, "mean_diff_tccer_minus_baseline": d.mean(), "wilcoxon_p": p})
    tests = pd.DataFrame(rows)
    # Holm-Bonferroni adjustment across all comparisons in this table
    order = tests.wilcoxon_p.fillna(1).sort_values().index
    m, running = len(order), 0.0
    adj = pd.Series(index=tests.index, dtype=float)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * (tests.wilcoxon_p.fillna(1)[i])))
        adj[i] = running
    tests["holm_p"] = adj
    tests.to_csv(os.path.join(args.dir, "paired_tests.csv"), index=False)
    print("\nPaired Wilcoxon (TCCE-R minus baseline; raw p and Holm-adjusted p):")
    print(tests.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    plot(df, ps, args.dir)
    print(f"\nwrote summary.csv, paired_tests.csv, *.png to {args.dir}")


def plot(df, ps, out):
    policies = sorted(df.policy.unique(), key=lambda p: (p != "tccer", p))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, m in zip(axes, ["E_hat", "lambda2"]):
        for p in policies:
            s = df[df.policy == p].groupby("epoch")[m].mean().rolling(5, min_periods=1).mean()
            ax.plot(s.index, s.values, label=p, lw=2.2 if p == "tccer" else 1.2)
        ax.set_xlabel("epoch")
        ax.set_title(METRICS[m] + " — mean over seeds, 5-epoch smoothing")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out, "timeseries.png"), dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6))
    for ax, m in zip(axes, ["E_hat", "disconnected", "lambda2", "mutations"]):
        g = ps.groupby("policy")[m]
        means, cis = g.mean().reindex(policies), g.agg(ci95).reindex(policies)
        ax.bar(range(len(policies)), means, yerr=cis, capsize=3,
               color=["#1f6feb" if p == "tccer" else "#8c959f" for p in policies])
        ax.set_xticks(range(len(policies)))
        ax.set_xticklabels(policies, rotation=40, ha="right")
        ax.set_title(m)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "summary_bars.png"), dpi=130)
    plt.close(fig)

    t = df[(df.policy == "tccer") & (df.seed == df.seed.min())]
    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.plot(t.epoch, t.debt, label="debt D", color="#d1242f")
    ax.plot(t.epoch, t.theta, label="threshold θ", color="#1f6feb", ls="--")
    ax.plot(t.epoch, t.E_hat, label="consensus stress E", color="#8c959f", lw=1)
    disc = t[t.components > 1]
    ax.scatter(disc.epoch, np.zeros(len(disc)), marker="|", s=200, color="black", label="disconnected epoch")
    for k in t[t.mutation.fillna("") != ""].epoch:
        ax.axvline(k, color="#2da44e", alpha=0.5)
    ax.set_xlabel("epoch (green lines = mutations)")
    ax.set_title(f"TCCE-R internal trace, seed {t.seed.iloc[0]}")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "tccer_trace.png"), dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
