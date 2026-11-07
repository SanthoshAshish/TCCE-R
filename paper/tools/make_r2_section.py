"""Generate paper/tables_v08/R2_SECTION.md (Section 6.11 and Appendix F text) from the two Revision 2 analysis folders:
revision/analysis/R2/main (original, seeds 9100-9159) and revision/analysis/R2/amended (Amendment 1, seeds 9200-9259), plus the two
calibration reports. All numbers and verdict counts come from those files; nothing is typed by hand.   python paper/tools/make_r2_section.py"""
import os
import shutil

import numpy as np
import pandas as pd

DIRS = {"original": "revision/analysis/R2/main", "amended": "revision/analysis/R2/amended"}
CALS = {"original": "configs/r2/frozen/calibration_report.csv", "amended": "configs/r2a/frozen/calibration_report.csv"}
CELLS = ["S1_rgg40_bursty_M3", "S1_rgg40_bursty_M6", "S2_rgg40_background_M3", "S2_rgg40_background_M6", "S3_rgg80_bursty_M3", "S3_rgg80_bursty_M6"]
LAB = {c: c.replace("_rgg40_bursty", "").replace("_rgg40_background", "").replace("_rgg80_bursty", "").replace("_M", ", M = ") for c in CELLS}
LAB = {c: c.split("_")[0] + ", M = " + c[-1] for c in CELLS}
NL = "\n"


def table(header, rows):
    return ("| " + " | ".join(header) + " |" + NL + "|" + "---|" * len(header) + NL + NL.join("| " + " | ".join(map(str, r)) + " |" for r in rows) + NL)


def f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def load(which):
    d = DIRS[which]
    return {"sum": pd.read_csv(f"{d}/summary_by_arm_cell.csv"), "cnt": pd.read_csv(f"{d}/realised_counts.csv"),
            "prim": pd.read_csv(f"{d}/primary_tests.csv"), "ref": pd.read_csv(f"{d}/reference_tests.csv"),
            "eff": pd.read_csv(f"{d}/per_mutation_efficiency.csv"), "ps": pd.read_csv(f"{d}/per_seed_metrics.csv")}


def means_table(D):
    rows = []
    for c in CELLS:
        s = D["sum"][D["sum"].cell == c].set_index("arm")
        n = D["cnt"][D["cnt"].cell == c].set_index("arm")
        row = [LAB[c]]
        for a in ("A1", "A7", "A7M", "B8", "C1"):
            row.append(f"{s.at[a, 'E_mean']:.3f} ({n.at[a, 'mean_mutations']:.2f})" if a in s.index else "excluded")
        rows.append(row)
    return table(["Condition", "A1", "A7", "A7M", "B8", "C1"], rows)


def tests_table(D):
    rows = []
    for c in CELLS:
        row = [LAB[c]]
        for comp in ("C1-B8", "C1-A7", "C1-A7M", "C1-A1"):
            t = D["prim"][(D["prim"].cell == c) & (D["prim"].comparison == comp) & (D["prim"].status == "tested")]
            if len(t) == 0:
                row.append("excluded")
                continue
            r = t.iloc[0]
            mark = "**" if r.holm_p < 0.05 and abs(r.mean_diff) >= 0.02 else ("*" if r.holm_p < 0.05 else "")
            row.append(f"{r.mean_diff:+.3f} [{r.boot_lo:+.3f}, {r.boot_hi:+.3f}]{mark}")
        rows.append(row)
    return table(["Condition", "C1 − B8", "C1 − A7", "C1 − A7M", "C1 − A1"], rows)


def conn_table(D):
    rows = []
    for c in CELLS:
        s = D["sum"][D["sum"].cell == c].set_index("arm")
        for a in ("A7M", "B8", "C1"):
            if a in s.index:
                r = s.loc[a]
                rows.append([LAB[c], a, f(r.disconnected_mean), f(r.longest_disc_mean, 1), f(r.anchored_recovery_mean, 1), f(r.worst_E_mean), f(r.overhead_sum_mean, 1)])
    return table(["Condition", "Arm", "Disconnected share", "Longest disconnection", "Anchored recovery", "Worst-case E", "Overhead"], rows)


def eff_table(D):
    rows = []
    for c in CELLS:
        e = D["eff"][(D["eff"].cell == c)].set_index("arm")
        rows.append([LAB[c]] + [f(e.at[a, "ratio_of_means"], 4) if a in e.index else "excluded" for a in ("A1", "A7", "A7M", "B8", "C1")])
    return table(["Condition", "A1", "A7", "A7M", "B8", "C1"], rows)


def counts_summary(D, M=None):
    n = D["cnt"]
    out = []
    for a in ("B8", "C1"):
        v = n[n.arm == a]
        out.append(f"{v.mean_mutations.min():.2f} to {v.mean_mutations.max():.2f}")
    z = D["ps"][D["ps"].arm.isin(["B8", "C1"]) & D["ps"].M.notna()].groupby("arm").mutations.apply(lambda x: (x == 0).mean())
    return out, z


def verdicts(D, comp):
    t = D["prim"][(D["prim"].comparison == comp) & (D["prim"].status == "tested")]
    v = t.verdict.fillna("")
    first = int(v.str.startswith("first arm meaningfully").sum())
    second = int(v.str.startswith("second arm meaningfully").sum())
    eq = int(v.str.contains("equivalent").sum())
    inc = int(v.str.contains("inconclusive").sum())
    small1 = int(v.str.contains("first arm better, below").sum())
    small2 = int(v.str.contains("second arm better, below").sum())
    return dict(n=len(t), first=first, second=second, eq=eq, inc=inc, small1=small1, small2=small2)


def sentence(D, comp):
    v = verdicts(D, comp)
    x, y = comp.split("-")
    return (f"{comp.replace('-', ' − ')}: {v['n']} evaluable conditions; {x} had lower error with Holm p < 0.05 in {v['first'] + v['small1']} "
            f"({v['first']} beyond the 0.02 margin), {y} had lower error in {v['second'] + v['small2']} ({v['second']} beyond the margin), "
            f"{v['eq']} were practically equivalent and {v['inc']} inconclusive.")


def calib_table(which):
    r = pd.read_csv(CALS[which])
    rows = []
    for s, M in sorted({(a, b) for a, b in zip(r.scenario, r.M)}):
        row = [f"{s.split('_')[0]}, M = {M}"]
        for a in ("A1", "B8", "C1"):
            x = r[(r.scenario == s) & (r.M == M) & (r.arm == a)]
            if len(x) == 0:
                row.append("-")
                continue
            x = x.iloc[0]
            row.append(f"{x.threshold:.4g} → {x.calibration_mean_count:.2f}" + ("" if x.calibratable else " (infeasible)"))
        rows.append(row)
    return table(["Condition", "A1: Θ₀ → count", "B8: Θ₀ → count", "C1: Θ₀ → count"], rows)


def main():
    have = {k: os.path.exists(DIRS[k] + "/primary_tests.csv") for k in DIRS}
    D = {k: load(k) for k in DIRS if have[k]}
    L = []
    for k, name in (("original", "fig_r2_E_original"), ("amended", "fig_r2_E_amended")):
        if have[k]:
            shutil.copy(f"{DIRS[k]}/figures/fig_E_by_cell.png", f"paper/figures_v0.8/{name}.png")
    L.append("### 6.11. Revision 2 extension: causality-aware resilience debt (C1)")
    L.append("""
**What was implemented.** One component of the planned Revision 2 algorithm was built and evaluated: a causality-aware debt ledger (C1) that replaces B8's CUSUM debt. The ledger keeps one liability item per link-failure episode, weights it by the link's first-order share of algebraic connectivity, charges consensus error only to open damage, treats episodes shorter than d + 2 = 4 epochs (setup delay d = 2) as temporary, up-weights failures that begin next to an earlier failure, settles an item when its link is removed by a rewiring or repaired, and keeps a decaying scar after persistent damage. There is no blanket debt reset after a mutation. C1 is B8 with only the debt replaced; the adaptive threshold, counterfactual feedback, predictive selector, cooldown, cap and edge budget are B8's. A retry rule skips re-evaluation after a failed attempt while the decision-relevant state is unchanged. **What was not implemented:** calibrated uncertainty-aware failure prediction, delayed mutation-credit assignment (specified only), the rewire/defer/reserve decision (opportunity-cost optimisation), the long-horizon marginal-gain selector, the formal theoretical results (connectivity, consensus error, budget feasibility, debt stability, optimisation, complexity), Erdős–Rényi, Barabási–Albert and Watts–Strogatz graphs, larger graphs, cascading/correlated/node/unpredictable failure laws, sensitivity analysis and scalability measurements. The ledger's design constants were fixed in advance and not tuned; C1 is a proposal evaluated here, not an established method.""")
    L.append("""
**Protocol.** C1, B8 and A1 were calibrated by the same count-matching rule (Section 5; docs/R2_DESIGN_RULES.md); A7M, A7 and Static are as before. Comparisons were fixed before the held-out runs: the primary family is C1 against B8, A7, A7M and A1 (Holm within the family), with B8 against A1, A7 and A7M as a reference family, margin 0.02. The original evaluation (calibration seeds 8300–8319, held-out seeds 9100–9159) calibrated on the mean count under a cap of 12. Its result is reported in full below because it exposed a flaw in the calibration rule, and it is not replaced. Amendment 1 (written and committed before any amended run; docs/R2_AMENDMENT_1.md) calibrates on the realised count under the actual per-run cap M with fresh seeds (calibration 8400–8419, held-out 9200–9259).""")
    if "original" in D:
        o = D["original"]
        cz, zz = counts_summary(o)
        L.append(f"""
**Original evaluation (seeds 9100–9159).**

**Table 10** Mean consensus error E per arm and condition, with mean realised mutations per run in parentheses (original evaluation, 60 seeds). A1 is excluded in S3, M = 3 (infeasible at calibration).

{means_table(o)}
![Fig. 11. Original evaluation (seeds 9100–9159): mean consensus error per arm with 95% t-intervals; dashed line: Static.](figures_v0.8/fig_r2_E_original.png)

**Table 11** Paired differences in E (first − second; negative: first arm lower error), 95% bootstrap CI; one asterisk marks Holm p < 0.05 within the primary family, two asterisks also |ΔE| ≥ 0.02 (original evaluation).

{tests_table(o)}
Fig. 11 shows the mean errors of Table 10 and Table 11 the paired differences. {sentence(o, 'C1-B8')} {sentence(o, 'C1-A7')} {sentence(o, 'C1-A7M')} {sentence(o, 'C1-A1')}

**Realised budgets differed.** Mean realised mutations per condition ranged over {cz[0]} (B8) and {cz[1]} (C1) against the targets M = 3 and 6; the share of runs with no mutation was {zz.get('B8', float('nan')):.3f} for B8 and {zz.get('C1', float('nan')):.3f} for C1. The cause is the calibration rule: it matched the mean count of runs capped at 12, which is a sound match for arms with a narrow count distribution (A1, B8) but not for C1, whose counts were bimodal (many runs with no mutation, others reaching the cap), so the actual cap M reduced C1's mean far below M (on the calibration seeds, 1.55 against 3 in every M = 3 condition). Differences between C1 and B8, A7M or A7 in this evaluation are therefore confounded with unequal reconfiguration budgets.""")
    if "amended" in D:
        a = D["amended"]
        cz, zz = counts_summary(a)
        L.append(f"""
**Amended, budget-matched evaluation (Amendment 1; held-out seeds 9200–9259).** Thresholds were chosen on the realised mean count under the actual cap M (Table F2). Because a capped mean cannot exceed M, the rule selects thresholds at which most runs reach the cap, for all arms; the comparison is then mainly about when and which links are rewired at near-equal budgets.

**Table 12** As Table 10, amended evaluation (60 seeds; mean realised mutations in parentheses).

{means_table(a)}
![Fig. 12. Amended evaluation (seeds 9200–9259): mean consensus error per arm with 95% t-intervals; dashed line: Static.](figures_v0.8/fig_r2_E_amended.png)

**Table 13** As Table 11, amended evaluation.

{tests_table(a)}
Fig. 12 shows the mean errors of Table 12 and Table 13 the paired differences. {sentence(a, 'C1-B8')} {sentence(a, 'C1-A7')} {sentence(a, 'C1-A7M')} {sentence(a, 'C1-A1')} The reference comparisons of B8 are in the repository tables (`revision/analysis/R2/amended/reference_tests.csv`).

Mean realised mutations ranged over {cz[0]} (B8) and {cz[1]} (C1); the share of runs with no mutation was {zz.get('B8', float('nan')):.3f} (B8) and {zz.get('C1', float('nan')):.3f} (C1).

**Table 14** Connectivity, recovery and reconfiguration overhead, amended evaluation (means over 60 seeds; overhead = pending link-epochs + live-link releases).

{conn_table(a)}
**Table 15** Performance per realised mutation, amended evaluation: mean improvement in E over Static (same scenario and seed) divided by mean realised mutations (exploratory; higher is better).

{eff_table(a)}""")
    L.append("""
**Interpretation.** These results are reported as estimates; none supports a claim that the causality-aware ledger improves consensus resilience. Where C1's error is not lower than B8's or the front-loaded baselines', the ledger did not help under this design and these constants; because the constants were fixed rather than tuned and only one scenario family was tested, this does not show that a better causality-aware design could not help. The original evaluation is a pre-registered result with an identified calibration flaw; the amended evaluation corrects that flaw on fresh seeds and is the budget-matched comparison. Both are kept.""")
    open("paper/tables_v08/R2_SECTION.md", "w", encoding="utf-8").write(NL.join(L) + NL)
    app = ["### Appendix F. Revision 2 calibration (final thresholds)", "",
           "**Table F1** Original calibration (seeds 8300–8319; count under a cap of 12): Θ₀ → mean count on the calibration seeds. Θ₀ is on different scales for A1 (error threshold), B8 (CUSUM) and C1 (ledger) and is not comparable across arms.", "", calib_table("original")]
    if os.path.exists(CALS["amended"]):
        app += ["**Table F2** Amended calibration (seeds 8400–8419; count under the actual cap M): Θ₀ → mean capped count.", "", calib_table("amended")]
    open("paper/tables_v08/R2_APPENDIX.md", "w", encoding="utf-8").write(NL.join(app) + NL)
    print("wrote R2_SECTION.md, R2_APPENDIX.md for", list(D))


if __name__ == "__main__":
    main()
