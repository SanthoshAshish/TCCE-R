"""(1) Dynamic Network State and (8) Reconfigured Network.

Links are indexed over a fixed list of *potential* edges (pairs within radio range), so every
array has the same length regardless of which policy is running.
  configured[i]: the controller wants link i active
  down[i]:       link i is physically failed (environment, independent of the policy)
  live = configured & ~down
"""
import networkx as nx
import numpy as np


class NetworkState:
    def __init__(self, pos, eu, ev, length, init_idx):
        self.pos = pos
        self.n = len(pos)
        self.eu, self.ev, self.length = eu, ev, length
        self.P = len(eu)
        self.index = {(int(u), int(v)): i for i, (u, v) in enumerate(zip(eu, ev))}
        self.configured = np.zeros(self.P, dtype=bool)
        self.configured[init_idx] = True
        self.down = np.zeros(self.P, dtype=bool)

    def live_mask(self, configured=None):
        cfg = self.configured if configured is None else configured
        return cfg & ~self.down

    def graph(self, mask=None) -> nx.Graph:
        mask = self.live_mask() if mask is None else mask
        g = nx.Graph()
        g.add_nodes_from(range(self.n))
        g.add_edges_from(zip(self.eu[mask].tolist(), self.ev[mask].tolist()))
        return g

    def mask_after(self, mutation) -> np.ndarray:
        """Live mask that would result from applying `mutation` (does not modify state)."""
        cfg = self.configured.copy()
        if mutation.add is not None:
            cfg[mutation.add] = True
        if mutation.remove is not None:
            cfg[mutation.remove] = False
        return self.live_mask(cfg)

    def apply(self, mutation) -> None:
        if mutation.add is not None:
            self.configured[mutation.add] = True
        if mutation.remove is not None:
            self.configured[mutation.remove] = False

    def edge(self, i):
        return int(self.eu[i]), int(self.ev[i])
