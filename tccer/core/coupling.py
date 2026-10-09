"""(5) Consensus-Resilience Coupling Evaluator.

For each candidate mutation it computes:
  d_comp  : change in number of connected components            (resilience, exact)
  gain    : predicted change in lambda2, first-order estimate     (consensus)
            adding (i,j)  -> +(f_i - f_j)^2, removing -> -(f_i - f_j)^2, f = unit Fiedler vector.
            This perturbation bound is ESTABLISHED (Ghosh & Boyd 2006). lambda2 of the Laplacian is used
            as a proxy for consensus speed; the Metropolis W rate is related but not identical.
  d_bridges: change in number of bridges                          (resilience cost, exact; shortlist only)
  length  : link length (energy / feasibility proxy)

Lexicographic ranking [PROPOSED combination of the above]:
  1. minimise d_comp (reconnecting the network comes first)
  2. maximise gain, treating candidates within `gain_tolerance` of the best as tied
  3. among ties, minimise d_bridges, then link length
"""
from dataclasses import dataclass

import networkx as nx
import numpy as np

from tccer.metrics.resilience import n_bridges


@dataclass
class Scored:
    mutation: object
    d_comp: int
    gain: float
    d_bridges: int = 0
    length: float = 0.0


def score_candidates(state, candidates, fiedler, connected: bool):
    g = state.graph()
    comp_of = {}
    for c, nodes in enumerate(nx.connected_components(g)):
        for x in nodes:
            comp_of[x] = c
    out = []
    for m in candidates:
        d_comp, gain, length = 0, 0.0, 0.0
        if m.add is not None:
            i, j = state.edge(m.add)
            length = float(state.length[m.add])
            if comp_of[i] != comp_of[j]:
                d_comp -= 1
            if connected:
                gain += (fiedler[i] - fiedler[j]) ** 2
        if m.remove is not None and connected:
            i, j = state.edge(m.remove)
            gain -= (fiedler[i] - fiedler[j]) ** 2
        out.append(Scored(m, d_comp, float(gain), 0, length))
    return out


def rank_lexicographic(state, scored, shortlist: int, tol: float):
    if not scored:
        return []
    scored = sorted(scored, key=lambda s: (s.d_comp, -s.gain, s.length))
    head, tail = scored[:shortlist], scored[shortlist:]
    b0 = n_bridges(state.graph())
    for s in head:
        s.d_bridges = n_bridges(state.graph(state.mask_after(s.mutation))) - b0
    best = head[0]
    slack = tol * abs(best.gain)
    tied = [s for s in head if s.d_comp == best.d_comp and s.gain >= best.gain - slack]
    rest = [s for s in head if s not in tied]
    tied.sort(key=lambda s: (s.d_bridges, s.length))
    return tied + rest + tail
