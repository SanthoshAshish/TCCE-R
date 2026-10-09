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


def budget_count(state, budget_on: str, configured=None) -> int:
    """Links counted against the edge budget: live links ("live") or all configured links ("configured")."""
    cfg = state.configured if configured is None else configured
    return int(cfg.sum() if budget_on == "configured" else state.live_mask(cfg).sum())


def _degree_ok(state, live, addable, d_max, removed=None):
    """Drop additions that would exceed d_max on the live graph (the gate would reject them anyway;
    filtering here keeps the selector's limited gate attempts for feasible moves). v0.3 fix."""
    if d_max is None:
        return addable
    deg = np.bincount(state.eu[live], minlength=state.n) + np.bincount(state.ev[live], minlength=state.n)
    if removed is not None and live[removed]:
        deg[state.eu[removed]] -= 1
        deg[state.ev[removed]] -= 1
    return addable[(deg[state.eu[addable]] < d_max) & (deg[state.ev[addable]] < d_max)]


def generate_candidates(state, budget: int, tabu: np.ndarray, fiedler: Optional[np.ndarray], budget_on: str = "live",
                        d_max: Optional[int] = None):
    """tabu[i] True -> edge i is in cooldown and may not be touched."""
    live = state.live_mask()
    addable = np.flatnonzero(~state.configured & ~state.down & ~tabu)
    if budget_count(state, budget_on) < budget:
        return [Mutation(add=int(a)) for a in _degree_ok(state, live, addable, d_max)]

    # Budget full: rewire. Remove the configured link with the smallest first-order lambda2 loss.
    # A failed (not live) link costs 0 now but forfeits its possible repair; a live link must not be a bridge.
    # If the live graph is disconnected the Fiedler vector is undefined: only failed links may be released
    # (v0.3 fix; before, no rewire was ever generated while disconnected).
    g = state.graph()
    bridges = {tuple(sorted(e)) for e in nx.bridges(g)}
    removable = [i for i in np.flatnonzero(state.configured & ~tabu)
                 if not live[i] or (fiedler is not None and state.edge(i) not in bridges)]
    if not removable:
        return []
    loss = [0.0 if not live[i] else (fiedler[state.eu[i]] - fiedler[state.ev[i]]) ** 2 for i in removable]
    r = int(removable[int(np.argmin(loss))])
    return [Mutation(add=int(a), remove=r) for a in _degree_ok(state, live, addable, d_max, removed=r)]
