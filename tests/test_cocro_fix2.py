"""COCRO Fix 2 tests: budget reservation by a hurdle family (variant cocro_r, and cocro_fgr = Fix 1 + Fix 2).
The one-step rollout compares 'act now with a*' with 'wait, then follow the base policy pi0'. pi0 acts at the first slot whose estimated net reward R
clears c_op, so when the present opportunity clears that hurdle the wait branch is just 'act next slot' and a larger later event is never 'seen'.
Fix 2 raises pi0's hurdle to h = f R* (R* = pi0's own statistic for a* now; f in a small family, f = 0 included): 'wait for an opportunity at least f times
as good as the present one'. f is chosen on an independent selection scenario set and evaluated on the test set; act only if the one-step rule AND
the hurdle comparison both favour acting (never more eager than before)."""
import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.core.cocro_ops import candidate_pairs
from tccer.core.scenarios import ScenarioSet
from tccer.policies import POLICIES
from tccer.sim.engine import simulate
from test_cocro_policy import D, K0, RULES, T_TOTAL, pricer, world
from test_v08_smoke import BASE

CFG = replace(BASE, epochs=36, mutation_cap=3)
TAU = T_TOTAL - 1 - K0
EXTRA = ((4, 11), (0, 15), (5, 20), (7, 22), (2, 17), (1, 16), (9, 24))
FACTORS = (1.0, 2.0)


@pytest.fixture(scope="module", autouse=True)
def reserve_registered():
    import tccer.policies.cocro as cc
    fast = cc.CocroParams.fast()
    for name, kw in (("cocro_r_t", dict(reserve_factors=FACTORS)), ("cocro_fgr_t", dict(shortlist=3, reserve_factors=FACTORS)),
                     ("cocro_r_nocf_t", dict(reserve_factors=FACTORS, cross_fit=False))):
        cc.register_variant(name, base=fast, **kw)
    yield cc
    for name in [n for n in POLICIES if n.startswith("cocro")]:
        POLICIES.pop(name)


def rows(cfg, seed, pol):
    return pd.DataFrame(simulate(cfg, seed, pol, log_rounds=False)[0])


class W:
    """A plain 30-ring (budget not full: additions only) with candidate chords; a* is the chord the base policy itself would take first."""

    def __init__(self, late_at=None, S=4, noise=0.0, seed=0, links=(3, 10)):
        self.n, self.eu, self.ev, self.ln, self.conf, self.budget, self.base = world(chords=(), extra=EXTRA, full_budget=False)
        self.P = len(self.eu)
        self.ready, self.touched, self.z = np.zeros(self.P, int), np.full(self.P, -10 ** 9), np.zeros(self.P, bool)
        self.pr, self.ge = pricer(self.n, self.eu, self.ev, self.ln, self.budget)
        self.a = candidate_pairs(self.n, self.eu, self.ev, self.ln, self.conf, self.conf, self.z, np.zeros(self.P, bool), self.budget, RULES, 1, 1)[0]
        self.late_at, self.S, self.noise, self.links, self.rng = late_at, S, noise, links, np.random.default_rng(seed)

    def scen(self):
        d = np.zeros((self.S, TAU, self.P), bool)
        if self.noise:
            d |= self.rng.random(d.shape) < self.noise
            d[:, :, list(self.links)] = False
        if self.late_at is not None:
            d[:, self.late_at:, list(self.links)] = True            # a severe, persistent outage that splits the ring from epoch k + 1 + late_at
        return ScenarioSet(down=d, node_down=np.zeros((self.S, TAU, 1), bool), k=K0, thetas=[])

    def one_step(self, m=1, test=None):
        return self.pr.price(self.conf, self.ready, self.touched, K0, m, self.a, test or self.scen())

    def reserve(self, m=1, sel=None, test=None, factors=FACTORS):
        return self.pr.reserve_check(self.conf, self.ready, self.touched, self.z, K0, m, self.a, sel or self.scen(), test or self.scen(), factors)


# ------------------------------------------------------------------ the hurdle itself
def test_hurdle_stops_the_base_policy_acting_on_marginal_opportunities():
    w = W()
    sc = w.scen()
    te = set(range(K0 + 1, K0 + 30))
    slots = set(range(K0 + 1, T_TOTAL, 4))
    e_null = w.pr._path(w.conf, w.ready, w.touched, 0, sc.down[0], K0, te, set(), 0, {}, False)
    acts = w.pr._path(w.conf, w.ready, w.touched, 1, sc.down[0], K0, te, slots, K0 + 1, {}, True, 0.0)
    blocked = w.pr._path(w.conf, w.ready, w.touched, 1, sc.down[0], K0, te, slots, K0 + 1, {}, True, 1e6)
    assert acts[K0 + 29] < e_null[K0 + 29]                          # hurdle 0: the base policy acts and the error falls
    assert all(blocked[t] == e_null[t] for t in te)                 # a prohibitive hurdle: it never acts, the path equals the null path


def test_base_reward_statistic_is_in_the_units_of_the_hurdle():
    w = W()
    R = w.pr.base_reward_now(w.conf, w.ready, w.z, K0, w.a)
    assert R > 0                                                    # the very statistic the base policy compares with c_op + h
    assert w.pr.base_reward_now(w.conf, w.ready, w.z, K0, (None, None)) == 0.0


# ------------------------------------------------------------------ reservation
@pytest.mark.parametrize("late_at", [9, 15])
def test_one_step_rule_spends_the_only_unit_but_the_hurdle_check_reserves_it(late_at):
    w = W(late_at=late_at)
    one, res = w.one_step(1), w.reserve(1)
    assert one.act and one.advantage > 0                            # the limitation: acting now beats 'wait, then act next slot' by one epoch
    assert res.checked and res.advantage0 == pytest.approx(one.advantage, abs=1e-9)
    assert res.advantage < 0 and not res.act and res.f_wait > 0     # a hurdle makes waiting for the outage worth far more than spending the unit now


def test_still_acts_when_there_is_no_larger_later_event():
    w = W(late_at=None)
    res = w.reserve(1)
    assert res.act and res.checked and res.f_wait == 0.0 and res.advantage > 0


def test_empty_or_nonpositive_factors_reproduce_the_one_step_rule():
    w = W(late_at=9)
    one = w.one_step(1)
    for factors in ((), (0.0, -1.0)):
        res = w.reserve(1, factors=factors)
        assert res.act == one.act and not res.checked


def test_reserve_is_never_more_eager_than_the_one_step_rule():
    n_checked = 0
    for seed, (late, p) in enumerate([(None, 0.0), (9, 0.0), (15, 0.02), (None, 0.03), (12, 0.04), (20, 0.0), (None, 0.06), (7, 0.02)]):
        w = W(late_at=late, noise=p, seed=seed)
        for m in (1, 2):
            sel, test = w.scen(), w.scen()
            one, res = w.one_step(m, test), w.reserve(m, sel, test)
            assert res.advantage0 == pytest.approx(one.advantage, abs=1e-9)         # step 1 is exactly the original comparison
            assert (not res.act) or one.act                                          # reserve-act implies one-step-act
            n_checked += res.checked
    assert n_checked >= 4                                                            # the hurdle comparison was actually exercised


def test_chosen_wait_hurdle_is_not_worse_than_hurdle_zero_on_the_selection_set():
    w = W(late_at=9)
    sel, test = w.scen(), w.scen()
    res = w.reserve(1, sel, test)
    hs = [0.0] + [f * res.scale for f in FACTORS]
    _, ww, wa = w.pr._values(w.conf, w.ready, w.touched, K0, 1, w.a, sel, hs, {})
    fam = [0.0] + list(FACTORS)
    assert ww.mean(axis=0)[fam.index(res.f_wait)] >= ww.mean(axis=0)[0] - 1e-12
    assert wa.mean(axis=0)[fam.index(res.f_act)] >= wa.mean(axis=0)[0] - 1e-12


# ------------------------------------------------------------------ cross-fitting independence
def test_hurdles_are_chosen_on_the_selection_set_only():
    sel = W(late_at=15).scen()                                                       # independent selection scenarios
    test_a, test_b = W(late_at=9).scen(), W(late_at=12).scen()                       # two different test sets (outage timing differs)
    w = W(late_at=9)
    ra, rb = w.reserve(1, sel, test_a), w.reserve(1, sel, test_b)
    assert ra.checked and rb.checked
    assert (ra.f_wait, ra.f_act, ra.scale) == (rb.f_wait, rb.f_act, rb.scale)       # the test set cannot influence the hurdle choice
    assert ra.advantage != rb.advantage                                              # but it does determine the evaluated advantage
    # the evaluated advantage equals a direct evaluation on the test set at the chosen hurdles
    _, tw, ta = w.pr._values(w.conf, w.ready, w.touched, K0, 1, w.a, test_a, sorted({0.0, ra.f_wait * ra.scale, ra.f_act * ra.scale}), {})
    need = sorted({0.0, ra.f_wait * ra.scale, ra.f_act * ra.scale})
    adv = ta[:, need.index(ra.f_act * ra.scale)] - w.pr.prm.c_op - tw[:, need.index(ra.f_wait * ra.scale)]
    assert ra.advantage == pytest.approx(float(adv.mean()), abs=1e-9)


# ------------------------------------------------------------------ budget
def test_with_one_unit_left_no_further_action_follows_for_any_hurdle():
    w = W(late_at=9)
    sc = w.scen()
    hs = [0.0, 1.0, 5.0]
    Gn, Ww, Wa = w.pr._values(w.conf, w.ready, w.touched, K0, 1, w.a, sc, hs, {})
    assert np.allclose(Wa, Gn[:, None])                                              # m - 1 = 0: W_act equals G_now whatever the hurdle


def test_hurdle_zero_values_equal_the_original_price_components():
    w = W(late_at=9, noise=0.02, seed=4)
    sc = w.scen()
    Gn, Ww, Wa = w.pr._values(w.conf, w.ready, w.touched, K0, 2, w.a, sc, [0.0], {})
    r = w.one_step(2, sc)
    assert (Gn.mean(), Ww[:, 0].mean(), Wa[:, 0].mean()) == pytest.approx((r.G_now, r.W_wait, r.W_act), abs=1e-9)


# ------------------------------------------------------------------ known limitation found while building Fix 2 (characterisation, not desired behaviour)
def test_known_limitation_two_units_one_step_rule_waits_because_base_policy_ignores_pending_links():
    """With two units and NO later event, the one-step rule still says wait: after acting at k, pi0's first slot (k+2) comes before a* is live
    (k+1+d), and pi0 ranks candidates on the LIVE graph only, so it picks a redundant second chord, while in the wait branch it finds a much better
    one. This biases the rule against acting when >= 2 units remain. Present in the committed code (not introduced by Fix 2); not fixed here."""
    w = W(late_at=None)
    one = w.one_step(2)
    assert not one.act and one.advantage < -2.0
    assert not w.reserve(2).act                                                      # reserve is a subset of the one-step rule, so it inherits this


# ------------------------------------------------------------------ the variants in the engine
@pytest.mark.parametrize("pol", ["cocro_r_t", "cocro_fgr_t", "cocro_r_nocf_t"])
def test_reserve_variants_respect_cap_budget_cooldown_and_log_decisions(pol):
    r = rows(CFG, 8521, pol)
    assert r.n_mutations.iloc[-1] <= CFG.mutation_cap and (r.configured_edges <= r.budget).all()
    mut = r[r.mutation != ""]
    assert (mut.select_outcome == "mutated").all()
    if len(mut) > 1:
        assert (np.diff(mut.epoch.to_numpy()) >= 2).all()
    assert set(r.cocro_decision.unique()) <= {"", "act", "defer", "reserve", "no_gain"}
    assert (r.cocro_decision == "reserve").sum() == r.cocro_reserved_total.iloc[-1]   # the counter matches the logged decisions
    assert r.cocro_adv_res.dropna().shape[0] >= (r.cocro_decision == "reserve").sum()


def test_reserve_variant_is_deterministic_and_seed_sensitive():
    a, b = rows(CFG, 8522, "cocro_r_t"), rows(CFG, 8522, "cocro_r_t")
    pd.testing.assert_frame_equal(a, b)
    assert not a.E_hat.equals(rows(CFG, 8523, "cocro_r_t").E_hat)


@pytest.mark.parametrize("pol", ["cocro_r_t", "cocro_fgr_t"])
def test_reserve_decisions_near_the_end_of_the_run_do_not_fail(pol):
    cfg = replace(CFG, epochs=14, mutation_cap=8)
    r = rows(cfg, 8524, pol)
    assert len(r) == 14 and (r[r.epoch >= 14 - 1 - cfg.link_setup_epochs].mutation == "").all()


def test_reserve_decisions_do_not_use_the_future_environment_trace():
    a = rows(replace(CFG, epochs=30, shock_epoch=20, shock_len=6), 8525, "cocro_r_t")
    b = rows(replace(CFG, epochs=30, shock_epoch=26, shock_len=6), 8525, "cocro_r_t")
    early = lambda df: df[df.epoch < 20][["epoch", "mutation", "cocro_decision", "cocro_N", "cocro_adv", "cocro_adv_res"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(early(a), early(b))


def test_default_parameters_and_unmodified_variants_do_not_use_reservation(reserve_registered):
    cc = reserve_registered
    base = cc.CocroParams()
    assert base.reserve_factors == () and base.shortlist == 0                          # the defaults are the original behaviour
    plain = cc.register_variant("cocro_plain_t", base=cc.CocroParams.fast())            # a variant with no overrides keeps the defaults
    assert plain.params.reserve_factors == () and plain.params.shortlist == 0
    r = rows(CFG, 8526, "cocro_plain_t")
    assert r.cocro_adv_res.isna().all() and r.cocro_res_fw.isna().all() and (r.cocro_decision != "reserve").all() and r.cocro_reserved_total.iloc[-1] == 0
