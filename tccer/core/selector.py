"""(7) Topology Mutation Selector: candidates -> (5) evaluator -> (6) gate -> chosen mutation."""
import math

import networkx as nx
import numpy as np

from tccer.core.coupling import rank_lexicographic, score_candidates
from tccer.core.mutations import generate_candidates
from tccer.core.safety import SafetyGate
from tccer.metrics.resilience import lambda2_fiedler

EMPTY_SELECTION = {"select_outcome": "", "n_candidates": 0, "M_dcomp": math.nan, "M_gain": math.nan,
                   "M_dbridges": math.nan, "M_length": math.nan, "removed_failed_link": False}


class MutationPipeline:
    def __init__(self, cfg, n_initial_edges: int, n_potential: int):
        self.cfg = cfg
        self.budget = int(round(cfg.edge_budget_frac * n_initial_edges))
        self.gate = SafetyGate(cfg, self.budget)
        self.last_touched = np.full(n_potential, -10**9)
        self.last = dict(EMPTY_SELECTION)    # logging only: outcome of the latest select() call this epoch

    def tabu(self, k: int) -> np.ndarray:
        return (k - self.last_touched) < self.cfg.edge_cooldown

    def _ranked(self, state, k, mode, rng):
        live = state.live_mask()
        connected = nx.is_connected(state.graph())
        fiedler = lambda2_fiedler(state.n, state.eu[live], state.ev[live])[1] if connected else None
        tabu = self.tabu(k)
        cands = generate_candidates(state, self.budget, tabu, fiedler, self.cfg.budget_on,
                                    self.cfg.d_max if self.cfg.degree_fix else None,
                                    self.cfg.degree_basis, self.cfg.failed_link_value)
        if mode == "random":
            return [(cands[i], None) for i in rng.permutation(len(cands))], tabu
        scored = score_candidates(state, cands, fiedler, connected)
        ranked = rank_lexicographic(state, scored, self.cfg.shortlist, self.cfg.gain_tolerance)
        return [(s.mutation, s) for s in ranked], tabu

    def select(self, state, k: int, mode: str = "lexicographic", rng=None, max_tries: int = 30):
        order, tabu = self._ranked(state, k, mode, rng)
        self.last = dict(EMPTY_SELECTION, n_candidates=len(order),
                         select_outcome="no_candidates" if not order else "all_rejected")
        for m, s in order[:max_tries]:
            ok, _ = self.gate.check(state, m, tabu)
            if ok:
                self.last.update(select_outcome="mutated",
                                 removed_failed_link=bool(m.remove is not None and not state.live_mask()[m.remove]))
                if s is not None:   # (5) coupling-score components of the chosen candidate, i.e. "M"
                    self.last.update(M_dcomp=s.d_comp, M_gain=s.gain, M_dbridges=s.d_bridges, M_length=s.length)
                return m
        return None

    def can_reconnect(self, state, k: int, max_tries: int = 30) -> bool:
        """Logging only, no side effects: could the shared selector + gate reduce the number of components
        this epoch? Used to verify that every policy has the same opportunity to reconnect."""
        order, tabu = self._ranked(state, k, "lexicographic", None)
        saved = self.gate.rejections
        try:
            for m, s in order[:max_tries]:
                if s.d_comp < 0 and self.gate.check(state, m, tabu)[0]:
                    return True
            return False
        finally:
            self.gate.rejections = saved

    def commit(self, mutation, k: int) -> None:
        for e in (mutation.add, mutation.remove):
            if e is not None:
                self.last_touched[e] = k
