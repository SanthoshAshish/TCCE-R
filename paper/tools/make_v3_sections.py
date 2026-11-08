"""Generate every result-dependent number, table and figure of the V3 manuscript from the committed analysis files.
Reads revision/analysis/R3/A (held-out tier A), revision/analysis/R3/step2 (development ablation), revision/analysis/E2 and R2 (earlier studies).
Writes paper/tables_v3/*.md, paper/tables_v3/v3_values.json and paper/figures_v3/*.png|pdf.   python paper/tools/make_v3_sections.py"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

A = "revision/analysis/R3/A"
OUT, FIG = "paper/tables_v3", "paper/figures_v3"
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)
MINUS = "−"
CELLS = ["S1_M3", "S1_M6", "S2_M3", "S2_M6", "S3_M3", "S3_M6"]
CL = {c: f"{c[:2]}, M = {c[-1]}" for c in CELLS}
LAB = {"A0": "A0 Static", "A1": "A1 Reactive", "A7": "A7 Front-loaded", "A7M": "A7M Front-loaded (exactly M)", "B8": "B8 Predictive (earlier)", "C1": "C1 Causal debt (earlier)",
       "cocro_m": "COCRO-M", "cocro": "COCRO + rollout timing (exploratory)", "cocro_mfg": "COCRO-M + full-horizon rerank", "cocro_m_plug": "no posterior sampling",
       "cocro_m_k1": "single removal candidate", "cocro_m_nb1": "no propagation term", "cocro_m_s1": "one scenario", "cocro_m_lap": "Laplacian surrogate"}


def f(x, d=3, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    s = f"{abs(x):.{d}f}"
    return (MINUS if x < 0 else ("+" if sign else "")) + s


def table(header, rows):
    return "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n" + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in rows) + "\n"


tests = pd.read_csv(f"{A}/tests.csv")
tt = tests[tests.status == "tested"]
summ = pd.read_csv(f"{A}/summary_by_arm_cell.csv")
eff = pd.read_csv(f"{A}/efficiency.csv")
V = {}


def S(arm, cell, col):
    r = summ[(summ.arm == arm) & (summ.cell == cell)]
    return float(r[col].iloc[0]) if len(r) else np.nan


def T(fam, comp, cell):
    r = tt[(tt.family == fam) & (tt.comparison == comp) & (tt.cell == cell)]
    return r.iloc[0] if len(r) else None


def mark(r, margin=0.01):
    if r is None:
        return ""
    return ("**" if abs(r.mean_diff) >= margin else "*") if r.holm_p < 0.05 else ""


# ------------------------------------------------------------------ values
P = tt[tt.family == "primary"]
V["n_primary"] = str(len(P))
V["primary_all_lower"] = "yes" if (P.mean_diff < 0).all() else "no"
V["primary_max_holm"] = f(float(P.holm_p.max()), 4).replace(MINUS, "")
for comp, key in (("cocro_m-A7M", "A7M"), ("cocro_m-B8", "B8"), ("cocro_m-C1", "C1")):
    q = P[P.comparison == comp]
    V[f"rng_{key}"] = f"{f(float(q.mean_diff.min()), 3)} to {f(float(q.mean_diff.max()), 3)}"
    V[f"n_{key}"] = str(len(q))
    V[f"m001_{key}"] = str(int(q["verdict_0.01"].str.contains("meaningful").sum()))
    V[f"m002_{key}"] = str(int(q["verdict_0.02"].str.contains("meaningful").sum()))
    V[f"dz_{key}"] = f"{f(float(q.dz.max()), 2)} to {f(float(q.dz.min()), 2)}"
V["m001_all"] = str(int(P["verdict_0.01"].str.contains("meaningful").sum()))
V["m002_all"] = str(int(P["verdict_0.02"].str.contains("meaningful").sum()))
rel = [(S("A7M", c, "E_mean") - S("cocro_m", c, "E_mean")) / S("A7M", c, "E_mean") * 100 for c in CELLS]
V["rel_A7M"] = f"{min(rel):.1f}% to {max(rel):.1f}%"
V["rel_A7M_s1s2"] = f"{min(rel[:4]):.1f}% to {max(rel[:4]):.1f}%"
V["A7M_below_margin_cells"] = ", ".join(CL[c] for c in CELLS if T("primary", "cocro_m-A7M", c) is not None and abs(T("primary", "cocro_m-A7M", c).mean_diff) < 0.01)
AB = tt[tt.family == "ablation"]
for ab, key in (("cocro_m_k1", "k1"), ("cocro_m_lap", "lap"), ("cocro_m_plug", "plug"), ("cocro_m_nb1", "nb1"), ("cocro_m_s1", "s1"), ("cocro_mfg", "mfg")):
    q = AB[AB.comparison == f"{ab}-cocro_m"]
    V[f"abl_{key}_rng"] = f"{f(float(q.mean_diff.min()), 3)} to {f(float(q.mean_diff.max()), 3)}"
    V[f"abl_{key}_sig"] = str(int((q.holm_p < 0.05).sum()))
    V[f"abl_{key}_worse"] = str(int(((q.holm_p < 0.05) & (q.mean_diff > 0)).sum()))
    V[f"abl_{key}_beyond"] = str(int(((q.holm_p < 0.05) & (q.mean_diff.abs() >= 0.01)).sum()))
R = tt[tt.family.str.startswith("rollout")]
V["roll_rng"] = f"{f(float(R.mean_diff.min()), 3)} to {f(float(R.mean_diff.max()), 3)}"
V["roll_min_holm"] = f(float(R.holm_p.min()), 4).replace(MINUS, "")
V["roll_sig"] = str(int((R.holm_p < 0.05).sum()))
ratios = [S("cocro", c, "ms_per_epoch") / S("cocro_m", c, "ms_per_epoch") for c in CELLS[:4]]
V["roll_cost_ratio"] = f"{min(ratios):.0f} to {max(ratios):.0f}"
V["cocro_m_vs_A7M_ms"] = f"{min(S('cocro_m', c, 'ms_per_epoch') / S('A7M', c, 'ms_per_epoch') for c in CELLS):.1f} to {max(S('cocro_m', c, 'ms_per_epoch') / S('A7M', c, 'ms_per_epoch') for c in CELLS):.1f}"
V["util_cocro_m"] = "yes" if all(abs(S("cocro_m", c, "mutations") - int(c[-1])) < 1e-9 for c in CELLS) else "no"
V["seeds_tier_A"] = "150"
V["runs_tier_A"] = f"{json.load(open(f'{A}/validation.json'))['n_runs']:,}"
V["commit_tier_A"] = json.load(open(f"{A}/validation.json"))["git_commit"][:7]
step2 = json.load(open("revision/analysis/R3/step2/rules.json"))
V["step2_final"] = step2["decision"]["final"]
V["step2_roll_mean"] = f(step2["rules"]["R-roll:plain (cocro vs cocro_m)"]["mean_d"], 4)
V["step2_roll_z"] = f(step2["rules"]["R-roll:plain (cocro vs cocro_m)"]["mean_z"], 2)
# wins/losses on connectivity metrics (descriptive)
def better(metric, a, b, lower=True):
    n = sum((S(a, c, metric) < S(b, c, metric)) if lower else (S(a, c, metric) > S(b, c, metric)) for c in CELLS if not np.isnan(S(b, c, metric)))
    return n, sum(1 for c in CELLS if not np.isnan(S(b, c, metric)))
V["disc_cocro_m_vs_A7M"] = "%d of %d" % better("disconnected", "cocro_m", "A7M")
V["disc_b8_vs_cocro_m"] = "%d of %d" % better("disconnected", "B8", "cocro_m")
V["rec_b8_vs_cocro_m"] = "%d of %d" % better("recovery", "B8", "cocro_m")
V["eff_cocro_m_best"] = "yes" if all(float(eff[(eff.cell == c) & (eff.arm == "cocro_m")].dE_per_mutation.iloc[0]) >=
                                     max(float(eff[(eff.cell == c) & (eff.arm == a)].dE_per_mutation.iloc[0]) for a in ("A7M", "B8", "C1") if len(eff[(eff.cell == c) & (eff.arm == a)])) for c in CELLS) else "no"

# ------------------------------------------------------------------ tables
arms_main = ["A0", "A1", "A7", "A7M", "B8", "C1", "cocro_m", "cocro"]
rows = []
for a in arms_main:
    r = [LAB[a]]
    for c in CELLS:
        e = S(a, c, "E_mean")
        r.append("not run" if np.isnan(e) and a in ("cocro", "B8") else (f"{e:.3f} ({S(a, c, 'E_sd'):.3f})"))
    rows.append(r)
open(f"{OUT}/t_means.md", "w", encoding="utf-8").write(table(["Arm"] + [CL[c] for c in CELLS], rows))

rows = []
for c in CELLS:
    row = [CL[c]]
    for comp in ("cocro_m-A7M", "cocro_m-B8", "cocro_m-C1"):
        r = T("primary", comp, c)
        row.append("not evaluated" if r is None else f"{f(r.mean_diff, 3)} [{f(r.boot_lo, 3)}, {f(r.boot_hi, 3)}]{mark(r)}")
    rows.append(row)
open(f"{OUT}/t_primary.md", "w", encoding="utf-8").write(table(["Condition", "COCRO-M − A7M", "COCRO-M − B8", "COCRO-M − C1"], rows))

rows = []
for _, r in P.iterrows():
    rows.append([CL[r.cell], r.comparison.replace("cocro_m", "COCRO-M").replace("-", " − "), int(r.n), f(r.mean_diff, 4), f"[{f(r.boot_lo, 4)}, {f(r.boot_hi, 4)}]", f(r.dz, 2),
                 f"{r.holm_p:.1e}" if r.holm_p < 0.001 else f"{r.holm_p:.3f}", r["verdict_0.01"], r["verdict_0.02"]])
open(f"{OUT}/t_primary_detail.md", "w", encoding="utf-8").write(table(["Condition", "Comparison", "n", "ΔE", "95% CI", "dz", "Holm p", "Verdict (margin 0.01)", "Verdict (margin 0.02)"], rows))

abl = [("cocro_m_k1", "single removal candidate"), ("cocro_m_lap", "Laplacian surrogate"), ("cocro_m_s1", "one scenario"), ("cocro_m_plug", "no posterior sampling"),
       ("cocro_m_nb1", "no propagation term"), ("cocro_mfg", "+ full-horizon rerank")]
rows = []
for c in CELLS:
    row = [CL[c]]
    for a, _ in abl:
        r = T("ablation", f"{a}-cocro_m", c)
        row.append(f"{f(r.mean_diff, 3)} [{f(r.boot_lo, 3)}, {f(r.boot_hi, 3)}]{mark(r)}")
    rows.append(row)
open(f"{OUT}/t_ablation.md", "w", encoding="utf-8").write(table(["Condition"] + [n for _, n in abl], rows))

for Mset, name in (("6", "t_conn_m6"), ("3", "t_conn_m3")):
    rows = []
    for c in [x for x in CELLS if x.endswith("M" + Mset)]:
        for a in ["A7M", "B8", "C1", "cocro_m", "cocro"]:
            if np.isnan(S(a, c, "E_mean")):
                continue
            rows.append([CL[c], LAB[a].replace(" (exploratory)", " (expl.)"), f"{S(a, c, 'disconnected'):.3f}", f"{S(a, c, 'longest_disc'):.1f}", f"{S(a, c, 'recovery'):.2f}",
                         f"{S(a, c, 'worst_E'):.3f}", f"{S(a, c, 'overhead'):.1f}", f"{S(a, c, 'mutations'):.2f}"])
    open(f"{OUT}/{name}.md", "w", encoding="utf-8").write(table(["Condition", "Arm", "Disconnected share", "Longest disconnection (epochs)", "Anchored recovery (epochs)", "Worst-case E",
                                                                  "Overhead", "Mutations"], rows))
rows = []
for a in ["A7M", "B8", "C1", "cocro_m", "cocro_mfg", "cocro"]:
    rows.append([LAB[a]] + [("n/a" if np.isnan(S(a, c, "ms_per_epoch")) else f"{S(a, c, 'ms_per_epoch'):.1f}") for c in ("S1_M6", "S2_M6", "S3_M6")] +
                [("n/a" if np.isnan(S(a, c, "seconds")) else f"{S(a, c, 'seconds'):.1f}") for c in ("S1_M6", "S2_M6", "S3_M6")])
open(f"{OUT}/t_cost.md", "w", encoding="utf-8").write(table(["Arm", "S1: ms/epoch", "S2: ms/epoch", "S3: ms/epoch", "S1: s/run", "S2: s/run", "S3: s/run"], rows))
rows = []
for a in ["A7M", "B8", "C1", "cocro_m"]:
    rows.append([LAB[a]] + [("n/a" if not len(eff[(eff.cell == c) & (eff.arm == a)]) else f"{float(eff[(eff.cell == c) & (eff.arm == a)].dE_per_mutation.iloc[0]):.4f}") for c in CELLS])
open(f"{OUT}/t_eff.md", "w", encoding="utf-8").write(table(["Arm"] + [CL[c] for c in CELLS], rows))

# earlier studies (v0.8 held-out E2, R2 original and amended): counts of conditions with the first arm lower / higher at Holm p < 0.05
def counts(path, comp, fam=None):
    d = pd.read_csv(path)
    d = d[(d.comparison == comp) & (d.status == "tested")]
    lo = int(((d.holm_p < 0.05) & (d.mean_diff < 0)).sum()); hi = int(((d.holm_p < 0.05) & (d.mean_diff > 0)).sum())
    return len(d), lo, hi, len(d) - lo - hi
E2, R2m, R2a = "revision/analysis/E2", "revision/analysis/R2/main", "revision/analysis/R2/amended"
rows = []
for study, path, comp, text in ((f"v0.8 held-out (60 seeds)", f"{E2}/primary_tests.csv", "B8-A1", "B8 vs A1 (reactive)"),
                                ("v0.8 held-out (60 seeds)", f"{E2}/primary_tests.csv", "B8-A7", "B8 vs A7 (front-loaded)"),
                                ("v0.8 held-out (60 seeds)", f"{E2}/matched_budget_tests.csv", "B8-A7M", "B8 vs A7M"),
                                ("R2 original (60 seeds)", f"{R2m}/primary_tests.csv", "C1-A7", "C1 vs A7"), ("R2 original (60 seeds)", f"{R2m}/primary_tests.csv", "C1-B8", "C1 vs B8"),
                                ("R2 amended, matched budgets (60 seeds)", f"{R2a}/primary_tests.csv", "C1-A7", "C1 vs A7"),
                                ("R2 amended, matched budgets (60 seeds)", f"{R2a}/primary_tests.csv", "C1-B8", "C1 vs B8")):
    n, lo, hi, eq = counts(path, comp)
    rows.append([study, text, n, lo, hi, eq])
open(f"{OUT}/t_earlier.md", "w", encoding="utf-8").write(table(["Study", "Comparison (first vs second)", "Conditions evaluated", "First arm lower error (Holm p < 0.05)", "Second arm lower error (Holm p < 0.05)",
                                                                    "No significant difference"], rows))
for name, path, comp in (("e2_b8_a7", f"{E2}/primary_tests.csv", "B8-A7"), ("r2a_c1_a7", f"{R2a}/primary_tests.csv", "C1-A7")):
    n, lo, hi, eq = counts(path, comp)
    V[name] = f"{hi} of {n}" if "b8" in name else f"{lo} of {n}"
n, lo, hi, eq = counts(f"{E2}/primary_tests.csv", "B8-A1"); V["e2_b8_a1_lower"] = f"{lo} of {n}"

# Step-2 rules
rows = []
for k, v in step2["rules"].items():
    rows.append([k.split(" (")[0].replace("R-", "R-"), k.split("(")[1].rstrip(")"), f(v["mean_d"], 4), f"{v['cells_nonpositive']}/{v['n_cells']}", f(v["mean_z"], 2), "yes" if v["adopt"] else "no"])
open(f"{OUT}/t_step2.md", "w", encoding="utf-8").write(table(["Rule", "Comparison", "Mean ΔE over 4 cells", "Cells with ΔE ≤ 0", "Mean z", "Adopted"], rows))
json.dump(V, open(f"{OUT}/v3_values.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ------------------------------------------------------------------ figures
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6})
COL = {"A7M": "#2a78d6", "B8": "#eb6834", "C1": "#8a8984", "cocro_m": "#1baf7a", "cocro": "#6250d6"}
fig, axes = plt.subplots(2, 3, figsize=(12, 6.2))
order = ["A1", "A7M", "B8", "C1", "cocro_m", "cocro"]
for ax, c in zip(axes.ravel(), CELLS):
    for i, a in enumerate(order):
        e = S(a, c, "E_mean")
        if np.isnan(e):
            continue
        ax.errorbar(e, i, xerr=[[e - S(a, c, "E_ci_lo")], [S(a, c, "E_ci_hi") - e]], fmt="o", color=COL.get(a, "#52514e"), ms=5, capsize=2, lw=1.2)
    ax.axvline(S("A0", c, "E_mean"), color="#8a8984", ls="--", lw=1)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(["A1", "A7M", "B8", "C1", "COCRO-M", "COCRO+rollout"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title(CL[c])
    ax.set_xlabel("mean E (95% interval); dashed: Static")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"{FIG}/fig_E_by_cell.{ext}", dpi=200, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(8.2, 5.4))
y, ylab = 0, []
for comp, nm in (("cocro_m-A7M", "A7M"), ("cocro_m-B8", "B8"), ("cocro_m-C1", "C1")):
    for c in CELLS:
        r = T("primary", comp, c)
        if r is None:
            continue
        ax.errorbar(r.mean_diff, y, xerr=[[r.mean_diff - r.boot_lo], [r.boot_hi - r.mean_diff]], fmt="o", color=COL[nm], ms=5, capsize=2, lw=1.3)
        ylab.append(f"vs {nm}: {CL[c]}")
        y += 1
    y += 0.6
ax.axvline(0, color="#52514e", lw=0.8)
ax.axvspan(-0.01, 0.01, color="#cde2fb", alpha=0.5, lw=0)
ax.set_yticks([i for i in range(len(ylab))] if False else [yy for yy in np.cumsum([0] * 0)])
pos, k = [], 0
for comp in range(3):
    n_ = sum(1 for c in CELLS if T("primary", ["cocro_m-A7M", "cocro_m-B8", "cocro_m-C1"][comp], c) is not None)
    pos += [k + j for j in range(n_)]
    k += n_ + 0.6
ax.set_yticks(pos)
ax.set_yticklabels(ylab, fontsize=7.5)
ax.invert_yaxis()
ax.set_xlabel("paired difference in mean E (COCRO-M minus comparator; negative = COCRO-M lower); band: margin 0.01; bars: 95% bootstrap CI")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"{FIG}/fig_primary_forest.{ext}", dpi=200, bbox_inches="tight")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=False)
for ax, c in zip(axes, ("S1_M6", "S2_M6", "S3_M6")):
    for a in ["A1", "A7M", "B8", "C1", "cocro_m", "cocro_mfg", "cocro"]:
        e, ms = S(a, c, "E_mean"), S(a, c, "ms_per_epoch")
        if np.isnan(e):
            continue
        ax.scatter(ms, e, color=COL.get(a, "#52514e"), s=40, zorder=3)
        ax.annotate({"A1": "A1", "A7M": "A7M", "B8": "B8", "C1": "C1", "cocro_m": "COCRO-M", "cocro_mfg": "+rerank", "cocro": "+rollout"}[a], (ms, e), xytext=(4, 3), textcoords="offset points", fontsize=7.5)
    ax.set_xscale("log")
    ax.set_title(CL[c])
    ax.set_xlabel("decision time per epoch (ms, log scale)")
    ax.set_ylabel("mean E")
fig.tight_layout()
for ext in ("png", "pdf"):
    fig.savefig(f"{FIG}/fig_cost_error.{ext}", dpi=200, bbox_inches="tight")
plt.close(fig)
print(json.dumps(V, indent=1, ensure_ascii=False)[:2500])


# ------------------------------------------------------------------ captions, static tables, procedure figure
CAP = {
    "t_step2_cap": "**Table 3** Development-stage adoption rules (seeds 8520–8539, four cells). Mean ΔE is the second-named variant minus the first-named; a rule passes only if mean ΔE is at most the threshold, ΔE ≤ 0 in at least 3 of 4 cells, and mean z ≤ −1.5. No rule passed.",
    "t_means_cap": "**Table 4** Mean consensus error E (SD over 150 seeds) per arm and condition; lower is better. Static has no mutations; B8 was not calibrated for S2, M = 6; the rollout variant was run in S1 and S2 only.",
    "t_primary_cap": "**Table 5** Primary family (17 tests, Holm within the family). ΔE = COCRO-M minus comparator, mean [95% bootstrap CI]; negative: COCRO-M has lower error. * Holm p < 0.05; ** also |ΔE| ≥ 0.01.",
    "t_ablation_cap": "**Table 6** Ablations relative to COCRO-M (ΔE = variant minus COCRO-M; positive: the variant has higher error), mean [95% bootstrap CI]. * Holm p < 0.05 within the 36-test family; ** also |ΔE| ≥ 0.01.",
    "t_conn_m6_cap": "**Table 7** Secondary measures, M = 6 (means over 150 seeds; descriptive, no tests). Disconnected share: fraction of epochs with a disconnected live graph; longest disconnection and anchored recovery in epochs; overhead: pending link-epochs plus live-link releases.",
    "t_conn_m3_cap": "**Table 8** Secondary measures, M = 3 (means over 150 seeds; descriptive, no tests).",
    "t_cost_cap": "**Table 9** Mean decision time per epoch (ms) and run time per run (s), M = 6; measured with parallel workers under load, indicative only. n/a: arm not run in that condition.",
    "t_eff_cap": "**Table 10** Error reduction per realised mutation relative to Static (higher is better; descriptive).",
    "t_earlier_cap": "**Table 11** Earlier studies (60 held-out seeds each): number of conditions in which the first-named or the second-named arm had significantly lower error (Holm p < 0.05) and in which neither did.",
    "t_primary_detail_cap": "**Table A1** All primary tests: ΔE = COCRO-M minus comparator; dz: standardised paired effect size; verdicts at the 0.01 and 0.02 margins.",
}
for k, v in CAP.items():
    open(f"{OUT}/{k}.md", "w", encoding="utf-8").write(v + "\n")
related = [["Consensus-law design (event-triggered, adaptive, fault-tolerant)", "Protocol", "Given or switching topology", "No topology change", "—"],
           ["Connectivity-preserving control (MPC, barrier functions)", "Motion or links, constraint-based", "Known model, connectivity constraint", "Continuous control", "No hard rewiring cap"],
           ["Budget-limited rewiring for information flow", "Which links to add", "Static objective", "Offline or one-shot", "No failure process"],
           ["Reactive threshold (A1); front-loaded schedules (A7, A7M)", "When to spend", "State-blind or error threshold", "Fixed rule", "Earlier controllers of this study"],
           ["Predictive and debt-based triggers (B8, C1)", "When and which", "Hand-built risk or debt scores", "Calibrated thresholds", "Earlier controllers of this study"],
           ["COCRO-M (this paper)", "Which link to swap", "Fitted posterior failure model; scenario-averaged spectral gain", "Timing fixed (front-loaded), selection by expected gain", "Centralised; tested on random geometric graphs only"]]
open(f"{OUT}/t_related.md", "w", encoding="utf-8").write("**Table 1** Mechanism comparison of the controller families discussed (qualitative; no performance comparison is implied).\n\n" + table(["Family", "Decision addressed", "Failure/objective model", "Adaptation", "Note"], related))
arms = [["A0", "Static", "No mutations", "earlier"], ["A1", "Reactive", "Spend when error exceeds a calibrated threshold", "earlier"], ["A7 / A7M", "Front-loaded", "Spend at the first eligible epochs (A7: count from a calibrated distribution; A7M: exactly M)", "earlier"],
        ["B8", "Predictive", "Risk-filtered predictive score and calibrated trigger", "earlier"], ["C1", "Causal debt", "Resilience debt with causal attribution of stress to failure episodes", "earlier"],
        ["COCRO-M", "Selection only", "Front-loaded timing; swap chosen by expected gain over 8 posterior scenarios (K_r = 2, K_a = 5)", "this paper (final)"],
        ["k1 / lap / s1 / plug / nb1", "Ablations", "One removal; Laplacian surrogate; one scenario; posterior mean; no lagged-neighbour term", "this paper"],
        ["mfg", "Full-horizon rerank", "COCRO-M with a shortlist reranked by full-horizon simulated gain", "this paper (exploratory)"], ["cocro", "Rollout timing", "COCRO with a rollout shadow price deciding when to act", "this paper (exploratory)"]]
open(f"{OUT}/t_arms.md", "w", encoding="utf-8").write("**Table 2** Arms. Thresholds of A1, B8, C1 and the A7 count distribution are the frozen earlier calibrations.\n\n" + table(["Arm", "Name", "Rule", "Origin"], arms))

from matplotlib.patches import FancyBboxPatch  # noqa: E402
fig, ax = plt.subplots(figsize=(11, 3.0))
ax.axis("off")
steps = ["1. Observe link\nstates", "2. Update CFPE\n(hazards, repair\nmixture)", "3. Safe candidates\n(top 2 removals x\ntop 5 additions,\ngate)", "4. Draw 8 posterior\nfailure scenarios\n(length d + H)", "5. Score gain\nS_setup + b(tau - d)\nper scenario", "6. Pick argmax of\nmean gain", "7. Apply if cooldown\nand cap M allow"]
for i, t in enumerate(steps):
    x = i * 1.52
    ax.add_patch(FancyBboxPatch((x, 0.2), 1.35, 1.6, boxstyle="round,pad=0.03", fc="#e6f0fb", ec="#2a78d6", lw=1.2))
    ax.text(x + 0.675, 1.0, t, ha="center", va="center", fontsize=7.6)
    if i < len(steps) - 1:
        ax.annotate("", xy=(x + 1.5, 1.0), xytext=(x + 1.38, 1.0), arrowprops=dict(arrowstyle="->", color="#52514e"))
ax.text(0, -0.15, "Not in the final algorithm: rollout shadow price for timing; full-horizon rerank (exploratory variants only).", fontsize=7.6, color="#52514e")
ax.set_xlim(-0.1, 10.8)
ax.set_ylim(-0.4, 2.0)
fig.savefig(f"{FIG}/fig_procedure.png", dpi=200, bbox_inches="tight")
fig.savefig(f"{FIG}/fig_procedure.pdf", bbox_inches="tight")
plt.close(fig)
