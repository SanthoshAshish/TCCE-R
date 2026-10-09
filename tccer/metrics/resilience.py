"""Resilience metrics (all established graph measures).

- Algebraic connectivity lambda2 and Fiedler vector (Fiedler 1973).
- Bridges: edges whose removal disconnects the graph.
"""
import networkx as nx
import numpy as np


def laplacian(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    L = np.zeros((n, n))
    L[u, v] = -1.0
    L[v, u] = -1.0
    L[np.diag_indices(n)] = -L.sum(axis=1)
    return L


def lambda2_fiedler(n: int, u: np.ndarray, v: np.ndarray):
    vals, vecs = np.linalg.eigh(laplacian(n, u, v))
    return float(max(vals[1], 0.0)), vecs[:, 1]


def lambda2(n: int, u: np.ndarray, v: np.ndarray) -> float:
    return float(max(np.linalg.eigvalsh(laplacian(n, u, v))[1], 0.0))


def n_bridges(g: nx.Graph) -> int:
    return sum(1 for _ in nx.bridges(g))


def vulnerability(g: nx.Graph) -> float:
    """C in [0, 1]: 1 if disconnected, else fraction of links that are bridges."""
    if not nx.is_connected(g):
        return 1.0
    m = g.number_of_edges()
    return n_bridges(g) / m if m else 1.0
