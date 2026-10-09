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
    "configured_edges": "configured links (budget usage)",
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


def holm(pvals) -> pd.Series:
    """Holm-Bonferroni step-down adjusted p-values. NaN p-values (no non-zero differences) count as 1."""
    p = pd.Series(pvals, dtype=float).fillna(1.0)
    order = p.sort_values(kind="mergesort").index
    m, running = len(p), 0.0
    adj = pd.Series(index=p.index, dtype=float)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj


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
    tests["holm_p"] = holm(tests.wilcoxon_p)   # across all comparisons in this table
    tests.to_csv(os.path.join(args.dir, "paired_tests.csv"), index=False)
    print("\nPaired Wilcoxon (TCCE-R minus baseline; raw p and Holm-adjusted p):")
    print(tests.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    plot(df, ps, args.dir)
    write_summary_txt(args.dir, df, summary, tests)
    print(f"\nwrote summary.csv, paired_tests.csv, summary.txt, *.png to {args.dir}")


def write_summary_txt(out, df, summary, tests):
    """Human-readable summary of one run folder (v0.5). Plain ASCII so it displays in any console/editor."""
    n_seeds = df.seed.nunique()
    scen = None
    cfg_path = os.path.join(out, "config_used.yaml")
    if os.path.exists(cfg_path):
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            scen = (yaml.safe_load(f) or {}).get("scenario_file")
    L = ["TCCE-R simulation summary", "=" * 25,
         f"folder:    {os.path.abspath(out)}",
         f"network:   {'scenario file ' + str(scen) if scen else 'seed-generated random geometric graph'}",
         f"seeds:     {n_seeds} ({df.seed.min()}..{df.seed.max()}),  epochs per run: {df.epoch.nunique()}",
         f"policies:  {', '.join(sorted(df.policy.unique()))}",
         "",
         "Mean over seeds, 95% CI half-width in brackets. Lower is better for E (consensus stress)",
         "and disconnected (fraction of epochs); higher is better for lambda2 (algebraic connectivity).",
         ""]
    hdr = (f"{'policy':<12} {'E':>16} {'disconnected':>16} {'lambda2':>16} {'mutations':>10} "
           f"{'1st mutation':>13}")
    L += [hdr, "-" * len(hdr)]
    for pol, r in summary.iterrows():
        def cell(m):
            return f"{r[m + '_mean']:.3f} ({r[m + '_ci95']:.3f})".rjust(16)
        L.append(f"{pol:<12} {cell('E_hat')} {cell('disconnected')} {cell('lambda2')} "
                 f"{r['mutations_mean']:>10.2f} {r['first_mut_epoch_mean']:>13.1f}")
    L += ["", "Paired comparison, TCCE-R minus each baseline (same seeds, same failures):"]
    for _, t in tests.iterrows():
        p = "n/a" if pd.isna(t.wilcoxon_p) else f"{t.wilcoxon_p:.4f}"
        h = "n/a" if pd.isna(t.wilcoxon_p) else f"{t.holm_p:.4f}"
        L.append(f"  vs {t.baseline:<12} {t.metric:<13} diff = {t.mean_diff_tccer_minus_baseline:+.4f}"
                 f"   Wilcoxon p = {p}   Holm p = {h}")
    L += ["", "Notes:",
          "  * Baselines are capped at TCCE-R's mutation count on each seed (fair budget), so TCCE-R",
          "    is always simulated first, even when it is not listed in --policies.",
          "  * p = n/a: the Wilcoxon test needs at least 5 seeds with non-zero differences."]
    if n_seeds < 5:
        L.append(f"  * Only {n_seeds} seed(s): treat these numbers as an ILLUSTRATION, not as evidence.")
    if n_seeds <= 6:
        L.append(f"  * With {n_seeds} seeds the smallest possible two-sided Wilcoxon p is "
                 f"{2 / 2 ** n_seeds:.4f}: with this few seeds no difference can be significant.")
    if scen:
        L.append("  * Scenario run: every seed uses the same network and scripted events; seeds differ only in")
        L.append("    the random parts (transient losses, random failures, x(0) if not given). Narrow CIs reflect")
        L.append("    that, not robustness across networks.")
    if n_seeds < 20:
        L.append("  * The reported v0.4 results use 30 held-out seeds; see RESULTS_SUMMARY.md.")
    with open(os.path.join(out, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


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
