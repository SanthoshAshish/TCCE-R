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


def degrees(state, basis: str, configured=None) -> np.ndarray:
    """Node degree over live links ("live") or over all configured links ("configured": failed and
    pending links still occupy a port and will count again once repaired / set up)."""
    cfg = state.configured if configured is None else configured
    mask = cfg if basis == "configured" else state.live_mask(cfg)
    return np.bincount(state.eu[mask], minlength=state.n) + np.bincount(state.ev[mask], minlength=state.n)


def _degree_ok(state, live, addable, d_max, removed=None, basis="live"):
    """Drop additions that would exceed d_max (the gate would reject them anyway;
    filtering here keeps the selector's limited gate attempts for feasible moves). v0.3 fix."""
    if d_max is None:
        return addable
    deg = degrees(state, basis)
    counted = state.configured if basis == "configured" else live
    if removed is not None and counted[removed]:
        deg[state.eu[removed]] -= 1
        deg[state.ev[removed]] -= 1
    return addable[(deg[state.eu[addable]] < d_max) & (deg[state.ev[addable]] < d_max)]


def generate_candidates(state, budget: int, tabu: np.ndarray, fiedler: Optional[np.ndarray], budget_on: str = "live",
                        d_max: Optional[int] = None, degree_basis: str = "live", failed_link_value: str = "zero"):
    """tabu[i] True -> edge i is in cooldown and may not be touched."""
    live = state.live_mask()
    addable = np.flatnonzero(~state.configured & ~state.down & ~tabu)
    if budget_count(state, budget_on) < budget:
        return [Mutation(add=int(a)) for a in _degree_ok(state, live, addable, d_max, basis=degree_basis)]

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
    # failed_link_value="if_up" (v0.4): a failed link is valued by what it contributes once it recovers,
    # so releasing it is no longer automatically free. Without a Fiedler vector (disconnected) every
    # candidate is a failed link and all losses are 0; ties go to the lowest index.
    free_if_down = failed_link_value == "zero" or fiedler is None
    loss = [0.0 if (not live[i] and free_if_down) else (fiedler[state.eu[i]] - fiedler[state.ev[i]]) ** 2
            for i in removable]
    r = int(removable[int(np.argmin(loss))])
    return [Mutation(add=int(a), remove=r)
            for a in _degree_ok(state, live, addable, d_max, removed=r, basis=degree_basis)]
