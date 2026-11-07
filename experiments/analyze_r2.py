"""Analysis of the Revision 2 main evaluation (arms A0, A1, A7, A7M, B8, C1). Reads one evaluation folder only.

  python -m experiments.analyze_r2 [--eval results/r2/main/eval] [--out revision/analysis/R2/main] [--frozen configs/r2/frozen]
  python -m experiments.analyze_r2 --smoke      # dev seeds 8202-8203, results/r2/smoke -> results/r2/smoke/analysis (pipeline check)

Comparisons are fixed here BEFORE the held-out run (first arm minus second arm in per-seed mean consensus error E; negative = first
arm lower error). Holm is applied within each family; margin 0.02; bootstrap 95% CI as in v0.8.
  PRIMARY   (confirmatory): C1-A7, C1-A7M, C1-A1, C1-B8
  REFERENCE (B8 against the baselines, to document B8's behaviour on the new seeds): B8-A1, B8-A7, B8-A7M
Everything else (other metrics, equal-count subsets, performance per successful mutation) is exploratory: estimates and CIs, no p-values.
No simulation is run, nothing is recalibrated, no raw file is modified.
"""
import argparse
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from experiments import analyze_v08 as v8  # noqa: E402
from experiments.analyze_v06 import boot_ci  # noqa: E402
from experiments.run_r2 import ARMS, EVAL_OUT, FROZEN_DIR, POLICY, SMOKE_FROZEN_DIR, SMOKE_OUT, SMOKE_SEEDS  # noqa: E402
from experiments.v08_common import CELLS, SCENARIOS, cell_name, frozen_path, sha256, verify_manifest  # noqa: E402

OUT_DIR = "revision/analysis/R2/main"
PRIMARY = [("C1", "A7"), ("C1", "A7M"), ("C1", "A1"), ("C1", "B8")]
REFERENCE = [("B8", "A1"), ("B8", "A7"), ("B8", "A7M")]
DETAIL = PRIMARY + REFERENCE
CELL_LIST = [cell_name(s, M) for s, M in CELLS]
v8.ARM_LABEL.update({"C1": "C1 causal debt"})
v8.ARM_COLOR.update({"C1": "#c0392b"})
v8.ARM_MARKER.update({"C1": "*"})
EPOCHS = v8.EPOCHS


def expected_groups(frozen):
    g = {f"A0_{s}": ["A0"] for s in SCENARIOS}
    for s, M in CELLS:
        g[cell_name(s, M)] = [a for a in ARMS if os.path.exists(frozen_path(frozen, a, s, M))]
    return g


def load_and_validate(eval_dir, frozen, seeds):
    problems = []
    add = problems.append
    ri = json.load(open(os.path.join(eval_dir, "run_info.json"), encoding="utf-8"))
    exp = expected_groups(frozen)
    n_exp = sum(len(a) for a in exp.values()) * len(seeds)
    if not os.path.exists(os.path.join(eval_dir, "COMPLETE")):
        add("COMPLETE marker missing")
    if not ri.get("complete") or ri.get("n_runs") != n_exp:
        add(f"run_info complete={ri.get('complete')} n_runs={ri.get('n_runs')} (expected True, {n_exp})")
    if list(ri["seeds"]) != list(seeds):
        add("run_info seeds differ from the expected seeds")
    if ri["git"]["dirty_files"]:
        add(f"tracked files were dirty at run time: {ri['git']['dirty_files'][:3]}")
    try:
        verify_manifest(os.path.join(frozen, "MANIFEST.sha256"))
    except Exception as e:  # noqa: BLE001
        add(f"frozen manifest: {e}")
    frames, total = [], 0
    for group, arms in exp.items():
        path = os.path.join(eval_dir, group, "epochs.csv")
        if not os.path.exists(path):
            add(f"missing {path}")
            continue
        df = pd.read_csv(path, low_memory=False)
        df["group"] = group
        if set(df.arm.unique()) != set(arms):
            add(f"{group}: arms {sorted(df.arm.unique())} != {sorted(arms)}")
        for arm in arms:
            a = df[df.arm == arm]
            if set(a.seed.unique()) != set(seeds):
                add(f"{group}/{arm}: seeds differ from expected")
            g = a.groupby("seed").epoch.agg(["count", "min", "max", "nunique"])
            bad = g[(g["count"] != EPOCHS) | (g["min"] != 0) | (g["max"] != EPOCHS - 1) | (g["nunique"] != EPOCHS)]
            if len(bad):
                add(f"{group}/{arm}: {len(bad)} malformed runs, e.g. seed {bad.index[0]}")
            if a.policy.nunique() != 1 or a.policy.iloc[0] != POLICY[arm]:
                add(f"{group}/{arm}: policy column {a.policy.unique()} != {POLICY[arm]}")
            for col in ("E_hat", "components", "n_mutations", "configured_edges", "budget"):
                if a[col].isna().any():
                    add(f"{group}/{arm}: NaN in {col}")
            total += a.seed.nunique()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    if total != n_exp or len(df) != n_exp * EPOCHS:
        add(f"found {total} runs / {len(df)} rows, expected {n_exp} / {n_exp * EPOCHS}")
    for key, h in ri["config_sha256"].items():
        group, arm = key.split("/")
        s = group.replace("A0_", "") if arm == "A0" else group.rsplit("_M", 1)[0]
        M = None if arm == "A0" else int(group.rsplit("_M", 1)[1])
        if sha256(frozen_path(frozen, arm, s, M)) != h:
            add(f"config hash mismatch for {key}")
    for (group, arm), a in df.groupby(["group", "arm"]):
        if arm == "A0":
            if (a.n_mutations != 0).any():
                add(f"{group}: Static mutated")
            continue
        M = int(group.rsplit("_M", 1)[1])
        if a.n_mutations.max() > M:
            add(f"{group}/{arm}: n_mutations {a.n_mutations.max()} exceeds cap {M}")
        if (a.configured_edges > a.budget).any():
            add(f"{group}/{arm}: configured edges exceed the budget")
        if not set(a.mutation_kind.dropna().unique()) <= {"", "rewire"}:
            add(f"{group}/{arm}: non-rewire mutation kinds")
        mono = a.sort_values(["seed", "epoch"]).groupby("seed").n_mutations.apply(lambda x: bool((np.diff(x.to_numpy()) >= 0).all()))
        if not mono.all():
            add(f"{group}/{arm}: n_mutations decreases within a run")
    df["scenario"] = df.group.str.replace("A0_", "").str.replace(r"_M\d$", "", regex=True)
    crn_bad = 0
    for (scen, seed), g in df.groupby(["scenario", "seed"]):
        ref = None
        for (grp, arm), a in g.groupby(["group", "arm"]):
            sig = (tuple(a.sort_values("epoch").n_down_potential), tuple(a.sort_values("epoch").n_burst_down))
            ref = ref or sig
            crn_bad += sig != ref
    if crn_bad:
        add(f"common random numbers violated in {crn_bad} (scenario, seed, arm) series")
    return df, {"problems": problems, "runs_found": int(total), "rows": int(len(df)), "expected_runs": int(n_exp),
                "git_commit": ri["git"]["commit"], "seconds": ri.get("seconds")}


def add_efficiency(ps):
    """Performance per successful mutation: improvement over Static of the same scenario and seed, per realised mutation.
    Undefined for runs with zero mutations (NaN). Exploratory."""
    st = ps[ps.arm == "A0"].set_index(["scenario", "seed"]).E
    ps["dE_vs_static"] = [st.get((r.scenario, r.seed), np.nan) - r.E if r.arm != "A0" else np.nan for r in ps.itertuples()]
    ps["dE_per_mutation"] = np.where(ps.mutations > 0, ps.dE_vs_static / ps.mutations.replace(0, np.nan), np.nan)
    return ps


def efficiency_tables(ps):
    rows, diffs = [], []
    for cell in CELL_LIST:
        for arm, g in ps[ps.group == cell].groupby("arm"):
            rows.append({"cell": cell, "arm": arm, "mean_dE_vs_static": g.dE_vs_static.mean(), "mean_mutations": g.mutations.mean(),
                         "ratio_of_means": g.dE_vs_static.mean() / g.mutations.mean() if g.mutations.mean() > 0 else np.nan,
                         "mean_per_mutation_seedlevel": g.dE_per_mutation.mean(), "seeds_with_mutation": int((g.mutations > 0).sum())})
        for x, y in DETAIL:
            a = ps[(ps.group == cell) & (ps.arm == x)].set_index("seed")
            b = ps[(ps.group == cell) & (ps.arm == y)].set_index("seed")
            if len(a) == 0 or len(b) == 0:
                continue
            j = a.index.intersection(b.index)
            d = (a.loc[j, "dE_per_mutation"] - b.loc[j, "dE_per_mutation"]).dropna().to_numpy(dtype=float)
            if len(d) >= 5:
                lo, hi = boot_ci(d)
                diffs.append({"cell": cell, "comparison": f"{x}-{y}", "n_seeds_both_mutated": len(d), "mean_diff": d.mean(),
                              "boot_lo": lo, "boot_hi": hi, "note": "exploratory; positive = first arm gains more per mutation"})
    return pd.DataFrame(rows), pd.DataFrame(diffs)


def fig_E(summ, out):
    fig, axes = plt.subplots(2, 3, figsize=(12, 6))
    order = ["A1", "A7", "A7M", "B8", "C1"]
    for ax, cell in zip(axes.ravel(), CELL_LIST):
        s = summ[summ.cell == cell].set_index("arm")
        for i, arm in enumerate(order):
            if arm in s.index:
                r = s.loc[arm]
                ax.errorbar(r.E_mean, i, xerr=[[r.E_mean - r.E_ci_lo], [r.E_ci_hi - r.E_mean]], fmt=v8.ARM_MARKER[arm],
                            color=v8.ARM_COLOR[arm], ms=6, capsize=2, lw=1.2, mec="#fcfcfb")
        st = summ[summ.cell == f"A0_{cell.rsplit('_M', 1)[0]}"]
        if len(st):
            ax.axvline(st.E_mean.iloc[0], color=v8.ARM_COLOR["A0"], ls="--", lw=1)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([v8.ARM_LABEL[a] for a in order], fontsize=8)
        ax.invert_yaxis()
        ax.grid(axis="x")
        ax.set_title(cell.replace("_", " "))
        ax.set_xlabel("mean E (95% t-interval); dashed: Static")
    fig.suptitle("Revision 2 main evaluation: mean consensus error (lower is better)", y=1.0)
    fig.tight_layout()
    v8._save(fig, out, "fig_E_by_cell")


def md(df, cols):
    return v8.md_table(df, cols)


def write_report(out, info, prim, ref, counts, summ, eqc, eff, effd, eval_dir, seeds):
    cols = ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi", "rank_biserial", "wilcoxon_p", "holm_p", "verdict"]
    L = [f"# Revision 2 main evaluation: analysis (seeds {seeds[0]}-{seeds[-1]})", "",
         f"Input `{eval_dir}` (commit `{info['git_commit'][:7]}`, {info['expected_runs']} runs, 80 epochs each, run time {info['seconds']} s). "
         "Generated by `python -m experiments.analyze_r2`. No performance claim is made in this file; it reports estimates.", "",
         "## Validation", "", "**All input checks passed.**" if not info["problems"] else "**Problems found:**\n" + "\n".join(f"- {p}" for p in info["problems"]), "",
         "## Reading guide",
         "- First arm minus second arm in per-seed mean E; negative = first arm lower error. Margin 0.02. Wilcoxon signed-rank, Holm within each family, "
         "95% bootstrap CI (10,000). 'practically equivalent' needs Holm p >= 0.05 and the CI inside +-0.02; otherwise 'inconclusive'.",
         "- Thresholds were calibrated to realised mutation counts, so counts are matched approximately, not exactly; see the count table.",
         "- A1 is absent in S3 M3 (infeasible at calibration; excluded, not retuned).", "",
         f"## Primary family: C1 against A7, A7M, A1, B8 ({int((prim.status == 'tested').sum())} tests, Holm over this family)", "",
         md(prim[prim.status == "tested"], cols), "",
         f"## Reference family: B8 against A1, A7, A7M ({int((ref.status == 'tested').sum())} tests, Holm over this family)", "",
         md(ref[ref.status == "tested"], cols), "",
         "## Realised mutation counts", "",
         md(counts, ["cell", "arm", "mean_mutations", "min", "max", "share_at_cap", "mean_intended", "mean_failed_attempts", "mean_deferred"]), "",
         "## Mean E, connectivity and overhead", "",
         md(summ[~summ.arm.eq("A0")].sort_values(["cell", "arm"]),
            ["cell", "arm", "E_mean", "E_ci_lo", "E_ci_hi", "disconnected_mean", "disc_episodes_mean", "longest_disc_mean",
             "anchored_recovery_mean", "worst_E_mean", "mutations_mean", "overhead_sum_mean"]), "",
         "## Performance per successful mutation (exploratory)", "",
         "Improvement over Static (same scenario and seed) per realised mutation. `ratio_of_means` = mean improvement / mean mutations.", "",
         md(eff, ["cell", "arm", "mean_dE_vs_static", "mean_mutations", "ratio_of_means", "mean_per_mutation_seedlevel", "seeds_with_mutation"]), "",
         "Paired differences in the per-mutation gain (seeds where both arms mutated):", "",
         md(effd, ["cell", "comparison", "n_seeds_both_mutated", "mean_diff", "boot_lo", "boot_hi"]) if len(effd) else "(none)", "",
         "## Equal-realised-count subsets (exploratory)", "",
         md(eqc, [c for c in ("cell", "comparison", "n_equal_count_seeds", "mean_diff", "boot_lo", "boot_hi", "note") if c in eqc.columns]), "",
         "## Not computed", "",
         "- Wall-clock decision time is not recorded in this evaluation path (the engine's timing side channel was not enabled); the overhead reported is "
         "reconfiguration overhead (pending link-epochs + live-link releases).", ""]
    open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--amended", action="store_true", help="Amendment 1 evaluation (seeds 9200-9259)")
    ap.add_argument("--eval")
    ap.add_argument("--out")
    ap.add_argument("--frozen")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    am = a.amended
    seeds = list(SMOKE_SEEDS) if a.smoke else list(range(9200, 9260) if am else range(9100, 9160))
    eval_dir = a.eval or (SMOKE_OUT if a.smoke else ("results/r2a/main/eval" if am else EVAL_OUT))
    frozen = a.frozen or (SMOKE_FROZEN_DIR if a.smoke else ("configs/r2a/frozen" if am else FROZEN_DIR))
    out = a.out or ("results/r2/smoke/analysis" if a.smoke else ("revision/analysis/R2/amended" if am else OUT_DIR))
    os.makedirs(out, exist_ok=True)
    df, info = load_and_validate(eval_dir, frozen, seeds)
    json.dump(info, open(os.path.join(out, "validation.json"), "w"), indent=2, default=str)
    print(f"validation: {len(info['problems'])} problems; runs found {info['runs_found']}/{info['expected_runs']}")
    if info["problems"]:
        for p in info["problems"]:
            print(" -", p)
        raise SystemExit("input validation failed; nothing analysed")
    ps = add_efficiency(v8.per_seed_metrics(df))
    ps.to_csv(os.path.join(out, "per_seed_metrics.csv"), index=False)
    prim = v8.test_family(ps, PRIMARY, "primary")
    ref = v8.test_family(ps, REFERENCE, "reference")
    prim.to_csv(os.path.join(out, "primary_tests.csv"), index=False)
    ref.to_csv(os.path.join(out, "reference_tests.csv"), index=False)
    eqc = v8.equal_count_tests(ps, DETAIL)
    eqc.to_csv(os.path.join(out, "equal_count_tests.csv"), index=False)
    v8.exploratory_metric_diffs(ps, DETAIL).to_csv(os.path.join(out, "exploratory_metric_diffs.csv"), index=False)
    summ = v8.summary_table(ps)
    summ.to_csv(os.path.join(out, "summary_by_arm_cell.csv"), index=False)
    counts = v8.count_table(ps)
    counts.to_csv(os.path.join(out, "realised_counts.csv"), index=False)
    eff, effd = efficiency_tables(ps)
    eff.to_csv(os.path.join(out, "per_mutation_efficiency.csv"), index=False)
    effd.to_csv(os.path.join(out, "per_mutation_paired_diffs.csv"), index=False)
    write_report(out, info, prim, ref, counts, summ, eqc, eff, effd, eval_dir, seeds)
    if not a.no_figures:
        v8._style()
        fig_E(summ, out)
        v8._forest(pd.concat([prim, ref]), [f"{x}-{y}" for x, y in DETAIL], "Paired differences in mean E", out, "fig_forest", ncols=4)
    inputs = {}
    for dp, _, fs in os.walk(eval_dir):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            inputs[p.replace("\\", "/")] = sha256(p)
    for f in sorted(os.listdir(frozen)):
        inputs[f"{frozen}/{f}"] = sha256(os.path.join(frozen, f))
    git = lambda *x: subprocess.run(["git", *x], capture_output=True, text=True).stdout.strip()
    json.dump({"command": "python -m experiments.analyze_r2 " + " ".join(sys.argv[1:]), "script_sha256": sha256(__file__),
               "git_commit": git("rev-parse", "HEAD"), "families": {"primary": PRIMARY, "reference": REFERENCE},
               "margin": v8.E_MARGIN, "bootstrap": {"n": 10000, "seed": 20261010}, "input_sha256": inputs},
              open(os.path.join(out, "run_manifest.json"), "w"), indent=1, default=str)
    print("analysis written to", out)


if __name__ == "__main__":
    main()
