"""Candidate topology mutations (input to (5) and (7)).

Mutation types:
  add    : activate one candidate link within radio range
  rewire : remove one live link + add one candidate link (used when the edge budget is full)
"""
from dataclasses import dataclass
from typing import Optional

import networkx as nx
import numpy as np


@dataclass(frozen=True)
class Mutation:
    add: Optional[int] = None
    remove: Optional[int] = None

    def kind(self) -> str:
        return "rewire" if (self.add is not None and self.remove is not None) else ("add" if self.add is not None else "remove")

    def describe(self, state) -> str:
        parts = []
        if self.remove is not None:
            parts.append("-%d-%d" % state.edge(self.remove))
        if self.add is not None:
            parts.append("+%d-%d" % state.edge(self.add))
        return " ".join(parts)


def generate_candidates(state, budget: int, tabu: np.ndarray, fiedler: Optional[np.ndarray]):
    """tabu[i] True -> edge i is in cooldown and may not be touched."""
    live = state.live_mask()
    addable = np.flatnonzero(~state.configured & ~state.down & ~tabu)
    if live.sum() < budget:
        return [Mutation(add=int(a)) for a in addable]

    # Budget full: rewire. Remove the non-bridge live link with the smallest first-order lambda2 loss.
    g = state.graph()
    bridges = {tuple(sorted(e)) for e in nx.bridges(g)}
    removable = [i for i in np.flatnonzero(live & ~tabu) if state.edge(i) not in bridges]
    if not removable or fiedler is None:
        return []
    loss = [(fiedler[state.eu[i]] - fiedler[state.ev[i]]) ** 2 for i in removable]
    r = int(removable[int(np.argmin(loss))])
    return [Mutation(add=int(a), remove=r) for a in addable]
