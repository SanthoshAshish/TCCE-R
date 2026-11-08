"""Additional V3 figures from the Tier A analysis files.   python paper/tools/make_v3_figs2.py   (run after make_v3_sections.py)"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

A, FIG = "revision/analysis/R3/A", "paper/figures_v3"
summ = pd.read_csv(f"{A}/summary_by_arm_cell.csv")
tests = pd.read_csv(f"{A}/tests.csv")
tt = tests[tests.status == "tested"]
ps = pd.read_csv(f"{A}/per_seed_metrics.csv")
eff = pd.read_csv(f"{A}/efficiency.csv")
step2 = json.load(open("revision/analysis/R3/step2/rules.json"))
CELLS = ["S1_M3", "S1_M6", "S2_M3", "S2_M6", "S3_M3", "S3_M6"]
CL = {c: f"{c[:2]}, M = {c[-1]}" for c in CELLS}
COL = {"A7M": "#2a78d6", "B8": "#eb6834", "C1": "#8a8984", "cocro_m": "#1baf7a", "cocro": "#6250d6"}
NAME = {"A7M": "A7M", "B8": "B8", "C1": "C1", "cocro_m": "COCRO-M", "cocro": "COCRO+rollout"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6})


def S(arm, cell, col):
    r = summ[(summ.arm == arm) & (summ.cell == cell)][col]
    return float(r.iloc[0]) if len(r) else np.nan


def save(fig, name):
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{FIG}/{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def grouped(ax, metric, arms, ylabel, title=None):
    w = 0.8 / len(arms)
    for j, a in enumerate(arms):
        v = [S(a, c, metric) for c in CELLS]
        ax.bar(np.arange(6) + j * w - 0.4 + w / 2, v, w, color=COL[a], label=NAME[a])
    ax.set_xticks(range(6))
    ax.set_xticklabels([CL[c] for c in CELLS], fontsize=7.5, rotation=20)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)


# 1. step-2 adoption rules
fig, ax = plt.subplots(figsize=(8, 3.6))
keys = list(step2["rules"])
vals = [step2["rules"][k]["mean_d"] for k in keys]
thr = [-0.010 if k.startswith("R-roll") else -0.005 for k in keys]
y = np.arange(len(keys))
ax.barh(y, vals, color="#8a8984", height=0.5, label="mean ΔE (4 development cells)")
ax.scatter(thr, y, marker="|", s=400, color="#eb6834", zorder=3, label="adoption threshold")
ax.axvline(0, color="#52514e", lw=0.8)
ax.set_yticks(y)
ax.set_yticklabels([k.split(" (")[0] + "\n(" + k.split("(")[1].rstrip(")") + ")" for k in keys], fontsize=7)
ax.invert_yaxis()
ax.set_xlabel("mean paired ΔE (negative favours the more complex variant)")
ax.legend(fontsize=7.5, loc="lower left")
save(fig, "fig_step2")

# 2. per-seed paired differences, three primary comparisons
fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
piv = ps.pivot_table(index=["cell", "seed"], columns="arm", values="E")
for ax, cmp_ in zip(axes, ("A7M", "B8", "C1")):
    data, labs = [], []
    for c in CELLS:
        if cmp_ in piv.columns and c in piv.index.get_level_values(0):
            d = (piv.loc[c]["cocro_m"] - piv.loc[c][cmp_]).dropna()
            if len(d):
                data.append(d.values)
                labs.append(CL[c])
    parts = ax.violinplot(data, showmedians=True, widths=0.8)
    for b in parts["bodies"]:
        b.set_facecolor(COL[cmp_])
        b.set_alpha(0.5)
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.set_xticks(range(1, len(labs) + 1))
    ax.set_xticklabels(labs, fontsize=7, rotation=25)
    ax.set_title(f"COCRO-M − {cmp_}")
axes[0].set_ylabel("per-seed ΔE (negative: COCRO-M lower)")
save(fig, "fig_perseed")

# 3. ablation forest
abl = [("cocro_m_k1", "single removal"), ("cocro_m_lap", "Laplacian surrogate"), ("cocro_m_s1", "one scenario"), ("cocro_m_plug", "no posterior sampling"), ("cocro_m_nb1", "no propagation"), ("cocro_mfg", "+ full-horizon rerank")]
fig, axes = plt.subplots(2, 3, figsize=(11, 5.6), sharex=True)
for ax, c in zip(axes.ravel(), CELLS):
    for i, (a, nm) in enumerate(abl):
        r = tt[(tt.family == "ablation") & (tt.comparison == f"{a}-cocro_m") & (tt.cell == c)].iloc[0]
        ax.errorbar(r.mean_diff, i, xerr=[[r.mean_diff - r.boot_lo], [r.boot_hi - r.mean_diff]], fmt="o", color="#2a78d6" if r.holm_p < 0.05 else "#8a8984", ms=4, capsize=2)
    ax.axvline(0, color="#52514e", lw=0.8)
    ax.axvspan(-0.01, 0.01, color="#cde2fb", alpha=0.5, lw=0)
    ax.set_yticks(range(len(abl)))
    ax.set_yticklabels([n for _, n in abl], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_title(CL[c])
for ax in axes[1]:
    ax.set_xlabel("ΔE vs COCRO-M (positive: variant worse)")
save(fig, "fig_ablation")

# 4. disconnection and recovery
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
for ax, (m, lab) in zip(axes, (("disconnected", "disconnected share"), ("longest_disc", "longest disconnection (epochs)"), ("recovery", "anchored recovery (epochs)"))):
    grouped(ax, m, ["A7M", "B8", "C1", "cocro_m", "cocro"], lab)
axes[0].legend(fontsize=7)
save(fig, "fig_connectivity")

# 5. trade-offs
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for a in ["A7M", "B8", "C1", "cocro_m", "cocro"]:
    for c in CELLS:
        e = S(a, c, "E_mean")
        if np.isnan(e):
            continue
        axes[0].scatter(S(a, c, "mutations"), e, color=COL[a], s=28, label=NAME[a] if c == CELLS[0] else None)
        axes[1].scatter(S(a, c, "overhead"), e, color=COL[a], s=28)
axes[0].set_xlabel("realised mutations per run")
axes[1].set_xlabel("reconfiguration overhead")
for ax in axes:
    ax.set_ylabel("mean E (one point per condition)")
axes[0].legend(fontsize=7)
save(fig, "fig_tradeoff")

# 6. worst-case E
fig, ax = plt.subplots(figsize=(8, 3.6))
grouped(ax, "worst_E", ["A7M", "B8", "C1", "cocro_m", "cocro"], "worst-case E (mean over seeds)")
ax.set_ylim(0.6, 0.82)
ax.legend(fontsize=7, ncol=3)
save(fig, "fig_worst")

# 7. efficiency
fig, ax = plt.subplots(figsize=(8, 3.6))
w = 0.2
for j, a in enumerate(["A7M", "B8", "C1", "cocro_m"]):
    v = [float(eff[(eff.cell == c) & (eff.arm == a)].dE_per_mutation.iloc[0]) if len(eff[(eff.cell == c) & (eff.arm == a)]) else np.nan for c in CELLS]
    ax.bar(np.arange(6) + j * w - 0.3, v, w, color=COL[a], label=NAME[a])
ax.set_xticks(range(6))
ax.set_xticklabels([CL[c] for c in CELLS], fontsize=7.5)
ax.set_ylabel("error reduction per mutation vs Static")
ax.legend(fontsize=7, ncol=4)
save(fig, "fig_efficiency")

# 8. decision time, all conditions
fig, ax = plt.subplots(figsize=(8, 3.6))
grouped(ax, "ms_per_epoch", ["A7M", "B8", "C1", "cocro_m", "cocro"], "decision time per epoch (ms, log scale)")
ax.set_yscale("log")
ax.legend(fontsize=7, ncol=3)
save(fig, "fig_time")
print("ok")
