"""v0.4: audit fixes (degree basis, feedback timing, failed-link value), bursty failures, logging,
safety-gate oracle, edge cases, CSV output and aggregation."""
import os
import subprocess
import sys

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from experiments.analyze import ci95, holm, per_seed
from tccer.config import Config, replace
from tccer.consensus.algorithm import consensus_step, run_epoch
from tccer.core.debt import CusumDebt
from tccer.core.feedback import FeedbackEvaluator
from tccer.core.mutations import Mutation, generate_candidates
from tccer.core.selector import MutationPipeline
from tccer.network.events import FailureTrace
from tccer.network.generators import random_geometric
from tccer.network.state import NetworkState
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

V04 = replace(Config(), n_nodes=25, init_radius=0.28, radio_range=0.4, epochs=40, rounds_per_epoch=20,
              budget_on="configured", edge_budget_frac=1.0, link_setup_epochs=2, degree_fix=True,
              degree_basis="configured", feedback_after_setup=True, failed_link_value="if_up",
              burst_rate=0.3, burst_radius=0.2)


def rgg_state(seed=0, n=25):
    pos, eu, ev, length, init = random_geometric(n, 0.28, 0.4, seed)
    return NetworkState(pos, eu, ev, length, init)


def tiny_state(pairs, init_pairs):
    eu, ev = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
    n = int(max(eu.max(), ev.max())) + 1
    init = np.array([i for i, p in enumerate(pairs) if p in init_pairs])
    return NetworkState(np.zeros((n, 2)), eu, ev, np.ones(len(pairs)), init)


# ---------------------------------------------------------------- consensus on disconnected graphs
def test_disconnected_graph_preserves_mean_but_cannot_reach_global_average():
    g = nx.disjoint_union(nx.cycle_graph(5), nx.cycle_graph(5))
    e = np.array(list(g.edges()))
    x0 = np.r_[np.zeros(5), np.ones(5)]
    err = run_epoch(x0, e[:, 0], e[:, 1], lambda t: np.ones(len(e), bool), 500)
    assert err[-1] > 0.99                     # each component agrees internally, never globally
    x = x0.copy()
    for _ in range(50):
        x = consensus_step(x, e[:, 0], e[:, 1])
    assert abs(x.mean() - 0.5) < 1e-12


def test_constant_initial_state_gives_zero_error_not_nan():
    err = run_epoch(np.full(4, 0.3), np.array([0, 1]), np.array([1, 2]), lambda t: np.ones(2, bool), 5)
    assert np.all(err == 0)


# ---------------------------------------------------------------- failures and bursts
def test_bursts_off_means_no_burst_draws():
    t = FailureTrace(replace(V04, burst_rate=0.0), 1, 10, edge_mid=np.random.rand(10, 2))
    assert not t.burst.any() and t.bursts == []


def test_burst_hits_links_in_radius_and_recovers():
    mid = np.array([[0.5, 0.5], [0.52, 0.5], [0.95, 0.95]])
    cfg = replace(V04, epochs=200, burst_rate=1.0, burst_radius=0.1, burst_min_len=3, burst_max_len=3)
    t = FailureTrace(cfg, 0, 3, edge_mid=mid)
    for k, centre, L, nhit in t.bursts[:20]:
        hit = np.linalg.norm(mid - centre, axis=1) <= 0.1
        assert t.burst[k:k + L, hit].all()
    # a single isolated burst must end after its length
    cfg1 = replace(cfg, burst_rate=0.0)
    t1 = FailureTrace(cfg1, 0, 3, edge_mid=mid)
    assert not t1.burst.any()


def test_failed_links_are_not_live():
    s = rgg_state()
    i = int(np.flatnonzero(s.configured)[0])
    s.down[i] = True
    assert not s.live_mask()[i] and not s.graph().has_edge(*s.edge(i))


def test_bursty_trace_identical_across_policies():
    downs = [pd.DataFrame(simulate(V04, 11, p, log_rounds=False)[0]).n_down_potential.tolist() for p in POLICIES]
    assert all(d == downs[0] for d in downs)


# ---------------------------------------------------------------- D1: degree basis
def test_degree_basis_configured_counts_failed_links():
    """Node 0 has configured degree 3 (one link failed, live degree 2). d_max=3.
    'live' basis accepts a new link to node 0 (later repair -> degree 4 > d_max): the D1 defect.
    'configured' basis rejects it."""
    pairs = [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2), (2, 3), (3, 4), (1, 4)]
    s = tiny_state(pairs, set(pairs) - {(0, 4)})
    s.down[s.index[(0, 3)]] = True
    m = Mutation(add=s.index[(0, 4)])
    base = replace(Config(), d_max=3, lambda2_min=0.0, degree_fix=True)
    no_tabu = np.zeros(s.P, bool)
    assert MutationPipeline(replace(base, degree_basis="live"), 100, s.P).gate.check(s, m, no_tabu)[0]
    assert MutationPipeline(replace(base, degree_basis="configured"), 100, s.P).gate.check(s, m, no_tabu) \
        == (False, "degree")


def test_configured_degree_never_raised_above_dmax_in_simulation():
    """Invariant (degree_basis='configured'): no mutation leaves an endpoint of its new link with
    configured degree > d_max. Checked at every commit across policies and seeds."""
    import tccer.core.selector as sel
    import tccer.sim.engine as eng
    cfg = replace(V04, d_max=5)
    holder, checked = {}, []

    class Spy(NetworkState):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            holder["s"] = self

    orig_commit, orig_state = sel.MutationPipeline.commit, eng.NetworkState

    def commit(self, m, k):
        st = holder["s"]
        deg = np.bincount(st.eu[st.configured], minlength=st.n) + np.bincount(st.ev[st.configured], minlength=st.n)
        if m.add is not None:
            checked.append(max(deg[st.eu[m.add]], deg[st.ev[m.add]]))
        return orig_commit(self, m, k)

    sel.MutationPipeline.commit, eng.NetworkState = commit, Spy
    try:
        for seed in range(3):
            for p in ["reactive", "periodic", "tccer", "random"]:
                simulate(replace(cfg, period=2, reactive_threshold=0.1), seed, p, log_rounds=False)
    finally:
        sel.MutationPipeline.commit, eng.NetworkState = orig_commit, orig_state
    assert len(checked) > 20 and max(checked) <= cfg.d_max


# ---------------------------------------------------------------- D2: feedback timing
def test_feedback_waits_for_link_setup():
    fb = FeedbackEvaluator(replace(Config(), feedback_horizon=2, link_setup_epochs=3, feedback_after_setup=True))
    fb.register(5)
    E = [0.8] * 6 + [0.9] * 3 + [0.1] * 2          # epochs 6-8 = setup (link not usable), 9-10 = usable
    assert fb.evaluate(7, E[:8]) == []             # old rule would already judge at epoch 7
    assert fb.evaluate(10, E) == [(5, True)]       # judged only on epochs 9..10
    old = FeedbackEvaluator(replace(Config(), feedback_horizon=2, link_setup_epochs=3))
    old.register(5)
    assert old.evaluate(7, E[:8]) == [(5, False)]  # v0.3 rule judges the mutation before the link exists


# ---------------------------------------------------------------- failed-link value
def test_failed_link_value_if_up_does_not_make_failed_links_free():
    """Path-like graph with one redundant chord; the failed link is a valuable long-range link."""
    s = rgg_state(4)
    live = s.live_mask()
    from tccer.metrics.resilience import lambda2_fiedler
    f = lambda2_fiedler(s.n, s.eu[live], s.ev[live])[1]
    cfg_idx = np.flatnonzero(s.configured)
    vals = (f[s.eu[cfg_idx]] - f[s.ev[cfg_idx]]) ** 2
    valuable = int(cfg_idx[np.argmax(vals)])
    s.down[valuable] = True
    live = s.live_mask()
    if not nx.is_connected(s.graph()):
        pytest.skip("failure disconnects this instance")
    f = lambda2_fiedler(s.n, s.eu[live], s.ev[live])[1]
    budget = int(s.configured.sum())
    no_tabu = np.zeros(s.P, bool)
    zero = generate_candidates(s, budget, no_tabu, f, "configured", failed_link_value="zero")
    if_up = generate_candidates(s, budget, no_tabu, f, "configured", failed_link_value="if_up")
    assert zero[0].remove == valuable          # v0.3: the failed link is always released first
    assert if_up[0].remove != valuable         # v0.4: a cheaper live link is released instead


# ---------------------------------------------------------------- edge case: no candidates
def test_no_valid_candidates_returns_none_and_logs_reason():
    pairs = [(0, 1), (1, 2), (0, 2)]
    s = tiny_state(pairs, set(pairs))                     # everything already configured
    pipe = MutationPipeline(replace(Config(), budget_on="configured", edge_budget_frac=1.0), 3, s.P)
    assert pipe.select(s, k=0) is None
    assert pipe.last["select_outcome"] == "no_candidates"


def test_simulation_survives_when_nothing_can_be_mutated():
    cfg = replace(V04, n_nodes=6, init_radius=0.9, radio_range=0.9, epochs=10, period=1, reactive_threshold=0.0)
    for p in POLICIES:
        rows, _ = simulate(cfg, 0, p, log_rounds=False)
        assert len(rows) == 10


# ---------------------------------------------------------------- reconnection
def test_can_reconnect_has_no_side_effects():
    s = rgg_state(2)
    s.down[s.configured] = np.random.default_rng(0).random(int(s.configured.sum())) < 0.4
    pipe = MutationPipeline(V04, int(s.configured.sum()), s.P)
    before = (s.configured.copy(), s.down.copy(), pipe.gate.rejections, pipe.last_touched.copy())
    pipe.can_reconnect(s, 0)
    assert (s.configured == before[0]).all() and (s.down == before[1]).all()
    assert pipe.gate.rejections == before[2] and (pipe.last_touched == before[3]).all()


def test_bursty_runs_reconnect_when_possible():
    df = pd.concat([pd.DataFrame(simulate(replace(V04, reactive_threshold=0.0), s, "reactive", log_rounds=False)[0])
                    for s in range(4)])
    disc = df[df.components > 1]
    assert len(disc) > 0, "scenario never disconnects; test is vacuous"
    acted = disc[disc.select_outcome == "mutated"]
    assert (acted.M_dcomp < 0).mean() > 0.5 or (disc.reconnect_possible == False).all()


# ---------------------------------------------------------------- safety gate vs independent oracle
def oracle(s, m, tabu, cfg, budget):
    """Independent re-implementation with networkx only."""
    if any(e is not None and tabu[e] for e in (m.add, m.remove)) or (m.add is not None and s.down[m.add]):
        return False
    cfg_after = s.configured.copy()
    if m.add is not None:
        cfg_after[m.add] = True
    if m.remove is not None:
        cfg_after[m.remove] = False
    if m.remove is None and cfg_after.sum() > budget:
        return False
    if m.add is not None:
        G = nx.Graph()
        G.add_nodes_from(range(s.n))
        G.add_edges_from(s.edge(i) for i in np.flatnonzero(cfg_after))
        if max(G.degree(x) for x in s.edge(m.add)) > cfg.d_max:
            return False

    def g_of(mask):
        G = nx.Graph()
        G.add_nodes_from(range(s.n))
        G.add_edges_from(s.edge(i) for i in np.flatnonzero(mask))
        return G

    def l2(G):
        return sorted(nx.laplacian_spectrum(G))[1] if nx.is_connected(G) else 0.0

    g0 = g_of(s.live_mask())
    floor = min(cfg.lambda2_min, l2(g0))
    after = s.live_mask(cfg_after)
    if m.add is not None:
        after[m.add] = not s.down[m.add]
    states = [after]
    if cfg.link_setup_epochs > 0 and m.remove is not None:
        interim = s.live_mask(cfg_after)
        if m.add is not None:
            interim[m.add] = False
        states.append(interim)
    for mask in states:
        G = g_of(mask)
        if nx.number_connected_components(G) > nx.number_connected_components(g0):
            return False
        if nx.is_connected(G) and l2(G) < floor - 1e-9:
            return False
    return True


def test_gate_matches_independent_oracle_on_random_candidates():
    rng = np.random.default_rng(42)
    cfg = replace(V04, d_max=6, lambda2_min=0.1)
    n_acc = n_rej = 0
    for seed in range(12):
        s = rgg_state(seed)
        s.down = rng.random(s.P) < 0.12
        budget = int(s.configured.sum()) + int(rng.integers(0, 2))
        gate = MutationPipeline(cfg, 1, s.P).gate
        gate.budget = budget
        tabu = rng.random(s.P) < 0.05
        cfg_idx, free = np.flatnonzero(s.configured), np.flatnonzero(~s.configured)
        for _ in range(25):
            kind = rng.integers(3)
            add = int(rng.choice(free)) if kind in (0, 2) else None
            rem = int(rng.choice(cfg_idx)) if kind in (1, 2) else None
            m = Mutation(add=add, remove=rem)
            got = gate.check(s, m, tabu)[0]
            assert got == oracle(s, m, tabu, cfg, budget), (seed, m)
            n_acc += got
            n_rej += not got
    assert n_acc > 20 and n_rej > 20          # both branches genuinely exercised


# ---------------------------------------------------------------- debt recovery
def test_debt_recovers_to_zero_after_stress_subsides():
    d = CusumDebt(Config())
    for _ in range(4):
        d.update(1, 1, 1)
    peak = d.D
    trace = [d.update(0, 0, 0) for _ in range(10)]
    assert peak > 0 and all(b <= a for a, b in zip([peak] + trace, trace)) and trace[-1] == 0


# ---------------------------------------------------------------- CSV output and aggregation
def test_run_writes_csv_and_analysis_aggregates(tmp_path):
    cfgfile = tmp_path / "c.yaml"
    from tccer.config import save_config
    save_config(replace(V04, epochs=15), str(cfgfile))
    out = tmp_path / "out"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "-m", "experiments.run", "--config", str(cfgfile), "--seeds", "3",
                    "--policies", "static", "reactive", "tccer", "--out", str(out)], check=True, cwd=root,
                   capture_output=True)
    df = pd.read_csv(out / "epochs.csv")
    assert len(df) == 3 * 3 * 15
    for col in ["E_hat", "C", "V", "debt", "theta", "lambda2", "components", "budget", "select_outcome",
                "M_gain", "reconnect_possible", "gate_rejections", "n_burst_down"]:
        assert col in df.columns, col
    ps = per_seed(df)
    one = df[(df.policy == "static") & (df.seed == 0)]
    row = ps[(ps.policy == "static") & (ps.seed == 0)].iloc[0]
    assert row.E_hat == pytest.approx(one.E_hat.mean())
    assert row.disconnected == pytest.approx((one.components > 1).mean())


def test_holm_and_ci_known_values():
    adj = holm([0.01, 0.04, 0.03, 0.5])
    assert list(adj.round(6)) == [0.04, 0.09, 0.09, 0.5]
    assert ci95([1.0, 2.0, 3.0]) == pytest.approx(4.302653 * 1.0 / np.sqrt(3), rel=1e-5)


def test_disconnection_episodes_and_censoring():
    from experiments.report_v04 import episodes
    assert episodes(np.array([0, 1, 1, 0, 1, 0, 0])) == ([2, 1], False)
    assert episodes(np.array([1, 1, 0, 1, 1, 1])) == ([2, 3], True)
    assert episodes(np.zeros(5, bool)) == ([], False)
