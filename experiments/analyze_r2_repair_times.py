"""Distribution of link-failure episode lengths (policy-independent environment) on DEVELOPMENT seeds 8200-8219, for the three
v0.8 scenario cells, to justify the ledger's persistence age cd_tau. Initial configured links only. No consensus is simulated.
  python -m experiments.analyze_r2_repair_times     -> results/r2/diag_repair/"""
import os

import numpy as np
import pandas as pd

from tccer.config import load_config
from tccer.network.events import FailureTrace
from tccer.network.generators import make_network
from tccer.network.scenario import load_scenario
from tccer.network.state import NetworkState

SEEDS = range(8200, 8220)
SC = {"S1_rgg40_bursty": "S1_rgg40_bursty_M3", "S2_rgg40_background": "S2_rgg40_background_M3", "S3_rgg80_bursty": "S3_rgg80_bursty_M3"}
OUT = "results/r2/diag_repair"


def episodes(cfg, seed):
    pos, eu, ev, length, init_idx = make_network(cfg, seed)
    st = NetworkState(pos, eu, ev, length, init_idx)
    tr = FailureTrace(cfg, seed, st.P, edge_mid=(pos[eu] + pos[ev]) / 2)
    bg = st.down.copy(); D = []
    for k in range(cfg.epochs):
        bg = tr.epoch_update(k, bg)
        D.append((bg | tr.burst[k])[init_idx])
    D = np.array(D); out = []
    for j in range(D.shape[1]):
        run, start = 0, None
        for k in range(cfg.epochs + 1):
            on = k < cfg.epochs and D[k, j]
            if on:
                run += 1
            elif run:
                out.append(dict(length=run, censored=(k == cfg.epochs), onset=k - run))
                run = 0
    return pd.DataFrame(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    allr, rows = [], []
    for name, cell in SC.items():
        cfg = load_config(f"configs/v0.8/frozen/B8_{cell}.yaml")
        e = pd.concat([episodes(cfg, s).assign(seed=s) for s in SEEDS]); e["cell"] = name; allr.append(e)
        c = e[~e.censored]
        r = dict(cell=name, episodes=len(e), censored=int(e.censored.sum()), mean_len=c.length.mean(),
                 q10=c.length.quantile(.1), q50=c.length.quantile(.5), q90=c.length.quantile(.9), p_repair=cfg.p_repair,
                 burst_rate=cfg.burst_rate, geometric_mean_1_over_p=1 / cfg.p_repair)
        for t in range(1, 7):                         # share of episodes still short at age t: a "temporary" class if age < t
            r[f"P(len<{t + 0}) "] = float((e.length < t).mean()) if t > 1 else 0.0
        rows.append(r)
    A = pd.concat(allr); A.to_csv(f"{OUT}/episodes.csv", index=False)
    S = pd.DataFrame(rows); S.to_csv(f"{OUT}/summary.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(S.round(3).to_string())
    print("\nall cells pooled, episodes (incl. censored as >=):", len(A))
    print("length counts 1..8 (share):", (A.length.clip(upper=9).value_counts(normalize=True).sort_index().round(3)).to_dict())


if __name__ == "__main__":
    main()
