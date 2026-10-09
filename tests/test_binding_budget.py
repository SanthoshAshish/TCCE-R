"""v0.3: strict (configured) edge budget and break-before-make link setup delay."""
import networkx as nx
import numpy as np
import pandas as pd

from tccer.config import Config, replace
from tccer.core.mutations import Mutation
from tccer.core.selector import MutationPipeline
from tccer.network.generators import random_geometric
from tccer.network.state import NetworkState
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

STRICT = replace(Config(), n_nodes=25, init_radius=0.28, radio_range=0.4, epochs=40, rounds_per_epoch=20,
                 budget_on="configured", edge_budget_frac=1.0, link_setup_epochs=2, p_fail=0.03)


def test_strict_budget_never_exceeded_and_only_rewires():
    for p in POLICIES:
        df = pd.DataFrame(simulate(replace(STRICT, period=3, reactive_threshold=0.2), 5, p, log_rounds=False)[0])
        assert (df.configured_edges <= df.configured_edges.iloc[0]).all()
        kinds = set(df.mutation_kind.dropna()) - {""}
        assert kinds <= {"rewire"}, (p, kinds)


def test_setup_delay_link_not_usable_until_ready():
    pos, eu, ev, length, init = random_geometric(20, 0.3, 0.45, 0)
    s = NetworkState(pos, eu, ev, length, init)
    a = int(np.flatnonzero(~s.configured)[0])
    s.epoch = 4
    s.apply(Mutation(add=a), setup_epochs=2)          # applied at end of epoch 4 -> usable from epoch 7
    for k, usable in [(5, False), (6, False), (7, True)]:
        s.epoch = k
        assert bool(s.live_mask()[a]) is usable


def test_interim_state_checked_by_gate():
    """Path 0-1-2-3, candidate link (0,3). Rewire: remove (2,3), add (0,3).
    Finished state is connected (path 3-0-1-2) -> OK without delay.
    With a setup delay, node 3 is isolated in the interim -> must be rejected."""
    pairs = [(0, 1), (0, 3), (1, 2), (2, 3)]
    eu, ev = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
    s = NetworkState(np.zeros((4, 2)), eu, ev, np.ones(4), np.array([0, 2, 3]))
    m = Mutation(add=s.index[(0, 3)], remove=s.index[(2, 3)])
    cfg = replace(Config(), lambda2_min=0.0, budget_on="configured", edge_budget_frac=1.0)
    no_tabu = np.zeros(s.P, bool)
    assert MutationPipeline(replace(cfg, link_setup_epochs=0), 3, s.P).gate.check(s, m, no_tabu) == (True, "ok")
    assert MutationPipeline(replace(cfg, link_setup_epochs=2), 3, s.P).gate.check(s, m, no_tabu) == (False, "disconnects")


def test_rewire_can_drop_failed_link():
    pos, eu, ev, length, init = random_geometric(25, 0.28, 0.4, 2)
    s = NetworkState(pos, eu, ev, length, init)
    dead = int(init[0])
    s.down[dead] = True
    pipe = MutationPipeline(replace(STRICT, d_max=100), len(init), s.P)
    if nx.is_connected(s.graph()):
        m = pipe.select(s, k=0)
        assert m is not None and m.kind() == "rewire" and m.remove == dead


def test_strict_budget_can_reconnect_disconnected_graph():
    """v0.3 fix: when disconnected under a full budget, a rewire releasing a failed link must be possible."""
    found = 0
    for seed in range(10):
        pos, eu, ev, length, init = random_geometric(25, 0.28, 0.4, seed)
        s = NetworkState(pos, eu, ev, length, init)
        g = s.graph()
        node = min(g.degree, key=lambda x: x[1])[0]        # isolate the lowest-degree node via failures
        for nb in list(g.neighbors(node)):
            s.down[s.index[tuple(sorted((node, nb)))]] = True
        if not (~s.configured & ~s.down & ((s.eu == node) | (s.ev == node))).any():
            continue                                        # no spare in-range link to this node
        cfg = replace(STRICT, degree_fix=True, link_setup_epochs=0)
        m = MutationPipeline(cfg, len(init), s.P).select(s, k=0)
        assert m is not None and m.kind() == "rewire" and s.down[m.remove]
        assert nx.number_connected_components(s.graph(s.mask_after(m))) < nx.number_connected_components(s.graph())
        found += 1
    assert found >= 3


def test_degree_fix_only_checks_new_link_endpoints():
    """A pre-existing node above d_max must not block an unrelated mutation (v0.3 fix);
    the old rule (degree_fix=False) blocks it, kept for v0.1/v0.2 reproducibility."""
    g = nx.star_graph(4)                      # centre 0 has degree 4
    g.add_edges_from([(1, 2), (2, 3), (3, 4)])
    pairs = sorted(tuple(sorted(e)) for e in g.edges()) + [(1, 4)]
    eu, ev = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
    s = NetworkState(np.zeros((5, 2)), eu, ev, np.ones(len(pairs)), np.arange(len(pairs) - 1))
    m = Mutation(add=s.index[(1, 4)])
    no_tabu = np.zeros(s.P, bool)
    base = replace(Config(), d_max=3, lambda2_min=0.0)
    assert MutationPipeline(replace(base, degree_fix=False), 100, s.P).gate.check(s, m, no_tabu) == (False, "degree")
    assert MutationPipeline(replace(base, degree_fix=True), 100, s.P).gate.check(s, m, no_tabu) == (True, "ok")
    m_hub = Mutation(add=s.index[(1, 4)])
    s2 = replace(base, degree_fix=True, d_max=2)   # endpoints 1 and 4 already have degree 2 -> 3 > 2
    assert MutationPipeline(s2, 100, s.P).gate.check(s, m_hub, no_tabu) == (False, "degree")
