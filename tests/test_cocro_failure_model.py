"""COCRO v2 CFPE tests: parameter recovery on synthetic processes with a KNOWN law, censored mixture, forgetting, node attribution."""
import numpy as np
import pytest

from tccer.core.failure_model import CFPEParams, PropagationFailureModel, Theta, fit_mixture, persistence_prob


def graph(n=30, extra=60, seed=0):
    rng = np.random.default_rng(seed)
    edges = {(i, (i + 1) % n) if i < (i + 1) % n else ((i + 1) % n, i) for i in range(n)}
    while len(edges) < n + extra:
        a, b = sorted(rng.choice(n, 2, replace=False))
        edges.add((int(a), int(b)))
    e = np.array(sorted(edges))
    return n, e[:, 0], e[:, 1]


def simulate(n, eu, ev, epochs, h0, lift, r_s, r_l, w, rng, h_after=None, switch=None):
    """Known generator: an up link fails with h0 (x lift if any adjacent link was down in the previous epoch); downtime ~ mixture of geometrics."""
    P = len(eu)
    down = np.zeros(P, bool)
    long_ = np.zeros(P, bool)
    out = []
    for k in range(epochs):
        h = h0 if (switch is None or k < switch) else h_after
        dn = np.bincount(eu, weights=down.astype(float), minlength=n) + np.bincount(ev, weights=down.astype(float), minlength=n)
        exposed = (dn[eu] + dn[ev]) > 0
        fail = ~down & (rng.random(P) < np.where(exposed, min(0.9, h * lift), h))
        rate = np.where(long_, r_l, r_s)
        repair = down & (rng.random(P) < rate)
        long_ = np.where(fail, rng.random(P) < w, long_)
        down = (down & ~repair) | fail
        out.append(down.copy())
    return out


def feed(model, series, configured):
    for k, d in enumerate(series):
        model.update(d, configured, k)


def test_iid_failures_recover_the_baseline_hazard_and_no_lift():
    n, eu, ev = graph()
    rng = np.random.default_rng(1)
    series = simulate(n, eu, ev, 400, 0.03, 1.0, 0.4, 0.4, 0.5, rng)
    m = PropagationFailureModel(n, eu, ev, CFPEParams(phi=0.995))
    feed(m, series, np.ones(len(eu), bool))
    th = m.map_theta()
    assert abs(th.h[0] - 0.03) < 0.008
    assert 0.5 < m.lift(th) < 2.2                      # no true propagation: the estimated association stays near 1


def test_lagged_adjacency_lift_is_detected():
    n, eu, ev = graph()
    rng = np.random.default_rng(2)
    series = simulate(n, eu, ev, 500, 0.02, 4.0, 0.4, 0.4, 0.5, rng)
    m = PropagationFailureModel(n, eu, ev, CFPEParams(phi=0.997))
    feed(m, series, np.ones(len(eu), bool))
    assert 2.0 < m.lift() < 9.0                        # true lift 4 (bucketed estimate averages over exposure levels)
    assert m.map_theta().h[1] > 2 * m.map_theta().h[0]


def test_forgetting_tracks_a_regime_change():
    n, eu, ev = graph()
    rng = np.random.default_rng(3)
    series = simulate(n, eu, ev, 300, 0.02, 1.0, 0.4, 0.4, 0.5, rng, h_after=0.10, switch=150)
    fast, slow = PropagationFailureModel(n, eu, ev, CFPEParams(phi=0.95)), PropagationFailureModel(n, eu, ev, CFPEParams(phi=1.0))
    for mdl in (fast, slow):
        feed(mdl, series, np.ones(len(eu), bool))
    assert abs(fast.map_theta().h[0] - 0.10) < 0.03
    assert abs(slow.map_theta().h[0] - 0.10) > abs(fast.map_theta().h[0] - 0.10)


def test_censored_mixture_beats_ignoring_censoring():
    rng = np.random.default_rng(4)
    w, rs, rl, N, Tobs = 0.3, 0.5, 0.04, 3000, 60
    comp = rng.random(N) < w
    d = rng.geometric(np.where(comp, rl, rs))             # durations >= 1
    start = rng.integers(0, Tobs, N)
    cens = start + d > Tobs                              # still down when the observation ends
    dur = np.where(cens, Tobs - start, d)
    prm = CFPEParams()
    wc, rsc, rlc = fit_mixture(dur, cens, np.ones(N), prm)
    wn, rsn, rln = fit_mixture(dur, np.zeros(N, bool), np.ones(N), prm)    # treats censored durations as complete
    assert abs(rlc - rl) < abs(rln - rl)
    assert abs(wc - w) < 0.12 and rsc > rlc


def test_persistence_probability_matches_survival_ratio():
    th = Theta(h=np.array([0.02]), w=0.35, r_s=0.45, r_l=0.05, node_h=0.0, node_r=0.2)
    S = lambda x: th.w * (1 - th.r_l) ** x + (1 - th.w) * (1 - th.r_s) ** x           # mixture survival (independent derivation)
    for a in (1, 3, 8, 25):
        for H in (2, 5):
            assert persistence_prob(a, th, H) == pytest.approx(S(a + H) / S(a), rel=1e-9)
    assert persistence_prob(25, th, 5) > persistence_prob(1, th, 5)                    # longer-down links are more likely persistent


def test_node_failures_are_attributed_to_the_node_not_to_link_statistics():
    n = 6
    eu, ev = np.array([0, 0, 0, 1, 2, 3]), np.array([1, 2, 3, 4, 5, 4])
    cfg = np.ones(len(eu), bool)
    m = PropagationFailureModel(n, eu, ev, CFPEParams(phi=1.0))
    up = np.zeros(len(eu), bool)
    m.update(up, cfg, 0)
    f0 = m.nb_f.sum()
    node0_down = up.copy()
    node0_down[[0, 1, 2]] = True                         # all links of node 0 (links 0, 1, 2) fail together
    m.update(node0_down, cfg, 1)
    assert m.node_down[0] and m.node_f == 1.0
    assert m.nb_f.sum() == f0                            # the three link failures were not counted as link-level failures
    assert m.ep_excluded[[0, 1, 2]].all()
    for k in range(2, 6):
        m.update(node0_down, cfg, k)
    m.update(up, cfg, 6)
    assert len(m.episodes) == 0                          # repairs of node-attributed episodes do not enter the downtime mixture


def test_updates_must_be_in_order():
    n, eu, ev = graph(10, 5)
    m = PropagationFailureModel(n, eu, ev)
    m.update(np.zeros(len(eu), bool), np.ones(len(eu), bool), 0)
    with pytest.raises(AssertionError):
        m.update(np.zeros(len(eu), bool), np.ones(len(eu), bool), 5)


def test_posterior_draws_spread_shrinks_with_data():
    n, eu, ev = graph()
    spreads = []
    for epochs in (30, 400):
        rng = np.random.default_rng(5)
        m = PropagationFailureModel(n, eu, ev, CFPEParams(phi=1.0))
        feed(m, simulate(n, eu, ev, epochs, 0.03, 1.0, 0.4, 0.4, 0.5, rng), np.ones(len(eu), bool))
        r = np.random.default_rng(9)
        spreads.append(np.std([m.sample_theta(r).h[0] for _ in range(200)]))
    assert spreads[1] < spreads[0]


def test_mixture_falls_back_to_prior_with_little_data():
    n, eu, ev = graph(10, 5)
    m = PropagationFailureModel(n, eu, ev)
    th = m.map_theta()
    assert th.r_s == th.r_l == m.prm.prior_r and th.w == 0.5
