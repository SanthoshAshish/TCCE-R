"""v0.7 analysis exactly as pre-specified in docs/PROTOCOL_v0.7.md sections 6-7.

  python -m experiments.analyze_v07 --run results/v0.7/eval            (or results/v0.7/smoke/run --smoke)

Reuses the v0.6 metric and statistics functions (experiments/analyze_v06.py) with per-scenario constants.
Writes <run>/analysis/: per_seed_metrics.csv, summary.csv, primary_tests.csv, secondary_tests.csv,
exploratory_diffs.csv, feedback_quality.csv, REPORT.md, fig_E_by_arm.png.
"""
import argparse
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy import stats

import experiments.analyze_v06 as an
from experiments.analyze import holm
from experiments.v07_common import BUDGETS, CELLS, FROZEN_DIR, SCENARIOS, cell_name, frozen_path
from tccer.config import load_config

PRIMARY = [("A5", "A1"), ("A5", "A7")]
SECONDARY = [("A2", "A1"), ("A3", "A1"), ("A3", "A2"), ("A4", "A3"), ("A5", "A4"), ("A6", "A1"), ("A7", "A1")]
EXPLORATORY = ["final_error", "disconnected", "lambda2", "E_second_half", "precision", "false_alarm",
               "detection_rate", "anchored_recovery", "mutations", "pending_link_epochs", "live_link_releases",
               "wasted_release_rate"]


def feedback_metrics(g):
    """A5 only: parse 'm:S(delta);' entries from theta_update (counterfactual) or 'm:S;' (legacy)."""
    txt = ";".join(x for x in g.get("theta_update", pd.Series(dtype=str)).dropna().astype(str) if x)
    items = re.findall(r"(\d+):([SFN])(?:\(([-+0-9.eE]+)\))?", txt)
    out = {"fb_updates": len(items)}
    if items:
        o = [i[1] for i in items]
        out.update(fb_success=o.count("S") / len(o), fb_failure=o.count("F") / len(o),
                   fb_neutral=o.count("N") / len(o))
        d = [float(i[2]) for i in items if i[2]]
        out["fb_mean_delta"] = float(np.mean(d)) if d else np.nan
    return out


def family(ps, pairs, cells, name):
    rows = []
    for s, M in cells:
        cell = cell_name(s, M)
        arms = set(ps[ps.group == cell].arm)
        for x, y in pairs:
            if x not in arms or y not in arms:
                rows.append({"cell": cell, "comparison": f"{x}-{y}", "status": "excluded (not calibratable)"})
                continue
            diff = an.paired(ps, cell, x, y, "E")
            p, nnz, ident = an.wilcoxon_p(diff)
            rows.append({"cell": cell, "scenario": s, "M": M, "comparison": f"{x}-{y}", "metric": "E",
                         **an.describe(diff), "wilcoxon_p": p, "n_nonzero": nnz, "identical": ident,
                         "status": "tested"})
    df = pd.DataFrame(rows)
    for c in ("mean_diff", "boot_lo", "boot_hi", "wilcoxon_p", "identical", "n"):
        if c not in df:
            df[c] = np.nan
    tested = df.status == "tested"
    df["family"], df["holm_p"], df["verdict"] = name, np.nan, ""
    df.loc[tested, "holm_p"] = holm(df.loc[tested, "wilcoxon_p"]).values
    for i in df.index[tested]:
        r = df.loc[i]
        df.loc[i, "verdict"] = an.verdict(r.holm_p, r.mean_diff, (r.boot_lo, r.boot_hi), bool(r.identical))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    frozen = "results/v0.7/smoke/frozen" if a.smoke else FROZEN_DIR
    with open(os.path.join(frozen, "constants.yaml"), encoding="utf-8") as f:
        consts = yaml.safe_load(f)["scenarios"]
    out = os.path.join(a.run, "analysis")
    os.makedirs(out, exist_ok=True)
    rows = []
    for s in SCENARIOS:
        an.CONST.clear()
        an.CONST.update(consts[s])
        static = pd.read_csv(os.path.join(a.run, f"A0_{s}", "epochs.csv"), low_memory=False)
        a0cfg = load_config(frozen_path(frozen, "A0", s))
        labels, traces = {}, {}
        for seed in sorted(static.seed.unique()):
            sg = static[static.seed == seed].sort_values("epoch")
            labels[seed] = {v: an.epoch_classes(sg.E_hat.to_numpy() > an.CONST["tau"], v) for v in an.VARIANTS}
            traces[seed] = an.rebuild_down(a0cfg, seed, sg.n_down_potential.to_numpy())
        for M in BUDGETS:
            cell = cell_name(s, M)
            path = os.path.join(a.run, cell, "epochs.csv")
            # A0 is analysed from its own file (as in v0.6): concatenating it with the arm rows would give it
            # empty v06_* columns, which run_metrics would try to read as integers
            parts = [static.assign(arm="A0")] + ([pd.read_csv(path, low_memory=False)] if os.path.exists(path) else [])
            for (arm, seed), g in ((k, gg) for part in parts for k, gg in part.groupby(["arm", "seed"])):
                Mi = None if arm == "A0" else M
                met = an.run_metrics(g, static[static.seed == seed], labels[seed], a0cfg.link_setup_epochs, Mi,
                                     *traces[seed])
                mut = g[g.select_outcome == "mutated"]
                met["live_link_releases"] = int((~mut.removed_failed_link.astype(bool)).sum()) if len(mut) else 0
                if arm == "A5":
                    met.update(feedback_metrics(g))
                rows.append({"group": cell, "scenario": s, "M": M, "arm": arm, "seed": seed, **met})
    ps = pd.DataFrame(rows)
    ps.to_csv(os.path.join(out, "per_seed_metrics.csv"), index=False)

    num = [c for c in ps.columns if c not in ("group", "scenario", "M", "arm", "seed")
           and pd.api.types.is_numeric_dtype(ps[c])]
    summ = []
    for (grp, arm), g in ps.groupby(["group", "arm"]):
        for m in num:
            v = g[m].dropna().to_numpy(dtype=float)
            half = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else np.nan
            summ.append({"group": grp, "arm": arm, "metric": m, "n": len(v),
                         "mean": v.mean() if len(v) else np.nan, "ci95_half": half})
    summary = pd.DataFrame(summ)
    summary.to_csv(os.path.join(out, "summary.csv"), index=False)

    prim = family(ps, PRIMARY, CELLS, "primary (Holm over 12)")
    sec = family(ps, SECONDARY, CELLS, "secondary (Holm over 42)")
    prim.to_csv(os.path.join(out, "primary_tests.csv"), index=False)
    sec.to_csv(os.path.join(out, "secondary_tests.csv"), index=False)
    expl = []
    for s, M in CELLS:
        cell = cell_name(s, M)
        arms = set(ps[ps.group == cell].arm)
        for x, y in PRIMARY + SECONDARY:
            if {x, y} <= arms:
                for m in EXPLORATORY:
                    expl.append({"cell": cell, "comparison": f"{x}-{y}", "metric": m,
                                 **an.describe(an.paired(ps, cell, x, y, m))})
                expl.append({"cell": cell, "comparison": f"{x}-{y}", "metric": "E | equal realised counts",
                             **an.describe(an.paired_equal_counts(ps, cell, x, y))})
    pd.DataFrame(expl).to_csv(os.path.join(out, "exploratory_diffs.csv"), index=False)
    fq = ps[ps.arm == "A5"].groupby("group")[[c for c in ps.columns if c.startswith("fb_")]].mean()
    fq.to_csv(os.path.join(out, "feedback_quality.csv"))

    # figure
    arms = ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    fig, axes = plt.subplots(1, len(CELLS), figsize=(3.2 * len(CELLS), 4.2), sharey=True)
    for ax, (s, M) in zip(np.atleast_1d(axes), CELLS):
        cell = cell_name(s, M)
        vals = [ps[(ps.group == cell) & (ps.arm == x)].E.dropna() for x in arms]
        means = [v.mean() if len(v) else np.nan for v in vals]
        errs = [stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0 for v in vals]
        ax.bar(range(len(arms)), means, yerr=errs, capsize=3,
               color=["#2a78d6" if x == "A5" else "#eb6834" if x == "A1" else "#9aa0a6" for x in arms])
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms, fontsize=8)
        ax.set_title(f"{s}\nM={M}", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel("Consensus stress E (lower is better)")
    fig.text(0.01, 0.01, "Mean over seeds, 95% t-CI. Blue = A5 TCCE-R, orange = A1 Reactive.", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(out, "fig_E_by_arm.png"), dpi=130)
    plt.close(fig)

    def tab(df, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in df[cols].itertuples(index=False):
            lines.append("| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in r) + " |")
        return "\n".join(lines)
    L = [f"# v0.7 results ({'SMOKE TEST: development seeds, not results' if a.smoke else 'held-out'})", "",
         "Generated by experiments/analyze_v07.py from raw CSVs. Each scenario x budget cell is a separate condition.",
         "", "## Primary (E; Holm over the family)", "",
         tab(prim[prim.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi",
                                             "wilcoxon_p", "holm_p", "verdict"]),
         "", "## Secondary (E; Holm over the family)", "",
         tab(sec[sec.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi", "holm_p",
                                           "verdict"]), "", "## A5 feedback quality", "", fq.round(3).to_string()]
    with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"analysis written to {out}")


if __name__ == "__main__":
    main()
