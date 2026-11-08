"""Analysis of an R3 held-out tier (docs/PROTOCOL_R3.md section 6, addendum). Comparisons are FIXED HERE before any held-out run.

  python -m experiments.analyze_r3 --tier A|B|C [--eval results/r3/<tier>] [--out revision/analysis/R3/<tier>]      (smoke: --eval results/r3/smoke/A --out results/r3/smoke/analysis_A)
Differences are first arm minus second arm in per-seed mean consensus error E (negative = first arm lower error). Wilcoxon signed-rank, Holm within each
family, 95% bootstrap CI (10,000), margins 0.01 (declared primary margin) and 0.02. Verdict: 'meaningful' if Holm p < 0.05 and |mean| >= margin;
'below margin' if Holm p < 0.05 but |mean| < margin; 'equivalent' if Holm p >= 0.05 and the CI lies within +-margin; else 'inconclusive'.
Families:  PRIMARY  A: cocro_m vs A7M, B8, C1 | B: cocro_m vs A7M | C: cocro_m vs A7M ; H2 (tier C): cocro vs cocro_m in the regime and mixed cells ;
           ABLATION cocro_m_plug/_k1/_nb1/_s1/_lap and cocro_mfg vs cocro_m ; EXPLORATORY: everything else (other baselines, rollout vs cocro_m outside H2).
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

from experiments.analyze import holm
from experiments.analyze_v06 import describe, wilcoxon_p
from experiments.analyze_v08 import EPOCHS, run_metrics
from experiments.run_r3 import SEEDS, SMOKE_SEEDS, policy_of, tier_cells

MARGINS = (0.01, 0.02)
ABL = ["cocro_m_plug", "cocro_m_k1", "cocro_m_nb1", "cocro_m_s1", "cocro_m_lap", "cocro_mfg"]


def load_and_validate(eval_dir, tier, seeds, cells, smoke=False):
    problems = []
    add = problems.append
    ri = json.load(open(os.path.join(eval_dir, "run_info.json"), encoding="utf-8"))
    if not os.path.exists(os.path.join(eval_dir, "COMPLETE")) or not ri.get("complete"):
        add("COMPLETE marker missing")
    if list(ri["seeds"]) != list(seeds):
        add("run_info seeds differ from the protocol seeds")
    if ri["git"]["dirty_files"] and not smoke:                   # smoke runs (pipeline check) may be made on a dirty tree; real evaluations may not
        add(f"tracked files were dirty at run time: {ri['git']['dirty_files'][:3]}")
    frames = []
    for cell, files, M in cells:
        path = os.path.join(eval_dir, cell, "epochs.csv")
        if not os.path.exists(path):
            add(f"missing {path}")
            continue
        df = pd.read_csv(path, low_memory=False)
        df["cell"] = cell
        if set(df.arm.unique()) != set(files):
            add(f"{cell}: arms {sorted(df.arm.unique())} != {sorted(files)}")
        for arm in files:
            a = df[df.arm == arm]
            if set(a.seed.unique()) != set(seeds):
                add(f"{cell}/{arm}: seeds differ")
            g = a.groupby("seed").epoch.agg(["count", "min", "max", "nunique"])
            if len(g[(g["count"] != EPOCHS) | (g["min"] != 0) | (g["max"] != EPOCHS - 1) | (g["nunique"] != EPOCHS)]):
                add(f"{cell}/{arm}: malformed runs")
            if a.policy.nunique() != 1 or a.policy.iloc[0] != policy_of(arm):
                add(f"{cell}/{arm}: policy column {a.policy.unique()} != {policy_of(arm)}")
            if arm == "A0" and (a.n_mutations != 0).any():
                add(f"{cell}: Static mutated")
            if arm != "A0":
                if a.n_mutations.max() > M:
                    add(f"{cell}/{arm}: cap exceeded")
                if (a.configured_edges > a.budget).any():
                    add(f"{cell}/{arm}: edge budget exceeded")
                if not set(a.mutation_kind.dropna().unique()) <= {"", "rewire", "add"}:
                    add(f"{cell}/{arm}: unexpected mutation kinds")
        ref = None
        for arm, a in df.groupby("arm"):                       # common random numbers: identical failure trace for every arm of a (cell, seed)
            sig = a.sort_values(["seed", "epoch"])[["n_down_potential", "n_burst_down"]].to_numpy()
            ref = sig if ref is None else ref
            if not np.array_equal(sig, ref):
                add(f"{cell}/{arm}: failure trace differs from the other arms")
        frames.append(df)
    return pd.concat(frames, ignore_index=True), problems, ri


def per_seed(df, timing):
    rows = []
    statics = {(c, s): g for (c, a, s), g in df[df.arm == "A0"].groupby(["cell", "arm", "seed"])}      # precomputed: same lookup, no repeated full-table filtering
    for (cell, arm, seed), g in df.groupby(["cell", "arm", "seed"]):
        static = statics.get((cell, seed))
        r = run_metrics(g, static if static is not None else g)
        r.update(cell=cell, arm=arm, seed=seed, M=int(cell.rsplit("_M", 1)[1]))
        rows.append(r)
    ps = pd.DataFrame(rows).merge(timing, on=["cell", "arm", "seed"], how="left")
    st = ps[ps.arm == "A0"].set_index(["cell", "seed"]).E
    ps["dE_vs_static"] = [st.get((c, s), np.nan) - e if a != "A0" else np.nan for c, s, e, a in zip(ps.cell, ps.seed, ps.E, ps.arm)]
    ps["dE_per_mutation"] = np.where(ps.mutations > 0, ps.dE_vs_static / ps.mutations.replace(0, np.nan), np.nan)
    return ps


def diffs(ps, cell, x, y, metric="E"):
    a = ps[(ps.cell == cell) & (ps.arm == x)].set_index("seed")[metric]
    b = ps[(ps.cell == cell) & (ps.arm == y)].set_index("seed")[metric]
    j = a.index.intersection(b.index)
    return (a.loc[j] - b.loc[j]).dropna().to_numpy(float)


def verdict(p, mean, lo, hi, m, adjusted=True):
    if adjusted and p < 0.05 or (not adjusted and p < 0.05):
        return ("first arm" if mean < 0 else "second arm") + (" better (meaningful)" if abs(mean) >= m else " better, below margin")
    return "practically equivalent" if (-m < lo and hi < m) else "inconclusive"


def run_family(ps, pairs, cells, name, adjust=True):
    rows = []
    for cell in cells:
        arms = set(ps[ps.cell == cell].arm)
        for x, y in pairs:
            if x not in arms or y not in arms:
                rows.append(dict(cell=cell, comparison=f"{x}-{y}", family=name, status="excluded (arm missing)"))
                continue
            d = diffs(ps, cell, x, y)
            p, nnz, ident = wilcoxon_p(d)
            rows.append(dict(cell=cell, comparison=f"{x}-{y}", family=name, status="tested", **describe(d), sd_diff=float(d.std(ddof=1)),
                             dz=float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 0 else np.nan, wilcoxon_p=p, identical=ident))
    df = pd.DataFrame(rows, columns=None if rows else ["cell", "comparison", "family", "status"])
    if not rows:                                               # e.g. no cell of the family in a smoke run
        return df
    ok = df.status == "tested"
    df["holm_p"] = np.nan
    if ok.any():
        df.loc[ok, "holm_p"] = holm(df.loc[ok, "wilcoxon_p"]).values if adjust else df.loc[ok, "wilcoxon_p"].values
    for m in MARGINS:
        df[f"verdict_{m}"] = ""
        for i in df.index[ok]:
            r = df.loc[i]
            df.loc[i, f"verdict_{m}"] = verdict(r.holm_p, r.mean_diff, r.boot_lo, r.boot_hi, m)
    df["tests_in_family"] = int(ok.sum())
    return df


def families(tier, cells):
    names = [c for c, _, _ in cells]
    if tier == "A":
        return [("primary", [("cocro_m", "A7M"), ("cocro_m", "B8"), ("cocro_m", "C1")], names, True),
                ("ablation", [(a, "cocro_m") for a in ABL], names, True),
                ("rollout-vs-cocro_m (exploratory)", [("cocro", "cocro_m")], [c for c in names if not c.startswith("S3")], False),
                ("other baselines (exploratory)", [("cocro_m", "A1"), ("cocro_m", "A7"), ("cocro_m", "A0")], names, False)]
    if tier == "B":
        return [("primary", [("cocro_m", "A7M")], names, True), ("ablation", [(a, "cocro_m") for a in ABL], names, True),
                ("exploratory", [("cocro_m", "A0")], names, False)]
    h2 = [c for c in names if c.startswith(("regime", "mixed"))]
    return [("primary", [("cocro_m", "A7M")], names, True), ("H2 (rollout vs cocro_m under regime change)", [("cocro", "cocro_m")], h2, True),
            ("ablation", [(a, "cocro_m") for a in ("cocro_m_plug", "cocro_m_k1", "cocro_m_nb1")], names, True),
            ("exploratory", [("cocro", "cocro_m")] if False else [("cocro_m", "A1"), ("cocro_m", "B8"), ("cocro_m", "C1"), ("cocro_m", "A0")], names, False)]


def md(df, cols):
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("" if (isinstance(v, float) and np.isnan(v)) else (f"{v:.2e}" if c in ("wilcoxon_p", "holm_p") else (f"{v:.4f}" if isinstance(v, float) else str(v))))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=list(SEEDS))
    ap.add_argument("--eval")
    ap.add_argument("--out")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    tier = a.tier
    seeds = SMOKE_SEEDS if a.smoke else SEEDS[tier]
    eval_dir = a.eval or (f"results/r3/smoke/{tier}" if a.smoke else f"results/r3/{tier}")
    out = a.out or (f"results/r3/smoke/analysis_{tier}" if a.smoke else f"revision/analysis/R3/{tier}")
    os.makedirs(out, exist_ok=True)
    cells = tier_cells(tier)
    if a.smoke:
        cells = cells[:1]
    df, problems, ri = load_and_validate(eval_dir, tier, seeds, cells, a.smoke)
    json.dump({"problems": problems, "n_runs": ri["n_runs"], "git_commit": ri["git"]["commit"]}, open(os.path.join(out, "validation.json"), "w"), indent=1)
    print(f"validation: {len(problems)} problems")
    if problems:
        for p in problems[:10]:
            print(" -", p)
        raise SystemExit("input validation failed; nothing analysed")
    timing = pd.read_csv(os.path.join(eval_dir, "timing.csv"))
    ps = per_seed(df, timing)
    ps.to_csv(os.path.join(out, "per_seed_metrics.csv"), index=False)
    names = [c for c, _, _ in cells]
    tabs = []
    for name, pairs, cl, adj in families(tier, cells):
        t = run_family(ps, pairs, [c for c in cl if c in names], name, adj)
        tabs.append(t)
    tests = pd.concat(tabs, ignore_index=True)
    tests.to_csv(os.path.join(out, "tests.csv"), index=False)
    summ = ps.groupby(["cell", "arm"]).agg(n=("E", "size"), E_mean=("E", "mean"), E_sd=("E", "std"), mutations=("mutations", "mean"), disconnected=("disconnected", "mean"),
                                           longest_disc=("longest_disc", "mean"), worst_E=("worst_E", "mean"), recovery=("anchored_recovery", "mean"),
                                           overhead=("overhead_sum", "mean"), ms_per_epoch=("ms_per_epoch", "mean"), seconds=("seconds", "mean")).reset_index()
    summ["E_ci_lo"] = summ.E_mean - 1.96 * summ.E_sd / np.sqrt(summ.n)
    summ["E_ci_hi"] = summ.E_mean + 1.96 * summ.E_sd / np.sqrt(summ.n)
    eff = ps[ps.arm != "A0"].groupby(["cell", "arm"]).agg(dE_vs_static=("dE_vs_static", "mean"), mutations=("mutations", "mean"),
                                                          dE_per_mutation=("dE_per_mutation", "mean")).reset_index()
    summ.to_csv(os.path.join(out, "summary_by_arm_cell.csv"), index=False)
    eff.to_csv(os.path.join(out, "efficiency.csv"), index=False)
    tcols = ["cell", "comparison", "n", "mean_diff", "boot_lo", "boot_hi", "rank_biserial", "dz", "wilcoxon_p", "holm_p", "verdict_0.01", "verdict_0.02"]
    L = [f"# R3 tier {tier} analysis (seeds {seeds[0]}-{seeds[-1]}; {ri['n_runs']} runs; commit `{ri['git']['commit'][:7]}`)", "",
         "Differences: first arm minus second arm in per-seed mean E (negative = first arm lower error). Margins 0.01 and 0.02; Holm within each family. "
         "No claim is made here; the protocol is `docs/PROTOCOL_R3.md`.", "", "**Validation:** all input checks passed." if not problems else "**Problems:** " + "; ".join(problems), ""]
    for name in tests.family.unique():
        t = tests[(tests.family == name) & (tests.status == "tested")]
        L += [f"## {name} ({len(t)} tests)", "", md(t, tcols), ""]
    L += ["## Mean E (95% interval), mutations, connectivity, overhead and decision time", "",
          md(summ, ["cell", "arm", "E_mean", "E_sd", "E_ci_lo", "E_ci_hi", "mutations", "disconnected", "longest_disc", "worst_E", "recovery", "overhead", "ms_per_epoch", "seconds"]), "",
          "## Improvement over Static per realised mutation (exploratory)", "", md(eff, ["cell", "arm", "dE_vs_static", "mutations", "dE_per_mutation"]), ""]
    open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L))
    print("analysis written to", out)


if __name__ == "__main__":
    main()
