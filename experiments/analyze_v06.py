"""v0.6 analysis exactly as pre-specified in docs/PROTOCOL_v0.6.md sections 4-6.

  python -m experiments.analyze_v06 --run results/v0.6/eval      (or results/v0.6/dryrun)

Writes to <run>/analysis/:
  per_seed_metrics.csv     one row per (cell, arm, seed) [+ uncapped / A2reset groups]
  summary.csv              mean, 95% t-CI, n per (group, arm, metric)
  primary_tests.csv        A3 vs A1 on E, 4 cells, Holm(4), verdicts
  secondary_tests.csv      7 comparisons x 4 cells on E, Holm(28), verdicts
  exploratory_diffs.csv    paired mean differences + CIs for all other metrics (no p-values)
  sensitivity.csv          precision / false alarms under S3, S6 and the disconnection label; C-2; C-4
  REPORT.md, fig_*.png
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

from experiments.analyze import holm
from experiments.v06_common import CELLS, FROZEN_DIR, cell_name
from tccer.config import load_config
from tccer.network.events import FailureTrace
from tccer.network.generators import random_geometric

E_MARGIN, P_MARGIN, BOOT_N, BOOT_SEED = 0.02, 0.05, 10_000, 20261010
PRIMARY = ("A3", "A1")
SECONDARY = [("A2", "A1"), ("A3", "A2"), ("A4", "A3"), ("A5", "A4"), ("A1", "A6"), ("A3", "A6"), ("A1", "A7")]
VARIANTS = {"primary": (2, 4), "S3": (2, 3), "S6": (2, 6)}   # (max transient length, min persistent length)


# ------------------------------------------------------------------ episodes and labels (protocol 4)
def episodes(flags):
    """Maximal runs of True: list of (start, length, censored)."""
    out, start = [], None
    for k, f in enumerate(flags):
        if f and start is None:
            start = k
        if not f and start is not None:
            out.append((start, k - start, False))
            start = None
    if start is not None:
        out.append((start, len(flags) - start, True))
    return out


def classify_length(L, variant="primary"):
    t_max, p_min = VARIANTS[variant]
    return "T" if L <= t_max else ("P" if L >= p_min else "I")


def epoch_classes(flags, variant="primary"):
    """Per-epoch class: 'calm' (not degraded), 'T', 'I' or 'P'."""
    cls = np.array(["calm"] * len(flags), dtype=object)
    for s, L, _ in episodes(flags):
        cls[s:s + L] = classify_length(L, variant)
    return cls


# ------------------------------------------------------------------ failure trace rebuild (wasted releases)
def rebuild_down(cfg, seed, logged_n_down):
    pos, eu, ev, length, init = random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, seed)
    trace = FailureTrace(cfg, seed, len(eu), edge_mid=(pos[eu] + pos[ev]) / 2)
    bg = np.zeros(len(eu), dtype=bool)
    down = np.zeros((cfg.epochs, len(eu)), dtype=bool)
    for k in range(cfg.epochs):
        bg = trace.epoch_update(k, bg)
        down[k] = bg | trace.burst[k]
    if not np.array_equal(down.sum(axis=1), np.asarray(logged_n_down)):
        raise RuntimeError(f"failure-trace rebuild does not match the log for seed {seed}: analysis aborted")
    index = {(int(u), int(v)): i for i, (u, v) in enumerate(zip(eu, ev))}
    return down, index


def removed_link(mutation_str):
    m = re.search(r"-(\d+)-(\d+)", mutation_str or "")
    if not m:
        return None
    u, v = int(m.group(1)), int(m.group(2))
    return (min(u, v), max(u, v))


# ------------------------------------------------------------------ per-run metrics (protocol 5)
def run_metrics(g, static_g, classes, d, M, down, index):
    g = g.sort_values("epoch").reset_index(drop=True)
    E = g.E_hat.to_numpy()
    mut = g[g.select_outcome == "mutated"]
    mut_epochs = mut.epoch.to_numpy()
    n = len(mut_epochs)
    r = {"E": E.mean(), "final_error": g.final_error.mean(), "disconnected": (g.components > 1).mean(),
         "lambda2": g.lambda2.mean(), "E_second_half": E[40:].mean(), "pending_link_epochs": g.pending_links.sum(),
         "mutations": int(g.n_mutations.iloc[-1]), "intended": M,
         "attempts": int(g.get("v06_attempts_total", pd.Series([0])).iloc[-1]),
         "failed_attempts": int(g.get("v06_failed_attempts_total", pd.Series([0])).iloc[-1])}
    r["cap_hit"] = bool(M is not None and r["mutations"] >= M)
    r["unexecuted"] = (M - r["mutations"]) if M is not None else np.nan
    for name, cls in classes.items():
        c = cls[mut_epochs] if n else np.array([])
        sfx = "" if name == "primary" else f"_{name}"
        r["precision" + sfx] = (c == "P").mean() if n else np.nan
        r["false_alarm" + sfx] = np.isin(c, ["T", "calm"]).mean() if n else np.nan
        r["false_alarm_transient" + sfx] = (c == "T").mean() if n else np.nan
        r["false_alarm_calm" + sfx] = (c == "calm").mean() if n else np.nan
        r["intermediate" + sfx] = (c == "I").mean() if n else np.nan
    # detection (primary label)
    flags = static_g.sort_values("epoch").E_hat.to_numpy() > CONST["tau"]
    pers = [(s, L) for s, L, _ in episodes(flags) if classify_length(L) == "P"]
    det = [next((m - s for m in sorted(mut_epochs) if s <= m <= s + L - 1), None) for s, L in pers]
    r["n_persistent"] = len(pers)
    r["detection_rate"] = np.mean([x is not None for x in det]) if pers else np.nan
    hits = [x for x in det if x is not None]
    r["detection_delay"] = np.mean(hits) if hits else np.nan
    # wasted releases
    released, wasted = 0, 0
    for _, row in mut[mut.removed_failed_link.astype(bool)].iterrows():
        link = removed_link(row.mutation)
        if link is None:
            continue
        released += 1
        m, i = int(row.epoch), index[link]
        window = range(m + 1, min(m + d + 3, len(down) - 1) + 1)
        if any(not down[t, i] for t in window):
            wasted += 1
    r["failed_link_releases"], r["wasted_releases"] = released, wasted
    r["wasted_release_rate"] = wasted / released if released else np.nan
    # anchored recovery (anchors = starts of static disconnection episodes)
    sd = static_g.sort_values("epoch").components.to_numpy() > 1
    conn = g.components.to_numpy() == 1
    rec, cens = [], 0
    for s, _, _ in episodes(sd):
        t = next((t for t in range(s, len(conn)) if conn[t]), None)
        if t is None:
            cens += 1
            rec.append(len(conn) - s)
        else:
            rec.append(t - s)
    r["anchored_recovery"] = np.mean(rec) if rec else np.nan
    r["n_anchors"], r["anchors_censored"] = len(rec), cens
    own = [L for _, L, _ in episodes(g.components.to_numpy() > 1)]
    r["own_disconnection_length"] = np.mean(own) if own else np.nan
    if "theta_updates_total" in g and g.theta_updates_total.notna().any():
        r["theta_updates"] = int(g.theta_updates_total.iloc[-1])
        r["theta_final"] = float(g.theta.iloc[-1])
    if "v06_schedule" in g and isinstance(g.v06_schedule.iloc[0], str):
        sched = [int(x) for x in g.v06_schedule.iloc[0].split()]
        r["lag_mean"] = np.mean([a - b for a, b in zip(sorted(mut_epochs), sched)]) if n else np.nan
    return r


# ------------------------------------------------------------------ statistics (protocol 6)
def wilcoxon_p(diff):
    nz = diff[diff != 0]
    if len(nz) == 0:
        return 1.0, 0, True
    return float(stats.wilcoxon(nz, zero_method="wilcox", method="auto").pvalue), len(nz), False


def rank_biserial(diff):
    nz = diff[diff != 0]
    if len(nz) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(nz))
    wp, wm = ranks[nz > 0].sum(), ranks[nz < 0].sum()
    return float((wp - wm) / (wp + wm))


def boot_ci(diff):
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(diff), size=(BOOT_N, len(diff)))
    means = diff[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def t_ci(diff):
    if len(diff) < 2:
        return np.nan, np.nan
    h = stats.t.ppf(0.975, len(diff) - 1) * diff.std(ddof=1) / np.sqrt(len(diff))
    return float(diff.mean() - h), float(diff.mean() + h)


def paired(ps, cell, x, y, metric):
    a = ps[(ps.group == cell) & (ps.arm == x)].set_index("seed")[metric]
    b = ps[(ps.group == cell) & (ps.arm == y)].set_index("seed")[metric]
    j = a.index.intersection(b.index)
    diff = (a.loc[j] - b.loc[j]).dropna().to_numpy(dtype=float)
    return diff


def describe(diff):
    lo, hi = boot_ci(diff) if len(diff) else (np.nan, np.nan)
    tlo, thi = t_ci(diff)
    return {"n": len(diff), "mean_diff": diff.mean() if len(diff) else np.nan, "boot_lo": lo, "boot_hi": hi,
            "t_lo": tlo, "t_hi": thi, "rank_biserial": rank_biserial(diff) if len(diff) else np.nan}


def verdict(p_holm, mean, ci, identical, prec_lo=None):
    if identical:
        return "practically equivalent (identical)"
    if p_holm < 0.05:
        if mean <= -E_MARGIN:
            if prec_lo is not None and not prec_lo > -P_MARGIN:
                return "first arm better on error, precision not shown non-inferior"
            return "first arm meaningfully better" if prec_lo is None else \
                "accumulated debt adds meaningful timing information"
        if mean < 0:
            return "first arm better, below minimum meaningful effect"
        if mean >= E_MARGIN:
            return "second arm meaningfully better"
        return "second arm better, below minimum meaningful effect"
    if -E_MARGIN < ci[0] and ci[1] < E_MARGIN:
        return "practically equivalent"
    return "inconclusive"


def family(ps, pairs, cells, holm_name, primary=False):
    rows = []
    for d, M in cells:
        cell = cell_name(d, M)
        arms = set(ps[ps.group == cell].arm)
        for x, y in pairs:
            if x not in arms or y not in arms:
                rows.append({"cell": cell, "comparison": f"{x}-{y}", "status": "excluded (not calibratable)"})
                continue
            diff = paired(ps, cell, x, y, "E")
            p, nnz, ident = wilcoxon_p(diff)
            row = {"cell": cell, "delay": d, "M": M, "comparison": f"{x}-{y}", "metric": "E", **describe(diff),
                   "wilcoxon_p": p, "n_nonzero": nnz, "identical": ident, "status": "tested"}
            if primary:
                pd_ = paired(ps, cell, x, y, "precision")
                lo, hi = boot_ci(pd_) if len(pd_) else (np.nan, np.nan)
                row.update({"precision_n": len(pd_), "precision_mean_diff": pd_.mean() if len(pd_) else np.nan,
                            "precision_boot_lo": lo, "precision_boot_hi": hi})
            rows.append(row)
    df = pd.DataFrame(rows)
    for c in ("delay", "M", "metric", "n", "mean_diff", "boot_lo", "boot_hi", "t_lo", "t_hi", "rank_biserial",
              "wilcoxon_p", "n_nonzero", "identical") + (("precision_n", "precision_mean_diff", "precision_boot_lo",
                                                           "precision_boot_hi") if primary else ()):
        if c not in df:
            df[c] = np.nan                     # all comparisons excluded (not calibratable): keep a stable schema
    tested = df.status == "tested"
    df["family"] = holm_name
    df["holm_p"] = np.nan
    df.loc[tested, "holm_p"] = holm(df.loc[tested, "wilcoxon_p"]).values
    df["verdict"] = ""
    for i in df.index[tested]:
        r = df.loc[i]
        df.loc[i, "verdict"] = verdict(r.holm_p, r.mean_diff, (r.boot_lo, r.boot_hi), r.identical,
                                       r.precision_boot_lo if primary else None)
    return df


# ------------------------------------------------------------------ main
CONST = {}
EXPLORATORY = ["final_error", "disconnected", "lambda2", "E_second_half", "precision", "false_alarm",
               "detection_rate", "detection_delay", "wasted_release_rate", "anchored_recovery", "pending_link_epochs"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    with open(os.path.join(FROZEN_DIR, "constants.yaml"), encoding="utf-8") as f:
        CONST.update(yaml.safe_load(f))
    out = os.path.join(a.run, "analysis")
    os.makedirs(out, exist_ok=True)
    static = pd.read_csv(os.path.join(a.run, "A0_static", "epochs.csv"))
    a0cfg = load_config(os.path.join(FROZEN_DIR, "A0_static.yaml"))
    seeds = sorted(static.seed.unique())

    labels, traces = {}, {}
    for s in seeds:
        sg = static[static.seed == s].sort_values("epoch")
        deg = sg.E_hat.to_numpy() > CONST["tau"]
        labels[s] = {v: epoch_classes(deg, v) for v in VARIANTS}
        labels[s]["disconnection"] = epoch_classes(sg.components.to_numpy() > 1, "primary")
        traces[s] = rebuild_down(a0cfg, s, sg.n_down_potential.to_numpy())

    rows = []
    groups = [g for g in sorted(os.listdir(a.run)) if os.path.isdir(os.path.join(a.run, g)) and g.startswith("d")]
    for group in ["A0_static"] + groups:
        df = static.assign(arm="A0") if group == "A0_static" else pd.read_csv(os.path.join(a.run, group, "epochs.csv"))
        m_ = re.match(r"d(\d+)_M(\d+)", group)
        for (arm, s), g in df.groupby(["arm", "seed"]):
            if group == "A0_static":
                cells = [cell_name(d, M) for d, M in CELLS]
                d, M = 2, None
            else:
                cells = [group]
                d, M = int(m_.group(1)), (None if group.endswith("_uncapped") else int(m_.group(2)))
            met = run_metrics(g, static[static.seed == s], labels[s], d, M, *traces[s])
            for c in cells:
                rows.append({"group": c, "arm": arm, "seed": s, **met})
    ps = pd.DataFrame(rows)
    ps.to_csv(os.path.join(out, "per_seed_metrics.csv"), index=False)

    metrics = [c for c in ps.columns if c not in ("group", "arm", "seed") and pd.api.types.is_numeric_dtype(ps[c])]
    summ = []
    for (grp, arm), g in ps.groupby(["group", "arm"]):
        for m in metrics:
            v = g[m].dropna().to_numpy(dtype=float)
            lo, hi = t_ci(v - v.mean()) if len(v) > 1 else (np.nan, np.nan)
            summ.append({"group": grp, "arm": arm, "metric": m, "n": len(v), "mean": v.mean() if len(v) else np.nan,
                         "ci95_half": (hi - lo) / 2 if len(v) > 1 else np.nan})
    summary = pd.DataFrame(summ)
    summary.to_csv(os.path.join(out, "summary.csv"), index=False)

    prim = family(ps, [PRIMARY], CELLS, "primary (Holm over 4)", primary=True)
    sec = family(ps, SECONDARY, CELLS, "secondary (Holm over 28)")
    prim.to_csv(os.path.join(out, "primary_tests.csv"), index=False)
    sec.to_csv(os.path.join(out, "secondary_tests.csv"), index=False)

    expl = []
    for d, M in CELLS:
        cell = cell_name(d, M)
        arms = set(ps[ps.group == cell].arm)
        for x, y in [PRIMARY] + SECONDARY + [(a_, "A0") for a_ in sorted(arms - {"A0"})]:
            if x in arms and y in arms:
                for m in EXPLORATORY + ["E"]:
                    expl.append({"cell": cell, "comparison": f"{x}-{y}", "metric": m,
                                 **describe(paired(ps, cell, x, y, m))})
    pd.DataFrame(expl).to_csv(os.path.join(out, "exploratory_diffs.csv"), index=False)

    sens = []
    for d, M in CELLS:
        cell = cell_name(d, M)
        for arm in sorted(set(ps[ps.group == cell].arm) - {"A0"}):
            g = ps[(ps.group == cell) & (ps.arm == arm)]
            for v in ("primary", "S3", "S6", "disconnection"):
                sfx = "" if v == "primary" else f"_{v}"
                sens.append({"analysis": f"label {v}", "cell": cell, "arm": arm,
                             "precision": g["precision" + sfx].mean(), "false_alarm": g["false_alarm" + sfx].mean()})
        for extra, label in ((cell + "_uncapped", "C-2 uncapped"), (cell + "_A2reset", "C-4 A2-reset")):
            g2 = ps[ps.group == extra]
            for arm in sorted(set(g2.arm)):
                gg = g2[g2.arm == arm]
                sens.append({"analysis": label, "cell": cell, "arm": arm, "E": gg.E.mean(),
                             "mutations": gg.mutations.mean(), "precision": gg.precision.mean()})
            if label == "C-2 uncapped" and {"A1", "A3"} <= set(g2.arm):
                dd = paired(ps, extra, "A3", "A1", "E")
                sens.append({"analysis": "C-2 uncapped A3-A1 on E", "cell": cell, **describe(dd)})
            if label == "C-4 A2-reset" and len(g2):
                both = pd.concat([ps[(ps.group == cell) & (ps.arm == "A2")], g2])
                both = both.assign(group="tmp")
                dd = paired(both, "tmp", "A2r", "A2", "E")
                sens.append({"analysis": "C-4 A2r-A2 on E", "cell": cell, **describe(dd)})
    pd.DataFrame(sens).to_csv(os.path.join(out, "sensitivity.csv"), index=False)

    figures(ps, prim, sec, out)
    report(a.run, out, ps, summary, prim, sec)
    print(f"analysis written to {out}")


def figures(ps, prim, sec, out):
    arms = ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    names = {"A0": "Static", "A1": "Reactive", "A2": "Moving avg", "A3": "CUSUM-E", "A4": "CUSUM-ECV",
             "A5": "TCCE-R", "A6": "Random", "A7": "Front-loaded"}
    for metric, label in (("E", "Consensus stress E (0-1, lower is better)"),
                          ("precision", "Precision: share of mutations in persistent episodes"),
                          ("false_alarm", "False-alarm share")):
        fig, axes = plt.subplots(1, 4, figsize=(17, 4.2), sharey=True)
        for ax, (d, M) in zip(axes, CELLS):
            cell = cell_name(d, M)
            vals = [ps[(ps.group == cell) & (ps.arm == a_)][metric].dropna() for a_ in arms]
            means = [v.mean() if len(v) else np.nan for v in vals]
            errs = [stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0 for v in vals]
            colors = ["#2a78d6" if a_ == "A3" else "#eb6834" if a_ == "A1" else "#9aa0a6" for a_ in arms]
            ax.bar(range(len(arms)), means, yerr=errs, color=colors, capsize=3)
            ax.set_xticks(range(len(arms)))
            ax.set_xticklabels([names[a_] for a_ in arms], rotation=45, ha="right", fontsize=8)
            ax.set_title(f"delay {d}, budget {M}", fontsize=10)
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", color="#e5e5e5", lw=0.8)
        axes[0].set_ylabel(label, fontsize=9)
        fig.text(0.01, 0.01, "Mean over held-out seeds; error bars = 95% t-CI. Blue = CUSUM-E (A3), orange = "
                             "Reactive (A1).", fontsize=8, color="#555")
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(os.path.join(out, f"fig_{metric}_by_arm.png"), dpi=140)
        plt.close(fig)
    t = pd.concat([prim, sec])
    t = t[t.status == "tested"].reset_index(drop=True)
    if t.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(t) + 1.5))
    y = np.arange(len(t))[::-1]
    ax.errorbar(t.mean_diff, y, xerr=[t.mean_diff - t.boot_lo, t.boot_hi - t.mean_diff], fmt="o",
                color="#2a78d6", ms=5, capsize=3)
    for v in (-E_MARGIN, 0, E_MARGIN):
        ax.axvline(v, color="#555" if v == 0 else "#bbb", lw=1, ls="-" if v == 0 else "--")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.cell}  {r.comparison}  (Holm p={r.holm_p:.3g})" for r in t.itertuples()], fontsize=7)
    ax.set_xlabel("Paired difference in E (first minus second arm); negative = first arm better; dashed = ±0.02")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_forest_E.png"), dpi=140)
    plt.close(fig)


def report(run, out, ps, summary, prim, sec):
    def tab(df, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in df[cols].itertuples(index=False):
            lines.append("| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in r) + " |")
        return "\n".join(lines)
    L = [f"# v0.6 results ({os.path.basename(run)})", "",
         "Generated automatically by `experiments/analyze_v06.py` from the raw CSVs. "
         "Verdicts follow docs/PROTOCOL_v0.6.md section 6.6; each delay-budget cell is a separate condition.", "",
         f"Constants (frozen): tau={CONST['tau']:.4f}, kappa_E={CONST['kappa_E']:.4f}, kappa_s={CONST['kappa_s']:.4f}", "",
         "## Primary: A3 (CUSUM-E) vs A1 (Reactive) on E", "",
         tab(prim[prim.status == "tested"], ["cell", "n", "mean_diff", "boot_lo", "boot_hi", "rank_biserial",
                                             "wilcoxon_p", "holm_p", "precision_mean_diff", "precision_boot_lo",
                                             "verdict"]), "",
         "## Secondary (E only, Holm over the family)", "",
         tab(sec[sec.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi",
                                           "holm_p", "verdict"]), ""]
    ex = sec[sec.status != "tested"]
    if len(ex):
        L += ["Excluded comparisons (not calibratable):", "", tab(ex, ["cell", "comparison", "status"]), ""]
    piv = summary[summary.metric.isin(["E", "disconnected", "lambda2", "mutations", "precision", "false_alarm",
                                       "detection_rate", "wasted_release_rate", "anchored_recovery"])]
    piv = piv[piv.group.str.fullmatch(r"d\d+_M\d+")].assign(v=lambda d: d["mean"].map("{:.3f}".format) + " ± " +
                                                   d.ci95_half.map("{:.3f}".format))
    L += ["## Means per cell (± 95% t-CI half-width)", ""]
    for grp in sorted(piv.group.unique()):
        p = piv[piv.group == grp].pivot(index="arm", columns="metric", values="v").reset_index()
        L += [f"### {grp}", "", tab(p, list(p.columns)), ""]
    with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
