"""Regression-to-the-mean check of the legacy before/after feedback rule (motivation for the counterfactual rule).

Data: ARCHIVED v0.6 held-out evaluation (archive/v0.6/eval, seeds 6000-6059). For every feedback update that the v0.6 A5 arm
logged (mutation epoch m on seed s), apply the LEGACY rule to the STATIC run of the same seed, where no mutation occurred:
    success  <=>  mean E over epochs m+d+1..m+d+3  <  mean E over epochs m-2..m        (H = 3, d = setup delay)
and compare with the success share A5 itself obtained. The counterfactual rule compares replays with and without the
mutation under identical observed events, so a null mutation gives delta = 0 by construction (neutral).
Writes paper/supplementary/placebo_check.csv. Run: python paper/tools/placebo_check.py
"""
import os
import re
import numpy as np
import pandas as pd

H = 3
static = pd.read_csv("archive/v0.6/eval/A0_static/epochs.csv", low_memory=False, usecols=["seed", "epoch", "E_hat"])
E = {s: g.sort_values("epoch").E_hat.to_numpy() for s, g in static.groupby("seed")}
rows = []
for cell, d in (("d2_M3", 2), ("d2_M6", 2), ("d8_M3", 8), ("d8_M6", 8)):
    df = pd.read_csv(f"archive/v0.6/eval/{cell}/epochs.csv", low_memory=False, usecols=["arm", "seed", "theta_update"])
    a5 = df[(df.arm == "A5") & df.theta_update.notna() & (df.theta_update.astype(str) != "")]
    own, plac, n = [], [], 0
    for seed, txt in zip(a5.seed, a5.theta_update.astype(str)):
        for m, outcome in re.findall(r"(\d+):([SF])", txt):
            m = int(m)
            e = E[seed]
            before, after = e[max(0, m - H + 1): m + 1].mean(), e[m + d + 1: m + d + H + 1].mean()
            own.append(outcome == "S")
            plac.append(after < before)
            n += 1
    rows.append({"cell": cell, "delay": d, "n_updates": n, "A5_legacy_success_share": float(np.mean(own)),
                 "static_placebo_legacy_success_share": float(np.mean(plac)),
                 "counterfactual_null_mutation_outcome": "neutral by construction (delta = 0)"})
out = pd.DataFrame(rows)
os.makedirs("paper/supplementary", exist_ok=True)
out.to_csv("paper/supplementary/placebo_check.csv", index=False)
print(out.round(3).to_string(index=False))
