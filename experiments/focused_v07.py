"""Focused v0.7 comparison: A1 Reactive vs A3 CUSUM-E vs A5 TCCE-R on the three v0.7 scenarios.

Design, run counts and decision rules: docs/FOCUSED_v0.7_PLAN.md. This is NOT the pre-registered eight-method
evaluation (docs/PROTOCOL_v0.7.md): it uses different seeds and a smaller, quicker calibration, and it is labelled
exploratory. Everything else is reused unchanged: simulator, policies (tccer/policies/v06.py), scenarios
(configs/v0.7/scenarios), count-matching calibration rule (calibrate_v06.choose), metrics and statistics
(analyze_v06 / analyze_v07 helpers).

  python -m experiments.focused_v07 --stage all              # calibrate -> freeze -> evaluate -> analyze
  python -m experiments.focused_v07 --stage calibrate|eval|analyze
  python -m experiments.focused_v07 --stage all --smoke      # development seeds, tiny grid, separate folder

Stages:
  calibrate  seeds 400-419 only. A0 static -> tau, kappa_E, kappa_s per scenario. A1/A3/A5 over a threshold grid
             (capped at CAL_CAP mutations to bound run time) -> mean count per threshold -> the threshold whose mean
             count is closest to M (ties: larger), feasible if within +-15% of M. Mutation counts only; no outcome
             metric is used. Writes frozen configs + SHA-256 manifest to configs/v0.7_focused/frozen. Refuses to
             recalibrate once frozen.
  eval       seeds 500-559 only, once. A0 once per scenario and seed; A1/A3/A5 per cell under the cap M.
  analyze    paired statistics on consensus stress E (Holm-corrected, margin 0.02) + exploratory metrics + figures.
"""
import argparse
import os
import re
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy import stats

import experiments.analyze_v06 as an
import experiments.analyze_v07 as a7
from experiments.calibrate_v06 import choose, static_constants
from experiments.calibrate_v07 import arm_config
from experiments.run_v06 import check_eval_allowed
from experiments.v07_common import (ARM_POLICY, FEASIBILITY, SCENARIOS, TAU_QUANTILE,
                                    assert_seeds, cell_name, git_state, run_tasks, scenario_config, sha256,
                                    verify_manifest, versions, write_json, write_manifest)
from tccer.config import load_config, replace, save_config

CAL_SEEDS = tuple(range(400, 420))
EVAL_SEEDS = tuple(range(500, 560))
SMOKE_CAL_SEEDS = (300, 301)
SMOKE_EVAL_SEEDS = (302, 303)
ARMS = ("A1", "A3", "A5")
BUDGETS = (3, 6)
CELLS = tuple((s, M) for s in SCENARIOS for M in BUDGETS)
CAL_CAP = 12                                   # >= 2 x the largest M; bounds the cost of low-threshold calibration runs
GRIDS = {"A1": np.linspace(0.50, 0.90, 24),    # ranges around the v0.6 calibrated thresholds, same resolution as the
         "A3": np.geomspace(0.30, 4.0, 24),    # 40-point protocol grid (about 0.75 mutations per grid step)
         "A5": np.geomspace(0.50, 6.0, 24)}
SMOKE_POINTS = 5
MARGIN = 0.02
PRIMARY = [("A5", "A1"), ("A3", "A1")]
SECONDARY = [("A5", "A3")]
EXPLORATORY = ["final_error", "disconnected", "lambda2", "E_second_half", "precision", "false_alarm",
               "detection_rate", "anchored_recovery", "mutations", "pending_link_epochs", "live_link_releases",
               "wasted_release_rate"]
COLORS = {"A0": "#9aa0a6", "A1": "#eb6834", "A3": "#1baf7a", "A5": "#2a78d6"}
NAMES = {"A0": "Static (reference)", "A1": "Reactive", "A3": "CUSUM-E", "A5": "TCCE-R"}


class Layout:
    """Folders and seeds for the real run or the smoke run."""

    def __init__(self, smoke):
        self.smoke = smoke
        self.cal_seeds = SMOKE_CAL_SEEDS if smoke else CAL_SEEDS
        self.eval_seeds = SMOKE_EVAL_SEEDS if smoke else EVAL_SEEDS
        self.cal_allowed = range(300, 320) if smoke else range(400, 420)
        self.eval_allowed = range(300, 320) if smoke else range(500, 560)
        root = "results/v0.7_focused/smoke" if smoke else "results/v0.7_focused"
        self.frozen = os.path.join(root, "frozen") if smoke else "configs/v0.7_focused/frozen"
        self.cal_out = os.path.join(root, "calibration")
        self.run_out = os.path.join(root, "run") if smoke else os.path.join(root, "eval")
        self.manifest = os.path.join(self.frozen, "MANIFEST.sha256")

    def grid(self, arm):
        g = GRIDS[arm]
        return g[np.linspace(0, len(g) - 1, SMOKE_POINTS).round().astype(int)] if self.smoke else g

    def path(self, arm, scenario, M=None):
        name = f"A0_{scenario}.yaml" if arm == "A0" else f"{arm}_{cell_name(scenario, M)}.yaml"
        return os.path.join(self.frozen, name)


# ------------------------------------------------------------------ stage 1: calibration
def calibrate(L, workers):
    assert_seeds(L.cal_seeds, L.cal_allowed, "focused calibration")
    if os.path.exists(L.manifest):
        raise SystemExit(f"{L.manifest} exists: calibration is frozen; refusing to recalibrate")
    for d in (L.frozen, L.cal_out):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    n = len(L.cal_seeds)

    res = run_tasks([(scenario_config(s), seed, "static", "rows") for s in SCENARIOS for seed in L.cal_seeds], workers)
    const = {}
    for i, s in enumerate(SCENARIOS):
        df = pd.DataFrame([r for rows in res[i * n:(i + 1) * n] for r in rows])
        const[s] = static_constants(df)
    print("constants:", {s: {k: round(v, 4) for k, v in c.items()} for s, c in const.items()}, flush=True)

    tasks, keys = [], []
    for s in SCENARIOS:
        base = scenario_config(s)
        for arm in ARMS:
            for gi, thr in enumerate(L.grid(arm)):
                cfg = arm_config(base, arm, thr, const[s], CAL_CAP)
                for seed in L.cal_seeds:
                    tasks.append((cfg, seed, ARM_POLICY[arm], "count"))
                    keys.append((s, arm, gi, float(thr), seed))
    print(f"calibration grid: {len(tasks)} runs (cap {CAL_CAP}) on {workers} workers", flush=True)
    counts = run_tasks(tasks, workers)
    cdf = pd.DataFrame(keys, columns=["scenario", "arm", "grid_index", "threshold", "seed"]).assign(count=counts)
    cdf.to_csv(os.path.join(L.cal_out, "calibration_counts.csv"), index=False)
    means = cdf.groupby(["scenario", "arm", "grid_index", "threshold"])["count"].mean().reset_index()

    report, files = [], []
    for s, M in CELLS:
        base = scenario_config(s)
        for arm in ARMS:
            m = means[(means.scenario == s) & (means.arm == arm)].sort_values("grid_index")
            thr, mean, ok = choose([(r.threshold, r["count"]) for _, r in m.iterrows()], M)
            idx = int(m[m.threshold == thr].grid_index.iloc[0])
            edge = idx in (0, len(m) - 1)
            write = ok or L.smoke                        # smoke mode exercises every path even if infeasible
            report.append({"scenario": s, "M": M, "arm": arm, "threshold": thr, "grid_index": idx,
                           "grid_edge": edge, "calibration_mean_count": mean, "calibratable": ok})
            if write:
                p = L.path(arm, s, M)
                save_config(arm_config(base, arm, thr, const[s], M), p)
                files.append(p)
    for s in SCENARIOS:
        p = L.path("A0", s)
        save_config(scenario_config(s), p)
        files.append(p)

    rep = os.path.join(L.frozen, "calibration_report.csv")
    pd.DataFrame(report).to_csv(rep, index=False)
    cpath = os.path.join(L.frozen, "constants.yaml")
    with open(cpath, "w", encoding="utf-8") as f:
        yaml.safe_dump({"scenarios": {s: {k: round(v, 10) for k, v in c.items()} for s, c in const.items()},
                        "tau_quantile": TAU_QUANTILE, "calibration_seeds": list(L.cal_seeds),
                        "feasibility": FEASIBILITY, "calibration_cap": CAL_CAP, "smoke": L.smoke,
                        "git_commit": git_state()["commit"]}, f, sort_keys=False)
    write_manifest(files + [rep, cpath], L.manifest)
    n_runs = len(res) + len(tasks)
    write_json(os.path.join(L.cal_out, "run_info.json"),
               {"seeds": list(L.cal_seeds), "n_runs": n_runs, "seconds": round(time.time() - t0, 1),
                "git": git_state(), "versions": versions(), "smoke": L.smoke})
    print(pd.DataFrame(report).to_string(index=False))
    bad = [r for r in report if not r["calibratable"]]
    print(f"\nfrozen {len(files)} configs; {len(bad)} not calibratable (excluded); {n_runs} runs; "
          f"{round(time.time() - t0, 1)} s; manifest {L.manifest}")


# ------------------------------------------------------------------ stage 2: evaluation
def evaluate(L, workers):
    assert_seeds(L.eval_seeds, L.eval_allowed, "focused evaluation")
    listed = verify_manifest(L.manifest)
    git = git_state()
    if not L.smoke:
        check_eval_allowed(L.run_out, git)
    elif os.path.exists(os.path.join(L.run_out, "COMPLETE")):
        raise SystemExit(f"{L.run_out} already complete; outputs are never overwritten")
    os.makedirs(L.run_out, exist_ok=True)
    jobs = []
    for s in SCENARIOS:
        jobs += [(f"A0_{s}", "A0", load_config(L.path("A0", s)), seed, "static", L.path("A0", s))
                 for seed in L.eval_seeds]
    for s, M in CELLS:
        for arm in ARMS:
            p = L.path(arm, s, M)
            if os.path.exists(p):                       # not calibratable -> excluded
                cfg = load_config(p)
                jobs += [(cell_name(s, M), arm, cfg, seed, ARM_POLICY[arm], p) for seed in L.eval_seeds]
    t0 = time.time()
    print(f"focused evaluation: {len(jobs)} runs on {workers} workers -> {L.run_out}", flush=True)
    results = run_tasks([(cfg, seed, pol, "rows") for _, _, cfg, seed, pol, _ in jobs], workers)
    groups, counts, hashes = {}, {}, {}
    for (group, arm, cfg, seed, _, path), rows in zip(jobs, results):
        if len(rows) != cfg.epochs:
            raise SystemExit(f"incomplete run {group}/{arm}/seed {seed}: {len(rows)} epochs")
        for r in rows:
            r["arm"] = arm
        groups.setdefault(group, []).extend(rows)
        counts[group] = counts.get(group, 0) + 1
        hashes[f"{group}/{arm}"] = sha256(path)
    for group, rows in groups.items():
        os.makedirs(os.path.join(L.run_out, group), exist_ok=True)
        pd.DataFrame(rows).to_csv(os.path.join(L.run_out, group, "epochs.csv"), index=False)
    write_json(os.path.join(L.run_out, "run_info.json"),
               {"seeds": [L.eval_seeds[0], L.eval_seeds[-1]], "n_runs": len(jobs), "runs_per_group": counts,
                "seconds": round(time.time() - t0, 1), "git": git, "versions": versions(), "manifest": listed,
                "config_sha256": hashes, "complete": True, "smoke": L.smoke,
                "script_sha256": sha256(os.path.abspath(__file__))})
    with open(os.path.join(L.run_out, "COMPLETE"), "w") as f:
        f.write(f"{len(jobs)} runs, commit {git['commit']}\n")
    print(f"done: {len(jobs)} runs in {round(time.time() - t0, 1)} s")


# ------------------------------------------------------------------ stage 3: analysis
def analyze(L):
    with open(os.path.join(L.frozen, "constants.yaml"), encoding="utf-8") as f:
        consts = yaml.safe_load(f)["scenarios"]
    out = os.path.join(L.run_out, "analysis")
    os.makedirs(out, exist_ok=True)
    rows = []
    for s in SCENARIOS:
        an.CONST.clear()
        an.CONST.update(consts[s])
        static = pd.read_csv(os.path.join(L.run_out, f"A0_{s}", "epochs.csv"), low_memory=False)
        a0cfg = load_config(L.path("A0", s))
        labels, traces = {}, {}
        for seed in sorted(static.seed.unique()):
            sg = static[static.seed == seed].sort_values("epoch")
            labels[seed] = {v: an.epoch_classes(sg.E_hat.to_numpy() > an.CONST["tau"], v) for v in an.VARIANTS}
            traces[seed] = an.rebuild_down(a0cfg, seed, sg.n_down_potential.to_numpy())
        for M in BUDGETS:
            cell = cell_name(s, M)
            path = os.path.join(L.run_out, cell, "epochs.csv")
            parts = [static.assign(arm="A0")] + ([pd.read_csv(path, low_memory=False)] if os.path.exists(path) else [])
            for (arm, seed), g in ((k, gg) for part in parts for k, gg in part.groupby(["arm", "seed"])):
                met = an.run_metrics(g, static[static.seed == seed], labels[seed], a0cfg.link_setup_epochs,
                                     None if arm == "A0" else M, *traces[seed])
                mut = g[g.select_outcome == "mutated"]
                met["live_link_releases"] = int((~mut.removed_failed_link.astype(bool)).sum()) if len(mut) else 0
                if arm == "A5":
                    met.update(a7.feedback_metrics(g))
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
            summ.append({"group": grp, "arm": arm, "metric": m, "n": len(v), "mean": v.mean() if len(v) else np.nan,
                         "ci95_half": half})
    pd.DataFrame(summ).to_csv(os.path.join(out, "summary.csv"), index=False)

    prim = a7.family(ps, PRIMARY, CELLS, "primary (Holm over 12)")
    sec = a7.family(ps, SECONDARY, CELLS, "secondary (Holm over 6)")
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
    fcols = [c for c in ps.columns if c.startswith("fb_")]
    fq = ps[ps.arm == "A5"].groupby("group")[fcols].mean() if fcols else pd.DataFrame()
    fq.to_csv(os.path.join(out, "feedback_quality.csv"))
    figures(ps, prim, sec, out)
    write_report(L, out, ps, prim, sec, fq)
    print(f"analysis written to {out}")


def figures(ps, prim, sec, out):
    arms = ["A0", "A1", "A3", "A5"]
    fig, axes = plt.subplots(1, len(CELLS), figsize=(2.9 * len(CELLS), 4.2), sharey=True)
    for ax, (s, M) in zip(np.atleast_1d(axes), CELLS):
        vals = [ps[(ps.group == cell_name(s, M)) & (ps.arm == a)].E.dropna() for a in arms]
        means = [v.mean() if len(v) else np.nan for v in vals]
        # error bars only with >= 5 seeds: a t-interval on 2-4 seeds is too wide to mean anything
        errs = [stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)) if len(v) >= 5 else 0 for v in vals]
        ax.set_axisbelow(True)
        ax.bar(range(len(arms)), means, yerr=errs if any(e > 0 for e in errs) else None, capsize=3,
               color=[COLORS[a] for a in arms])
        ax.set_ylim(0, 1)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms)
        ax.set_title(f"{s.split('_', 1)[0]} {s.split('_', 1)[1]}\nbudget M = {M}", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e5e5e5", lw=0.8)
    np.atleast_1d(axes)[0].set_ylabel("Consensus stress E (0-1, lower is better)")
    fig.text(0.01, 0.01, "Mean over seeds; 95% t-CI shown when n >= 5. A0 = static reference (no mutations), "
                         "A1 = Reactive, A3 = CUSUM-E, A5 = TCCE-R.", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(os.path.join(out, "fig_E_by_cell.png"), dpi=140)
    plt.close(fig)

    t = pd.concat([prim, sec])
    t = t[t.status == "tested"].reset_index(drop=True)
    if t.empty:
        return
    fig, ax = plt.subplots(figsize=(8.5, 0.3 * len(t) + 1.6))
    y = np.arange(len(t))[::-1]
    col = [COLORS[r.comparison.split("-")[0]] for r in t.itertuples()]
    for yi, r, c in zip(y, t.itertuples(), col):
        ax.errorbar(r.mean_diff, yi, xerr=[[r.mean_diff - r.boot_lo], [r.boot_hi - r.mean_diff]], fmt="o", color=c,
                    ms=5, capsize=3)
    for v in (-MARGIN, 0, MARGIN):
        ax.axvline(v, color="#555" if v == 0 else "#bbb", lw=1, ls="-" if v == 0 else "--")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.cell}  {r.comparison}  (Holm p={r.holm_p:.2g})" for r in t.itertuples()], fontsize=7)
    ax.set_xlabel("Paired difference in E (first arm minus second); negative = first arm better; dashed = ±0.02")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_forest_E.png"), dpi=140)
    plt.close(fig)


def write_report(L, out, ps, prim, sec, fq):
    def tab(df, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in df[cols].itertuples(index=False):
            lines.append("| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in r) + " |")
        return "\n".join(lines)
    n = ps.groupby("arm").seed.nunique().to_dict()
    sm = ps[ps.arm != "A0"].groupby(["group", "arm"])[["E", "disconnected", "lambda2", "mutations"]].mean().round(3)
    L_ = [f"# Focused v0.7 comparison ({'SMOKE TEST - development seeds, not results' if L.smoke else 'exploratory'})",
          "", "Generated by `experiments/focused_v07.py` from raw CSVs. Plan and caveats: `docs/FOCUSED_v0.7_PLAN.md`. "
          "Each scenario x budget cell is a separate condition. Seeds per arm: " + str(n), "",
          "## Primary: A5 and A3 vs A1 Reactive on E (Holm over the family)", "",
          tab(prim[prim.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi",
                                              "wilcoxon_p", "holm_p", "verdict"]), "",
          "## Secondary: A5 TCCE-R vs A3 CUSUM-E on E", "",
          tab(sec[sec.status == "tested"], ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi",
                                            "wilcoxon_p", "holm_p", "verdict"]), "",
          "## Means per cell and arm", "", "```", sm.to_string(), "```", ""]
    if len(fq):
        L_ += ["## A5 feedback quality (shares of counterfactual outcomes)", "", "```", fq.round(3).to_string(), "```", ""]
    miss = prim[prim.status != "tested"]
    if len(miss):
        L_ += ["Excluded (not calibratable): " + ", ".join(f"{r.cell} {r.comparison}" for r in miss.itertuples()), ""]
    with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L_) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["calibrate", "eval", "analyze", "all"], default="all")
    ap.add_argument("--smoke", action="store_true", help="development seeds, 5-point grid, separate folder")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    L = Layout(a.smoke)
    if a.stage in ("calibrate", "all"):
        calibrate(L, a.workers)
    if a.stage in ("eval", "all"):
        evaluate(L, a.workers)
    if a.stage in ("analyze", "all"):
        analyze(L)


if __name__ == "__main__":
    main()
