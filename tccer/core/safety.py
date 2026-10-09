"""(6) Constraint / Safety Gate. Every policy (TCCE-R and baselines) goes through this same gate.

A mutation is accepted only if, on the live graph after the mutation:
  1. the number of connected components does not increase;
  2. if connected, lambda2 >= min(lambda2_min, lambda2_before)   (resilience floor R_min; never
     push a graph that is already above the floor below it, never make a weak graph weaker);
  3. no node exceeds degree d_max;
  4. a pure addition keeps live links <= edge budget;
  5. no touched edge is in cooldown (stability constraint, prevents flapping);
  6. with link_setup_epochs > 0, rules 1-2 must also hold in the interim state (old link removed,
     new link not yet usable): break-before-make must not disconnect the graph or breach the floor.
"""
import networkx as nx
import numpy as np

from tccer.core.mutations import budget_count
from tccer.metrics.resilience import lambda2


class SafetyGate:
    def __init__(self, cfg, budget: int):
        self.cfg = cfg
        self.budget = budget
        self.rejections = 0

    def check(self, state, mutation, tabu: np.ndarray):
        for e in (mutation.add, mutation.remove):
            if e is not None and tabu[e]:
                return self._reject("cooldown")
        if mutation.add is not None and state.down[mutation.add]:
            return self._reject("link down")

        before, after = state.live_mask(), state.mask_after(mutation)
        if mutation.remove is None:
            cfg_after = state.configured.copy()
            cfg_after[mutation.add] = True
            n_after = int(cfg_after.sum()) if self.cfg.budget_on == "configured" else int(after.sum())
            if n_after > self.budget:
                return self._reject("edge budget")

        u, v = state.eu[after], state.ev[after]
        deg = np.bincount(u, minlength=state.n) + np.bincount(v, minlength=state.n)
        if self.cfg.degree_fix:
            # only the endpoints of the new link gain degree; pre-existing high-degree nodes do not block
            ends = [state.eu[mutation.add], state.ev[mutation.add]] if mutation.add is not None else []
            if any(deg[x] > self.cfg.d_max for x in ends):
                return self._reject("degree")
        elif deg.max() > self.cfg.d_max:          # v0.1/v0.2 rule (kept for reproducibility)
            return self._reject("degree")

        c0 = nx.number_connected_components(state.graph(before))
        l0 = lambda2(state.n, state.eu[before], state.ev[before]) if c0 == 1 else 0.0
        masks = [after]
        if self.cfg.link_setup_epochs > 0 and mutation.remove is not None:
            masks.append(state.mask_after(mutation, interim=True))
        for m in masks:
            c1 = nx.number_connected_components(state.graph(m))
            if c1 > c0:
                return self._reject("disconnects")
            if c1 == 1 and lambda2(state.n, state.eu[m], state.ev[m]) < min(self.cfg.lambda2_min, l0) - 1e-12:
                return self._reject("lambda2 floor")
        return True, "ok"

    def _reject(self, reason):
        self.rejections += 1
        return False, reason
