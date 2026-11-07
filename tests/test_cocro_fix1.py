"""COCRO Fix 1 tests: full-horizon candidate gain, shortlist reranking (variant cocro_fg), and preservation of the existing COCRO behaviour.
Fix 1 replaces, for candidate SELECTION and the no-gain gate only, the extrapolated gain G = S_setup + b (tau - d) (assumption A8: the benefit rate of the
first H epochs after the link is ready persists to the end) by the simulated full-horizon gain on the selection scenarios, for a shortlist."""
import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.core.mutations import Mutation
from tccer.core.scenarios import ScenarioSampler, ScenarioSet, controller_rng
from tccer.policies import POLICIES
from tccer.policies.cocro import select_candidate
from tccer.sim.engine import simulate
from test_cocro_policy import D, K0, T_TOTAL, pricer, world
from test_cocro_scenarios import fitted
from test_v08_smoke import BASE

CFG = replace(BASE, epochs=36, mutation_cap=3)
TAU = T_TOTAL - 1 - K0


@pytest.fixture(scope="module", autouse=True)
def fg_registered():
    import tccer.policies.cocro as cc
    fast = cc.CocroParams.fast()
    for name, kw in (("cocro_ref_t", {}), ("cocro_fg_t", dict(shortlist=3)), ("cocro_fg_nocf_t", dict(shortlist=3, cross_fit=False)),
                     ("cocro_fg_m_t", dict(shortlist=3, price="none")), ("cocro_fg_l0_t", dict(shortlist=3, price="zero")),
                     ("cocro_fg_costly_t", dict(shortlist=3, c_op=1e6))):
        cc.register_variant(name, base=fast, **kw)
    yield cc
    for name in [n for n in POLICIES if n.startswith("cocro")]:
        POLICIES.pop(name)


def rows(cfg, seed, pol):
    return pd.DataFrame(simulate(cfg, seed, pol, log_rounds=False)[0])


def transient_world(extra, t_out, cut=(3, 10)):
    """A plain ring (budget not full: additions only) whose links `cut` are down for the first t_out epochs and then repaired."""
    n, eu, ev, ln, conf, budget, base = world(chords=(), extra=extra, full_budget=False)
    P = len(eu)
    down = np.zeros((3, TAU, P), bool)
    down[:, :t_out, list(cut)] = True
    full = ScenarioSet(down=down, node_down=np.zeros((3, TAU, 1), bool), k=K0, thetas=[])
    short = ScenarioSet(down=down[:, :D + 3], node_down=full.node_down[:, :D + 3], k=K0, thetas=[])
    pr, ge = pricer(n, eu, ev, ln, budget)
    return dict(n=n, P=P, conf=conf, base=base, ready=np.zeros(P, int), touched=np.full(P, -10 ** 9), full=full, short=short, pr=pr, ge=ge)


# ------------------------------------------------------------------ gain accuracy
def test_gain_full_equals_the_rollout_g_now_and_single_calls():
    n, eu, ev, ln, conf, budget, base = world(full_budget=False)
    pr, _ = pricer(n, eu, ev, ln, budget)
    P = len(eu)
    rng = np.random.default_rng(0)
    sc = ScenarioSet(down=rng.random((4, TAU, P)) < 0.04, node_down=np.zeros((4, TAU, 1), bool), k=K0, thetas=[])
    ready, touched = np.zeros(P, int), np.full(P, -10 ** 9)
    muts = [(base + 1, None), (base + 2, None), (base + 3, 0)]
    many = pr.gain_full_many(conf, ready, touched, K0, muts, sc)
    assert many.shape == (4, 3)
    for c, m in enumerate(muts):
        r = pr.price(conf, ready, touched, K0, 2, m, sc)
        assert many[:, c].mean() == pytest.approx(r.G_now, abs=1e-9)                 # same surrogate, path and scenarios as the pricer
        assert np.allclose(pr.gain_full(conf, ready, touched, K0, m, sc), many[:, c])  # the shared null path changes nothing


def test_extrapolated_gain_overstates_transient_damage_full_horizon_does_not():
    w = transient_world(((5, 20), (7, 22)), t_out=6)
    cands = [Mutation(add=w["base"]), Mutation(add=w["base"] + 1)]
    gx = w["ge"].estimate(w["conf"], w["ready"], K0, w["short"], cands, TAU).G
    gf = w["pr"].gain_full_many(w["conf"], w["ready"], w["touched"], K0, [(c.add, None) for c in cands], w["full"]).mean(axis=0)
    assert (gf > 0).all() and (gx > 2.5 * gf).all()          # the outage looks permanent inside the short window; it repairs after 6 epochs


def test_full_gain_is_zero_when_the_added_link_never_helps():
    w = transient_world(((5, 20),), t_out=0)               # no outage at all and the ring is already connected: a chord still helps a bit
    g = w["pr"].gain_full_many(w["conf"], w["ready"], w["touched"], K0, [(w["base"], None)], w["full"])
    assert g.mean() > 0
    sat = w["conf"].copy()
    sat[:] = True                                            # every potential link configured: error on the floor, the extra move is a no-op
    g2 = w["pr"].gain_full_many(sat, w["ready"], w["touched"], K0, [(None, None)], w["full"])
    assert g2.mean() == 0.0


# ------------------------------------------------------------------ ranking
def test_rank_inversion_is_corrected_by_the_full_horizon_rerank():
    w = transient_world(((4, 11), (0, 15), (2, 17)), t_out=3)   # (4,11) bypasses the outage (short window loves it); (0,15) helps for the whole run
    feas = [Mutation(add=w["base"] + i) for i in range(3)]
    args = (w["ge"], w["pr"], w["conf"], w["ready"], w["touched"], K0, feas, w["short"], w["full"], TAU)
    old = select_candidate(*args, 0, 0.0)
    new = select_candidate(*args, 3, 0.0)
    gx = w["ge"].estimate(w["conf"], w["ready"], K0, w["short"], feas, TAU).G
    gf = w["pr"].gain_full_many(w["conf"], w["ready"], w["touched"], K0, [(f.add, None) for f in feas], w["full"]).mean(axis=0)
    assert gx[0] > gx[1] and gf[0] < gf[1]                     # the inversion exists in this world
    assert old["j"] == 0 and np.isnan(old["G_full"]) and np.isnan(old["changed"])      # shortlist 0 = original behaviour
    assert new["j"] in (1, 2) and new["changed"] == 1.0
    assert new["G_full"] == pytest.approx(float(gf[new["j"]])) and new["G_full"] > gf[0]
    assert select_candidate(*args, 1, 0.0)["j"] == 0           # risk: a shortlist of 1 cannot correct the ranking (documented limitation)


def test_no_gain_gate_sees_the_full_horizon_gain():
    w = transient_world(((5, 20), (7, 22)), t_out=6)
    feas = [Mutation(add=w["base"]), Mutation(add=w["base"] + 1)]
    args = (w["ge"], w["pr"], w["conf"], w["ready"], w["touched"], K0, feas, w["short"], w["full"], TAU)
    a, b = select_candidate(*args, 0, 0.0), select_candidate(*args, 2, 0.0)
    c_op = 0.5 * (a["G"] + b["G_full"])                        # between the inflated and the simulated gain
    assert a["G"] - c_op > 0 > b["G_full"] - c_op              # the old gate would pass, the new gate stops


def test_gate_is_enforced_in_the_policy_with_a_prohibitive_price():
    r = rows(CFG, 8511, "cocro_fg_costly_t")
    ev = r[r.cocro_evaluated > 0]
    assert r.n_mutations.iloc[-1] == 0 and len(ev) > 0
    assert (ev.cocro_decision == "no_gain").all() and ev.cocro_Gfull.notna().all()


# ------------------------------------------------------------------ cross-fit independence
def test_selection_scenarios_prefix_property_and_independence_from_the_test_set():
    m, sp = fitted()
    short = sp.sample(6, 5, controller_rng(1, 20, 1))
    long = sp.sample(6, 30, controller_rng(1, 20, 1))
    assert np.array_equal(long.down[:, :5], short.down) and np.array_equal(long.node_down[:, :5], short.node_down)   # slicing is exact
    m.update(np.zeros(m.P, bool), np.ones(m.P, bool), m.k + 1)                      # all links up: no shared initial condition
    sel = sp.sample(200, 20, controller_rng(7, 20, 1), plug_in=True).down.astype(float).ravel()
    tst = sp.sample(200, 20, controller_rng(7, 20, 2), plug_in=True).down.astype(float).ravel()
    assert abs(np.corrcoef(sel, tst)[0, 1]) < 0.1 and not np.array_equal(sel, tst)


# ------------------------------------------------------------------ the variant in the engine
@pytest.mark.parametrize("pol", ["cocro_fg_t", "cocro_fg_nocf_t", "cocro_fg_m_t", "cocro_fg_l0_t"])
def test_fg_variants_respect_cap_budget_cooldown_and_log_the_new_columns(pol):
    r = rows(CFG, 8512, pol)
    assert r.n_mutations.iloc[-1] <= CFG.mutation_cap and (r.configured_edges <= r.budget).all()
    mut = r[r.mutation != ""]
    assert (mut.select_outcome == "mutated").all()
    if len(mut) > 1:
        assert (np.diff(mut.epoch.to_numpy()) >= 2).all()
    ev = r[r.cocro_evaluated > 0]
    assert len(ev) > 0 and ev.cocro_Gfull.notna().all() and set(ev.cocro_rank_changed.unique()) <= {0.0, 1.0}


def test_original_variant_does_not_log_full_gain():
    r = rows(CFG, 8512, "cocro_ref_t")
    assert r.cocro_Gfull.isna().all() and r.cocro_rank_changed.isna().all()


def test_fg_is_deterministic_and_seed_sensitive():
    a, b = rows(CFG, 8513, "cocro_fg_t"), rows(CFG, 8513, "cocro_fg_t")
    pd.testing.assert_frame_equal(a, b)
    assert not a.E_hat.equals(rows(CFG, 8514, "cocro_fg_t").E_hat)


@pytest.mark.parametrize("pol", ["cocro_fg_t", "cocro_fg_nocf_t", "cocro_fg_m_t", "cocro_fg_l0_t"])
def test_fg_decisions_near_the_end_of_the_run_do_not_fail(pol):
    cfg = replace(CFG, epochs=14, mutation_cap=8)
    r = rows(cfg, 8515, pol)
    assert len(r) == 14 and (r[r.epoch >= 14 - 1 - cfg.link_setup_epochs].mutation == "").all()


def test_decisions_do_not_use_the_future_environment_trace_fg():
    a = rows(replace(CFG, epochs=30, shock_epoch=20, shock_len=6), 8516, "cocro_fg_t")
    b = rows(replace(CFG, epochs=30, shock_epoch=26, shock_len=6), 8516, "cocro_fg_t")
    early = lambda df: df[df.epoch < 20][["epoch", "mutation", "cocro_decision", "cocro_G", "cocro_Gfull", "cocro_N"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(early(a), early(b))


# ------------------------------------------------------------------ preservation of existing behaviour (golden values taken before Fix 1)
GOLDEN = {  # (variant, seed): (mutations as (epoch, text), decision counts, round(sum of E_hat, 9)) on CFG with CocroParams.fast()
    ("t", 8501): ([(0, "-14-18 +4-16"), (2, "-16-19 +0-11"), (5, "-3-10 +4-8")], {"": 32, "act": 3, "defer": 1}, 22.120693509),
    ("m", 8503): ([(0, "-0-2 +9-16"), (2, "-3-18 +16-19"), (4, "-1-7 +13-18")], {"": 33, "act": 3}, 21.667337171),
    ("nocf", 8503): ([(0, "-0-2 +9-16"), (3, "-6-10 +11-19"), (6, "-2-10 +15-16")], {"": 31, "act": 3, "defer": 2}, 21.564122129),
    ("l0", 8501): ([(0, "-14-18 +4-16"), (2, "-16-19 +0-11"), (4, "-2-11 +13-15")], {"": 33, "act": 3}, 22.230981077),
}


@pytest.mark.parametrize("variant,seed", list(GOLDEN))
def test_existing_cocro_variants_are_unchanged_by_fix1(fg_registered, variant, seed):
    kw = {"t": {}, "m": dict(price="none"), "nocf": dict(cross_fit=False), "l0": dict(price="zero")}[variant]
    fg_registered.register_variant(f"cocro_gold_{variant}", base=fg_registered.CocroParams.fast(), **kw)
    r = rows(CFG, seed, f"cocro_gold_{variant}")
    muts, decisions, sum_e = GOLDEN[(variant, seed)]
    assert [(int(e), m) for e, m in zip(r.epoch, r.mutation) if m] == muts
    assert r.cocro_decision.value_counts().to_dict() == decisions
    assert round(float(r.E_hat.sum()), 9) == sum_e
