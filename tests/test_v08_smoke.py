"""v0.8 draft code: validation, graph families, shock, observation perturbation, ablation arms, predictor.
Small smoke tests only (n <= 24, <= 24 epochs). They check invariants and wiring, not scientific performance."""
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from tccer.config import Config, replace
from tccer.core.predict import HazardEstimator, Predictor, _rho
from tccer.core.selector import MutationPipeline
from tccer.network.events import FailureTrace
from tccer.network.generators import make_network, random_geometric
from tccer.network.state import NetworkState
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

BASE = replace(Config(), n_nodes=20, init_radius=0.3, radio_range=0.42, epochs=24, rounds_per_epoch=15,
               link_setup_epochs=2, degree_fix=True, burst_rate=0.15, burst_radius=0.2, p_fail=0.02,
               mutation_cap=3, v06_threshold=0.3, v06_kappa=0.2, theta0=0.3, theta_min=0.075, theta_max=1.2,
               feedback_rule="counterfactual", edge_budget_frac=1.0, budget_on="configured", degree_basis="configured",
               feedback_after_setup=True, failed_link_value="if_up", d_max=10)
ER = replace(BASE, graph_family="er", er_p_init=0.3, er_p_pot=0.3)
BA = replace(BASE, graph_family="ba", ba_m=2, er_p_pot=0.3)
V08 = [p for p in POLICIES if p.startswith("v08_")]


def rows(cfg, seed, policy):
    return pd.DataFrame(simulate(cfg, seed, policy, log_rounds=False)[0])


@pytest.mark.parametrize("bad", [dict(graph_family="ER"), dict(graph_family="ba", ba_m=0), dict(obs_noise=-0.1),
                                 dict(obs_delay=-1), dict(v08_w="1,2"), dict(v08_w="0,0,0"), dict(cand_k=0),
                                 dict(shock_epoch=3, shock_len=0), dict(j_beta=-1.0),
                                 dict(graph_family="er", er_p_init=0.0)])
def test_invalid_v08_options_rejected(bad):
    with pytest.raises(ValueError):
        replace(BASE, **bad)


def test_defaults_are_valid_and_inert():
    c = Config()
    assert (c.graph_family, c.shock_epoch, c.obs_noise, c.obs_delay, c.v08_w, c.v08_front) == ("rgg", -1, 0.0, 0, None, 0)


@pytest.mark.parametrize("cfg", [ER, BA], ids=["er", "ba"])
def test_non_geometric_generators(cfg):
    a, b = make_network(cfg, 5), make_network(cfg, 5)
    for x, y in zip(a, b):
        assert np.array_equal(x, y)                     # deterministic in the seed
    pos, eu, ev, length, init_idx = a
    assert (eu < ev).all() and len(set(zip(eu.tolist(), ev.tolist()))) == len(eu)
    assert (length > 0).all() and len(init_idx) > 0 and init_idx.max() < len(eu)
    g = nx.Graph(list(zip(eu[init_idx].tolist(), ev[init_idx].tolist())))
    g.add_nodes_from(range(cfg.n_nodes))
    assert nx.is_connected(g)                           # initial graph connected
    assert len(eu) > len(init_idx)                      # there are candidate links to add


@pytest.mark.parametrize("cfg", [ER, BA], ids=["er", "ba"])
def test_non_rgg_families_run_with_cap_budget_and_common_trace(cfg):
    traces = []
    for pol in ("static", "v06_reactive", "v06_tccer", "v08_rcpr"):
        r = rows(cfg, 11, pol)
        assert len(r) == cfg.epochs
        assert r.n_mutations.iloc[-1] <= cfg.mutation_cap
        assert (r.configured_edges <= r.budget).all()   # strict edge budget never exceeded
        traces.append(r.n_down_potential.tolist())
    assert all(t == traces[0] for t in traces)           # failure trace independent of the policy


def test_rgg_default_path_unchanged_by_make_network():
    a = make_network(BASE, 3)
    b = random_geometric(BASE.n_nodes, BASE.init_radius, BASE.radio_range, 3)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))


def test_shock_adds_only_the_window_and_leaves_other_streams_alone():
    mid = np.random.default_rng(0).random((60, 2))
    c0 = replace(BASE, burst_rate=0.0)
    c1 = replace(c0, shock_epoch=5, shock_len=4, shock_radius=0.5)
    t0, t1 = FailureTrace(c0, 9, 60, edge_mid=mid), FailureTrace(c1, 9, 60, edge_mid=mid)
    assert np.array_equal(t0.u_transient, t1.u_transient) and np.array_equal(t0.u_fail, t1.u_fail)
    assert not t0.burst.any() and t1.burst.any()
    assert not t1.burst[:5].any() and not t1.burst[9:].any()      # confined to epochs 5..8
    assert t1.burst[5:9].all(axis=0).sum() == t1.bursts[0][3]     # the same links are down for the whole window
    FailureTrace(replace(c0, shock_epoch=22, shock_len=15, shock_radius=0.5), 9, 60, edge_mid=mid)   # runs past horizon


def test_shock_default_off_matches_no_shock():
    pd.testing.assert_frame_equal(rows(BASE, 4, "v06_reactive"), rows(replace(BASE, shock_epoch=-1), 4, "v06_reactive"))


def test_observation_perturbation_affects_only_the_controller_view():
    d = 3
    truth = rows(BASE, 2, "static")
    for cfg in (replace(BASE, obs_delay=d), replace(BASE, obs_noise=0.2), replace(BASE, obs_delay=d, obs_noise=0.2)):
        pd.testing.assert_frame_equal(truth, rows(cfg, 2, "static"))     # the logged world state is the truth
    # reactive arm reads the delayed value: its statistic at k is the true E at max(0, k - d)
    r = rows(replace(BASE, obs_delay=d, v06_threshold=2.0), 2, "v06_reactive")    # unreachable threshold: never mutates
    e = r.E_hat.to_numpy()
    assert np.allclose(r.v06_stat.to_numpy(), e[np.maximum(0, np.arange(len(e)) - d)])
    # noisy view: reproducible, clipped, different from the truth
    cn = replace(BASE, obs_noise=0.3, v06_threshold=2.0)
    a, b = rows(cn, 2, "v06_reactive"), rows(cn, 2, "v06_reactive")
    pd.testing.assert_frame_equal(a, b)
    assert a.v06_stat.between(0, 1).all() and not np.allclose(a.v06_stat, a.E_hat)


def test_zero_perturbation_equals_baseline_policy_rows():
    pd.testing.assert_frame_equal(rows(BASE, 6, "v06_tccer"),
                                  rows(replace(BASE, obs_noise=0.0, obs_delay=0), 6, "v06_tccer"))


@pytest.mark.parametrize("pol", V08)
def test_v08_arms_run_respect_cap_budget_and_are_deterministic(pol):
    cfg = replace(BASE, v08_front=2) if pol == "v08_hybrid" else BASE
    a, b = rows(cfg, 8, pol), rows(cfg, 8, pol)
    pd.testing.assert_frame_equal(a, b)
    assert a.n_mutations.iloc[-1] <= cfg.mutation_cap and (a.configured_edges <= a.budget).all()
    assert set(a.mutation_kind) <= {"", "rewire"}                  # strict budget: every mutation is a rewire


def test_hybrid_with_zero_front_equals_b8():
    pd.testing.assert_frame_equal(rows(BASE, 8, "v08_hybrid").drop(columns=["policy", "hyb_n_front"]),   # hyb_n_front: hybrid-only log column
                                  rows(BASE, 8, "v08_rcpr").drop(columns=["policy"]))


def test_hybrid_front_phase_acts_early_and_state_blind():
    cfg = replace(BASE, v08_front=2, v06_threshold=50.0)           # RCPR trigger unreachable: only the front phase acts
    r = rows(cfg, 8, "v08_hybrid")
    assert r.index[r.mutation != ""].tolist() == [0, 2]


def test_predictor_and_hazards():
    h, r = HazardEstimator().rates()
    assert abs(h - 0.02) < 1e-9 and abs(r - 0.1) < 1e-9            # prior only
    assert _rho(3, np.array([], dtype=int), np.array([], dtype=int), np.array([])) == 1.0
    u, v = np.array([0, 1, 2, 3]), np.array([1, 2, 3, 0])
    assert _rho(4, u, v, np.full(4, 0.5)) > _rho(4, u, v, np.ones(4))        # less reliable links mix slower
    pos, eu, ev, length, init_idx = make_network(BASE, 1)
    st = NetworkState(pos, eu, ev, length, init_idx)
    pr = Predictor(BASE, HazardEstimator())
    null = pr.evaluate(st, None, st.live_mask())
    assert null["C"] == 0 and null["S"] == 0 and 0 <= null["E"] <= 1 and 0 <= null["R"] <= 1
    m = MutationPipeline(BASE, len(init_idx), len(eu))._ranked(st, 0, "lexicographic", None)[0][0][0]
    a = pr.evaluate(st, m, st.live_mask())
    assert 0 <= a["E"] <= 1 and 0 <= a["R"] <= 1 and a["C"] in (0.25, 1.0) and a["S"] >= 0
    assert pr.J(null) == BASE.j_alpha * null["E"] + BASE.j_beta * null["R"]
