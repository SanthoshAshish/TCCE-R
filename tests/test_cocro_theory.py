"""Numerical checks of the propositions in docs/COCRO_THEORY.md against the implementation (each test names its proposition)."""
import networkx as nx
import numpy as np
import pytest

from tccer.config import replace
from tccer.consensus.algorithm import metropolis_matrix, run_epoch_state
from tccer.core.causal_debt import CausalDebtLedger
from tccer.core.cocro_ops import Rules, candidate_pairs
from tccer.core.mutations import Mutation
from tccer.core.safety import SafetyGate
from tccer.core.scenarios import ScenarioSet
from tccer.core.value import GainEstimator
from tccer.network.generators import make_network
from tccer.network.state import NetworkState
from tccer.policies import POLICIES
from tccer.sim.engine import simulate
from test_cocro_policy import world
from test_r2_causal_debt import make_state
from test_v08_smoke import BASE


def ring_chords(n, chords):
    e = [tuple(sorted((i, (i + 1) % n))) for i in range(n)] + [tuple(sorted(c)) for c in chords]
    return np.array([a for a, b in e]), np.array([b for a, b in e])


# ------------------------------------------------------------------ Proposition 3
def test_prop3_i_exact_mean_square_identity_and_disconnected_lower_bound():
    n, T = 12, 7
    eu, ev = ring_chords(n, [(0, 6), (3, 9)])
    W = metropolis_matrix(n, eu, ev)
    J = np.ones((n, n)) / n
    lam = np.sort(np.linalg.eigvalsh(W))[::-1]
    exact = np.trace(np.linalg.matrix_power(W, 2 * T) @ (np.eye(n) - J))                 # E||W^T c||^2 / sigma^2 (trace formula)
    assert exact == pytest.approx(np.sum(lam[1:] ** (2 * T)), rel=1e-9, abs=1e-12)
    rng = np.random.default_rng(0)
    x0 = rng.normal(size=(40000, n))
    c0 = x0 - x0.mean(axis=1, keepdims=True)
    xT = (np.linalg.matrix_power(W, T) @ x0.T).T
    mc = ((xT - xT.mean(axis=1, keepdims=True)) ** 2).sum() / (c0 ** 2).sum()
    assert mc == pytest.approx(np.sum(lam[1:] ** (2 * T)) / (n - 1), rel=0.03)
    assert np.sum(lam[1:] ** (2 * T)) / (n - 1) <= np.max(np.abs(lam[1:])) ** (2 * T) + 1e-12   # <= rho^(2T)
    # two components: the ratio cannot go below (c - 1)/(n - 1)
    h = n // 2
    eu2 = np.r_[np.arange(h - 1), np.arange(h, n - 1)]
    ev2 = eu2 + 1
    W2 = metropolis_matrix(n, eu2, ev2)
    lam2 = np.sort(np.linalg.eigvalsh(W2))[::-1]
    assert np.sum(lam2[1:] ** (2 * 200)) / (n - 1) >= 1.0 / (n - 1) - 1e-9


def test_prop3_ii_randomized_gossip_bound_holds_in_the_simulator():
    n, T, p_tr = 16, 10, 0.2
    eu, ev = ring_chords(n, [(0, 8), (4, 12), (2, 10)])
    rng = np.random.default_rng(1)
    EW2 = np.zeros((n, n))
    N = 20000
    for _ in range(N):                                                               # E[W_t^2] by Monte Carlo over the round's surviving links
        m = rng.random(len(eu)) >= p_tr
        W = metropolis_matrix(n, eu[m], ev[m])
        EW2 += W @ W
    EW2 /= N
    lam2 = np.sort(np.linalg.eigvalsh(EW2))[-2]
    bound = lam2 ** T
    x0 = rng.random(n)
    c0 = np.sum((x0 - x0.mean()) ** 2)
    sq = []
    for s in range(3000):
        r = np.random.default_rng(100 + s)
        err, x = run_epoch_state(x0, eu, ev, lambda t, r=r: r.random(len(eu)) >= p_tr, T)
        sq.append(np.sum((x - x0.mean()) ** 2) / c0)
    emp = float(np.mean(sq))
    assert 0 < emp <= bound * 1.05 and bound < 1                                     # empirical mean-square ratio under the theoretical bound (MC tolerance 5%)


# ------------------------------------------------------------------ Propositions 1 and 2
def components(state, mask):
    return nx.number_connected_components(state.graph(mask))


def test_prop2_accepted_mutations_never_increase_components():
    cfg = BASE
    accepted = rejected = 0
    rules = Rules(d_max=cfg.d_max, degree_basis=cfg.degree_basis, failed_link_value=cfg.failed_link_value, strict_budget=True)
    for seed in range(30):
        pos, eu, ev, length, init = make_network(cfg, seed)
        st = NetworkState(pos, eu, ev, length, init)
        st.epoch = 10
        rng = np.random.default_rng(seed)
        st.down = rng.random(st.P) < 0.15
        budget = len(init)
        gate = SafetyGate(cfg, budget)
        live = st.live_mask()
        before = components(st, live)
        lam_before = None
        pairs = candidate_pairs(st.n, eu, ev, length, st.configured, live, st.down, np.zeros(st.P, bool), budget, rules, 3, 6)
        for a, r in pairs:
            m = Mutation(add=a, remove=r)
            ok, _ = gate.check(st, m, np.zeros(st.P, bool))
            if not ok:
                rejected += 1
                continue
            accepted += 1
            assert components(st, st.mask_after(m)) <= before                        # final graph
            assert components(st, st.mask_after(m, interim=True)) <= before          # break-before-make interim graph
    assert accepted >= 50                                                            # the property was exercised on many accepted candidates
    # non-vacuity: a mutation that disconnects the graph (removes the only remaining link of a path) is rejected by the gate
    pos, eu, ev, length, init = make_network(cfg, 0)
    st = NetworkState(pos, eu, ev, length, init)
    st.epoch = 10
    st.down = np.zeros(st.P, bool)
    g = SafetyGate(cfg, len(init))
    G = st.graph(st.live_mask())
    bridges = list(nx.bridges(G))
    if not bridges:                                                                  # make one: drop every live link of a degree-2 node but one
        v = min(G.nodes, key=G.degree)
        keep = next(iter(G[v]))
        for u in list(G[v]):
            if u != keep:
                st.down[[i for i in range(st.P) if {int(st.eu[i]), int(st.ev[i])} == {v, u}]] = True
        bridges = list(nx.bridges(st.graph(st.live_mask())))
    assert bridges, "could not construct a bridge"
    a, b = bridges[0]
    idx = [i for i in range(st.P) if {int(st.eu[i]), int(st.ev[i])} == {a, b}][0]
    ok, _ = g.check(st, Mutation(remove=idx), np.zeros(st.P, bool))
    assert not ok


@pytest.fixture(scope="module")
def theory_variant():
    import tccer.policies.cocro as cc
    cc.register_variant("cocro_m_th_t", base=cc.CocroParams.fast(), price="none")
    yield "cocro_m_th_t"
    POLICIES.pop("cocro_m_th_t", None)


@pytest.mark.parametrize("seed", [8541, 8542, 8543, 8544])
def test_prop1_feasibility_invariants_over_runs(theory_variant, seed):
    cfg = replace(BASE, epochs=30, mutation_cap=4)
    log = []

    def on_epoch(k, state, m):
        if m is not None:
            log.append((k, m, int(state.configured.sum())))
    rows = simulate(cfg, seed, theory_variant, log_rounds=False, on_epoch=on_epoch)[0]
    budget = rows[0]["budget"]
    assert len(log) <= 4                                                              # (a) cap
    ks = [k for k, _, _ in log]
    assert all(b - a >= 2 for a, b in zip(ks, ks[1:]))                                # (b) one per epoch, cooldown >= 2
    assert all(c <= budget for _, _, c in log) and all(r["configured_edges"] <= budget for r in rows)   # (c) strict budget
    last = {}
    for k, m, _ in log:                                                               # (d) edge tabu
        for e in (m.add, m.remove):
            if e is not None:
                assert k - last.get(e, -10 ** 9) >= cfg.edge_cooldown
                last[e] = k


# ------------------------------------------------------------------ Proposition 4
def test_prop4_selection_error_obeys_the_hoeffding_bound_and_falls_with_scenarios():
    n, eu, ev, ln, conf, budget, base = world(chords=(), extra=((4, 11), (0, 15), (7, 22), (2, 17)), full_budget=False)
    P = len(eu)
    rng = np.random.default_rng(3)
    pool, Hs, d, H, tau = 400, 5, 2, 3, 30
    sc = ScenarioSet(down=rng.random((pool, Hs, P)) < 0.12, node_down=np.zeros((pool, Hs, 1), bool), k=5, thetas=[])
    ge = GainEstimator(n, eu, ev, 60, 0.01, 0.0, d, H)
    cands = [Mutation(add=base + i) for i in range(4)]
    Gs = ge.estimate(conf, np.zeros(P, int), 5, sc, cands, tau).G_s                   # (pool, K) per-scenario gains
    g = Gs.mean(axis=0)
    star = int(np.argmax(g))
    others = [a for a in range(4) if a != star]
    delta = np.array([g[star] - g[a] for a in others])
    assert (delta > 1e-6).all()                                                       # unique maximiser in this world
    R = max(np.abs(Gs[:, star] - Gs[:, a]).max() for a in others)
    errs = {}
    for S in (2, 8, 32):
        wrong = 0
        for t in range(1500):
            idx = rng.integers(0, pool, S)
            wrong += int(np.argmax(Gs[idx].mean(axis=0)) != star)
        errs[S] = wrong / 1500
        bound = min(1.0, float(np.sum(np.exp(-S * delta ** 2 / (2 * R ** 2)))))
        assert errs[S] <= bound + 0.03                                               # empirical error under the Hoeffding bound
    assert errs[2] >= errs[8] - 0.02 >= errs[32] - 0.04 and errs[32] < errs[2]       # more scenarios, fewer wrong selections


# ------------------------------------------------------------------ Proposition 7 (C1 ledger)
def test_prop7_ledger_is_bounded_under_recoverable_disturbances():
    L_max, W_win = 6, 8
    cfg = replace(BASE, cd_tau=2, cd_w_prop=1.5, cd_lam_E=1.0, cd_scar=0.25, cd_gamma=0.8, cd_e_ok=0.3)
    a = cfg.cd_w_prop * (1 + cfg.cd_lam_E)
    delta = cfg.cd_scar * a * L_max
    bound = a * L_max + delta * (1 + cfg.cd_gamma * (W_win - 1)) / (1 - cfg.cd_gamma)
    worst, recovered = 0.0, 0
    for trial in range(25):
        rng = np.random.default_rng(trial)
        st = make_state()
        P = len(st.eu)
        led = CausalDebtLedger(cfg, st.n, st.eu, st.ev)
        remaining = np.zeros(P, int)
        for k in range(300):
            start = (remaining == 0) & (rng.random(P) < 0.12)
            remaining = np.where(start, rng.integers(1, L_max + 1, P), np.maximum(remaining - 1, 0)) if k else remaining
            st.down = remaining > 0
            E = cfg.cd_e_ok * 0.5 if k % W_win == 0 else float(rng.random())          # a recovery epoch in every window of W_win epochs
            worst = max(worst, led.update(st, E))
        recovered += led.n_recovered
    assert recovered > 20 and worst > 0.1                                             # the persistent-settlement path (the scar) was exercised
    assert worst <= bound + 1e-9
