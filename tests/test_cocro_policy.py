"""COCRO v2 tests: rollout shadow price (unit, hand-built scenarios) and the policy (integration on small simulations).
Covers budget constraints, act/wait decisions, setup delays, diminishing returns, leakage and deterministic reproducibility."""
import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.core.cocro_ops import Rules, candidate_pairs
from tccer.core.opportunity import RolloutParams, RolloutPricer
from tccer.core.scenarios import ScenarioSet
from tccer.core.value import GainEstimator
from tccer.policies import POLICIES
from tccer.sim.engine import simulate
from test_cocro_value import ring_edges
from test_v08_smoke import BASE


@pytest.fixture(scope="module", autouse=True)
def cocro_registered():
    """Register the COCRO variants only while this module runs: other test modules iterate over every registered policy and would
    otherwise run the (slow) COCRO variants too."""
    import tccer.policies.cocro as cc
    fast = cc.CocroParams.fast()
    for name, kw in (("cocro_t", {}), ("cocro_m_t", dict(price="none")), ("cocro_l0_t", dict(price="zero")),
                     ("cocro_plugin_t", dict(plug_in=True)), ("cocro_nocf_t", dict(cross_fit=False))):
        cc.register_variant(name, base=fast, **kw)
    yield cc
    for name in [n for n in POLICIES if n.startswith("cocro")]:
        POLICIES.pop(name)

T_TOTAL, K0, D = 40, 5, 2
RULES = Rules(d_max=10, degree_basis="configured", failed_link_value="if_up", strict_budget=True)


def world(n=30, chords=((0, 15),), extra=((7, 22), (5, 20), (10, 25), (3, 18), (12, 27), (1, 16)), full_budget=True):
    eu, ev = ring_edges(n, list(chords) + list(extra))
    base = n + len(chords)
    conf = np.zeros(len(eu), bool)
    conf[:base] = True
    return n, eu, ev, np.ones(len(eu)), conf, (int(conf.sum()) if full_budget else int(conf.sum()) + 10), base


def pricer(n, eu, ev, ln, budget, d=D, c_op=0.0, slot=4, T=T_TOTAL):
    ge = GainEstimator(n, eu, ev, 60, 0.01, 0.0, d, 3)
    return RolloutPricer(n, eu, ev, ln, ge, RULES, d, 5, budget, T, RolloutParams(slot=slot, c_op=c_op)), ge


def scen(P, S=3, down=None, k=K0, T=T_TOTAL):
    tau = T - 1 - k
    d = np.zeros((S, tau, P), bool) if down is None else down
    return ScenarioSet(down=d, node_down=np.zeros((S, tau, 1), bool), k=k, thetas=[])


# ------------------------------------------------------------------ setup delay
def test_setup_outage_then_benefit_in_the_rollout_path():
    n, eu, ev, ln, conf, budget, base = world()
    pr, _ = pricer(n, eu, ev, ln, budget)
    sc = scen(len(eu))
    te = set(range(K0 + 1, K0 + 12))
    ready, touched = np.zeros(len(eu), int), np.full(len(eu), -10 ** 9)
    mut = (base + 1, 0)                                          # remove ring link 0 (a non-bridge), add a chord
    conf_a, ready_a, touched_a = pr._apply(conf, ready, touched, mut, K0)
    assert ready_a[base + 1] == K0 + 1 + D                       # the added link is usable only from k + 1 + d
    e_null = pr._path(conf, ready, touched, 0, sc.down[0], K0, te, set(), 0, {}, False)
    e_a = pr._path(conf_a, ready_a, touched_a, 0, sc.down[0], K0, te, set(), 0, {}, False)
    for t in (K0 + 1, K0 + D):
        assert e_a[t] > e_null[t]                                # epochs k+1 .. k+d are the setup: the old link is gone, the new one not yet usable
    assert e_a[K0 + 1 + D] < e_null[K0 + 1 + D]                  # from k+1+d the new link is live: net benefit
    pr0, _ = pricer(n, eu, ev, ln, budget, d=0)
    c0, r0, t0 = pr0._apply(conf, ready, touched, mut, K0)
    assert r0[base + 1] == K0 + 1                                # with d = 0 there is no outage window
    e0 = pr0._path(c0, r0, t0, 0, sc.down[0], K0, te, set(), 0, {}, False)
    assert e0[K0 + 1] < e_a[K0 + 1]


# ------------------------------------------------------------------ budget and the rollout identity
def test_identity_advantage_equals_net_gain_minus_shadow_price():
    n, eu, ev, ln, conf, budget, base = world(full_budget=False)
    pr, _ = pricer(n, eu, ev, ln, budget, c_op=0.05)
    r = pr.price(conf, np.zeros(len(eu), int), np.full(len(eu), -10 ** 9), K0, 2, (base + 2, None), scen(len(eu), S=4))
    assert r.advantage == pytest.approx(r.N - r.Lambda, abs=1e-9)   # N - Lambda = W_act - c_op - W_wait by construction
    assert r.act == (r.advantage > 0)


def test_no_unit_left_after_acting_means_w_act_equals_g_now():
    n, eu, ev, ln, conf, budget, base = world(full_budget=False)
    pr, _ = pricer(n, eu, ev, ln, budget)
    r = pr.price(conf, np.zeros(len(eu), int), np.full(len(eu), -10 ** 9), K0, 1, (base + 2, None), scen(len(eu)))
    assert r.W_act == pytest.approx(r.G_now, abs=1e-9)           # budget: with m = 1 the base policy cannot act again after a*


# ------------------------------------------------------------------ diminishing returns
def test_diminishing_returns_second_improvement_is_worth_less():
    n, eu, ev, ln, conf, budget, base = world(full_budget=False)
    pr, _ = pricer(n, eu, ev, ln, budget)
    add1, add2 = base + 1, base + 2
    ready, touched = np.zeros(len(eu), int), np.full(len(eu), -10 ** 9)
    r1 = pr.price(conf, ready, touched, K0, 1, (add1, None), scen(len(eu)))
    richer = conf.copy(); richer[[base + 3, base + 4, base + 5]] = True                  # the same network with three more chords
    r2 = pr.price(richer, ready, touched, K0, 1, (add1, None), scen(len(eu)))
    assert r1.G_now > r2.G_now >= 0                              # the same link is worth less on an already-improved graph (concave lambda2)
    assert r1.G_now > 0


# ------------------------------------------------------------------ act / wait
def test_act_when_persistent_damage_makes_the_rewire_valuable():
    # a plain ring whose links (3,4) and (10,11) fail for the rest of the run: two arcs, disconnected; the chord (5,20) joins them
    n, eu, ev, ln, conf, budget, base = world(chords=(), extra=((5, 20), (7, 22)))
    P = len(eu)
    down = np.zeros((3, T_TOTAL - 1 - K0, P), bool)
    down[:, :, [3, 10]] = True
    pr, _ = pricer(n, eu, ev, ln, budget)
    r = pr.price(conf, np.zeros(P, int), np.full(P, -10 ** 9), K0, 1, (base, 3), scen(P, down=down))   # release failed link 3, add the chord (5,20)
    assert r.act and r.advantage > 0 and r.G_now > 5            # reconnecting a split network is worth many error-epochs
    pairs = candidate_pairs(n, eu, ev, ln, conf, conf & ~down[0, 0], down[0, 0], np.zeros(P, bool), budget, RULES, 2, 3)
    assert pairs and pairs[0][0] == base and all(r_ in (3, 10) for _, r_ in pairs)   # the generator proposes the reconnecting chord and only failed removals


def test_wait_when_the_network_is_already_strong_or_the_price_exceeds_the_gain():
    n, eu, ev, ln, conf, budget, base = world()
    strong = conf.copy(); strong[base:] = True                  # ring plus every chord: error is on the floor, nothing to gain
    pr, _ = pricer(n, eu, ev, ln, strong.sum() + 5)
    P = len(eu)
    r = pr.price(strong, np.zeros(P, int), np.full(P, -10 ** 9), K0, 2, (None, 0), scen(P))
    assert not r.act                                            # removing a link from a saturated graph cannot help
    pr2, _ = pricer(n, eu, ev, ln, budget, c_op=50.0)           # an absurd operational price: acting is never worth it
    r2 = pr2.price(conf, np.zeros(P, int), np.full(P, -10 ** 9), K0, 2, (base + 1, 0), scen(P))
    assert not r2.act and r2.N < 0


def test_candidates_respect_budget_tabu_and_degree_rules():
    n, eu, ev, ln, conf, budget, base = world()
    P = len(eu)
    live = conf.copy(); down = np.zeros(P, bool); tabu = np.zeros(P, bool)
    pairs = candidate_pairs(n, eu, ev, ln, conf, live, down, tabu, budget, RULES, 3, 4)
    assert pairs and all(r is not None for _, r in pairs)        # budget is full: only rewires (a removal accompanies every addition)
    assert all(not conf[a] and conf[r] for a, r in pairs)       # adds are unconfigured links, removals configured ones
    tabu[:] = True                                               # every link just touched: nothing may be proposed
    assert candidate_pairs(n, eu, ev, ln, conf, live, down, tabu, budget, RULES, 3, 4) == []
    pairs_nb = candidate_pairs(n, eu, ev, ln, conf, live, down, np.zeros(P, bool), budget + 5, RULES, 3, 4)
    assert pairs_nb and all(r is None for _, r in pairs_nb)      # budget not full: additions only


# ------------------------------------------------------------------ integration on small simulations
CFG = replace(BASE, epochs=36, mutation_cap=3)


def rows(cfg, seed, policy, **kw):
    return pd.DataFrame(simulate(cfg, seed, policy, log_rounds=False, **kw)[0])


def test_registered_variants_run_and_respect_the_cap_and_edge_budget():
    for pol in ("cocro_t", "cocro_m_t", "cocro_l0_t", "cocro_plugin_t", "cocro_nocf_t"):
        assert pol in POLICIES
        r = rows(CFG, 8501, pol)
        assert r.n_mutations.iloc[-1] <= CFG.mutation_cap
        assert (r.configured_edges <= r.budget).all()            # strict edge budget
        assert set(r.mutation_kind.dropna().unique()) <= {"", "rewire", "add"}
        mut = r[r.mutation != ""]
        assert (mut.select_outcome == "mutated").all()           # the logged outcome matches the applied action
        if len(mut) > 1:
            assert (np.diff(mut.epoch.to_numpy()) >= 2).all()    # cooldown of 2 epochs between mutations


def test_mutations_obey_setup_delay_tabu_and_the_gate_in_the_engine():
    seen, live_after = [], {}

    def on_epoch(k, state, m):
        live_after[k] = state.live_mask().copy()
        if m is not None:
            seen.append((k, m, state.ready_at.copy()))
    simulate(CFG, 8502, "cocro_m_t", log_rounds=False, on_epoch=on_epoch)
    assert len(seen) == CFG.mutation_cap                         # COCRO-M spends the whole budget
    d = CFG.link_setup_epochs
    last = {}
    for k, m, ready in seen:
        assert ready[m.add] == k + 1 + d                         # setup delay
        assert not live_after[k + 1][m.add] if k + 1 in live_after and d >= 1 else True
        for e in (m.add, m.remove):
            if e is not None:
                assert k - last.get(e, -10 ** 9) >= CFG.edge_cooldown      # the edge tabu is respected
                last[e] = k
    assert [k for k, _, _ in seen] == sorted(k for k, _, _ in seen)
    assert seen[0][0] == 0 and np.all(np.diff([k for k, _, _ in seen]) == 2)   # COCRO-M: A7-like timing 0, 2, 4


def test_deterministic_reproducibility_same_seed_identical_runs():
    a, b = rows(CFG, 8503, "cocro_t"), rows(CFG, 8503, "cocro_t")
    pd.testing.assert_frame_equal(a, b)                          # includes every logged diagnostic
    c = rows(CFG, 8504, "cocro_t")
    assert not a.E_hat.equals(c.E_hat)


def test_decisions_do_not_use_the_future_environment_trace():
    """Two environments identical until epoch 20 (a shock at 20 vs at 26): every decision before epoch 20 must be identical."""
    a = rows(replace(CFG, epochs=30, shock_epoch=20, shock_len=6), 8505, "cocro_t")
    b = rows(replace(CFG, epochs=30, shock_epoch=26, shock_len=6), 8505, "cocro_t")
    early = lambda df: df[df.epoch < 20][["epoch", "mutation", "cocro_decision", "cocro_G", "cocro_N", "cocro_Lambda", "cocro_adv"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(early(a), early(b))
    assert a[a.epoch < 20].E_hat.equals(b[b.epoch < 20].E_hat)   # sanity: the observed past really was identical


def test_importing_cocro_does_not_change_existing_policies():
    r1 = rows(CFG, 8506, "v06_front")
    r2 = rows(CFG, 8506, "v06_front")
    pd.testing.assert_frame_equal(r1, r2)
    assert {"v08_rcpr", "v06_front", "r2_causal"} <= set(POLICIES)


def test_costly_reconfiguration_makes_cocro_act_less(cocro_registered):
    cheap = rows(CFG, 8507, "cocro_t")
    cocro_registered.register_variant("cocro_t_costly", base=cocro_registered.CocroParams.fast(), c_op=5.0)
    dear = rows(CFG, 8507, "cocro_t_costly")
    assert dear.n_mutations.iloc[-1] <= cheap.n_mutations.iloc[-1]


@pytest.mark.parametrize("pol", ["cocro_t", "cocro_m_t", "cocro_l0_t", "cocro_plugin_t", "cocro_nocf_t"])
def test_decisions_near_the_end_of_the_run_do_not_fail(pol):
    """Regression: when fewer than d + H epochs remain the scenario sets must still cover the selection window (found by the all-policies tests)."""
    cfg = replace(CFG, epochs=14, mutation_cap=8)
    r = rows(cfg, 8508, pol)
    assert len(r) == 14 and r.n_mutations.iloc[-1] <= 8
    assert (r[r.epoch >= 14 - 1 - cfg.link_setup_epochs].mutation == "").all()       # no action once no benefit epoch remains after the setup
