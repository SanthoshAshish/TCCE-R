"""COCRO v2 toy study tests (no simulator): exact DP vs expectimax, rollout vs exact, the i.i.d. method's over-deferral under correlated
opportunities, diminishing returns, and constructed act-versus-wait cases. The qualitative expectations were declared in
tccer/toy/shadow_price.py before the study was run."""
import numpy as np
import pytest

from tccer.toy.shadow_price import (ToyConfig, evaluate_policy, expectimax, policies, rollout_price_table, simulate_paths, solve_exact,
                                    solve_iid, solve_old)

TINY = [ToyConfig(T=6, M=2, rho=0.7, delta=0.7, b=(0.0, 0.1, 0.4), pi=(0.5, 0.3, 0.2)),
        ToyConfig(T=7, M=2, rho=0.0, delta=1.0, b=(0.0, 0.2), pi=(0.6, 0.4)),
        ToyConfig(T=6, M=3, rho=0.95, delta=0.5, b=(0.05, 0.3), pi=(0.7, 0.3))]


@pytest.mark.parametrize("cfg", TINY)
def test_vectorised_dp_equals_expectimax_tree(cfg):
    V, _ = solve_exact(cfg)
    for m in range(cfg.M + 1):
        for z in range(cfg.Z):
            for cd in (0, 1):
                assert abs(V[0, m, z, cd] - expectimax(cfg, 0, m, z, cd)) < 1e-9


def test_transition_matrix_is_stochastic_with_stationary_pi():
    cfg = ToyConfig(rho=0.9)
    P, pi = cfg.P(), np.array(cfg.pi)
    assert np.allclose(P.sum(axis=1), 1) and np.allclose(pi @ P, pi) and np.isclose(pi.sum(), 1)


def test_iid_method_is_exact_when_opportunities_are_uncorrelated():
    cfg = ToyConfig(rho=0.0, M=3, delta=0.7)
    _, lam = solve_exact(cfg)
    _, lam_iid = solve_iid(cfg)
    for t in range(cfg.T - cfg.d - 1):
        for m in range(1, cfg.M + 1):
            for z in range(cfg.Z):
                assert abs(lam[t, m, z] - lam_iid[t, m]) < 1e-9


def test_correlated_opportunities_make_the_iid_method_over_defer():
    cfg = ToyConfig(rho=0.97, M=2, delta=1.0)
    pol, _ = policies(cfg, S=600)
    paths = simulate_paths(cfg, N=2000, seed=5)
    ex = evaluate_policy(cfg, paths, pol["EXACT"])
    iid = evaluate_policy(cfg, paths, pol["IID"])
    assert iid[2] > ex[2] + 0.10                  # waits at many more positive-reward visits than the optimal policy
    assert iid[0].mean() < ex[0].mean() - 0.1     # and loses value


def test_exact_price_falls_with_correlation_when_waiting_is_worth_less():
    """If damage persists, a fresh high-value draw is less likely than under independence, so the price of a unit at a low-value state falls."""
    z_low, t, m = 1, 5, 1
    p = {rho: solve_exact(ToyConfig(rho=rho, M=2))[1][t, m, z_low] for rho in (0.0, 0.9)}
    assert p[0.9] < p[0.0]


def test_diminishing_returns_reward_and_value_structure():
    cfg = ToyConfig(M=3, delta=0.7, rho=0.5)
    r = [float(cfg.reward(3, 4, u)) for u in range(3)]
    assert r[0] > r[1] > r[2]                                       # later units earn less
    pi = np.array(cfg.pi)
    # value of a budget of k units *from scratch* needs a separate problem per k (u = M - m inside one problem mixes budget and usage)
    v = [0.0] + [float(solve_exact(ToyConfig(M=k, delta=0.7, rho=0.5))[0][0, k, :, 0] @ pi) for k in (1, 2, 3)]
    inc = np.diff(v)
    assert (inc > 0).all() and (np.diff(inc) < 1e-12).all()        # increasing and concave in the budget
    v1 = float(solve_exact(ToyConfig(M=3, delta=1.0, rho=0.5))[0][0, 3, :, 0] @ pi)
    assert v[3] < v1                                                # diminishing returns lower the value of the budget


def test_old_method_ignores_diminishing_returns_and_loses_value():
    cfg = ToyConfig(M=3, delta=0.5, rho=0.5)
    pol, _ = policies(cfg, S=400)
    paths = simulate_paths(cfg, N=2000, seed=11)
    opt = evaluate_policy(cfg, paths, pol["EXACT"])[0].mean()
    old = evaluate_policy(cfg, paths, pol["OLD"])[0].mean()
    assert old < opt


def _two_state(P01, T=30, M=1, b=(0.01, 0.20)):
    """A tiny instance: state 0 weak, state 1 strong; rho is implemented through pi: from either state jump to pi with prob (1 - rho)."""
    return ToyConfig(T=T, M=M, rho=0.0, delta=1.0, b=b, pi=(1 - P01, P01))


def test_constructed_case_wait_is_strictly_better_when_a_large_event_is_likely():
    cfg = _two_state(P01=0.5)                                         # half the slots are strong: waiting for one is cheap
    _, lam = solve_exact(cfg)
    R0 = float(cfg.reward(0, 0, 0))
    assert R0 < lam[0, 1, 0]                                          # exact: wait at the weak state
    R1 = float(cfg.reward(0, 1, 0))
    assert R1 >= lam[0, 1, 1]                                         # exact: act at the strong state
    roll = rollout_price_table(cfg, S=1500, seed=3)
    assert R0 < roll[0, 1, 0] and R1 >= roll[0, 1, 1]                # rollout makes the same two decisions


def test_constructed_case_act_now_when_no_better_event_will_come():
    cfg = _two_state(P01=0.0, b=(0.05, 0.05))                         # nothing better ever arrives; benefit grows with remaining time
    _, lam = solve_exact(cfg)
    R = float(cfg.reward(0, 0, 0))
    assert R > 0 and R >= lam[0, 1, 0]                                # act now
    assert lam[0, 1, 0] < R
    roll = rollout_price_table(cfg, S=800, seed=3)
    assert R >= roll[0, 1, 0]


def test_late_event_less_valuable_than_early_one_flow_rewards():
    """Persistent-flow reward shrinks with remaining time, so the price of waiting rises with t only through the lost flow: the exact
    act threshold on the benefit rate b rises with t (it takes a larger rate to justify acting late)."""
    cfg = ToyConfig(M=1, rho=0.9)
    thr = []
    for t in (2, 20, 35):
        need = (cfg.s * cfg.d + cfg.c_op) / (cfg.T - t - cfg.d)       # smallest b with R > 0 at slot t
        thr.append(need)
    assert thr[0] < thr[1] < thr[2]


def test_rollout_policy_improves_on_its_base_policy_and_tracks_exact():
    cfg = ToyConfig(rho=0.9, M=2, delta=0.7)
    pol, tab = policies(cfg, S=800)
    paths = simulate_paths(cfg, N=2500, seed=21)
    g = evaluate_policy(cfg, paths, pol["GREEDY"])[0]
    r = evaluate_policy(cfg, paths, pol["ROLLOUT"])[0]
    diff = r - g
    assert diff.mean() >= -2 * diff.std(ddof=1) / np.sqrt(len(diff))   # policy improvement up to Monte-Carlo error
    e = evaluate_policy(cfg, paths, pol["EXACT"])[0]
    assert r.mean() >= 0.95 * e.mean()
    # decision agreement on non-marginal states
    agree = tot = 0
    for t in range(cfg.T - cfg.d - 1):
        for m in range(1, cfg.M + 1):
            for z in range(cfg.Z):
                R, ex, ro = float(cfg.reward(t, z, cfg.M - m)), tab["exact"][t, m, z], tab["roll"][t, m, z]
                if abs(R - ex) > 0.05 * max(1.0, abs(ex)):
                    tot += 1
                    agree += (R >= ex) == (R >= ro)
    assert agree / tot >= 0.90


def test_base_policy_greedy_and_front_are_dominated_by_exact():
    cfg = ToyConfig(rho=0.5, M=3, delta=0.7)
    pol, _ = policies(cfg, S=300)
    paths = simulate_paths(cfg, N=1500, seed=2)
    vals = {k: evaluate_policy(cfg, paths, f)[0].mean() for k, f in pol.items()}
    assert vals["EXACT"] >= max(vals.values()) - 1e-9
