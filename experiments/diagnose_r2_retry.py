"""Revision 2 retry-rule diagnostic (development seeds 8200-8219 only; no parameter changed).
C1 is run three times per cell/seed with r2_retry = none | audit | state. 'audit' must reproduce 'none' exactly; its counters
say how many re-attempts hit an unchanged decision-relevant state and how many of those would have turned into a mutation.
  python -m experiments.diagnose_r2_retry          -> results/r2/diag_retry/
"""
import os

import numpy as np
import pandas as pd

from experiments.diagnose_r2_c1 import CELLS, SEEDS
from experiments.v06_common import run_tasks
from tccer.config import load_config, replace

OUT = "results/r2/diag_retry"


def main():
    assert min(SEEDS) >= 8200 and max(SEEDS) <= 8219
    os.makedirs(OUT, exist_ok=True)
    modes = ("none", "audit", "state")
    jobs = [(sc, M, mode, seed, replace(load_config(f"configs/v0.8/frozen/B8_{sc}_M{M}.yaml"), r2_retry=mode))
            for sc, M in CELLS for mode in modes for seed in SEEDS]
    res = run_tasks([(c, s, "r2_causal", "rows") for _, _, _, s, c in jobs], max(1, (os.cpu_count() or 2) - 1))
    rec, df = [], {}
    for (sc, M, mode, seed, _), rows in zip(jobs, res):
        d = pd.DataFrame(rows); df[(sc, M, mode, seed)] = d
        l = d.iloc[-1]
        rec.append(dict(cell=f"{sc}_M{M}", mode=mode, seed=seed, n_mut=int(l.n_mutations), attempts=int(l.v06_attempts_total),
                        failed=int(l.v06_failed_attempts_total), suppressible=int(l.r2_suppressible), suppressed=int(l.r2_suppressed),
                        flips=int(l.r2_flips), E_mean=d.E_hat.mean(), disc=float((d.components > 1).mean()),
                        first_mut=float(d.index[d.n_mutations >= 1][0]) if (d.n_mutations >= 1).any() else np.nan))
    per = pd.DataFrame(rec); per.to_csv(f"{OUT}/per_run.csv", index=False)
    ident = all(np.array_equal(df[(sc, M, "none", s)][c].values, df[(sc, M, "audit", s)][c].values)
                for sc, M in CELLS for s in SEEDS for c in ("E_hat", "n_mutations", "mutation", "debt"))
    print("audit reproduces none exactly (E_hat, n_mutations, mutation, debt) in all runs:", ident)
    same_mut = sum(df[(sc, M, "none", s)].mutation.tolist() == df[(sc, M, "state", s)].mutation.tolist()
                   for sc, M in CELLS for s in SEEDS)
    print(f"state reproduces none's exact mutation sequence in {same_mut}/{len(CELLS) * len(SEEDS)} runs")
    m = per.groupby(["cell", "mode"]).mean(numeric_only=True).drop(columns="seed")
    m.to_csv(f"{OUT}/summary.csv")
    pd.set_option("display.width", 250)
    print(m.round(3).to_string())


if __name__ == "__main__":
    main()
