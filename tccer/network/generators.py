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


def _connected(n, iu, ju, mask):
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(zip(iu[mask], ju[mask]))
    return nx.is_connected(g)


def non_geometric(n: int, family: str, p_init: float, p_pot: float, ba_m: int, seed: int, max_tries: int = 1000):
    """Erdos-Renyi ("er") or Barabasi-Albert ("ba") initial graph on random node positions.

    Positions are only used for link lengths (tie-breaks) and for spatially correlated outages.
    potential edges = initial edges + every other pair with probability p_pot (candidate links).
    """
    rng = np.random.default_rng([seed, 0])
    iu, ju = np.triu_indices(n, k=1)
    for t in range(max_tries):
        pos = rng.random((n, 2))
        if family == "er":
            u = rng.random(len(iu))
            init = u < p_init
        else:
            g0 = nx.barabasi_albert_graph(n, ba_m, seed=int(rng.integers(2**31)))
            key = {(min(a, b), max(a, b)) for a, b in g0.edges()}
            init = np.array([(int(a), int(b)) in key for a, b in zip(iu, ju)])
        pot = init | (rng.random(len(iu)) < p_pot)
        if _connected(n, iu, ju, init):
            dist = np.linalg.norm(pos[iu] - pos[ju], axis=1)
            return pos, iu[pot], ju[pot], dist[pot], np.flatnonzero(init[pot])
    raise RuntimeError("Could not sample a connected initial graph; raise the initial density")


def make_network(cfg, seed: int):
    if cfg.graph_family == "rgg":
        return random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, seed)
    return non_geometric(cfg.n_nodes, cfg.graph_family, cfg.er_p_init, cfg.er_p_pot, cfg.ba_m, seed)
