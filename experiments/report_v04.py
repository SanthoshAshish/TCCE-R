"""v0.4 final report: aggregates the bursty-failure experiment across reconfiguration delays.

Reads   results/v0.4/eval_d{D}/epochs.csv for D in DELAYS
Writes  results/v0.4/report/per_seed_metrics.csv     one row per (delay, policy, seed)
        results/v0.4/report/summary.csv              mean and 95% CI per (delay, policy, metric)
        results/v0.4/report/paired_tests.csv         TCCE-R minus comparator, paired over seeds
        results/v0.4/report/*.png                    comparison figures

Statistics (fixed in docs/PROTOCOL_v0.4.md before the evaluation was run):
  * the unit of analysis is the seed (per-seed means over the 80 epochs);
  * paired two-sided Wilcoxon signed-rank tests, because all strategies share each seed's failure trace;
  * 95% t-interval for the mean paired difference;
  * PRIMARY family: TCCE-R vs reactive on consensus stress E at each delay (4 tests), Holm-adjusted;
  * SECONDARY family: every other comparison/metric, Holm-adjusted together;
  * practical-significance thresholds: |dE| >= 0.02, |d disconnected| >= 0.02, |d lambda2| >= 0.01.

Usage:  python -m experiments.report_v04 [--root results/v0.4]
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
from scipy import stats

from experiments.analyze import ci95, holm

DELAYS = [0, 2, 4, 8]
POLICIES = ["static", "periodic", "reactive", "tccer", "tccer_fixed"]
LABEL = {"static": "Static", "periodic": "Periodic", "reactive": "Reactive (fixed E threshold)",
         "tccer": "TCCE-R", "tccer_fixed": "TCCE-R, fixed θ (ablation)"}
# validated categorical palette (dataviz reference, light mode); markers/linestyles = secondary encoding
STYLE = {"tccer": ("#2a78d6", "o", "-"), "reactive": ("#eb6834", "s", "--"), "periodic": ("#1baf7a", "^", "-."),
         "static": ("#eda100", "D", ":"), "tccer_fixed": ("#e87ba4", "v", (0, (1, 1)))}
PRACTICAL = {"E_hat": 0.02, "disconnected": 0.02, "lambda2": 0.01}
METRIC_LABEL = {
    "E_hat": "Consensus stress E (0–1, lower is better)",
    "disconnected": "Fraction of epochs disconnected (lower is better)",
    "lambda2": "Algebraic connectivity λ₂ (higher is better)",
    "mutations": "Topology mutations per run (count)",
    "first_mut_epoch": "Epoch of first mutation (80 = never)",
    "recovery_epochs": "Mean disconnection episode length (epochs)",
}


def episodes(disc: np.ndarray):
    """Lengths of maximal runs of disconnected epochs; a run still open at the end is right-censored."""
    lengths, run = [], 0
    for d in disc:
        if d:
            run += 1
        elif run:
            lengths.append(run)
            run = 0
    censored = run > 0
    if run:
        lengths.append(run)
    return lengths, censored


def per_seed_metrics(df: pd.DataFrame, delay: int) -> pd.DataFrame:
    rows = []
    for (pol, seed), g in df.groupby(["policy", "seed"], sort=False):
        g = g.sort_values("epoch")
        disc = (g.components > 1).to_numpy()
        lens, censored = episodes(disc)
        attempted_disc = g[(g.components > 1) & g.select_outcome.isin(["no_candidates", "all_rejected", "mutated"])]
        rows.append({
            "delay": delay, "policy": pol, "seed": seed,
            "E_hat": g.E_hat.mean(), "final_error": g.final_error.mean(), "disconnected": disc.mean(),
            "lambda2": g.lambda2.mean(), "mutations": int(g.n_mutations.iloc[-1]),
            "first_mut_epoch": int(g[g.mutation.fillna("") != ""].epoch.min()) if (g.mutation.fillna("") != "").any()
            else len(g),
            "recovery_epochs": float(np.mean(lens)) if lens else np.nan,
            "n_disconnection_episodes": len(lens), "last_episode_censored": censored,
            "gate_rejections": int(g.gate_rejections.iloc[-1]),
            "budget_violation_epochs": int((g.configured_edges > g.budget).sum()),
            "attempts_while_disconnected": len(attempted_disc),
            "reconnection_failures": int(attempted_disc.select_outcome.isin(["no_candidates", "all_rejected"]).sum()),
            "reconnect_impossible_epochs": int(((g.components > 1) & ~g.reconnect_possible.astype(bool)).sum()),
            "released_failed_links": int((g.removed_failed_link.astype(bool) & (g.select_outcome == "mutated")).sum()),
            "pending_link_epochs": int(g.pending_links.sum()),
            "live_edges": g.live_edges.mean(), "configured_edges": g.configured_edges.mean(),
        })
    return pd.DataFrame(rows)


def paired(ps: pd.DataFrame):
    rows = []
    for d in sorted(ps.delay.unique()):
        t = ps[(ps.delay == d) & (ps.policy == "tccer")].set_index("seed")
        for comp in ["reactive", "periodic", "static", "tccer_fixed"]:
            o = ps[(ps.delay == d) & (ps.policy == comp)].set_index("seed").loc[t.index]
            for m in ["E_hat", "disconnected", "lambda2"]:
                diff = t[m] - o[m]
                p = stats.wilcoxon(t[m], o[m]).pvalue if (diff != 0).any() else 1.0
                rows.append({"delay": d, "comparator": comp, "metric": m, "n_seeds": len(diff),
                             "mean_tccer": t[m].mean(), "mean_comparator": o[m].mean(),
                             "mean_diff": diff.mean(), "diff_ci95": ci95(diff), "wilcoxon_p": p,
                             "family": "primary" if (comp == "reactive" and m == "E_hat") else "secondary"})
    tests = pd.DataFrame(rows)
    tests["holm_p"] = np.nan
    for fam in ["primary", "secondary"]:
        idx = tests.family == fam
        tests.loc[idx, "holm_p"] = holm(tests.loc[idx, "wilcoxon_p"]).values
    better_if_lower = tests.metric.isin(["E_hat", "disconnected"])
    tccer_better = np.where(better_if_lower, tests.mean_diff < 0, tests.mean_diff > 0)
    tests["statistically_supported"] = tests.holm_p < 0.05
    tests["practically_meaningful"] = tests.mean_diff.abs() >= tests.metric.map(PRACTICAL)
    tests["verdict"] = np.select(
        [tests.statistically_supported & tccer_better, tests.statistically_supported & ~tccer_better],
        ["TCCE-R better", "TCCE-R worse"], "no supported difference")
    return tests


def fig_metric_vs_delay(summary, metric, path, title):
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    for pol in POLICIES:
        s = summary[(summary.policy == pol) & (summary.metric == metric)].sort_values("delay")
        if s.empty:
            continue
        c, mk, ls = STYLE[pol]
        ax.errorbar(s.delay + 0.08 * (POLICIES.index(pol) - 2), s["mean"], yerr=s.ci95, color=c, marker=mk,
                    ls=ls, lw=2, ms=7, capsize=3, label=LABEL[pol])
    ax.set_xticks(DELAYS)
    ax.set_xlabel("Reconfiguration (link setup) delay, epochs")
    ax.set_ylabel(METRIC_LABEL[metric])
    ax.set_title(title, fontsize=11)
    ax.grid(axis="y", color="#e5e5e5", lw=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.text(0.01, 0.01, "Mean over 30 held-out seeds; error bars = 95% CI", fontsize=7, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_forest(tests, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, m in zip(axes, ["E_hat", "disconnected", "lambda2"]):
        t = tests[(tests.comparator == "reactive") & (tests.metric == m)].sort_values("delay")
        y = np.arange(len(t))
        ax.errorbar(t.mean_diff, y, xerr=t.diff_ci95, fmt="o", color="#2a78d6", ms=7, capsize=4, lw=2)
        ax.axvline(0, color="#555", lw=1)
        for yy, (_, r) in zip(y, t.iterrows()):
            ax.annotate(f"Holm p={r.holm_p:.3g}", (r.mean_diff, yy), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=7, color="#333")
        ax.set_yticks(y)
        ax.set_yticklabels([f"delay {d}" for d in t.delay])
        ax.set_ylim(-0.6, len(t) - 0.4)
        better = "← TCCE-R better" if m != "lambda2" else "TCCE-R better →"
        ax.set_xlabel(f"TCCE-R − Reactive, {m}  ({better})", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", color="#e5e5e5", lw=0.8)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
    fig.suptitle("Paired difference TCCE-R minus Reactive (mean ± 95% CI over 30 held-out seeds)", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/v0.4")
    args = ap.parse_args()
    out = os.path.join(args.root, "report")
    os.makedirs(out, exist_ok=True)

    ps = pd.concat([per_seed_metrics(pd.read_csv(os.path.join(args.root, f"eval_d{d}", "epochs.csv")), d)
                    for d in DELAYS], ignore_index=True)
    ps.to_csv(os.path.join(out, "per_seed_metrics.csv"), index=False)

    metrics = ["E_hat", "disconnected", "lambda2", "mutations", "first_mut_epoch", "recovery_epochs",
               "n_disconnection_episodes", "gate_rejections", "budget_violation_epochs",
               "attempts_while_disconnected", "reconnection_failures", "reconnect_impossible_epochs",
               "released_failed_links", "pending_link_epochs", "live_edges", "configured_edges"]
    long = ps.melt(id_vars=["delay", "policy", "seed"], value_vars=metrics, var_name="metric")
    summary = (long.groupby(["delay", "policy", "metric"]).value
               .agg(mean="mean", ci95=lambda x: ci95(x.dropna()), n="count").reset_index())
    summary.to_csv(os.path.join(out, "summary.csv"), index=False)

    tests = paired(ps)
    tests.to_csv(os.path.join(out, "paired_tests.csv"), index=False)

    for m, f in [("E_hat", "fig1_consensus_stress.png"), ("disconnected", "fig2_disconnected.png"),
                 ("lambda2", "fig3_lambda2.png"), ("mutations", "fig4_mutations.png"),
                 ("first_mut_epoch", "fig5_first_mutation.png"), ("recovery_epochs", "fig6_recovery.png")]:
        fig_metric_vs_delay(summary, m, os.path.join(out, f), METRIC_LABEL[m].split(" (")[0] + " vs reconfiguration delay")
    fig_forest(tests, os.path.join(out, "fig7_paired_tccer_minus_reactive.png"))

    pd.set_option("display.width", 200)
    piv = summary[summary.metric.isin(["E_hat", "disconnected", "lambda2", "mutations", "first_mut_epoch",
                                       "recovery_epochs"])]
    piv = piv.assign(v=piv["mean"].round(3).astype(str) + " ± " + piv.ci95.round(3).astype(str))
    print(piv.pivot_table(index=["delay", "policy"], columns="metric", values="v", aggfunc="first").to_string())
    print("\nIntegrity (sums over seeds):")
    print(ps.groupby(["delay", "policy"])[["gate_rejections", "budget_violation_epochs", "reconnection_failures",
                                           "reconnect_impossible_epochs", "released_failed_links"]].sum().to_string())
    print("\nPaired tests:")
    print(tests[["delay", "comparator", "metric", "mean_diff", "diff_ci95", "wilcoxon_p", "holm_p", "family",
                 "verdict", "practically_meaningful"]].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nwrote {out}/")


if __name__ == "__main__":
    main()
