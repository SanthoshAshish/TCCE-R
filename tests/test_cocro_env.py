"""Tests for the evaluation environments added for COCRO: Watts-Strogatz and scale-free graphs, and the extended failure model (cascade, node, regime).
Additive: the legacy path must be unchanged, and every policy must face the same failure trace (common random numbers)."""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.network.events import FailureTrace
from tccer.network.failure_models import ExtendedTrace, make_trace
from tccer.network.generators import make_network
from tccer.policies import POLICIES
from tccer.sim.engine import simulate
from test_v08_smoke import BASE

WS = replace(BASE, graph_family="ws", ws_k=4, ws_p=0.2, er_p_pot=0.3, n_nodes=30)
SF = replace(BASE, graph_family="sf", ba_m=2, sf_p=0.3, er_p_pot=0.3, n_nodes=30)
EXT = dict(failure_model="extended")


def trace_of(cfg, seed):
    pos, eu, ev, length, init = make_network(cfg, seed)
    return make_trace(cfg, seed, len(eu), (pos[eu] + pos[ev]) / 2, eu, ev, cfg.n_nodes), eu, ev


# ------------------------------------------------------------------ graph generators
@pytest.mark.parametrize("cfg", [WS, SF], ids=["ws", "sf"])
def test_new_graph_families_are_deterministic_connected_and_have_candidate_links(cfg):
    a, b = make_network(cfg, 11), make_network(cfg, 11)
    for x, y in zip(a, b):
        assert np.array_equal(x, y)
    pos, eu, ev, length, init = a
    assert (eu < ev).all() and len(set(zip(eu.tolist(), ev.tolist()))) == len(eu) and (length > 0).all()
    g = nx.Graph(list(zip(eu[init].tolist(), ev[init].tolist())))
    g.add_nodes_from(range(cfg.n_nodes))
    assert nx.is_connected(g) and len(eu) > len(init)
    assert not np.array_equal(make_network(cfg, 12)[1], eu) or not np.array_equal(make_network(cfg, 12)[4], init)   # the seed changes the graph


def test_watts_strogatz_is_regular_ish_and_scale_free_is_heterogeneous():
    big_ws = replace(WS, n_nodes=100, ws_p=0.1)
    big_sf = replace(SF, n_nodes=100)
    for cfg, label in ((big_ws, "ws"), (big_sf, "sf")):
        pos, eu, ev, length, init = make_network(cfg, 3)
        deg = np.bincount(np.r_[eu[init], ev[init]], minlength=cfg.n_nodes)
        if label == "ws":
            assert abs(deg.mean() - cfg.ws_k) < 0.1 and deg.max() <= cfg.ws_k + 5          # near-regular
        else:
            assert deg.max() > 3 * deg.mean() * 0.5 and deg.max() >= 3 * deg.min()          # hub-dominated


@pytest.mark.parametrize("bad", [dict(graph_family="ws", ws_k=3), dict(graph_family="ws", ws_p=1.5), dict(graph_family="sf", sf_p=2.0),
                                 dict(failure_model="weird"), dict(casc_gain=0.5), dict(node_rate=1.0), dict(node_repair=0.0),
                                 dict(regime_epoch=-5), dict(regime_mult=0.0)])
def test_invalid_environment_options_are_rejected(bad):
    with pytest.raises(ValueError):
        replace(BASE, **bad)


def test_defaults_are_the_original_environment():
    c = BASE
    assert (c.failure_model, c.casc_gain, c.node_rate, c.regime_epoch, c.regime_mult) == ("legacy", 1.0, 0.0, -1, 1.0)


# ------------------------------------------------------------------ the legacy path is untouched
def test_legacy_make_trace_is_the_original_failure_trace():
    cfg = replace(BASE, burst_rate=0.2)
    tr, eu, ev = trace_of(cfg, 5)
    assert type(tr) is FailureTrace
    pos, eu2, ev2, ln, init = make_network(cfg, 5)
    ref = FailureTrace(cfg, 5, len(eu2), edge_mid=(pos[eu2] + pos[ev2]) / 2)
    for name in ("u_transient", "u_fail", "u_repair", "burst"):
        assert np.array_equal(getattr(tr, name), getattr(ref, name))


def test_extended_trace_keeps_the_original_random_draws():
    cfg = replace(BASE, burst_rate=0.2, **EXT, casc_gain=4.0, node_rate=0.05, regime_epoch=10, regime_mult=3.0)
    tr, eu, ev = trace_of(cfg, 5)
    assert isinstance(tr, ExtendedTrace)
    ref = trace_of(replace(BASE, burst_rate=0.2), 5)[0]
    for name in ("u_transient", "u_fail", "u_repair"):
        assert np.array_equal(getattr(tr, name), getattr(ref, name))                      # node/regime/cascade use separate streams or thresholds only


def test_extended_with_neutral_parameters_equals_legacy():
    a = pd.DataFrame(simulate(replace(BASE, epochs=20), 8531, "v06_front", log_rounds=False)[0])
    b = pd.DataFrame(simulate(replace(BASE, epochs=20, **EXT), 8531, "v06_front", log_rounds=False)[0])
    pd.testing.assert_frame_equal(a, b)


# ------------------------------------------------------------------ failure processes
def failure_events(cfg, seed, epochs):
    """Run the background process alone; return (n_new_failures_exposed, exposed_up, n_new_failures_unexposed, unexposed_up)."""
    tr, eu, ev = trace_of(replace(cfg, epochs=epochs), seed)
    n = cfg.n_nodes
    down = np.zeros(len(eu), bool)
    fe = ue = fo = uo = 0
    for k in range(epochs):
        dn = np.bincount(eu, weights=down.astype(float), minlength=n) + np.bincount(ev, weights=down.astype(float), minlength=n)
        exposed = (dn[eu] + dn[ev]) > 0
        new = tr.epoch_update(k, down)
        fail = new & ~down
        fe += int((fail & exposed).sum()); ue += int((~down & exposed).sum())
        fo += int((fail & ~exposed).sum()); uo += int((~down & ~exposed).sum())
        down = new
    return fe, ue, fo, uo


def test_cascade_raises_the_failure_rate_of_links_adjacent_to_failures():
    base = replace(BASE, n_nodes=30, p_fail=0.02, p_repair=0.2)
    fe, ue, fo, uo = failure_events(base, 1, 400)
    ratio_legacy = (fe / ue) / (fo / uo)
    fe, ue, fo, uo = failure_events(replace(base, **EXT, casc_gain=6.0), 1, 400)
    ratio_cascade = (fe / ue) / (fo / uo)
    assert 0.6 < ratio_legacy < 1.6 and ratio_cascade > 3.0


def test_node_failures_take_down_every_incident_link_and_only_those():
    cfg = replace(BASE, n_nodes=30, burst_rate=0.0, **EXT, node_rate=0.08, node_repair=0.5, epochs=60)      # BASE has spatial bursts on: switch them off here
    tr, eu, ev = trace_of(cfg, 2)
    assert tr.node_down.any()
    expect = tr.node_down[:, eu] | tr.node_down[:, ev]
    assert np.array_equal(tr.burst, expect)                                       # with no spatial bursts the burst mask is exactly the node-incident mask
    k = int(np.flatnonzero(tr.node_down.any(axis=1))[0])
    v = int(np.flatnonzero(tr.node_down[k])[0])
    assert tr.burst[k][(eu == v) | (ev == v)].all()


def test_node_failure_stream_is_policy_independent_and_seeded():
    cfg = replace(BASE, n_nodes=30, **EXT, node_rate=0.05, epochs=40)
    a, b, c = trace_of(cfg, 7)[0], trace_of(cfg, 7)[0], trace_of(cfg, 8)[0]
    assert np.array_equal(a.node_down, b.node_down) and not np.array_equal(a.node_down, c.node_down)


def test_regime_switch_raises_the_failure_rate_only_after_the_switch():
    cfg = replace(BASE, n_nodes=30, p_fail=0.02, p_repair=0.2, **EXT, regime_epoch=200, regime_mult=5.0)
    tr, eu, ev = trace_of(replace(cfg, epochs=400), 3)
    down = np.zeros(len(eu), bool)
    early = late = 0
    for k in range(400):
        new = tr.epoch_update(k, down)
        fails = int((new & ~down).sum())
        early, late = (early + fails, late) if k < 200 else (early, late + fails)
        down = new
    assert late > 2.5 * early


def test_failure_trace_is_identical_across_policies_in_the_extended_environment():
    cfg = replace(BASE, epochs=20, **EXT, casc_gain=4.0, node_rate=0.04, regime_epoch=8, regime_mult=2.0)
    traces = [pd.DataFrame(simulate(cfg, 8532, p, log_rounds=False)[0])[["n_down_potential", "n_burst_down"]].to_numpy()
              for p in ("static", "v06_front", "v06_reactive", "v08_rcpr")]
    for t in traces[1:]:
        assert np.array_equal(traces[0], t)


# ------------------------------------------------------------------ COCRO on the new environments
@pytest.mark.parametrize("cfg", [WS, SF, replace(BASE, **EXT, casc_gain=4.0, node_rate=0.03, regime_epoch=8, regime_mult=2.0)], ids=["ws", "sf", "extended-rgg"])
def test_cocro_m_runs_on_the_new_environments_and_respects_cap_and_budget(cfg):
    import tccer.policies.cocro as cc
    cc.register_variant("cocro_m_env_t", base=cc.CocroParams.fast(), price="none")
    try:
        r = pd.DataFrame(simulate(replace(cfg, epochs=24, mutation_cap=3), 8533, "cocro_m_env_t", log_rounds=False)[0])
        assert r.n_mutations.iloc[-1] <= 3 and (r.configured_edges <= r.budget).all() and len(r) == 24
        assert r.cocro_evaluated.sum() >= 1
    finally:
        POLICIES.pop("cocro_m_env_t", None)
