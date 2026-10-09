"""Debt, trigger, threshold, feedback, safety gate, selector."""
import networkx as nx
import numpy as np

from tccer.config import Config, replace
from tccer.core.debt import CusumDebt
from tccer.core.feedback import FeedbackEvaluator
from tccer.core.mutations import Mutation
from tccer.core.safety import SafetyGate
from tccer.core.selector import MutationPipeline
from tccer.core.threshold import AdaptiveThreshold
from tccer.core.trigger import Trigger
from tccer.metrics.resilience import lambda2
from tccer.network.generators import random_geometric
from tccer.network.state import NetworkState

CFG = Config()


def test_cusum_stays_zero_below_kappa_and_grows_on_step():
    d = CusumDebt(CFG)
    for _ in range(50):
        d.update(0, 0, 0)
    assert d.D == 0
    for _ in range(5):
        d.update(1, 1, 1)
    assert abs(d.D - 5 * (1 - CFG.kappa)) < 1e-9
    d.repay()
    assert d.D == 0


def test_threshold_stays_in_bounds():
    th = AdaptiveThreshold(CFG)
    for _ in range(100):
        th.update(False)
    assert th.theta == CFG.theta_max
    for _ in range(200):
        th.update(True)
    assert th.theta == CFG.theta_min


def test_trigger_cooldown():
    tr = Trigger(CFG)
    assert tr.should_fire(2.0, 1.0, 10, None)
    assert not tr.should_fire(2.0, 1.0, 10, 9)
    assert not tr.should_fire(0.5, 1.0, 10, None)


def test_feedback_success_and_failure():
    fb = FeedbackEvaluator(CFG)
    fb.register(3)
    E = [0.9, 0.9, 0.9, 0.9, 0.2, 0.2, 0.2]
    assert fb.evaluate(5, E[:6]) == []
    assert fb.evaluate(6, E) == [(3, True)]
    fb.register(3)
    assert fb.evaluate(6, [0.1] * 4 + [0.5] * 3) == [(3, False)]


def make_state(seed=0):
    pos, eu, ev, length, init = random_geometric(30, 0.25, 0.35, seed)
    return NetworkState(pos, eu, ev, length, init)


def test_gate_rejects_disconnecting_removal():
    s = make_state()
    gate = SafetyGate(CFG, budget=10**6)
    g = s.graph()
    no_tabu = np.zeros(s.P, bool)
    for a, b in nx.bridges(g):
        ok, reason = gate.check(s, Mutation(remove=s.index[tuple(sorted((a, b)))]), no_tabu)
        assert not ok and reason in ("disconnects", "lambda2 floor")


def test_gate_enforces_budget_and_cooldown():
    s = make_state()
    live = int(s.live_mask().sum())
    add = int(np.flatnonzero(~s.configured)[0])
    gate = SafetyGate(replace(CFG, d_max=100), budget=live)
    assert gate.check(s, Mutation(add=add), np.zeros(s.P, bool)) == (False, "edge budget")
    gate = SafetyGate(replace(CFG, d_max=100), budget=live + 1)
    tabu = np.zeros(s.P, bool)
    tabu[add] = True
    assert gate.check(s, Mutation(add=add), tabu) == (False, "cooldown")


def test_selector_never_disconnects_or_breaks_floor():
    """Property test: across random graphs/failure states, any selected mutation keeps the graph connected
    (if it was) and respects the lambda2 floor; works in both add and rewire mode."""
    rng = np.random.default_rng(0)
    for seed in range(15):
        s = make_state(seed)
        s.down = rng.random(s.P) < 0.05
        for frac in (1.3, 1.0):  # 1.3 -> additions allowed; 1.0 -> budget full -> rewires
            pipe = MutationPipeline(replace(CFG, edge_budget_frac=frac), int(s.configured.sum()), s.P)
            m = pipe.select(s, k=0)
            if m is None:
                continue
            before = nx.number_connected_components(s.graph())
            after_mask = s.mask_after(m)
            assert nx.number_connected_components(s.graph(after_mask)) <= before
            if before == 1:
                l0 = lambda2(s.n, s.eu[s.live_mask()], s.ev[s.live_mask()])
                l1 = lambda2(s.n, s.eu[after_mask], s.ev[after_mask])
                assert l1 >= min(CFG.lambda2_min, l0) - 1e-12


def test_selector_prefers_reconnecting_edge():
    s = make_state(1)
    g = s.graph()
    # Force a split by marking all edges of one bridge (or a cut) down: pick a node and isolate it.
    node = 0
    for nb in list(g.neighbors(node)):
        s.down[s.index[tuple(sorted((node, nb)))]] = True
    s.down[~s.configured] = False
    assert nx.number_connected_components(s.graph()) > 1
    pipe = MutationPipeline(replace(CFG, d_max=100, edge_budget_frac=2.0), int(s.configured.sum()), s.P)
    m = pipe.select(s, k=0)
    if m is not None:  # node 0 may have no spare in-range link; otherwise it must reconnect
        assert nx.number_connected_components(s.graph(s.mask_after(m))) < nx.number_connected_components(s.graph())
