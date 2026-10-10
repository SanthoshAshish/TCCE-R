"""v0.7 direct mathematical tests: parameter validation, volatility, candidate ranking / tie-breaking, and the
first-order lambda2 estimate against exact eigenvalues (Ghosh & Boyd 2006, CDC, eqs. 8 and 10, p. 6608)."""
import os
import warnings

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from tccer.config import Config, load_config, replace
from tccer.core.coupling import rank_lexicographic, score_candidates
from tccer.core.debt import volatility
from tccer.core.mutations import Mutation
from tccer.metrics.resilience import lambda2, lambda2_fiedler, laplacian, n_bridges
from tccer.network.generators import random_geometric
from tccer.network.state import NetworkState
from tccer.sim.engine import simulate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ parameter validation
@pytest.mark.parametrize("bad", [dict(eps=0.0), dict(eps=1.0), dict(eps=1.5), dict(w_E=-0.1), dict(w_C=-1),
                                 dict(w_V=-0.01), dict(kappa=-0.1), dict(feedback_horizon=0), dict(vol_window=0),
                                 dict(theta0=0.1), dict(theta0=5.0), dict(theta_min=0.0, theta0=0.5),
                                 dict(alpha=-0.1), dict(beta=1.0), dict(epochs=0), dict(rounds_per_epoch=0)])
def test_invalid_parameters_are_rejected(bad):
    with pytest.raises(ValueError, match="Invalid configuration"):
        replace(Config(), **bad)


def test_boundary_values_are_valid():
    replace(Config(), theta0=0.25, theta_min=0.25, theta_max=0.25, w_E=0, w_C=0, w_V=0, kappa=0,
            feedback_horizon=1, vol_window=1, beta=0.0, alpha=0.0)


# ------------------------------------------------------------------ volatility
def test_volatility_formula():
    assert volatility([0, 0, 0], 10, 3) == 0.0
    assert volatility([5, 1, 2, 3], 20, 3) == pytest.approx((1 + 2 + 3) / 20)   # only the last w epochs
    assert volatility([1], 20, 3) == pytest.approx(1 / 20)                      # shorter history than w
    assert volatility([30, 40], 10, 3) == 1.0                                   # clipped at 1
    assert volatility([2], 0, 3) == 2.0 / 1 or volatility([2], 0, 3) == 1.0     # guard: no division by zero


def test_volatility_in_engine_counts_environmental_flips_of_configured_links():
    """custom_4node: links 0-1 and 2-3 fail at epoch 5; 2-3 recovers at epoch 10 (0-1 was released by the
    mutation at epoch 6, so its recovery is not a configured flip). Window 3, 4 configured links."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        cfg = load_config(os.path.join(ROOT, "configs", "v0.5", "custom_4node.yaml"))
    df = pd.DataFrame(simulate(cfg, 0, "tccer", log_rounds=False)[0]).set_index("epoch")
    assert df.V[4] == 0.0
    assert df.V[5] == pytest.approx(2 / 4) and df.V[7] == pytest.approx(2 / 4)   # flips at 5 inside window 5..7
    assert df.V[8] == 0.0                                                         # window 6..8: no flips
    assert df.V[10] == pytest.approx(1 / 4)                                       # only the configured 2-3 recovers
    assert df.V[13] == 0.0
    static = pd.DataFrame(simulate(cfg, 0, "static", log_rounds=False)[0]).set_index("epoch")
    assert static.V[10] == pytest.approx(2 / 4)                                   # both recover when kept configured


# ------------------------------------------------------------------ candidate ranking and tie-breaking
def path_state():
    """Path 0-1-2-3-4 at unit spacing; candidates (0,2),(1,3),(2,4),(0,3),(0,4)."""
    pos = np.array([[float(i), 0.0] for i in range(5)])
    pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 2), (1, 3), (2, 4), (0, 3), (0, 4)]
    eu, ev = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
    length = np.linalg.norm(pos[eu] - pos[ev], axis=1)
    return NetworkState(pos, eu, ev, length, np.arange(4)), pairs


def test_ranking_matches_independent_specification():
    s, pairs = path_state()
    live = s.live_mask()
    _, f = lambda2_fiedler(s.n, s.eu[live], s.ev[live])
    cands = [Mutation(add=s.index[p]) for p in [(0, 2), (1, 3), (2, 4), (0, 3), (0, 4)]]
    ranked = rank_lexicographic(s, score_candidates(s, cands, f, True), shortlist=10, tol=0.1)
    # independent restatement of the rule
    rows = []
    for m in cands:
        i, j = s.edge(m.add)
        g = nx.path_graph(5)
        g.add_edge(i, j)
        rows.append(dict(m=m, gain=(f[i] - f[j]) ** 2, length=abs(i - j), dbr=n_bridges(g) - 4))
    best = max(r["gain"] for r in rows)
    tied = sorted([r for r in rows if r["gain"] >= best - 0.1 * best], key=lambda r: (r["dbr"], r["length"]))
    rest = sorted([r for r in rows if r["gain"] < best - 0.1 * best], key=lambda r: (-r["gain"], r["length"]))
    assert [x.mutation for x in ranked] == [r["m"] for r in tied + rest]
    assert ranked[0].mutation == Mutation(add=s.index[(0, 4)])     # largest Fiedler gap and 0 bridges remain


def test_reconnection_ranked_first_and_tie_breaks_by_bridges_then_length():
    s, _ = path_state()
    s.down[s.index[(2, 3)]] = True                                   # components {0,1,2} and {3,4}
    cands = [Mutation(add=s.index[p]) for p in [(0, 2), (1, 3), (2, 4), (0, 3), (0, 4)]]
    sc = score_candidates(s, cands, None, False)
    assert {x.mutation: x.d_comp for x in sc}[Mutation(add=s.index[(0, 2)])] == 0
    ranked = rank_lexicographic(s, sc, shortlist=10, tol=0.1)
    reconnecting = [x for x in ranked if x.d_comp == -1]
    assert ranked[:len(reconnecting)] == reconnecting                # all reconnecting moves come first
    keys = [(x.d_bridges, x.length) for x in reconnecting]
    assert keys == sorted(keys)                                      # then by (d_bridges, length)
    assert all(x.gain == 0.0 for x in sc)                            # no consensus term while disconnected


def test_shortlist_boundary_keeps_tail_order():
    s, _ = path_state()
    live = s.live_mask()
    _, f = lambda2_fiedler(s.n, s.eu[live], s.ev[live])
    cands = [Mutation(add=s.index[p]) for p in [(0, 2), (1, 3), (2, 4), (0, 3), (0, 4)]]
    ranked = rank_lexicographic(s, score_candidates(s, cands, f, True), shortlist=2, tol=0.0)
    tail = ranked[2:]
    assert [(x.d_comp, -x.gain, x.length) for x in tail] == sorted((x.d_comp, -x.gain, x.length) for x in tail)


# ------------------------------------------------------------------ first-order lambda2 estimate vs exact
def test_first_order_estimate_respects_ghosh_boyd_bounds():
    checked = 0
    for seed in range(8):
        pos, eu, ev, length, init = random_geometric(30, 0.28, 0.4, seed)
        u, v = eu[init], ev[init]
        vals, vecs = np.linalg.eigh(laplacian(30, u, v))
        l2, l3, f = vals[1], vals[2], vecs[:, 1]
        if l3 - l2 < 1e-9:
            continue                                                  # bounds need an isolated lambda2
        for i, j in zip(eu[~np.isin(np.arange(len(eu)), init)], ev[~np.isin(np.arange(len(eu)), init)]):
            est = (f[i] - f[j]) ** 2
            exact = lambda2(30, np.r_[u, i], np.r_[v, j]) - l2
            assert exact <= est + 1e-9                                # eq. (10): upper bound
            assert exact >= est / (6 / (l3 - l2) + 1.5) - 1e-9        # eq. (8): lower bound
            checked += 1
    assert checked > 100


def test_first_order_estimate_ranks_candidates_sensibly():
    pos, eu, ev, length, init = random_geometric(30, 0.28, 0.4, 3)
    u, v = eu[init], ev[init]
    _, f = lambda2_fiedler(30, u, v)
    l2 = lambda2(30, u, v)
    cand = np.flatnonzero(~np.isin(np.arange(len(eu)), init))
    est = np.array([(f[eu[c]] - f[ev[c]]) ** 2 for c in cand])
    exact = np.array([lambda2(30, np.r_[u, eu[c]], np.r_[v, ev[c]]) - l2 for c in cand])
    from scipy.stats import spearmanr
    assert spearmanr(est, exact).correlation > 0.8
    # The first-order pick is NOT guaranteed to be the exact best (measured on 40 dev graphs: median 99.3% of the
    # best exact gain, minimum 42.5%). What is guaranteed (eq. 8) is a positive lower bound on its exact gain:
    vals = np.linalg.eigvalsh(laplacian(30, u, v))
    assert exact[np.argmax(est)] >= est.max() / (6 / (vals[2] - vals[1]) + 1.5) - 1e-12
