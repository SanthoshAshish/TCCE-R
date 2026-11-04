"""Generate every results table of the manuscript from the frozen v0.7 analysis outputs (no hand-typed numbers).

Inputs : results/v0.7/eval/analysis/*.csv, configs/v0.7/frozen/*, configs/v0.7/scenarios/*, paper/supplementary/*.csv,
         results/v0.7_focused/eval/analysis/*.csv (supplementary replication, if present)
Outputs: paper/tables/<name>.md (Markdown tables) and paper/tables/<name>.csv
Run    : python paper/tools/make_tables.py
"""
import os
import re

import numpy as np
import pandas as pd
import yaml

A = "results/v0.7/eval/analysis"
OUT = "paper/tables"
os.makedirs(OUT, exist_ok=True)
SC = {"S1_rgg40_bursty": "S1", "S2_rgg40_background": "S2", "S3_rgg80_bursty": "S3"}
CELL_ORDER = [f"{s}_M{m}" for s in SC for m in (3, 6)]
SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def cell_label(cell):
    m = re.match(r"(S\d)_.*_M(\d)", cell)
    return f"{m.group(1)}, M={m.group(2)}"


def fmt_p(p):
    if pd.isna(p):
        return "n/a"
    if p >= 0.001:
        return f"{p:.3f}"
    mant, exp = f"{p:.2e}".split("e")
    return f"{float(mant):.2f}×10{str(int(exp)).translate(SUP)}"


def fmt_ci(lo, hi, nd=4):
    return f"[{lo:+.{nd}f}, {hi:+.{nd}f}]"


def interpret(comp, verdict):
    """Plain-language reading of a verdict for the comparison 'X-Y' (difference = E_X - E_Y)."""
    x, y = comp.split("-")
    v = verdict
    if v.startswith("practically equivalent"):
        return "practically equivalent"
    if v == "inconclusive":
        return "inconclusive"
    if v.startswith("first arm meaningfully"):
        return f"{x} lower E, ≥ margin"
    if v.startswith("second arm meaningfully"):
        return f"{y} lower E, ≥ margin"
    if v.startswith("first arm better"):
        return f"{x} lower E, < margin"
    if v.startswith("second arm better"):
        return f"{y} lower E, < margin"
    return v


def write(name, df, caption_note=""):
    df.to_csv(f"{OUT}/{name}.csv", index=False)
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    open(f"{OUT}/{name}.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{name}: {len(df)} rows")


def tests_table(df, name, with_n=True):
    t = df[df.status == "tested"].copy()
    t["order"] = t.cell.map({c: i for i, c in enumerate(CELL_ORDER)})
    t = t.sort_values(["comparison", "order"]) if name.startswith("secondary") else t.sort_values(["order", "comparison"])
    out = pd.DataFrame({"Condition": t.cell.map(cell_label), "Comparison (E_X − E_Y)": t.comparison.str.replace("-", " − "),
                        "n": t.n.astype(int), "ΔE": t.mean_diff.map(lambda v: f"{v:+.4f}"),
                        "95% bootstrap CI": [fmt_ci(a, b) for a, b in zip(t.boot_lo, t.boot_hi)],
                        "Holm p": t.holm_p.map(fmt_p), "Reading": [interpret(c, v) for c, v in zip(t.comparison, t.verdict)]})
    return out


# ---- Table 2: scenarios, settings, calibration constants
cons = yaml.safe_load(open("configs/v0.7/frozen/constants.yaml", encoding="utf-8"))["scenarios"]
rows = []
for sc, short in SC.items():
    c = yaml.safe_load("\n".join(l for l in open(f"configs/v0.7/scenarios/{sc}.yaml", encoding="utf-8")
                                  if not l.startswith("#")))
    rows.append({"Scenario": short, "Nodes": c["n_nodes"], "Initial link radius": c["init_radius"],
                 "Radio range (candidate links)": c["radio_range"],
                 "Transient loss / round": c["p_transient"], "Background failure / repair (per epoch)": f"{c['p_fail']} / {c['p_repair']}",
                 "Bursts (rate; radius; duration)": ("none" if c["burst_rate"] == 0 else
                                                     f"{c['burst_rate']}/epoch; {c['burst_radius']}; {c['burst_min_len']}–{c['burst_max_len']} epochs"),
                 "Epochs × rounds": f"{c['epochs']} × {c['rounds_per_epoch']}", "Setup delay (epochs)": c["link_setup_epochs"],
                 "τ (episode threshold)": f"{cons[sc]['tau']:.4f}", "κ_E": f"{cons[sc]['kappa_E']:.4f}",
                 "κ_s": f"{cons[sc]['kappa_s']:.4f}"})
write("table2_scenarios", pd.DataFrame(rows))

# ---- Table 3: primary
prim = pd.read_csv(f"{A}/primary_tests.csv")
write("table3_primary", tests_table(prim, "primary"))

# ---- Table 4: secondary summary by comparison (+ full table for the appendix)
sec = pd.read_csv(f"{A}/secondary_tests.csv")
write("tableA1_secondary_full", tests_table(sec, "secondary_full"))
t = sec[sec.status == "tested"].copy()
rows = []
for comp, g in t.groupby("comparison", sort=False):
    v = g.verdict
    rows.append({"Comparison (E_X − E_Y)": comp.replace("-", " − "), "Evaluable conditions": len(g),
                 "Practically equivalent": int(v.str.startswith("practically equivalent").sum()),
                 "X lower E, ≥ margin": int(v.str.startswith("first arm meaningfully").sum()),
                 "X lower E, < margin (significant)": int(v.str.startswith("first arm better").sum()),
                 "Y lower E, ≥ margin": int(v.str.startswith("second arm meaningfully").sum()),
                 "Y lower E, < margin (significant)": int(v.str.startswith("second arm better").sum()),
                 "Inconclusive": int((v == "inconclusive").sum()),
                 "Range of ΔE": f"{g.mean_diff.min():+.4f} to {g.mean_diff.max():+.4f}",
                 "Smallest Holm p": fmt_p(g.holm_p.min())})
write("table4_secondary_summary", pd.DataFrame(rows))

# ---- Table 5: descriptive means (A0, A1, A5, A7) and exploratory paired differences
s = pd.read_csv(f"{A}/summary.csv")
s = s[s.group.isin(CELL_ORDER)]
def piv(metric, nd):
    p = s[s.metric == metric].pivot(index="group", columns="arm", values="mean")
    return p.reindex(CELL_ORDER)
rows = []
for cell in CELL_ORDER:
    for arm in ("A0", "A1", "A5", "A7"):
        def g(m, nd):
            v = piv(m, nd).loc[cell, arm]
            return "—" if pd.isna(v) else f"{v:.{nd}f}"
        rows.append({"Condition": cell_label(cell), "Arm": arm, "E": g("E", 4), "Disconnected fraction": g("disconnected", 3),
                     "λ₂": g("lambda2", 3), "Anchored recovery (epochs)": g("anchored_recovery", 2),
                     "Realised mutations": g("mutations", 2), "Live-link releases": g("live_link_releases", 2)})
write("table5a_descriptive", pd.DataFrame(rows))
e = pd.read_csv(f"{A}/exploratory_diffs.csv")
rows = []
for cell in CELL_ORDER:
    for comp in ("A5-A1", "A5-A7"):
        r = {"Condition": cell_label(cell), "Comparison": comp.replace("-", " − ")}
        sub = e[(e.cell == cell) & (e.comparison == comp)].set_index("metric")
        if sub.empty:
            continue
        for m, lab, nd in (("disconnected", "Δ disconnected", 3), ("lambda2", "Δ λ₂", 3), ("anchored_recovery", "Δ recovery (epochs)", 2),
                           ("live_link_releases", "Δ live-link releases", 2), ("E | equal realised counts", "ΔE, equal counts", 4)):
            x = sub.loc[m]
            r[lab] = f"{x.mean_diff:+.{nd}f} {fmt_ci(x.boot_lo, x.boot_hi, nd)}" + (f" (n={int(x.n)})" if m.startswith("E |") else "")
        rows.append(r)
write("table5b_exploratory_diffs", pd.DataFrame(rows))

# ---- feedback quality, calibration, mechanism
fq = pd.read_csv(f"{A}/feedback_quality.csv")
fq = fq.set_index("group").reindex(CELL_ORDER).reset_index()
write("table6_feedback", pd.DataFrame({"Condition": fq.group.map(cell_label), "Updates per A5 run": fq.fb_updates.map("{:.2f}".format),
                                       "Success": fq.fb_success.map("{:.1%}".format), "Failure": fq.fb_failure.map("{:.1%}".format),
                                       "Neutral": fq.fb_neutral.map("{:.1%}".format), "Mean Δ (E_with − E_without)": fq.fb_mean_delta.map("{:+.4f}".format)}))
cal = pd.read_csv("configs/v0.7/frozen/calibration_report.csv")
cal["Condition"] = cal.scenario.map(SC) + ", M=" + cal.M.astype(str)
write("tableA2_calibration", pd.DataFrame({"Condition": cal.Condition, "Arm": cal.arm, "Threshold": cal.threshold.map("{:.3f}".format),
                                           "Mean count (calibration seeds)": cal.calibration_mean_count.map("{:.2f}".format),
                                           "Feasible (±15% of M)": cal.calibratable.map({True: "yes", False: "NO"})}))
mc = pd.read_csv("paper/supplementary/mechanism_check.csv")
mc = mc[mc.arm.isin(["A1", "A3", "A5", "A6", "A7"])].copy()
mc["order"] = mc.cell.map({c: i for i, c in enumerate(CELL_ORDER)})
mc = mc.sort_values(["order", "arm"])
write("tableA3_mechanism", pd.DataFrame({"Condition": mc.cell.map(cell_label), "Arm": mc.arm, "Mutations (all runs)": mc.n_mutations,
                                         "Made while disconnected": mc.share_while_disconnected.map("{:.1%}".format),
                                         "Reconnecting moves": mc.share_reconnecting.map("{:.1%}".format),
                                         "Mean λ₂-gain estimate (connected)": mc.mean_gain_connected.map("{:.3f}".format),
                                         "Mean epoch of first mutation": mc.mean_first_epoch.map("{:.1f}".format)}))
pc = pd.read_csv("paper/supplementary/placebo_check.csv")
write("tableA4_placebo", pd.DataFrame({"v0.6 condition": pc.cell, "Feedback updates": pc.n_updates,
                                       "Legacy rule, A5's own updates: success": pc.A5_legacy_success_share.map("{:.1%}".format),
                                       "Legacy rule on Static run (no mutation): 'success'": pc.static_placebo_legacy_success_share.map("{:.1%}".format)}))

# ---- supplementary focused replication (exploratory; only if present)
fp = "results/v0.7_focused/eval/analysis"
if os.path.exists(f"{fp}/primary_tests.csv"):
    f1, f2 = pd.read_csv(f"{fp}/primary_tests.csv"), pd.read_csv(f"{fp}/secondary_tests.csv")
    both = pd.concat([f1, f2])
    both["order"] = both.cell.map({c: i for i, c in enumerate(CELL_ORDER)})
    both = both.sort_values(["order", "comparison"])
    out = pd.DataFrame({"Condition": both.cell.map(cell_label), "Comparison (E_X − E_Y)": both.comparison.str.replace("-", " − "),
                        "ΔE": both.mean_diff.map(lambda v: "excluded" if pd.isna(v) else f"{v:+.4f}"),
                        "95% bootstrap CI": [("not calibratable" if pd.isna(a) else fmt_ci(a, b)) for a, b in zip(both.boot_lo, both.boot_hi)],
                        "Holm p": both.holm_p.map(fmt_p),
                        "Reading": [("excluded" if st != "tested" else interpret(c, v)) for st, c, v in zip(both.status, both.comparison, both.verdict)]})
    write("tableS1_focused_replication", out)
