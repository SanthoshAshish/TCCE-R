"""Post-run integrity checks on the v0.4 evaluation (read-only diagnostics; nothing is re-tuned).
1. per-seed mutation-count matching; 2. gate rejection reasons; 3. why reconnection was impossible."""
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd

import tccer.core.safety as S
import tccer.sim.engine as eng
from tccer.config import load_config, replace
from tccer.network.state import NetworkState
from tccer.sim.engine import simulate

# 1. matching
for d in [0, 2, 4, 8]:
    df = pd.read_csv(f"results/v0.4/eval_d{d}/epochs.csv")
    M = df[df.epoch == 79].pivot(index="seed", columns="policy", values="n_mutations")
    print(f"d={d}: seeds with count == TCCE-R  reactive {(M.reactive == M.tccer).sum()}/30, "
          f"periodic {(M.periodic == M.tccer).sum()}/30")

# 2 + 3. replay seeds with instrumentation (same configs, same seeds; identical runs)
reasons, why = Counter(), Counter()
orig_rej = S.SafetyGate._reject
S.SafetyGate._reject = lambda self, r: (reasons.update([(CUR, r)]), orig_rej(self, r))[1]
holder = {}
class Spy(NetworkState):
    def __init__(s, *a, **k):
        super().__init__(*a, **k); holder["s"] = s
eng.NetworkState = Spy
orig_can = eng.MutationPipeline.can_reconnect
def can(self, state, k, max_tries=30):
    ok = orig_can(self, state, k, max_tries)
    if not ok:
        comp = {x: c for c, nodes in enumerate(nx.connected_components(state.graph())) for x in nodes}
        cross_up = [i for i in range(state.P) if comp[state.eu[i]] != comp[state.ev[i]] and not state.down[i]]
        if not cross_up:
            why["physically impossible: every in-range link between components is failed"] += 1
        elif all(state.configured[i] for i in cross_up):
            why["crossing links configured but still in setup"] += 1
        else:
            tabu = self.tabu(k)
            free_failed = state.configured & state.down & ~tabu
            why["no releasable failed link (all in cooldown)" if not free_failed.any()
                else "crossing link exists but in cooldown / degree / gate"] += 1
    return ok
eng.MutationPipeline.can_reconnect = can
for d in [2, 8]:
    cfg = load_config(f"configs/v0.4/selected_d{d}.yaml")
    # replay TCCE-R and matched reactive/periodic exactly as experiments.run does
    for seed in range(5000, 5030):
        CUR = "tccer"
        M = simulate(cfg, seed, "tccer", log_rounds=False)[0][-1]["n_mutations"]
        for CUR in ["reactive", "periodic"]:
            simulate(replace(cfg, mutation_cap=M, period=max(1, cfg.epochs // (M + 1)) if M else cfg.epochs + 1),
                     seed, CUR, log_rounds=False)
print("\ngate rejection reasons (d=2 and d=8, matched runs):", dict(reasons))
print("reconnect-impossible epochs, by cause:", dict(why))
