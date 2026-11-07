"""COCRO v2 gain-estimator tests: spectral error vs Monte-Carlo, component logic, timeline of setup and benefit, decomposition arithmetic,
calibration map, Laplacian surrogate agreement, and the effect of failures on gains."""
import numpy as np
import pytest

from tccer.core.mutations import Mutation
from tccer.core.scenarios import ScenarioSet
from tccer.core.value import (CalibrationMap, GainEstimator, laplacian_E, metropolis_W, spectral_E)

T, EPS = 60, 0.01


def ring_edges(n, chords=()):
    e = [(i, (i + 1) % n) for i in range(n)] + list(chords)
    e = [tuple(sorted(x)) for x in e]
    return np.array([a for a, b in e]), np.array([b for a, b in e])


def mc_E(n, eu, ev, T, eps, draws=3000, seed=0):
    """Monte-Carlo mean of the simulator's metric E = 1 - min(1, ln e(T) / ln eps), e(T) = ||x_T - mean|| / ||x_0 - mean||, x_0 ~ U[0,1]^n."""
    W = metropolis_W(n, eu, ev)
    rng = np.random.default_rng(seed)
    x0 = rng.random((draws, n))
    c0 = x0 - x0.mean(axis=1, keepdims=True)
    xT = np.linalg.matrix_power(W, T) @ x0.T
    cT = xT.T - xT.T.mean(axis=1, keepdims=True)
    e = np.linalg.norm(cT, axis=1) / np.linalg.norm(c0, axis=1)
    return float(np.mean(1.0 - np.minimum(1.0, np.maximum(0.0, np.log(e) / np.log(EPS)))))


# NB: graphs with n <= 14 sit on the error floor (E = 0 within T = 60 rounds), so the checks below use n >= 24 where E is mid-range.
@pytest.mark.parametrize("n,chords", [(24, ()), (30, ()), (30, ((0, 15),)), (40, ((0, 20), (10, 30)))])
def test_spectral_E_tracks_the_monte_carlo_metric(n, chords):
    eu, ev = ring_edges(n, chords)
    s, m = spectral_E(n, eu, ev, T, EPS), mc_E(n, eu, ev, T, EPS)
    assert 0.05 < m < 0.95                                # not on a floor/ceiling: the comparison is informative
    assert abs(s - m) < 0.12                              # measured bias is 0.04-0.09 (surrogate above the simulated mean): why a calibration map exists
    assert s >= m - 0.02                                  # the bias is upward (mean-square contraction vs mean of per-draw log ratios)


def test_spectral_E_orders_graphs_like_the_metric():
    n = 30
    graphs = [ring_edges(n), ring_edges(n, ((0, 15),)), ring_edges(n, ((0, 15), (7, 22), (3, 18)))]
    s = [spectral_E(n, *g, T, EPS) for g in graphs]
    m = [mc_E(n, *g, T, EPS) for g in graphs]
    assert s[0] > s[1] > s[2] and m[0] > m[1] > m[2]


def test_disconnected_and_empty_graphs_have_unit_error():
    n = 8
    assert spectral_E(n, np.array([0, 1]), np.array([1, 2]), T, EPS) == 1.0          # most nodes isolated
    assert spectral_E(n, np.array([], int), np.array([], int), T, EPS) == 1.0
    assert laplacian_E(n, np.array([0, 1]), np.array([1, 2]), T, EPS) == 1.0


def test_transient_failures_raise_the_surrogate_error():
    n = 30
    eu, ev = ring_edges(n, ((0, 15),))
    assert spectral_E(n, eu, ev, T, EPS, p_transient=0.2) > spectral_E(n, eu, ev, T, EPS, p_transient=0.0)


def test_floor_effect_two_saturated_graphs_give_zero_gain():
    """Design risk R4 made concrete: when both graphs converge below eps within the epoch (E = 0), an improvement has zero measured gain."""
    n = 12
    eu0, ev0 = ring_edges(n)
    eu1, ev1 = ring_edges(n, ((0, 6),))
    assert spectral_E(n, eu0, ev0, T, EPS) == 0.0 and spectral_E(n, eu1, ev1, T, EPS) == 0.0


def test_laplacian_surrogate_ranks_like_the_spectral_value():
    rng = np.random.default_rng(3)
    n, a, b = 20, [], []
    for _ in range(40):
        extra = int(rng.integers(0, 14))
        eu, ev = ring_edges(n, [tuple(sorted(rng.choice(n, 2, replace=False))) for _ in range(extra) if True])
        keep = np.array([i for i in range(len(eu)) if eu[i] != ev[i]])
        pairs = {(int(eu[i]), int(ev[i])) for i in keep}
        eu2, ev2 = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
        a.append(spectral_E(n, eu2, ev2, T, EPS)); b.append(laplacian_E(n, eu2, ev2, T, EPS))
    from scipy.stats import spearmanr
    assert spearmanr(a, b)[0] > 0.8                       # hypothesis check on random graphs (the real check uses development-seed states)


def test_calibration_map_identity_then_isotonic():
    cm = CalibrationMap(min_n=4)
    assert cm(0.37) == 0.37                               # identity until fitted
    cm.fit([1, 2, 3, 4], [1, 3, 2, 4])
    assert np.allclose(cm.y, [1, 1, 2.5, 2.5, 4, 4]) and np.isclose(cm(1.5), 1.75) and np.isclose(cm(2.5), 2.5)   # pooled block is a step
    xs = np.linspace(0, 5, 50)
    assert (np.diff(cm(xs)) >= -1e-12).all()              # monotone


def test_calibration_map_reduces_the_surrogate_bias_on_held_out_graphs():
    rng = np.random.default_rng(0)
    pred, real = [], []
    for n in (24, 28, 32, 36, 40):
        for k in range(4):
            ch = [tuple(sorted(rng.choice(n, 2, replace=False))) for _ in range(k)]
            eu, ev = ring_edges(n, ch)
            pairs = sorted({(int(a), int(b)) for a, b in zip(eu, ev) if a != b})
            eu, ev = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
            pred.append(spectral_E(n, eu, ev, T, EPS)); real.append(mc_E(n, eu, ev, T, EPS, 1500, seed=n + k))
    pred, real = np.array(pred), np.array(real)
    train, test = np.arange(len(pred)) % 2 == 0, np.arange(len(pred)) % 2 == 1
    cm = CalibrationMap(min_n=5).fit(pred[train], real[train])
    assert np.abs(cm(pred[test]) - real[test]).mean() < np.abs(pred[test] - real[test]).mean()


def scenarios_no_failures(P, k, S=2, Hs=5):
    return ScenarioSet(down=np.zeros((S, Hs, P), bool), node_down=np.zeros((S, Hs, 1), bool), k=k, thetas=[])


def setup(n=30, chords=((0, 15),), extra=((7, 22), (5, 20), (10, 25))):
    eu, ev = ring_edges(n, chords)
    base = len(eu)
    pe = ring_edges(n, list(chords) + list(extra))
    eu, ev = pe
    conf = np.zeros(len(eu), bool)
    conf[:base] = True
    return n, eu, ev, conf, base


def test_timeline_matches_a_hand_computation_without_failures():
    n, eu, ev, conf, base = setup()
    d, H, k, tau = 2, 3, 10, 30
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, d, H)
    ready = np.zeros(len(eu), int)
    add = base                                              # a configured-set extension: pure addition (not a rewire)
    res = ge.estimate(conf, ready, k, scenarios_no_failures(len(eu), k, S=2, Hs=d + H), [Mutation(add=add)], tau)
    E0 = spectral_E(n, eu[conf], ev[conf], T, EPS)
    cfg1 = conf.copy(); cfg1[add] = True
    E1 = spectral_E(n, eu[cfg1], ev[cfg1], T, EPS)
    assert res.S_setup[0] == pytest.approx(0.0, abs=1e-12)  # an addition costs nothing during setup (the old graph is unchanged)
    assert res.b[0] == pytest.approx(E0 - E1)               # NB: E0 - E1 is the benefit (error falls) -> positive
    assert res.b[0] > 0
    assert res.G[0] == pytest.approx((E0 - E1) * (tau - d))


def test_rewire_pays_the_setup_outage_then_collects_the_benefit():
    n, eu, ev, conf, base = setup()
    d, H, k, tau = 2, 3, 10, 30
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, d, H)
    rem = 0                                                  # remove ring link 0 (a non-bridge: the chord keeps the ring connected) ...
    add = base + 1                                           # ... and add a new chord
    res = ge.estimate(conf, np.zeros(len(eu), int), k, scenarios_no_failures(len(eu), k, Hs=d + H), [Mutation(add=add, remove=rem)], tau)
    E0 = spectral_E(n, eu[conf], ev[conf], T, EPS)
    interim = conf.copy(); interim[rem] = False
    final = interim.copy(); final[add] = True
    assert res.S_setup[0] == pytest.approx(d * (E0 - spectral_E(n, eu[interim], ev[interim], T, EPS)))
    assert res.S_setup[0] < 0                                # the setup outage is a cost
    assert res.b[0] == pytest.approx(E0 - spectral_E(n, eu[final], ev[final], T, EPS))
    assert res.G[0] == pytest.approx(res.S_setup[0] + res.b[0] * (tau - d))


def test_decomposition_and_truncation_arithmetic():
    n, eu, ev, conf, base = setup()
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3)
    sc = scenarios_no_failures(len(eu), 10, Hs=5)
    cand = [Mutation(add=base), Mutation(add=base + 1, remove=0)]
    for tau in (40, 3, 1):
        r = ge.estimate(conf, np.zeros(len(eu), int), 10, sc, cand, tau)
        assert np.allclose(r.G_imm + r.G_fut, r.G)
        assert np.allclose(r.G, r.S_setup + r.b * max(0, tau - 2))
    r = ge.estimate(conf, np.zeros(len(eu), int), 10, sc, cand, tau_k=2)           # nothing remains after the setup: only the setup cost
    assert np.allclose(r.G, r.S_setup)


def test_noop_candidate_has_zero_gain_and_identical_graphs_are_cached():
    n, eu, ev, conf, base = setup()
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3)
    r = ge.estimate(conf, np.zeros(len(eu), int), 10, scenarios_no_failures(len(eu), 10, Hs=5), [Mutation()], 30)
    assert r.G[0] == 0.0 and r.se[0] == 0.0


def test_removing_a_bridge_is_strongly_negative_and_failures_change_the_gain():
    n = 10
    eu, ev = ring_edges(n)                                   # ring; remove two links to make a path -> then removing a path link disconnects
    conf = np.ones(len(eu), bool)
    conf[0] = False                                          # path graph 1-2-...-9-0 (a tree): every remaining link is a bridge
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3)
    r = ge.estimate(conf, np.zeros(len(eu), int), 5, scenarios_no_failures(len(eu), 5, Hs=5), [Mutation(remove=4)], 30)
    assert r.G[0] < -1.0                                     # disconnects: error rises to 1 for the rest of the run
    # a failure of the benefiting link in some scenarios lowers the expected gain of a candidate that relies on it
    n2, eu2, ev2, conf2, base = setup()
    cand = [Mutation(add=base)]
    sc0 = scenarios_no_failures(len(eu2), 10, S=4, Hs=5)
    sc1 = scenarios_no_failures(len(eu2), 10, S=4, Hs=5)
    sc1.down[:2, :, base] = True                             # the added link is down in half of the scenarios
    ge2 = GainEstimator(n2, eu2, ev2, T, EPS, 0.0, 2, 3)
    g0 = ge2.estimate(conf2, np.zeros(len(eu2), int), 10, sc0, cand, 30).G[0]
    g1 = ge2.estimate(conf2, np.zeros(len(eu2), int), 10, sc1, cand, 30).G[0]
    assert g1 == pytest.approx(0.5 * g0, rel=1e-9)


def test_common_random_numbers_make_candidate_comparison_paired():
    """With the same scenario set, the gain difference between two candidates has lower variance than independent scenario sets would give."""
    n, eu, ev, conf, base = setup()
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3)
    rng = np.random.default_rng(0)
    P = len(eu)

    def sc():
        d = rng.random((40, 5, P)) < 0.15
        return ScenarioSet(down=d, node_down=np.zeros((40, 5, 1), bool), k=10, thetas=[])
    cands = [Mutation(add=base), Mutation(add=base + 1)]
    paired, indep = [], []
    for _ in range(25):
        s1 = sc(); r = ge.estimate(conf, np.zeros(P, int), 10, s1, cands, 30)
        paired.append(r.G[0] - r.G[1])
        a = ge.estimate(conf, np.zeros(P, int), 10, s1, cands[:1], 30).G[0]
        b = ge.estimate(conf, np.zeros(P, int), 10, sc(), cands[1:], 30).G[0]
        indep.append(a - b)
    assert np.std(paired) < np.std(indep)


def test_exact_and_laplacian_modes_agree_in_sign_on_a_clear_improvement():
    n, eu, ev, conf, base = setup()
    P = len(eu)
    rng = np.random.default_rng(1)
    sc = ScenarioSet(down=rng.random((12, 5, P)) < 0.05, node_down=np.zeros((12, 5, 1), bool), k=10, thetas=[])
    cand = [Mutation(add=base), Mutation(add=base + 2)]
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3, mode="exact").estimate(conf, np.zeros(P, int), 10, sc, cand, 30).G
    gl = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3, mode="laplacian").estimate(conf, np.zeros(P, int), 10, sc, cand, 30).G
    assert (ge > 0).all() and (gl > 0).all()


def test_pending_links_are_not_live_until_ready():
    n, eu, ev, conf, base = setup()
    ge = GainEstimator(n, eu, ev, T, EPS, 0.0, 2, 3)
    ready = np.zeros(len(eu), int)
    conf2 = conf.copy(); conf2[base] = True; ready[base] = 20          # configured but still being set up until epoch 20
    m = ge.live_masks(conf2, ready, 10, np.zeros((5, len(eu)), bool), None)
    assert not m[:, base].any()                                          # not ready during epochs 11..15
    ready[base] = 12
    m = ge.live_masks(conf2, ready, 10, np.zeros((5, len(eu)), bool), None)
    assert (m[:, base] == np.array([False, True, True, True, True])).all()
