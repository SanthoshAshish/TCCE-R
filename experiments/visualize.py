"""Network visualisation for demonstrations (v0.5).

  python -m experiments.visualize --config <config.yaml> --seed 0 --epochs 0 10 20 29 --out <folder>
        [--policies static periodic reactive tccer]

Re-runs ONE seed for each policy with exactly the same budget matching as experiments.run (TCCE-R first,
baselines capped at its mutation count), so the pictures correspond to the rows in epochs.csv for that seed.
Writes:
  network_initial.png    initial topology: initial links and all possible (in-range) links
  network_snapshots.png  rows = policies, columns = the requested epochs
  edge_states.csv        raw data behind the pictures: one row per (policy, epoch, link) with its status

Link status at epoch k (what the network looked like while epoch k ran, plus the decision taken at its end):
  active       configured, working, usable                 solid dark grey
  failed       configured but failed (random or scripted)  red dashed
  in setup     requested, not usable yet (setup delay)     blue dash-dot
  rewired in   added by a mutation since the previous      thick green (if active)
               snapshot column
  removed      released by a mutation since the previous   orange dotted
               snapshot column
  possible     in range but not configured                 faint grey dotted
Nodes outside the largest connected component are drawn as hollow orange squares.
Shaded red circles are scripted failure regions active at that epoch (scenario files only).
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

from tccer.config import load_config, replace
from tccer.network.scenario import load_scenario
from tccer.sim.engine import simulate

STYLE = {  # status: (colour, linestyle, linewidth, zorder)
    "possible": ("#c8c8c8", ":", 0.8, 1),
    "removed": ("#eb6834", ":", 2.2, 2),
    "active": ("#4a4a4a", "-", 1.4, 3),
    "rewired in": ("#1baf7a", "-", 3.4, 4),
    "in setup": ("#2a78d6", "-.", 2.2, 4),
    "failed": ("#d03b3b", "--", 2.0, 5),
}
ORDER = ["active", "rewired in", "failed", "in setup", "removed", "possible"]


def matched_config(cfg, M):
    """Same budget matching as experiments.run."""
    return replace(cfg, mutation_cap=M, period=max(1, cfg.epochs // (M + 1)) if M else cfg.epochs + 1)


def record(cfg, seed, policy):
    """Simulate and return (state, per-epoch snapshots, epoch rows)."""
    snaps = {}

    def on_epoch(k, state, m):
        cfg_now = state.configured.copy()
        cfg_during = cfg_now.copy()
        if m is not None and m.add is not None:
            cfg_during[m.add] = False
        if m is not None and m.remove is not None:
            cfg_during[m.remove] = True
        ready = state.ready_at <= k
        snaps[k] = {"configured": cfg_during, "down": state.down.copy(), "ready": ready,
                    "added": m.add if m is not None else None, "removed": m.remove if m is not None else None}
        holder["state"] = state

    holder = {}
    rows, _ = simulate(cfg, seed, policy, log_rounds=False, on_epoch=on_epoch)
    return holder["state"], snaps, rows


def statuses(state, snaps, k, prev_k):
    """Status of every potential link at snapshot epoch k (exclusive categories, most important first)."""
    s = snaps[k]
    added, removed = set(), set()
    for j in range(prev_k if prev_k is not None else 0, k):   # decided at end of prev..k-1 -> in effect by k
        if snaps[j]["added"] is not None:
            added.add(snaps[j]["added"])
        if snaps[j]["removed"] is not None:
            removed.add(snaps[j]["removed"])
    out = []
    for i in range(state.P):
        if s["configured"][i]:
            if s["down"][i]:
                st = "failed"
            elif not s["ready"][i]:
                st = "in setup"
            elif i in added:
                st = "rewired in"
            else:
                st = "active"
        else:
            st = "removed" if i in removed else "possible"
        out.append(st)
    return out


def draw(ax, state, status, title, regions=()):
    pos = state.pos
    for c, r in regions:
        ax.add_patch(Circle(c, r, color="#d03b3b", alpha=0.10, lw=0, zorder=0))
    for i, st in enumerate(status):
        col, ls, lw, z = STYLE[st]
        u, v = state.edge(i)
        ax.plot(*zip(pos[u], pos[v]), color=col, ls=ls, lw=lw, zorder=z, solid_capstyle="round")
    live = [i for i, st in enumerate(status) if st in ("active", "rewired in")]
    g = nx.Graph()
    g.add_nodes_from(range(state.n))
    g.add_edges_from(state.edge(i) for i in live)
    comps = sorted(nx.connected_components(g), key=len, reverse=True)
    main = comps[0]
    others = [x for x in range(state.n) if x not in main]
    ax.scatter(pos[list(main), 0], pos[list(main), 1], s=34, color="#1f1f1f", zorder=6)
    if others:
        ax.scatter(pos[others, 0], pos[others, 1], s=60, facecolor="white", edgecolor="#eb6834",
                   marker="s", lw=1.8, zorder=7)
    ax.set_title(f"{title}\ncomponents = {len(comps)},  working links = {len(live)}", fontsize=9)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    pad = 0.05
    ax.set_xlim(pos[:, 0].min() - pad, pos[:, 0].max() + pad)
    ax.set_ylim(pos[:, 1].min() - pad, pos[:, 1].max() + pad)
    return len(comps)


def legend_handles():
    h = [Line2D([], [], color=STYLE[s][0], ls=STYLE[s][1], lw=STYLE[s][2], label=s) for s in ORDER]
    h.append(Line2D([], [], marker="o", color="#1f1f1f", ls="", label="node (main component)"))
    h.append(Line2D([], [], marker="s", markerfacecolor="white", markeredgecolor="#eb6834", ls="",
                    label="node cut off from main component"))
    return h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, nargs="+", help="snapshot epochs (default: 4 evenly spaced)")
    ap.add_argument("--policies", nargs="+", default=["static", "periodic", "reactive", "tccer"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = load_config(a.config)
    os.makedirs(a.out, exist_ok=True)
    E = cfg.epochs
    epochs = sorted(set(a.epochs)) if a.epochs else sorted({0, E // 3, 2 * E // 3, E - 1})
    bad = [k for k in epochs if not 0 <= k < E]
    if bad:
        raise SystemExit(f"--epochs {bad} out of range: the config has epochs={E} (valid 0..{E - 1})")

    scen = load_scenario(cfg.scenario_file, cfg) if cfg.scenario_file else None

    def regions_at(k):
        if scen is None:
            return []
        return [(e["center"], e["radius"]) for e in scen.events
                if e["type"] == "region" and e["epoch"] <= k < e["epoch"] + e["duration"]]

    # TCCE-R first (budget matching), then the others
    t_state, t_snaps, t_rows = record(cfg, a.seed, "tccer")
    M = t_rows[-1]["n_mutations"]
    runs = {}
    for p in a.policies:
        if p == "tccer":
            runs[p] = (t_state, t_snaps, t_rows)
        else:
            runs[p] = record(cfg if p == "tccer_fixed" else matched_config(cfg, M), a.seed, p)

    # initial topology
    state0 = t_state
    from tccer.network.generators import random_geometric
    if scen is None:   # initial configured set is the seed's initial links
        init_idx = random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, a.seed)[4]
    else:
        init_idx = scen.init_idx
    init_status = ["active" if i in set(init_idx.tolist()) else "possible" for i in range(state0.P)]
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    draw(ax, state0, init_status, f"Initial topology (seed {a.seed}): {len(init_idx)} links, "
                                  f"{state0.P} possible links")
    ax.legend(handles=[legend_handles()[0], legend_handles()[5], legend_handles()[6]], fontsize=8,
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "network_initial.png"), dpi=150)
    plt.close(fig)

    # snapshot grid + raw edge states
    rows = []
    fig, axes = plt.subplots(len(a.policies), len(epochs), figsize=(3.3 * len(epochs), 4.0 * len(a.policies) + 0.9),
                             squeeze=False)
    for r, p in enumerate(a.policies):
        state, snaps, prows = runs[p]
        prev = None
        for c, k in enumerate(epochs):
            st = statuses(state, snaps, k, prev)
            E_k = prows[k]["E_hat"]
            draw(axes[r][c], state, st, f"{p}: epoch {k}  (E = {E_k:.2f})", regions_at(k))
            for i, s_ in enumerate(st):
                if s_ != "possible":
                    u, v = state.edge(i)
                    rows.append({"seed": a.seed, "policy": p, "epoch": k, "u": u, "v": v, "status": s_})
            prev = k
    fig.legend(handles=legend_handles(), loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.suptitle(f"Topology over time, seed {a.seed}: same failures for every policy "
                 f"(green = rewired in since the previous column)", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.subplots_adjust(hspace=0.32)
    fig.savefig(os.path.join(a.out, "network_snapshots.png"), dpi=130)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "edge_states.csv"), index=False)
    print(f"wrote network_initial.png, network_snapshots.png, edge_states.csv to {a.out}")


if __name__ == "__main__":
    main()
