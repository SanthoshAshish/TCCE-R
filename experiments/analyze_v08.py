"""Analysis of the held-out v0.8 E2 evaluation (docs/PROTOCOL_v0.8.md sections 11-12). Reads results/v0.8/E2/eval only.

  python -m experiments.analyze_v08 [--eval results/v0.8/E2/eval] [--out revision/analysis/E2] [--no-figures]

No simulation is run, nothing is recalibrated and no raw file is modified. Steps:
  1. validate the inputs (arms, cells, seeds 9000-9059, 80 epochs, markers, config hashes, common random numbers, caps);
  2. per-run metrics (protocol section 11) -> per_seed_metrics.csv;
  3. paired tests per section 12: primary family (18), ablation family (48), matched-budget family (12), each Holm-adjusted
     within its family; continuity comparisons are exploratory (unadjusted p, labelled);
  4. exploratory paired differences of the other metrics (no p-values), equal-realised-count subsets;
  5. tables (csv/md), figures (png/pdf), summary.json and run_manifest.json (input hashes, command, versions).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from experiments.analyze import holm  # noqa: E402
from experiments.analyze_v06 import (E_MARGIN, boot_ci, describe, episodes, rank_biserial, t_ci, verdict,  # noqa: E402
                                     wilcoxon_p)
from experiments.v08_common import (ARM_POLICY, CELLS, EVAL_ARMS, EVAL_SEEDS, FROZEN_DIR, SCENARIOS, cell_name,  # noqa: E402
                                    frozen_path, sha256, verify_manifest)
from tccer.config import load_config  # noqa: E402

EVAL_DIR, OUT_DIR = "results/v0.8/E2/eval", "revision/analysis/E2"
T_ROUNDS = 60
EPOCHS = 80
PRIMARY = [("B8", "A1"), ("B8", "A7"), ("H1", "A7")]
ABLATION = [("B2", "A1"), ("B3", "A1"), ("B4", "B2"), ("B4", "B3"), ("B5", "B4"), ("B6", "B5"), ("B8", "B6"), ("B8", "B7")]
MATCHED = [("B8", "A7M"), ("H1", "A7M")]
CONTINUITY = [("A5", "A1"), ("A5", "A7"), ("B8", "A5"), ("H1", "B8"), ("A7", "A1"), ("A7M", "A7"), ("B5", "A1")]
EXPLORATORY_METRICS = ["E_second_half", "disconnected", "disc_episodes", "longest_disc", "anchored_recovery", "worst_E",
                       "ttc_mean", "mutations", "pending_link_epochs", "live_link_releases", "overhead_sum", "lambda2"]
ARM_LABEL = {"A0": "A0 Static", "A1": "A1 Reactive", "A5": "A5 TCCE-R (v0.7)", "A7": "A7 Front-loaded",
             "A7M": "A7M Front-loaded (exactly M)", "B2": "B2 E+C", "B3": "B3 E+V", "B4": "B4 E+C+V",
             "B5": "B5 debt (=A4)", "B6": "B6 debt+pred, fixed", "B7": "B7 RCPR, legacy fb", "B8": "B8 RCPR",
             "H1": "H1 Hybrid-FrontRisk"}
ARM_COLOR = {"A0": "#8a8984", "A1": "#2a78d6", "A5": "#2a78d6", "A7": "#2a78d6", "A7M": "#2a78d6", "B2": "#eb6834",
             "B3": "#eb6834", "B4": "#eb6834", "B5": "#eb6834", "B6": "#eb6834", "B7": "#eb6834", "B8": "#1baf7a",
             "H1": "#6250d6"}                     # blue = baselines, orange = ablation arms, aqua = B8, violet = hybrid
ARM_MARKER = {"A0": "x", "A1": "o", "A5": "s", "A7": "D", "A7M": "^", "B2": "o", "B3": "s", "B4": "D", "B5": "^",
              "B6": "v", "B7": "P", "B8": "o", "H1": "*"}
CELL_LIST = [cell_name(s, M) for s, M in CELLS]


# ---------------------------------------------------------------------------------------------------- validation
def load_and_validate(eval_dir):
    problems, info = [], {}
    problems_add = problems.append
    if not os.path.exists(os.path.join(eval_dir, "COMPLETE")):
        problems_add("COMPLETE marker missing")
    ri = json.load(open(os.path.join(eval_dir, "run_info.json"), encoding="utf-8"))
    info["run_info"] = {k: ri[k] for k in ("mode", "n_runs", "seconds", "complete") if k in ri}
    info["git_commit"], info["git_dirty"] = ri["git"]["commit"], ri["git"]["dirty_files"]
    if not ri.get("complete") or ri.get("n_runs") != 4500:
        problems_add(f"run_info says complete={ri.get('complete')} n_runs={ri.get('n_runs')} (expected True, 4500)")
    if list(ri["seeds"]) != list(EVAL_SEEDS):
        problems_add("run_info seeds differ from 9000-9059")
    if ri["git"]["dirty_files"]:
        problems_add(f"tracked files were dirty at run time: {ri['git']['dirty_files'][:3]}")
    try:
        verify_manifest(os.path.join(FROZEN_DIR, "MANIFEST.sha256"))
        info["frozen_manifest"] = "verifies"
    except Exception as e:  # noqa: BLE001
        problems_add(f"frozen manifest: {e}")
    frames = []
    expected_groups = {f"A0_{s}": ["A0"] for s in SCENARIOS}
    expected_groups.update({c: list(EVAL_ARMS) for c in CELL_LIST})
    seed_set = set(EVAL_SEEDS)
    total_runs = 0
    for group, arms in expected_groups.items():
        path = os.path.join(eval_dir, group, "epochs.csv")
        if not os.path.exists(path):
            problems_add(f"missing {path}")
            continue
        df = pd.read_csv(path, low_memory=False)
        df["group"] = group
        if set(df.arm.unique()) != set(arms):
            problems_add(f"{group}: arms {sorted(df.arm.unique())} != {sorted(arms)}")
        for arm in arms:
            a = df[df.arm == arm]
            if set(a.seed.unique()) != seed_set:
                problems_add(f"{group}/{arm}: seeds {len(a.seed.unique())} distinct, expected exactly 9000-9059")
            g = a.groupby("seed").epoch.agg(["count", "min", "max", "nunique"])
            bad = g[(g["count"] != EPOCHS) | (g["min"] != 0) | (g["max"] != EPOCHS - 1) | (g["nunique"] != EPOCHS)]
            if len(bad):
                problems_add(f"{group}/{arm}: {len(bad)} runs with duplicated/missing/malformed epochs, e.g. seed {bad.index[0]}")
            if a.policy.nunique() != 1 or a.policy.iloc[0] != ARM_POLICY[arm]:
                problems_add(f"{group}/{arm}: policy column {a.policy.unique()} != {ARM_POLICY[arm]}")
            for col in ("E_hat", "components", "n_mutations", "configured_edges", "budget"):
                if a[col].isna().any():
                    problems_add(f"{group}/{arm}: NaN in {col}")
            total_runs += a.seed.nunique()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    info["rows"], info["runs_found"] = int(len(df)), int(total_runs)
    if total_runs != 4500 or len(df) != 4500 * EPOCHS:
        problems_add(f"found {total_runs} runs / {len(df)} rows, expected 4500 / {4500 * EPOCHS}")
    # configuration hashes vs the frozen files
    for key, h in ri["config_sha256"].items():
        group, arm = key.split("/")
        s = group.replace("A0_", "") if arm == "A0" else group.rsplit("_M", 1)[0]
        M = None if arm == "A0" else int(group.rsplit("_M", 1)[1])
        if sha256(frozen_path(FROZEN_DIR, arm, s, M)) != h:
            problems_add(f"config hash mismatch for {key}")
    # caps, strict budget, static, rewires only, monotone mutation counter, common random numbers
    for (group, arm), a in df.groupby(["group", "arm"]):
        if arm == "A0":
            if (a.n_mutations != 0).any():
                problems_add(f"{group}: Static mutated")
            continue
        M = int(group.rsplit("_M", 1)[1])
        if a.n_mutations.max() > M:
            problems_add(f"{group}/{arm}: n_mutations {a.n_mutations.max()} exceeds cap {M}")
        if (a.configured_edges > a.budget).any():
            problems_add(f"{group}/{arm}: configured edges exceed the budget")
        if not set(a.mutation_kind.dropna().unique()) <= {"", "rewire"}:
            problems_add(f"{group}/{arm}: non-rewire mutation kinds {a.mutation_kind.unique()}")
        mono = a.sort_values(["seed", "epoch"]).groupby("seed").n_mutations.apply(lambda x: bool((np.diff(x.to_numpy()) >= 0).all()))
        if not mono.all():
            problems_add(f"{group}/{arm}: n_mutations decreases within a run")
    df["scenario"] = df.group.str.replace("A0_", "").str.replace(r"_M\d$", "", regex=True)
    crn_bad = 0
    for (scen, seed), g in df.groupby(["scenario", "seed"]):
        ref = None
        for (grp, arm), a in g.groupby(["group", "arm"]):
            sig = (tuple(a.sort_values("epoch").n_down_potential), tuple(a.sort_values("epoch").n_burst_down))
            ref = ref or sig
            crn_bad += sig != ref
    if crn_bad:
        problems_add(f"common random numbers violated in {crn_bad} (scenario, seed, arm) series")
    info["crn_checked"] = True
    info["problems"] = problems
    return df, info


# ---------------------------------------------------------------------------------------------------- metrics
def run_metrics(g, static_g):
    g = g.sort_values("epoch")
    E = g.E_hat.to_numpy()
    comps = g.components.to_numpy()
    disc = comps > 1
    eps = episodes(disc)
    mut = g[g.select_outcome == "mutated"]
    last = g.iloc[-1]
    conv = g.conv_round.to_numpy()
    ttc = np.where(conv < 0, T_ROUNDS, conv)
    r = {"E": E.mean(), "E_second_half": E[EPOCHS // 2:].mean(), "worst_E": E.max(), "lambda2": g.lambda2.mean(),
         "disconnected": disc.mean(), "disc_episodes": len(eps), "longest_disc": max([L for _, L, _ in eps], default=0),
         "own_disc_length": np.mean([L for _, L, _ in eps]) if eps else np.nan,
         "ttc_mean": ttc.mean(), "nonconverged_share": (conv < 0).mean(),
         "mutations": int(last.n_mutations), "attempts": last.get("v06_attempts_total", np.nan),
         "failed_attempts": last.get("v06_failed_attempts_total", np.nan),
         "pending_link_epochs": float(g.pending_links.sum()),
         "live_link_releases": int((~mut.removed_failed_link.astype(bool)).sum()),
         "failed_link_releases": int(mut.removed_failed_link.astype(bool).sum())}
    r["overhead_sum"] = r["pending_link_epochs"] + r["live_link_releases"]
    r["intended"] = last.get("v06_intended", np.nan)
    sd = static_g.sort_values("epoch").components.to_numpy() > 1
    conn = comps == 1
    rec, cens = [], 0
    for s, _, _ in episodes(sd):
        t = next((t for t in range(s, len(conn)) if conn[t]), None)
        if t is None:
            cens += 1
            rec.append(len(conn) - s)
        else:
            rec.append(t - s)
    r["anchored_recovery"] = float(np.mean(rec)) if rec else np.nan
    r["n_anchors"], r["anchors_censored"] = len(rec), cens
    s_, f_, n_ = (last.get(c, np.nan) for c in ("theta_success_total", "theta_failure_total", "theta_neutral_total"))
    r["fb_success"], r["fb_failure"], r["fb_neutral"] = s_, f_, n_
    r["adapt_success_rate"] = s_ / (s_ + f_) if (s_ == s_ and f_ == f_ and s_ + f_ > 0) else np.nan
    for c in ("rcpr_deferred", "rcpr_risk_filtered", "hyb_n_front"):
        r[c] = last.get(c, np.nan)
    r["theta_final"] = last.get("theta", np.nan)
    return r


def per_seed_metrics(df):
    rows = []
    for (group, arm, seed), g in df.groupby(["group", "arm", "seed"]):
        if arm == "A0":
            continue
        scen = g.scenario.iloc[0]
        static_g = df[(df.group == f"A0_{scen}") & (df.arm == "A0") & (df.seed == seed)]
        r = run_metrics(g, static_g)
        r.update({"group": group, "scenario": scen, "M": int(group.rsplit("_M", 1)[1]), "arm": arm, "seed": seed})
        rows.append(r)
    for (group, seed), g in df[df.arm == "A0"].groupby(["group", "seed"]):
        r = run_metrics(g, g)
        r.update({"group": group, "scenario": g.scenario.iloc[0], "M": np.nan, "arm": "A0", "seed": seed})
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------- statistics
def pair_diff(ps, cell, x, y, metric):
    a = ps[(ps.group == cell) & (ps.arm == x)].set_index("seed")[metric]
    b = ps[(ps.group == cell) & (ps.arm == y)].set_index("seed")[metric]
    j = a.index.intersection(b.index)
    return (a.loc[j] - b.loc[j]).dropna().to_numpy(dtype=float)


def test_family(ps, pairs, name, adjust=True):
    rows = []
    for cell in CELL_LIST:
        arms = set(ps[ps.group == cell].arm)
        for x, y in pairs:
            if x not in arms or y not in arms:
                rows.append({"cell": cell, "comparison": f"{x}-{y}", "family": name, "status": "excluded (arm missing)"})
                continue
            d = pair_diff(ps, cell, x, y, "E")
            p, nnz, ident = wilcoxon_p(d)
            rows.append({"cell": cell, "comparison": f"{x}-{y}", "first": x, "second": y, "family": name, "metric": "E",
                         **describe(d), "dz": float(d.mean() / d.std(ddof=1)) if len(d) > 1 and d.std(ddof=1) > 0 else np.nan,
                         "wilcoxon_p": p, "n_nonzero": nnz, "identical": ident, "status": "tested"})
    df = pd.DataFrame(rows)
    tested = df.status == "tested"
    df["holm_p"] = np.nan
    if adjust:
        df.loc[tested, "holm_p"] = holm(df.loc[tested, "wilcoxon_p"]).values
    df["verdict"] = ""
    for i in df.index[tested]:
        r = df.loc[i]
        if adjust:
            df.loc[i, "verdict"] = verdict(r.holm_p, r.mean_diff, (r.boot_lo, r.boot_hi), r.identical)
        else:                                   # exploratory: no adjusted p; practical assessment from the CI only
            lo, hi = r.boot_lo, r.boot_hi
            df.loc[i, "verdict"] = ("CI within +-0.02 (unadjusted exploratory)" if (-E_MARGIN < lo and hi < E_MARGIN)
                                    else "CI excludes 0, beyond margin possible" if (lo > 0 or hi < 0) else "inconclusive")
    df["tests_in_family"] = int(tested.sum())
    return df


def equal_count_tests(ps, pairs):
    rows = []
    for cell in CELL_LIST:
        for x, y in pairs:
            a = ps[(ps.group == cell) & (ps.arm == x)].set_index("seed")
            b = ps[(ps.group == cell) & (ps.arm == y)].set_index("seed")
            j = [s for s in a.index.intersection(b.index) if a.at[s, "mutations"] == b.at[s, "mutations"]]
            d = (a.loc[j, "E"] - b.loc[j, "E"]).to_numpy(dtype=float)
            rows.append({"cell": cell, "comparison": f"{x}-{y}", "n_equal_count_seeds": len(j), **(describe(d) if len(d) >= 5 else {}),
                         "note": "exploratory; fewer than 5 equal-count seeds: not estimated" if len(d) < 5 else "exploratory"})
    return pd.DataFrame(rows)


def exploratory_metric_diffs(ps, pairs):
    rows = []
    for cell in CELL_LIST:
        for x, y in pairs:
            for m in EXPLORATORY_METRICS:
                d = pair_diff(ps, cell, x, y, m)
                if len(d) < 5:
                    rows.append({"cell": cell, "comparison": f"{x}-{y}", "metric": m, "n": len(d)})
                    continue
                lo, hi = boot_ci(d)
                rows.append({"cell": cell, "comparison": f"{x}-{y}", "metric": m, "n": len(d), "mean_diff": d.mean(),
                             "median_diff": np.median(d), "boot_lo": lo, "boot_hi": hi})
    return pd.DataFrame(rows)


def summary_table(ps):
    rows = []
    for (cell, arm), g in ps.groupby(["group", "arm"]):
        r = {"cell": cell, "arm": arm, "n_seeds": len(g)}
        for m in ["E"] + EXPLORATORY_METRICS + ["nonconverged_share", "adapt_success_rate", "rcpr_deferred", "failed_attempts"]:
            v = g[m].dropna().to_numpy(dtype=float)
            r[m + "_mean"] = v.mean() if len(v) else np.nan
            r[m + "_sd"] = v.std(ddof=1) if len(v) > 1 else np.nan
            if m == "E" and len(v) > 1:
                r["E_ci_lo"], r["E_ci_hi"] = t_ci(v)
            r[m + "_n"] = len(v)
        rows.append(r)
    return pd.DataFrame(rows)


def count_table(ps):
    rows = []
    for (cell, arm), g in ps[ps.arm != "A0"].groupby(["group", "arm"]):
        M = int(cell.rsplit("_M", 1)[1])
        rows.append({"cell": cell, "arm": arm, "M": M, "mean_mutations": g.mutations.mean(), "min": g.mutations.min(),
                     "max": g.mutations.max(), "share_at_cap": (g.mutations >= M).mean(),
                     "mean_intended": g.intended.mean() if g.intended.notna().any() else np.nan,
                     "mean_failed_attempts": g.failed_attempts.mean(), "mean_deferred": g.rcpr_deferred.mean()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------- figures
def _style():
    plt.rcParams.update({"figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
                         "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e", "xtick.color": "#52514e",
                         "ytick.color": "#52514e", "text.color": "#0b0b0b", "font.size": 9, "axes.titlesize": 9.5,
                         "axes.spines.top": False, "axes.spines.right": False, "grid.color": "#e6e5e0", "grid.linewidth": 0.6})


def _save(fig, out, name):
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out, "figures", f"{name}.{ext}"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_E_by_cell(summ, out):
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), sharex=False)
    order = ["A1", "A5", "A7", "A7M", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "H1"]
    for ax, cell in zip(axes.ravel(), CELL_LIST):
        s = summ[summ.cell == cell].set_index("arm")
        for i, arm in enumerate(order):
            if arm not in s.index:
                continue
            r = s.loc[arm]
            ax.errorbar(r.E_mean, i, xerr=[[r.E_mean - r.E_ci_lo], [r.E_ci_hi - r.E_mean]], fmt=ARM_MARKER[arm],
                        color=ARM_COLOR[arm], ms=6, capsize=2, lw=1.2, mec="#fcfcfb")
        sc = cell.rsplit("_M", 1)[0]
        st = summ[(summ.cell == f"A0_{sc}")]
        if len(st):
            ax.axvline(st.E_mean.iloc[0], color=ARM_COLOR["A0"], ls="--", lw=1)
            ax.text(st.E_mean.iloc[0], -0.9, " Static", color="#52514e", fontsize=7.5, va="center")
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([ARM_LABEL[a] for a in order], fontsize=8)
        ax.invert_yaxis()
        ax.grid(axis="x")
        ax.set_title(cell.replace("_", " "))
        ax.set_xlabel("mean E (95% t-interval, 60 seeds)")
    fig.suptitle("Held-out E2: mean consensus error by arm and cell (lower is better)", y=1.0)
    fig.tight_layout()
    _save(fig, out, "fig_E_by_cell")


def _forest(tests, comps, title, out, name, ncols=None):
    comps = [c for c in comps if c in set(tests.comparison)]
    ncols = ncols or min(4, len(comps))
    nrows = int(np.ceil(len(comps) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.6 * ncols, 2.7 * nrows + 0.6), sharey=True, squeeze=False)
    for ax, comp in zip(axes.ravel(), comps):
        t = tests[(tests.comparison == comp) & (tests.status == "tested")].set_index("cell").reindex(CELL_LIST)
        for i, cell in enumerate(CELL_LIST):
            r = t.loc[cell]
            if pd.isna(r.mean_diff):
                continue
            sig = r.holm_p < 0.05 if "holm_p" in r and not pd.isna(r.holm_p) else False
            ax.errorbar(r.mean_diff, i, xerr=[[r.mean_diff - r.boot_lo], [r.boot_hi - r.mean_diff]], fmt="o",
                        color="#2a78d6" if sig else "#8a8984", ms=5.5, capsize=2, lw=1.3, mec="#fcfcfb")
        ax.axvline(0, color="#52514e", lw=0.8)
        ax.axvspan(-E_MARGIN, E_MARGIN, color="#cde2fb", alpha=0.45, lw=0)
        ax.set_title(comp.replace("-", " minus "), fontsize=9)
        ax.set_yticks(range(len(CELL_LIST)))
        ax.set_yticklabels([c.replace("_", " ") for c in CELL_LIST], fontsize=7.5)
        ax.invert_yaxis()
        ax.grid(axis="x")
        ax.set_xlabel("paired dE (negative: first arm lower error)", fontsize=8)
    for ax in axes.ravel()[len(comps):]:
        ax.axis("off")
    fig.suptitle(title + "  [blue: Holm p < 0.05; grey: not significant; band: +-0.02 margin; bars: 95% bootstrap CI]", y=1.0, fontsize=9.5)
    fig.tight_layout()
    _save(fig, out, name)


def fig_scatter(summ, xcol, xlabel, name, out, title):
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.2))
    for ax, cell in zip(axes.ravel(), CELL_LIST):
        s = summ[summ.cell == cell]
        for r in s.itertuples():
            ax.scatter(getattr(r, xcol), r.E_mean, marker=ARM_MARKER[r.arm], color=ARM_COLOR[r.arm], s=46, zorder=3,
                       edgecolor="#fcfcfb", linewidth=0.8)
            ax.annotate(r.arm, (getattr(r, xcol), r.E_mean), textcoords="offset points", xytext=(4, 3), fontsize=7.5, color="#52514e")
        ax.set_title(cell.replace("_", " "))
        ax.set_xlabel(xlabel)
        ax.set_ylabel("mean E")
        ax.grid(True)
    fig.suptitle(title, y=1.0)
    fig.tight_layout()
    _save(fig, out, name)


def fig_resilience(summ, out):
    metrics = [("disconnected_mean", "disconnected fraction"), ("longest_disc_mean", "longest disconnection (epochs)"),
               ("anchored_recovery_mean", "anchored recovery (epochs)"), ("worst_E_mean", "worst-case E (per-seed max)")]
    order = ["A1", "A5", "A7", "A7M", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "H1"]
    fig, axes = plt.subplots(len(metrics), 6, figsize=(17, 9), sharey=True)
    for j, (col, lab) in enumerate(metrics):
        for k, cell in enumerate(CELL_LIST):
            ax = axes[j, k]
            s = summ[summ.cell == cell].set_index("arm")
            for i, arm in enumerate(order):
                if arm in s.index and not pd.isna(s.loc[arm, col]):
                    ax.scatter(s.loc[arm, col], i, marker=ARM_MARKER[arm], color=ARM_COLOR[arm], s=34, edgecolor="#fcfcfb", linewidth=0.7, zorder=3)
            ax.set_yticks(range(len(order)))
            ax.set_yticklabels([ARM_LABEL[a].split(" ")[0] for a in order], fontsize=7.5)
            ax.invert_yaxis()
            ax.grid(axis="x")
            if j == 0:
                ax.set_title(cell.replace("_", " "), fontsize=8.5)
            if k == 0:
                ax.set_ylabel(lab, fontsize=8)
    fig.suptitle("Resilience measures by arm and cell (means over 60 seeds; no uncertainty shown here, see tables)", y=1.0)
    fig.tight_layout()
    _save(fig, out, "fig_resilience")


def fig_counts(counts, out):
    order = ["A1", "A5", "A7", "A7M", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "H1"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.5))
    for ax, cell in zip(axes.ravel(), CELL_LIST):
        c = counts[counts.cell == cell].set_index("arm")
        M = int(cell.rsplit("_M", 1)[1])
        for i, arm in enumerate(order):
            r = c.loc[arm]
            ax.hlines(i, r["min"], r["max"], color="#c3c2b7", lw=2.5, zorder=1)
            ax.scatter(r.mean_mutations, i, marker=ARM_MARKER[arm], color=ARM_COLOR[arm], s=34, zorder=3, edgecolor="#fcfcfb", linewidth=0.7)
        ax.axvline(M, color="#52514e", ls=":", lw=1)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([ARM_LABEL[a] for a in order], fontsize=8)
        ax.invert_yaxis()
        ax.grid(axis="x")
        title = cell.replace("_", " ")
        if cell == "S2_rgg40_background_M6":
            title += "  (B8 threshold 0.0145: calibration limit)"
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("realised mutations per run")
    fig.suptitle("Realised mutation counts in the held-out run (dot: mean, bar: min-max, dotted line: cap M)", y=1.0)
    fig.tight_layout()
    _save(fig, out, "fig_realised_counts")


# ---------------------------------------------------------------------------------------------------- reporting
def md_table(df, cols, fmt=None):
    fmt = fmt or {}
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append("" if np.isnan(v) else (f"{v:.2e}" if c in ("wilcoxon_p", "holm_p") else f"{v:.4f}"))
            else:
                cells.append(str(v))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def write_report(out, info, prim, abl, mat, cont, summ, counts, eqc):
    cols = ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi", "rank_biserial", "wilcoxon_p", "holm_p", "verdict"]
    L = ["# E2 analysis (held-out seeds 9000-9059)", "",
         f"Inputs: `{EVAL_DIR}` (commit `{info['git_commit'][:7]}`, 4,500 runs, 80 epochs each). Frozen configuration: "
         f"`configs/v0.8/frozen` (manifest {info.get('frozen_manifest')}). Generated by `python -m experiments.analyze_v08`.", "",
         "## Validation", "", ("**All input checks passed**: arms, cells, seeds 9000-9059, 80 epochs per run, COMPLETE marker, config hashes, "
                               "caps, strict budget, rewires only, common random numbers across all arms of a (scenario, seed).")
         if not info["problems"] else "**Problems found:**\n" + "\n".join(f"- {p}" for p in info["problems"]), "",
         "## Reading guide",
         "- Differences are first arm minus second arm in per-seed mean consensus error E; negative = first arm lower error (better). "
         "Margin for a meaningful effect: 0.02. Wilcoxon signed-rank p, Holm-adjusted within each family; 95% bootstrap CI (10,000 resamples). "
         "'practically equivalent' requires Holm p >= 0.05 AND the CI inside +-0.02; otherwise a non-significant result is 'inconclusive'.",
         "- **Calibration limitation:** B5-B8 and H1 share B8's Theta0, which in S2 at M=6 is 0.0145 (the lowest of all; the trigger fires whenever the "
         "cooldown allows) -- see the realised-count table. B5/B6/B7/H1 were not calibrated for count; counts differ between arms.", "",
         "## Primary family (18 tests, Holm over 18)", "", md_table(prim[prim.status == "tested"], cols), "",
         "## Matched-budget family: vs A7M, exactly M scheduled attempts (12 tests, Holm over 12)", "",
         md_table(mat[mat.status == "tested"], cols), "",
         "## Ablation family (48 tests, Holm over 48)", "", md_table(abl[abl.status == "tested"], cols), "",
         "## Exploratory continuity comparisons (unadjusted p shown in CSV only; no claims)", "",
         md_table(cont[cont.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi", "verdict"]), "",
         "## Realised mutation counts (held-out)", "",
         md_table(counts, ["cell", "arm", "mean_mutations", "min", "max", "share_at_cap", "mean_intended", "mean_failed_attempts", "mean_deferred"]), "",
         "## Mean E per arm and cell", "",
         md_table(summ[~summ.arm.eq("A0")].sort_values(["cell", "arm"]), ["cell", "arm", "E_mean", "E_ci_lo", "E_ci_hi", "disconnected_mean",
                                                                         "longest_disc_mean", "anchored_recovery_mean", "worst_E_mean", "mutations_mean"]), "",
         "## Metrics not computed", "",
         "- Wasted releases, precision, false-alarm and detection rates (v0.6/v0.7 episode labelling) are not part of the protocol section 11 set and need the "
         "failure-trace rebuild of `analyze_v06`; not computed here.",
         "- Time to consensus: `conv_round` is -1 in most epochs (the error tolerance eps = 0.01 is rarely reached within 60 rounds); "
         "`ttc_mean` censors at 60 and `nonconverged_share` is reported, so it carries little information.",
         "- Adaptation success rate exists only for arms that update Theta (A5, B7, B8, H1); NaN elsewhere.", ""]
    open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default=EVAL_DIR)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--allow-problems", action="store_true", help="continue despite validation problems (they are recorded)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    df, info = load_and_validate(a.eval)
    json.dump(info, open(os.path.join(a.out, "validation.json"), "w"), indent=2, default=str)
    print(f"validation: {len(info['problems'])} problems; runs found {info['runs_found']}")
    if info["problems"] and not a.allow_problems:
        for p in info["problems"]:
            print(" -", p)
        raise SystemExit("input validation failed; nothing analysed (see validation.json)")
    ps = per_seed_metrics(df)
    ps.to_csv(os.path.join(a.out, "per_seed_metrics.csv"), index=False)
    prim = test_family(ps, PRIMARY, "primary")
    abl = test_family(ps, ABLATION, "ablation")
    mat = test_family(ps, MATCHED, "matched-budget")
    cont = test_family(ps, CONTINUITY, "exploratory-continuity", adjust=False)
    for name, t in (("primary_tests", prim), ("ablation_tests", abl), ("matched_budget_tests", mat), ("exploratory_continuity_tests", cont)):
        t.to_csv(os.path.join(a.out, name + ".csv"), index=False)
    eqc = equal_count_tests(ps, PRIMARY + MATCHED)
    eqc.to_csv(os.path.join(a.out, "equal_count_tests.csv"), index=False)
    expl = exploratory_metric_diffs(ps, PRIMARY + MATCHED + ABLATION)
    expl.to_csv(os.path.join(a.out, "exploratory_metric_diffs.csv"), index=False)
    summ = summary_table(ps)
    summ.to_csv(os.path.join(a.out, "summary_by_arm_cell.csv"), index=False)
    counts = count_table(ps)
    counts.to_csv(os.path.join(a.out, "realised_counts.csv"), index=False)
    write_report(a.out, info, prim, abl, mat, cont, summ, counts, eqc)
    if not a.no_figures:
        _style()
        fig_E_by_cell(summ, a.out)
        _forest(pd.concat([prim, mat]), ["B8-A1", "B8-A7", "H1-A7", "B8-A7M", "H1-A7M"], "Primary and matched-budget comparisons", a.out, "fig_primary_forest", ncols=5)
        _forest(abl, [f"{x}-{y}" for x, y in ABLATION], "Ablation steps", a.out, "fig_ablation_forest", ncols=4)
        sm = summ[~summ.arm.eq("A0")].assign(cell=lambda d: d.cell)
        fig_scatter(sm, "mutations_mean", "realised mutations per run", "fig_tradeoff_mutations", a.out, "Error vs realised reconfiguration (per cell)")
        fig_scatter(sm, "overhead_sum_mean", "overhead: pending link-epochs + live-link releases", "fig_tradeoff_overhead", a.out, "Error vs reconfiguration overhead (per cell)")
        fig_resilience(sm, a.out)
        fig_counts(counts, a.out)
    # headline numbers + manifest
    def row(t, cell, comp):
        r = t[(t.cell == cell) & (t.comparison == comp)].iloc[0]
        return {k: (None if pd.isna(r[k]) else (float(r[k]) if k not in ("verdict",) else r[k])) for k in ("mean_diff", "boot_lo", "boot_hi", "holm_p", "verdict")}
    summary = {"n_runs": info["runs_found"], "validation_problems": info["problems"],
               "primary": {f"{c}|{comp}": row(prim, c, comp) for c in CELL_LIST for comp in ("B8-A1", "B8-A7", "H1-A7")},
               "matched": {f"{c}|{comp}": row(mat, c, comp) for c in CELL_LIST for comp in ("B8-A7M", "H1-A7M")}}
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=2, default=str)
    inputs = {}
    for dp, _, fs in os.walk(a.eval):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            inputs[p.replace("\\", "/")] = sha256(p)
    for f in sorted(os.listdir(FROZEN_DIR)):
        inputs[f"{FROZEN_DIR}/{f}"] = sha256(os.path.join(FROZEN_DIR, f))
    import scipy
    git = lambda *x: subprocess.run(["git", *x], capture_output=True, text=True).stdout.strip()
    json.dump({"command": "python -m experiments.analyze_v08 " + " ".join(sys.argv[1:]), "script_sha256": sha256(__file__),
               "git_commit": git("rev-parse", "HEAD"), "git_dirty_tracked": [l for l in git("status", "--porcelain").splitlines() if not l.startswith("??")],
               "python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
               "matplotlib": matplotlib.__version__, "bootstrap": {"n": 10000, "seed": 20261010}, "margin": E_MARGIN,
               "families": {"primary": PRIMARY, "ablation": ABLATION, "matched": MATCHED, "continuity_exploratory": CONTINUITY},
               "exclusions": "none (all 4,500 runs analysed)" if not info["problems"] else info["problems"],
               "input_sha256": inputs}, open(os.path.join(a.out, "run_manifest.json"), "w"), indent=1, default=str)
    print("analysis written to", a.out)


if __name__ == "__main__":
    main()
