"""(7) Topology Mutation Selector: candidates -> (5) evaluator -> (6) gate -> chosen mutation."""
import networkx as nx
import numpy as np

from tccer.core.coupling import rank_lexicographic, score_candidates
from tccer.core.mutations import generate_candidates
from tccer.core.safety import SafetyGate
from tccer.metrics.resilience import lambda2_fiedler


class MutationPipeline:
    def __init__(self, cfg, n_initial_edges: int, n_potential: int):
        self.cfg = cfg
        self.budget = int(round(cfg.edge_budget_frac * n_initial_edges))
        self.gate = SafetyGate(cfg, self.budget)
        self.last_touched = np.full(n_potential, -10**9)

    def tabu(self, k: int) -> np.ndarray:
        return (k - self.last_touched) < self.cfg.edge_cooldown

    def select(self, state, k: int, mode: str = "lexicographic", rng=None, max_tries: int = 30):
        live = state.live_mask()
        g = state.graph()
        connected = nx.is_connected(g)
        fiedler = lambda2_fiedler(state.n, state.eu[live], state.ev[live])[1] if connected else None
        tabu = self.tabu(k)
        cands = generate_candidates(state, self.budget, tabu, fiedler, self.cfg.budget_on,
                                    self.cfg.d_max if self.cfg.degree_fix else None)
        if mode == "random":
            order = [cands[i] for i in rng.permutation(len(cands))]
        else:
            scored = score_candidates(state, cands, fiedler, connected)
            order = [s.mutation for s in rank_lexicographic(state, scored, self.cfg.shortlist, self.cfg.gain_tolerance)]
        for m in order[:max_tries]:
            ok, _ = self.gate.check(state, m, tabu)
            if ok:
                return m
        return None

    def commit(self, mutation, k: int) -> None:
        for e in (mutation.add, mutation.remove):
            if e is not None:
                self.last_touched[e] = k
