import networkx as nx
import numpy as np
import pytest

from tccer.metrics.resilience import lambda2, vulnerability


def l2(g):
    e = np.array(list(g.edges()))
    return lambda2(g.number_of_nodes(), e[:, 0], e[:, 1])


@pytest.mark.parametrize("n", [5, 10, 17])
def test_lambda2_closed_forms(n):
    assert l2(nx.complete_graph(n)) == pytest.approx(n)
    assert l2(nx.cycle_graph(n)) == pytest.approx(2 - 2 * np.cos(2 * np.pi / n))
    assert l2(nx.path_graph(n)) == pytest.approx(2 - 2 * np.cos(np.pi / n))


def test_lambda2_zero_when_disconnected():
    g = nx.disjoint_union(nx.cycle_graph(4), nx.cycle_graph(4))
    assert l2(g) == pytest.approx(0, abs=1e-9)


def test_vulnerability():
    assert vulnerability(nx.path_graph(5)) == 1.0          # every edge is a bridge
    assert vulnerability(nx.cycle_graph(5)) == 0.0         # no bridges
    assert vulnerability(nx.empty_graph(3)) == 1.0         # disconnected
