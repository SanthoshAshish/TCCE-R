"""COCRO v2 scenario-sampler tests: determinism, common random numbers, independence from the environment's streams (leakage guard),
statistical fidelity to the fitted model, age-dependent repair, node outages, plug-in vs posterior sampling, cross-fitting independence."""
import inspect

import numpy as np

import tccer.core.scenarios as scen_mod
from tccer.core.failure_model import CFPEParams, PropagationFailureModel
from tccer.core.scenarios import CONTROLLER_STREAM, ScenarioSampler, controller_rng
from test_cocro_failure_model import feed, graph, simulate


def fitted(h0=0.03, lift=1.0, epochs=300, phi=0.995, seed=1, w=0.5, rs=0.4, rl=0.4):
    n, eu, ev = graph()
    series = simulate(n, eu, ev, epochs, h0, lift, rs, rl, w, np.random.default_rng(seed))
    m = PropagationFailureModel(n, eu, ev, CFPEParams(phi=phi))
    feed(m, series, np.ones(len(eu), bool))
    return m, ScenarioSampler(m)


def test_shapes_determinism_and_dtype():
    m, sp = fitted()
    a = sp.sample(8, 5, controller_rng(1, 10, 1))
    b = sp.sample(8, 5, controller_rng(1, 10, 1))
    assert a.down.shape == (8, 5, m.P) and a.down.dtype == bool and a.node_down.shape == (8, 5, m.n) and a.k == m.k
    assert np.array_equal(a.down, b.down)
    c = sp.sample(8, 5, controller_rng(1, 10, 2))
    assert not np.array_equal(a.down, c.down)


def test_controller_streams_are_independent_of_the_environment_streams():
    # environment streams are default_rng([seed, 0..6]); the controller stream carries the marker 7919 and the role, so no key can coincide
    assert CONTROLLER_STREAM not in range(7)
    for seed in (0, 1, 8500, 9300):
        c = controller_rng(seed, 3, 1).random(1000)
        for env_role in range(7):
            e = np.random.default_rng([seed, env_role]).random(1000)
            assert abs(np.corrcoef(c, e)[0, 1]) < 0.15 and not np.allclose(c, e)
    src = inspect.getsource(scen_mod)
    assert not hasattr(scen_mod, "FailureTrace") and "from tccer.network" not in src and "import tccer.network" not in src   # no access to the trace


def test_decisions_cannot_depend_on_the_future_environment_trace():
    """The sampler consumes only the model (past observations) and its own rng: changing a FUTURE environment trace changes nothing."""
    n, eu, ev = graph()
    past = simulate(n, eu, ev, 60, 0.03, 1.0, 0.4, 0.4, 0.5, np.random.default_rng(7))
    outs = []
    for future_seed in (100, 200):                        # two different (unobserved) futures
        _ = simulate(n, eu, ev, 20, 0.03, 1.0, 0.4, 0.4, 0.5, np.random.default_rng(future_seed))
        m = PropagationFailureModel(n, eu, ev, CFPEParams())
        feed(m, past, np.ones(len(eu), bool))
        outs.append(ScenarioSampler(m).sample(6, 4, controller_rng(1, 60, 1)).down)
    assert np.array_equal(outs[0], outs[1])


def test_scenario_failure_rate_matches_the_fitted_hazard():
    m, sp = fitted(h0=0.03, lift=1.0)
    m.update(np.zeros(m.P, bool), np.ones(m.P, bool), m.k + 1)           # all links up now
    th = m.map_theta()
    s = sp.sample(2000, 1, controller_rng(2, 0, 1), plug_in=True)
    rate = s.down[:, 0, :].mean()
    assert abs(rate - th.h[0]) < 0.006                    # first-step failure frequency equals the plug-in hazard (no lagged exposure yet)


def test_lagged_adjacency_raises_scenario_failure_rate_when_the_data_say_so():
    m, sp = fitted(h0=0.02, lift=5.0, epochs=500, phi=0.998, seed=3)
    d = np.zeros(m.P, bool)
    d[0] = True                                          # one link down now: its neighbours are exposed in the next step
    m.update(d, np.ones(m.P, bool), m.k + 1)
    s = sp.sample(3000, 2, controller_rng(3, 0, 1), plug_in=True)
    dn = np.bincount(m.eu, weights=d.astype(float), minlength=m.n) + np.bincount(m.ev, weights=d.astype(float), minlength=m.n)
    exposed = ((dn[m.eu] + dn[m.ev]) > 0) & ~d
    # first simulated epoch: failure frequency of links exposed by the current state (a neighbour is down) vs unexposed up links
    r_exposed, r_other = s.down[:, 0, exposed].mean(), s.down[:, 0, ~exposed & ~d].mean()
    assert r_exposed > 1.5 * r_other


def test_repair_depends_on_age_through_the_mixture():
    m, sp = fitted(w=0.4, rs=0.6, rl=0.03, epochs=400, seed=5, phi=0.999)
    th = m.map_theta()
    assert th.r_s > 3 * th.r_l                           # the fit separates the components
    short = np.zeros(m.P, bool); short[0] = True
    long = np.zeros(m.P, bool); long[1] = True
    m2 = PropagationFailureModel(m.n, m.eu, m.ev, m.prm)
    m2.__dict__.update({k: (v.copy() if hasattr(v, "copy") else v) for k, v in m.__dict__.items()})
    down = np.zeros(m.P, bool); down[[0, 1]] = True
    m2.prev_down = down.copy()
    m2.age = np.zeros(m.P, int); m2.age[0] = 1; m2.age[1] = 40               # one fresh, one long-standing episode
    m2.ep_excluded = np.zeros(m.P, bool); m2.node_down = np.zeros(m.n, bool)
    s = ScenarioSampler(m2).sample(4000, 3, controller_rng(4, 0, 1), plug_in=True)
    still_down_fresh, still_down_old = s.down[:, 2, 0].mean(), s.down[:, 2, 1].mean()
    assert still_down_old > still_down_fresh + 0.2        # a link that has been down long is much more likely to persist


def test_node_outage_forces_incident_links_down():
    m, _ = fitted()
    m.node_down = np.zeros(m.n, bool); m.node_down[0] = True
    m.prev_down = np.zeros(m.P, bool)
    inc = (m.eu == 0) | (m.ev == 0)
    s = ScenarioSampler(m).sample(500, 1, controller_rng(5, 0, 1), plug_in=True)
    th = m.map_theta()
    frac_down = s.down[:, 0, inc].all(axis=1).mean()
    assert abs(frac_down - (1 - th.node_r)) < 0.06        # the node stays down with probability 1 - node_r, all incident links down with it
    assert s.down[:, 0, inc][s.node_down[:, 0, 0]].all()   # whenever the node is down in a scenario, every incident link is down


def test_plug_in_has_identical_thetas_posterior_sampling_varies():
    m, sp = fitted(epochs=40, phi=1.0)
    a = sp.sample(6, 2, controller_rng(6, 0, 1), plug_in=True)
    b = sp.sample(6, 2, controller_rng(6, 0, 1), plug_in=False)
    assert all(np.array_equal(t.h, a.thetas[0].h) for t in a.thetas)
    assert len({round(float(t.h[0]), 8) for t in b.thetas}) > 1


def test_cross_fitting_streams_give_independent_scenario_sets():
    m, sp = fitted()
    # start from an all-up state: otherwise both sets share the currently-down links (a shared initial condition, not shared randomness)
    m.update(np.zeros(m.P, bool), np.ones(m.P, bool), m.k + 1)
    sel = sp.sample(200, 4, controller_rng(7, 20, 1), plug_in=True).down.astype(float).ravel()
    tst = sp.sample(200, 4, controller_rng(7, 20, 2), plug_in=True).down.astype(float).ravel()
    assert abs(np.corrcoef(sel, tst)[0, 1]) < 0.1
