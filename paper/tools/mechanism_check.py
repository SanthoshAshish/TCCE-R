"""Exploratory descriptive check (NOT a pre-specified test): how does each arm spend its mutations in the v0.7 held-out
evaluation? Reads results/v0.7/eval/<cell>/epochs.csv. Writes paper/supplementary/mechanism_check.csv.

Per arm and cell (all seeds pooled, one row per mutation):
  share_while_disconnected : mutation decided at an epoch whose live graph had > 1 component
  share_reconnecting       : the chosen mutation joined two components (M_dcomp = -1)
  mean_gain_connected      : mean first-order lambda2-gain estimate M_gain of mutations made while connected
  share_first20            : mutation decided in epochs 0-19
  mean_first_epoch         : mean over runs of the epoch of the first mutation (runs with none excluded)
"""
import os
import numpy as np
import pandas as pd

ROOT = "results/v0.7/eval"
rows = []
for cell in sorted(d for d in os.listdir(ROOT) if d.startswith("S")):
    df = pd.read_csv(os.path.join(ROOT, cell, "epochs.csv"), low_memory=False,
                     usecols=["arm", "seed", "epoch", "components", "select_outcome", "M_dcomp", "M_gain"])
    mut = df[df.select_outcome == "mutated"]
    for arm, g in mut.groupby("arm"):
        conn = g[g.components == 1]
        first = g.groupby("seed").epoch.min()
        rows.append({"cell": cell, "arm": arm, "n_mutations": len(g), "n_runs": df[df.arm == arm].seed.nunique(),
                     "share_while_disconnected": float((g.components > 1).mean()),
                     "share_reconnecting": float((g.M_dcomp == -1).mean()),
                     "mean_gain_connected": float(conn.M_gain.mean()) if len(conn) else np.nan,
                     "share_first20": float((g.epoch < 20).mean()), "mean_first_epoch": float(first.mean())})
out = pd.DataFrame(rows)
os.makedirs("paper/supplementary", exist_ok=True)
out.to_csv("paper/supplementary/mechanism_check.csv", index=False)
pd.set_option("display.width", 220)
print(out.round(3).to_string(index=False))
