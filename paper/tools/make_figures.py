"""Manuscript figures. Figures 1-2 are diagrams drawn from verified implementation facts; Figure 3 is the existing
frozen-analysis figure (copied unchanged); Figures 4-5 are drawn from the frozen analysis CSVs.
Run: python paper/tools/make_figures.py   ->  paper/figures/fig{1..5}_*.png (+ .pdf for 1, 2, 4, 5)
"""
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

A = "results/v0.7/eval/analysis"
OUT = "paper/figures"
os.makedirs(OUT, exist_ok=True)
BLUE, ORANGE, GREEN, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#1f2328", "#59636e", "#e5e5e5"
CELLS = [f"{s}_M{m}" for s in ("S1_rgg40_bursty", "S2_rgg40_background", "S3_rgg80_bursty") for m in (3, 6)]
LABEL = {c: f"{c[:2]}, M={c[-1]}" for c in CELLS}
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK})


def box(ax, x, y, w, h, title, body, fc="#f3f6fb", ec=BLUE, tsize=8.6, bsize=6.9, num=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.012", fc=fc, ec=ec, lw=1.3))
    n_lines = title.count("\n") + 1
    ax.text(x + w / 2, y + h - 0.025, (f"({num}) " if num else "") + title, ha="center", va="top", fontsize=tsize,
            fontweight="bold", linespacing=1.15)
    ax.text(x + w / 2, y + h - (0.075 + 0.062 * n_lines), body, ha="center", va="top", fontsize=bsize, color=INK,
            linespacing=1.4)


def arrow(ax, p, q, style="-|>", ls="-", color=INK, rad=0.0, lw=1.3):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, lw=lw, ls=ls, color=color,
                                 connectionstyle=f"arc3,rad={rad}"))


# ------------------------------------------------------------------ Figure 1: architecture
def fig1():
    fig, ax = plt.subplots(figsize=(13.2, 7.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w, h = 0.172, 0.29
    xs = [0.012 + i * 0.198 for i in range(5)]
    yA, yB = 0.60, 0.20
    grey, blue = ("#f5f5f5", MUTED), ("#eef4fd", BLUE)
    row1 = [
        (1, "Dynamic Network\nState", "links: configured / failed / in setup\nfailures: transient, background\non-off, spatial bursts\nnode values x(t)", grey),
        (2, "Distributed Consensus\nMonitor", "Metropolis averaging, 60 rounds\nE = 1 − min(1, max(0, ln e(T)/ln ε))\nlocal disagreement: logged only", grey),
        (3, "Resilience-Debt\nEstimator", "C: bridge fraction (1 if disconnected)\nV: windowed link-state flips\ns = w_E·E + w_C·C + w_V·V\nD ← max(0, D + s − κ)", blue),
        (4, "Adaptive Mutation\nTrigger", "attempt a mutation if\nD > Θ  and  cooldown elapsed\nΘ ∈ [Θ₀/4, 4Θ₀]", blue),
        (5, "Consensus–Resilience\nCoupling Evaluator", "lexicographic ranking M:\nΔcomponents, λ₂-gain estimate,\nΔbridges, link length", blue),
    ]
    row2 = [
        (6, "Constraint /\nSafety Gate", "connectivity; λ₂ floor (R_min);\ndegree; edge budget;\ncooldowns; interim state", blue),
        (7, "Topology Mutation\nSelector", "first gate-approved candidate\nfrom the ranking (≤ 30 tries);\nrewire under a full budget", blue),
        (8, "Reconfigured\nNetwork", "removed link gone at once;\nnew link usable after\nd epochs (setup delay)", grey),
        (9, "Feedback Loop", "replay with / without the\nmutation (same observed events)\n→ Δ: success / failure /\nneutral → update Θ", blue),
    ]
    for x, (n, t, b, (fc, ec)) in zip(xs, row1):
        box(ax, x, yA, w, h, t, b, fc=fc, ec=ec, num=n)
    xs2 = [xs[4], xs[3], xs[2], xs[1]]
    for x, (n, t, b, (fc, ec)) in zip(xs2, row2):
        box(ax, x, yB, w, h, t, b, fc=fc, ec=ec, num=n)
    for i in range(4):                                                    # 1 -> 2 -> 3 -> 4 -> 5
        arrow(ax, (xs[i] + w + 0.004, yA + h / 2), (xs[i + 1] - 0.004, yA + h / 2))
    arrow(ax, (xs[4] + w / 2, yA - 0.005), (xs[4] + w / 2, yB + h + 0.005))                  # 5 -> 6
    for a, b in ((4, 3), (3, 2), (2, 1)):                                                      # 6 -> 7 -> 8 -> 9
        arrow(ax, (xs[a] - 0.004, yB + h / 2), (xs[b] + w + 0.004, yB + h / 2))
    arrow(ax, (xs[1] + w * 0.8, yB + h + 0.005), (xs[3] + w * 0.3, yA - 0.005), ls="--", color=BLUE, rad=-0.1)   # 9 -> 4
    ax.text(0.405, 0.50, "Θ update", fontsize=7.6, color=BLUE, ha="center")
    x8, x1, ybot = xs[2] + w / 2, xs[0] + w / 2, 0.155                                         # 8 -> 1, orthogonal path
    ax.plot([x8, x8, x1, x1], [yB - 0.005, ybot, ybot, yA - 0.03], color=MUTED, lw=1.3, ls="--")
    arrow(ax, (x1, yA - 0.03), (x1, yA - 0.005), color=MUTED, ls="--")
    ax.text((x8 + x1) / 2, ybot + 0.012, "reconfigured topology: next epoch's network state and measurements", fontsize=7.4,
            color=MUTED, ha="center")
    ax.plot([xs[0], xs[1] + w], [yA + h + 0.04] * 2, color=MUTED, lw=1.6)
    ax.text((xs[0] + xs[1] + w) / 2, yA + h + 0.052, "consensus dynamics: local neighbour exchange", ha="center",
            fontsize=8, color=MUTED)
    ax.plot([xs[2], xs[4] + w], [yA + h + 0.04] * 2, color=BLUE, lw=1.6)
    ax.text((xs[2] + xs[4] + w) / 2, yA + h + 0.052, "logically centralised topology controller (global graph information)",
            ha="center", fontsize=8, color=BLUE)
    ax.text(0.012, 0.085, "Not implemented as mechanisms: node load, traffic conditions, trust / uncertainty, adversarial-attack model.   "
            "R is operationalised provisionally as λ₂ (algebraic connectivity) of the live graph.", fontsize=7.6,
            color=MUTED, va="center")
    ax.text(0.012, 0.045, "Blue = stages that implement the proposed mechanism or differ between the compared strategies; "
            "grey = shared environment.  Arms A3–A5 use subsets of stages 3–4 (Table 1).", fontsize=7.6, color=MUTED,
            va="center")
    fig.savefig(f"{OUT}/fig1_architecture.png", dpi=220, bbox_inches="tight")
    fig.savefig(f"{OUT}/fig1_architecture.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ Figure 2: workflow
def fig2():
    fig, ax = plt.subplots(figsize=(13.2, 4.2))
    ax.set_xlim(-0.005, 1.012)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bw, bh, y = 0.185, 0.56, 0.36
    items = [
        (0.005, "Calibration", "seeds 200–219 (20)\n\nA0 static → τ, κ_E, κ_s\nA1–A5 threshold grid, uncapped\nselect threshold whose mean\nmutation count ≈ M (±15 %)\n(mutation counts only)", "#eef4fd", BLUE),
        (0.215, "Freeze", "A6/A7 count distributions\nfrom capped A1–A5 runs\n\n47 files + SHA-256 manifest\ncommitted before evaluation\n(commit 7a81352)", "#fff7e6", "#b7791f"),
        (0.425, "Held-out evaluation", "seeds 7000–7059 (60)\nrun once, clean git tree\n\n3 scenarios × 2 budgets\n× 8 arms × 60 seeds\n= 2,640 runs (2,700 planned)", "#eef4fd", BLUE),
        (0.635, "Analysis", "paired by seed, per condition\nWilcoxon signed-rank,\nHolm correction, bootstrap CI\npractical margin |ΔE| = 0.02\n\nprimary: 11 tests\nsecondary: 38 tests", "#eef4fd", BLUE),
    ]
    for x, t, b, fc, ec in items:
        box(ax, x, y, bw, bh, t, b, fc=fc, ec=ec, tsize=9.4, bsize=7.8)
    for i in range(3):
        arrow(ax, (items[i][0] + bw + 0.004, y + bh / 2), (items[i + 1][0] - 0.004, y + bh / 2), lw=1.6)
    box(ax, 0.848, y, 0.14, bh, "Outputs", "per-run CSV logs\nanalysis tables\nrun_info.json\n(commit, versions,\nconfig hashes)",
        "#f5f5f5", MUTED, tsize=9.4, bsize=7.8)
    arrow(ax, (items[3][0] + bw + 0.004, y + bh / 2), (0.844, y + bh / 2), lw=1.6)
    ax.text(0.005, 0.25, "Development seeds 300–319: tests and smoke runs only; never reported as results.", fontsize=8.2, color=MUTED)
    ax.text(0.005, 0.15, "A1 in S3 with M = 3 was not calibratable (best mean count 2.50, below the feasibility window 2.55–3.45); "
            "its 60 runs and the comparisons involving it are excluded.", fontsize=8.2, color=INK)
    ax.text(0.005, 0.05, "Calibration never uses consensus-error outcomes; held-out seeds are never used for any tuning.",
            fontsize=8.2, color=INK)
    fig.savefig(f"{OUT}/fig2_workflow.png", dpi=220, bbox_inches="tight")
    fig.savefig(f"{OUT}/fig2_workflow.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ Figure 4: primary forest
def forest(ax, rows, xlabel, margin=None, xlim=None):
    ys = np.arange(len(rows))[::-1]
    for y, r in zip(ys, rows):
        ax.errorbar(r["d"], y, xerr=[[r["d"] - r["lo"]], [r["hi"] - r["d"]]], fmt=r.get("m", "o"), color=r["c"], ms=5.5,
                    capsize=3, lw=1.6, zorder=3)
        if r.get("txt"):
            ax.text(r["hi"] + (xlim[1] - xlim[0]) * 0.015 if xlim else r["hi"], y, r["txt"], va="center", fontsize=7.2,
                    color=MUTED)
    ax.axvline(0, color=INK, lw=0.9)
    if margin:
        for v in (-margin, margin):
            ax.axvline(v, color=MUTED, lw=0.9, ls="--")
    ax.set_yticks(ys)
    ax.set_yticklabels([r["lab"] for r in rows], fontsize=8)
    ax.set_xlabel(xlabel, fontsize=8.6)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if xlim:
        ax.set_xlim(*xlim)


def fig4():
    p = pd.read_csv(f"{A}/primary_tests.csv")
    p = p[p.status == "tested"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3))
    for ax, comp, color, mk, title, lim in (
            (axes[0], "A5-A1", BLUE, "o", "TCCE-R (A5) − Reactive (A1)", (-0.03, 0.045)),
            (axes[1], "A5-A7", GREEN, "s", "TCCE-R (A5) − Front-loaded (A7)", (-0.03, 0.125))):
        d = p[p.comparison == comp].set_index("cell")
        d = d.reindex([c for c in CELLS if c in d.index])
        rows = [{"lab": LABEL[c], "d": r.mean_diff, "lo": r.boot_lo, "hi": r.boot_hi, "c": color, "m": mk,
                 "txt": f"Holm p = {r.holm_p:.2g}"} for c, r in d.iterrows()]
        forest(ax, rows, "Paired difference in E (positive: second arm has lower error)", 0.02, lim)
        ax.set_title(title, fontsize=9.6, loc="left")
    axes[0].text(0.0, -0.22, "A1 in S3, M=3 not calibratable: no comparison.", transform=axes[0].transAxes, fontsize=7.6,
                 color=MUTED)
    fig.text(0.01, 0.005, "Points: mean paired difference over 60 held-out seeds; bars: 95% bootstrap CI; solid line: 0; "
             "dashed lines: ±0.02 practical-effect margin.", fontsize=7.8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(f"{OUT}/fig4_primary_forest.png", dpi=220, bbox_inches="tight")
    fig.savefig(f"{OUT}/fig4_primary_forest.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ Figure 5: exploratory trade-offs
def fig5():
    e = pd.read_csv(f"{A}/exploratory_diffs.csv")
    metrics = [("disconnected", "Δ fraction of epochs disconnected"), ("lambda2", "Δ λ₂ (mean algebraic connectivity)"),
               ("anchored_recovery", "Δ anchored recovery time (epochs)"), ("live_link_releases", "Δ working links released per run")]
    fig, axes = plt.subplots(1, 4, figsize=(15.2, 4.6), sharey=True)
    for ax, (m, lab) in zip(axes, metrics):
        for cell in CELLS:
            for comp, c, mk, off in (("A5-A1", BLUE, "o", 0.16), ("A5-A7", GREEN, "s", -0.16)):
                r = e[(e.cell == cell) & (e.comparison == comp) & (e.metric == m)]
                if len(r):
                    r = r.iloc[0]
                    y = (len(CELLS) - 1 - CELLS.index(cell)) + off
                    ax.errorbar(r.mean_diff, y, xerr=[[r.mean_diff - r.boot_lo], [r.boot_hi - r.mean_diff]], fmt=mk,
                                color=c, ms=4.6, capsize=2.5, lw=1.4)
        ax.axvline(0, color=INK, lw=0.9)
        ax.set_xlabel(lab, fontsize=8.2)
        ax.grid(axis="x", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_yticks(range(len(CELLS)))
        ax.set_yticklabels([LABEL[c] for c in CELLS][::-1], fontsize=8)
    axes[0].legend(handles=[Line2D([], [], marker="o", color=BLUE, ls="", label="A5 − A1"),
                            Line2D([], [], marker="s", color=GREEN, ls="", label="A5 − A7")],
                   frameon=False, fontsize=8, loc="upper left")
    fig.text(0.01, 0.005, "Exploratory (not pre-specified tests). Mean paired difference over 60 seeds with 95% bootstrap CI. "
             "Lower is better for disconnection and recovery time; higher is better for λ₂.", fontsize=7.8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(f"{OUT}/fig5_exploratory_tradeoffs.png", dpi=220, bbox_inches="tight")
    fig.savefig(f"{OUT}/fig5_exploratory_tradeoffs.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig1()
    fig2()
    shutil.copyfile(f"{A}/fig_E_by_arm.png", f"{OUT}/fig3_E_by_arm.png")        # unchanged copy of the frozen-analysis figure
    fig4()
    fig5()
    print("figures written to", OUT, sorted(os.listdir(OUT)))
