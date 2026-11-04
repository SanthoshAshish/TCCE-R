"""Schematic figures for the v0.8 manuscript (no data): study workflow and the B8 per-epoch decision procedure.
   python paper/tools/make_figs_v08.py   -> paper/figures_v0.8/fig_workflow_v08.{png,pdf}, fig_b8_procedure.{png,pdf}"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = "paper/figures_v0.8"
INK, MUTE, BLUE, FILL, GREY = "#0b0b0b", "#52514e", "#2a78d6", "#edf4fd", "#f4f4f2"


def box(ax, x, y, w, h, title, body="", color=BLUE, fill=FILL, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.02", fc=fill, ec=color, lw=1.6))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=fs, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h / 2 - 0.02, body, ha="center", va="center", fontsize=fs - 1.5, color=MUTE, linespacing=1.35)


def arrow(ax, p, q, style="-|>", ls="-", color=INK, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, lw=1.3, ls=ls, color=color,
                                 connectionstyle=f"arc3,rad={rad}"))


def workflow():
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    w, h, y = 0.205, 0.40, 0.46
    xs = [0.01, 0.265, 0.52, 0.775]
    box(ax, xs[0], y, w, h, "1  Calibration", "seeds 8000-8019 only\nthresholds from mean mutation\ncounts (no error metric)\n28-point grids, runs capped at 12")
    box(ax, xs[1], y, w, h, "2  Amendment 1", "before any held-out run:\nfiner grids for 7 excluded\narm-cells + lower bound for B8\nin S2 at M = 6; same seeds")
    box(ax, xs[2], y, w, h, "3  Freeze", "configs + count PMFs + SHA-256\nmanifest (78 entries)\ncommit e16a208")
    box(ax, xs[3], y, w, h, "4  Held-out evaluation", "seeds 9000-9059, run once\n4,500 runs (12 arms x 6 cells\nx 60 seeds + Static)")
    for i in range(3):
        arrow(ax, (xs[i] + w + 0.004, y + h / 2), (xs[i + 1] - 0.004, y + h / 2))
    box(ax, 0.52, 0.04, 0.455, 0.27, "5  Pre-specified paired analysis", "Wilcoxon signed-rank, Holm per family (18 / 48 / 12 tests)\n95% bootstrap CI, rank-biserial r, margin 0.02;\nequivalence only if Holm p >= 0.05 and CI inside +-0.02", fs=9)
    arrow(ax, (xs[3] + w / 2, y - 0.004), (0.75, 0.315))
    box(ax, 0.01, 0.04, 0.455, 0.27, "Development seeds 8100-8119", "E1 predictor validation, smoke tests, code review;\nnever reported as results and never used\nto set a threshold", color=MUTE, fill=GREY, fs=9)
    ax.text(0.5, 0.975, "Study workflow (v0.8). Raw outputs are not modified by the analysis.", ha="center", va="top", fontsize=10, color=INK)
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/fig_workflow_v08.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def b8():
    fig, ax = plt.subplots(figsize=(12, 6.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    w, h = 0.225, 0.27
    row1, row2 = 0.62, 0.20
    box(ax, 0.01, row1, w, h, "Measure", "E_k, C_k, V_k from the epoch\ns_k = 0.5E + 0.3C + 0.2V\nD_k = max(0, D_{k-1} + s_k - kappa)")
    box(ax, 0.255, row1, w, h, "Trigger", "attempt iff D_k > Theta_k,\ncooldown of 2 epochs elapsed,\nfewer than M mutations so far")
    box(ax, 0.50, row1, w, h, "Shared candidates + gate", "one removed link r, added links\n(first 30 lexicographic ranks)\nfeasible shortlist, at most 10")
    box(ax, 0.745, row1, w, h, "Predict (B6, B7, B8, H1)", "E(a), R(a), C(a), S(a) for each a\nJ = E + 0.5 R + 0.05 C + S\nrisk filter: R(a) <= max(0.20, R(null))")
    box(ax, 0.745, row2, w, h, "Decide", "a* = argmin J\nact iff J(null) - J(a*) > 0\notherwise defer (attempt fails)")
    box(ax, 0.50, row2, w, h, "Apply", "rewire: remove r, add a*;\nadded link usable after d = 2 epochs;\ndebt reset to 0")
    box(ax, 0.255, row2, w, h, "Counterfactual feedback (B8, A5)", "after d + 3 epochs: replay with and\nwithout the mutation. Delta < 0 success,\n> 0 failure, = 0 neutral. Theta x0.9 /\nx1.25 / unchanged within [Theta0/4, 4 Theta0]", fs=8.5)
    box(ax, 0.01, row2, w, h, "Variants", "A4 (B5): lexicographic first choice\nB6: predictive, fixed Theta\nB7: legacy before/after feedback\nH1: A7-style front phase first", color=MUTE, fill=GREY)
    for a, b in (((0.236, row1 + h / 2), (0.254, row1 + h / 2)), ((0.481, row1 + h / 2), (0.499, row1 + h / 2)),
                 ((0.726, row1 + h / 2), (0.744, row1 + h / 2)), ((0.8575, row1 - 0.004), (0.8575, row2 + h + 0.004)),
                 ((0.744, row2 + h / 2), (0.726, row2 + h / 2)), ((0.499, row2 + h / 2), (0.481, row2 + h / 2))):
        arrow(ax, a, b)
    arrow(ax, (0.3675, row2 + h + 0.004), (0.3675, row1 - 0.004), ls="--", color=BLUE)
    ax.text(0.378, 0.5, "Theta update", color=BLUE, fontsize=9, va="center")
    ax.text(0.5, 0.97, "B8 (RCPR) per-epoch procedure as implemented. Centralised controller; the risk filter is an empirical criterion, not a guarantee.", ha="center", va="top", fontsize=10)
    ax.text(0.5, 0.04, "A1: attempt iff E_k > h. A7: attempts at epochs 0, 2, 4, ... A7M: the same with exactly M attempts. B2-B4: attempt iff the instantaneous stress exceeds h.", ha="center", fontsize=8.5, color=MUTE)
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/fig_b8_procedure.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def primary_forest_3col():
    """Re-lay-out of the E2 primary/matched forest plot (same data, 3 columns instead of 5) for legibility at print width."""
    import shutil
    import pandas as pd
    import experiments.analyze_v08 as A
    A._style()
    tests = pd.concat([pd.read_csv("revision/analysis/E2/primary_tests.csv"), pd.read_csv("revision/analysis/E2/matched_budget_tests.csv")])
    tmp = "paper/_tmp_fig"
    A._forest(tests, ["B8-A1", "B8-A7", "H1-A7", "B8-A7M", "H1-A7M"], "Primary and matched-budget comparisons", tmp, "fig_primary_forest", ncols=3)
    for ext in ("png", "pdf"):
        shutil.copy(f"{tmp}/figures/fig_primary_forest.{ext}", f"{OUT}/fig_primary_forest.{ext}")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    workflow()
    b8()
    primary_forest_3col()
    print("figures written to", OUT)
