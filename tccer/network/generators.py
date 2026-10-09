"""Random geometric graph (RGG) generation. Established model (Penrose 2003)."""
import networkx as nx
import numpy as np


def random_geometric(n: int, init_radius: float, radio_range: float, seed: int, max_tries: int = 1000):
    """Return (positions, potential_edges, initial_edge_indices).

    potential_edges: all pairs within radio_range (the only links that can ever exist).
    initial edges:   pairs within init_radius (a sparser starting topology), resampled until connected.
    """
    if init_radius > radio_range:
        raise ValueError("init_radius must be <= radio_range")
    rng = np.random.default_rng([seed, 0])
    iu, ju = np.triu_indices(n, k=1)
    for _ in range(max_tries):
        pos = rng.random((n, 2))
        dist = np.linalg.norm(pos[iu] - pos[ju], axis=1)
        pot = dist <= radio_range
        init = dist <= init_radius
        g = nx.Graph()
        g.add_nodes_from(range(n))
        g.add_edges_from(zip(iu[init], ju[init]))
        if nx.is_connected(g):
            eu, ev, length = iu[pot], ju[pot], dist[pot]
            init_idx = np.flatnonzero(init[pot])
            return pos, eu, ev, length, init_idx
    raise RuntimeError("Could not sample a connected initial RGG; increase init_radius")
