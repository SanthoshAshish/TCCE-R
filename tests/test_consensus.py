import networkx as nx
import numpy as np

from tccer.consensus.algorithm import consensus_step, metropolis_matrix, run_epoch
from tccer.consensus.monitor import summarize


def edges(g):
    e = np.array(list(g.edges()))
    return e[:, 0], e[:, 1]


def test_metropolis_is_symmetric_doubly_stochastic():
    u, v = edges(nx.erdos_renyi_graph(15, 0.3, seed=1))
    W = metropolis_matrix(15, u, v)
    assert np.allclose(W, W.T)
    assert np.allclose(W.sum(axis=1), 1)
    assert (W >= -1e-12).all()


def test_step_equals_matrix_product():
    u, v = edges(nx.cycle_graph(10))
    x = np.random.default_rng(0).random(10)
    assert np.allclose(consensus_step(x, u, v), metropolis_matrix(10, u, v) @ x)


def test_converges_to_true_average_and_preserves_mean():
    n = 12
    u, v = edges(nx.cycle_graph(n))
    x = np.random.default_rng(0).random(n)
    avg = x.mean()
    for _ in range(2000):
        x = consensus_step(x, u, v)
        assert abs(x.mean() - avg) < 1e-12
    assert np.allclose(x, avg, atol=1e-8)


def test_mean_preserved_under_random_link_failures():
    n = 20
    u, v = edges(nx.random_geometric_graph(n, 0.4, seed=3))
    rng = np.random.default_rng(1)
    x0 = rng.random(n)
    masks = rng.random((50, len(u))) > 0.3
    x = x0.copy()
    for t in range(50):
        x = consensus_step(x, u[masks[t]], v[masks[t]])
    assert abs(x.mean() - x0.mean()) < 1e-12


def test_empirical_rate_matches_slem():
    """Error decay rate on a static graph -> second-largest eigenvalue modulus of W."""
    n = 16
    u, v = edges(nx.cycle_graph(n))
    W = metropolis_matrix(n, u, v)
    slem = sorted(np.abs(np.linalg.eigvalsh(W)))[-2]
    x0 = np.random.default_rng(2).random(n)
    err = run_epoch(x0, u, v, lambda t: np.ones(len(u), bool), 400)
    empirical = (err[400] / err[300]) ** (1 / 100)
    assert abs(empirical - slem) < 1e-3


def test_monitor_stress_bounds():
    assert summarize(np.array([1.0, 0.5, 0.005]), eps=0.01).E_hat == 0.0
    assert summarize(np.array([1.0, 1.0, 1.0]), eps=0.01).E_hat == 1.0
    r = summarize(np.array([1.0, 0.1, 0.1]), eps=0.01)
    assert abs(r.E_hat - 0.5) < 1e-9 and r.conv_round is None
