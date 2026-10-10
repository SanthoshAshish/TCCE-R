"""Distributed average consensus, x(t+1) = W(t) x(t), with Metropolis-Hastings weights.

Established method: Xiao & Boyd (2004); Xiao, Boyd & Lall (2005). W is symmetric and doubly
stochastic for any undirected graph, so the network average is preserved even under link failures.
Each node needs only its neighbours' degrees -> fully local.
"""
import numpy as np


def metropolis_weights(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    deg = np.bincount(u, minlength=n) + np.bincount(v, minlength=n)
    return 1.0 / (1.0 + np.maximum(deg[u], deg[v]))


def metropolis_matrix(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Dense W (used for tests / spectral analysis only)."""
    w = metropolis_weights(n, u, v)
    W = np.zeros((n, n))
    W[u, v] = w
    W[v, u] = w
    W[np.diag_indices(n)] = 1.0 - W.sum(axis=1)
    return W


def consensus_step(x: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """One synchronous round over active links (u, v). Equivalent to W @ x."""
    if len(u) == 0:
        return x.copy()
    w = metropolis_weights(len(x), u, v)
    flow = w * (x[v] - x[u])
    out = x.copy()
    np.add.at(out, u, flow)
    np.add.at(out, v, -flow)
    return out


def run_epoch_state(x0: np.ndarray, u: np.ndarray, v: np.ndarray, up_mask_fn, rounds: int):
    """As run_epoch, but also returns the final node states x(rounds). Arithmetic is identical to run_epoch."""
    xbar = x0.mean()
    norm0 = np.linalg.norm(x0 - xbar)
    if norm0 == 0:                      # already in consensus: no disagreement to remove (v0.4 guard)
        return np.zeros(rounds + 1), x0.copy()
    x = x0.copy()
    err = np.empty(rounds + 1)
    err[0] = 1.0
    for t in range(rounds):
        m = up_mask_fn(t)
        x = consensus_step(x, u[m], v[m])
        err[t + 1] = np.linalg.norm(x - xbar) / norm0
    return err, x


def run_epoch(x0: np.ndarray, u: np.ndarray, v: np.ndarray, up_mask_fn, rounds: int) -> np.ndarray:
    """Run `rounds` iterations; up_mask_fn(t) -> bool mask over (u, v) of links up in round t.

    Returns normalized disagreement e(t) = ||x(t) - xbar 1|| / ||x(0) - xbar 1||, t = 0..rounds,
    where xbar is the true average of x(0).
    """
    return run_epoch_state(x0, u, v, up_mask_fn, rounds)[0]


def local_disagreement(x: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Per-node local disagreement delta_i = sum_{j in N(i)} (x_i - x_j)^2 over the given (live) links.

    Standard graph quantity (the spec names "local disagreement" without a formula): sum_i delta_i / 2 equals the
    Laplacian disagreement x^T L x = sum over links of (x_i - x_j)^2. Monitoring only; it does not feed the debt.
    """
    d = np.zeros(len(x))
    if len(u):
        sq = (x[u] - x[v]) ** 2
        np.add.at(d, u, sq)
        np.add.at(d, v, sq)
    return d
