"""Descriptive evidence for the retry-rule proposal, from the existing dev-seed (8200-8219) logs in results/r2/diag_c1.
Pools C1 and B8 logs. No parameter changed, no inference: bins and counts only.   python -m experiments.analyze_r2_retry_evidence"""
import glob
import re

import numpy as np
import pandas as pd

rows_fail, rows_mut = [], []
for f in sorted(glob.glob("results/r2/diag_c1/epochs_*.csv")):
    arm = f.rsplit("_", 1)[1][:-4]
    for seed, d in pd.read_csv(f).groupby("seed"):
        d = d.reset_index(drop=True)
        att = d[d.v06_attempt.astype(bool)]
        outs = []
        for s in d.theta_update.fillna(""):
            outs += re.findall(r":([SFN])\(([-+0-9.e]+)\)", s)
        mi, nfail_since = 0, 0
        for i, r in att.iterrows():
            nxt = att[att.index > i]
            if r.v06_attempt_ok:
                o = outs[mi] if mi < len(outs) else (None, np.nan)
                rows_mut.append(dict(arm=arm, seed=seed, epoch=i, fails_before=nfail_since, outcome=o[0], delta=float(o[1]) if o[1] is not None and o[0] else np.nan,
                                     benefit=r.rcpr_benefit))
                mi += 1; nfail_since = 0
            else:
                nfail_since += 1
                rows_fail.append(dict(arm=arm, seed=seed, epoch=i, margin=r.rcpr_benefit, nxt_ok=(bool(nxt.iloc[0].v06_attempt_ok) if len(nxt) else np.nan),
                                      gap=(nxt.index[0] - i) if len(nxt) else np.nan))
F, M = pd.DataFrame(rows_fail), pd.DataFrame(rows_mut)
F["bin"] = pd.cut(F.margin, [-np.inf, -0.05, -0.02, -0.005, 0.0], labels=["<=-0.05", "-0.05..-0.02", "-0.02..-0.005", "-0.005..0"]).astype(object).fillna("no candidate passes risk/gate")
print("FAILED ATTEMPTS:", len(F), " (with a following attempt in the same run:", int(F.nxt_ok.notna().sum()), ")")
print(F.groupby("bin").agg(n=("margin", "size"), next_attempt_succeeds=("nxt_ok", "mean"), mean_gap_epochs=("gap", "mean")).round(3).to_string())
M["fb"] = pd.cut(M.fails_before, [-1, 0, 2, 100], labels=["0", "1-2", ">=3"])
print("\nMUTATIONS:", len(M), " evaluated outcomes:", int(M.outcome.notna().sum()))
g = M[M.outcome.notna()].groupby("fb", observed=True)
print(g.agg(n=("outcome", "size"), success=("outcome", lambda x: (x == "S").mean()), failure=("outcome", lambda x: (x == "F").mean()),
            neutral=("outcome", lambda x: (x == "N").mean()), mean_delta=("delta", "mean")).round(3).to_string())
print("\nmean predicted benefit at mutation by outcome:"); print(M.groupby("outcome").benefit.agg(["size", "mean"]).round(4).to_string())
F.to_csv("results/r2/diag_retry/failed_attempts.csv", index=False); M.to_csv("results/r2/diag_retry/mutations.csv", index=False)
