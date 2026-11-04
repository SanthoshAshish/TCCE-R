"""v0.8 variants (docs/PROTOCOL_v0.8.md): the intended differences between B6, B7, B8 and the hybrid H1, and the
configurable predictor constants. Small runs only."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.core.predict import Predictor, HazardEstimator
from tccer.policies.v08 import HybridArm, RCPRArm
from tccer.sim.engine import simulate
from test_v06 import StubPipeline
from test_v08_smoke import BASE, make_network, NetworkState, MutationPipeline

LONG = replace(BASE, epochs=40)                                 # long enough for threshold feedback to close
LEGACY = replace(LONG, feedback_rule="before_after")


def rows(cfg, seed, policy):
    return pd.DataFrame(simulate(cfg, seed, policy, log_rounds=False)[0])


# ---- B7 -----------------------------------------------------------------------------------------------------------
def test_b7_selects_legacy_feedback_itself_and_differs_from_b8():
    b7_cf, b7_leg = rows(LONG, 8, "v08_rcpr_legacy"), rows(LEGACY, 8, "v08_rcpr_legacy")
    pd.testing.assert_frame_equal(b7_cf, b7_leg)                # the arm ignores cfg.feedback_rule
    b8 = rows(LONG, 8, "v08_rcpr")
    assert b8.theta_updates_total.iloc[-1] > 0 and b7_cf.theta_updates_total.iloc[-1] > 0   # both adapt (non-vacuous)
    ups8 = " ".join(b8.theta_update.astype(str)); ups7 = " ".join(b7_cf.theta_update.astype(str))
    assert "(" in ups8 and "(" not in ups7                      # B8 logs counterfactual deltas, B7 plain S/F outcomes
    assert not b8.theta.equals(b7_cf.theta)                     # the two feedback rules lead to different thresholds


# ---- B6 -----------------------------------------------------------------------------------------------------------
def test_b6_threshold_is_fixed_and_b8_adapts():
    b6, b8 = rows(LONG, 8, "v08_rcpr_fixed"), rows(LONG, 8, "v08_rcpr")
    assert b6.theta.nunique() == 1 and b6.theta.iloc[0] == LONG.v06_threshold
    assert b8.theta.nunique() > 1


# ---- hybrid -------------------------------------------------------------------------------------------------------
class _St:
    down = np.zeros(3, bool)
    configured = np.ones(3, bool)


def _hybrid(front, theta=50.0, fail_at=()):
    cfg = replace(BASE, feedback_rule="before_after", v06_threshold=theta, v06_kappa=0.2, v08_front=front)
    pipe = StubPipeline(fail_at)
    return HybridArm(cfg, pipe, np.random.default_rng([0, 3])), pipe


def test_hybrid_phase1_moves_do_not_reset_debt_or_register_feedback():
    pol, pipe = _hybrid(front=2)
    debts, acted = [], []
    for k in range(8):
        m = pol.decide(k, {"E_hat": 0.9, "C": 0.0, "V": 0.0}, _St())      # stress 0.45, kappa 0.2 -> +0.25 per epoch
        debts.append(round(pol.stat, 6))
        if m is not None:
            acted.append(k)
    assert acted == [0, 2]                                                 # owed attempts at 2*n_front, state-blind
    assert debts == [round(0.25 * (i + 1), 6) for i in range(8)]           # the debt was never reset
    assert len(pol.feedback.pending) == 0 and pol.n_updates == 0           # no feedback registered
    assert pol.n_front == 2 and pol.n_mutations == 2


def test_hybrid_ordinary_arm_would_reset_debt_and_register_feedback():
    """Control for the test above: the plain B8 arm does reset and register on the same inputs."""
    cfg = replace(BASE, feedback_rule="before_after", v06_threshold=0.1, v06_kappa=0.2)
    pol, pipe = RCPRArm(cfg, StubPipeline(), np.random.default_rng([0, 3])), None
    pol._select = lambda k, state: ("mut", k)                              # bypass the predictive scoring
    pol.decide(0, {"E_hat": 0.9, "C": 0.0, "V": 0.0}, _St())
    assert pol.n_mutations == 1 and pol.stat == 0.0 and len(pol.feedback.pending) == 1


def test_hybrid_phase1_window_and_zero_front():
    pol, _ = _hybrid(front=2)
    assert pol._phase1(0) and pol._phase1(7) and not pol._phase1(8)        # phase 1 ends at epoch 4F at the latest
    pol0, _ = _hybrid(front=0)
    assert not pol0._phase1(0)


def test_hybrid_in_simulation_front_then_risk_aware_within_cap():
    cfg = replace(LONG, v08_front=2, mutation_cap=4)
    r = rows(cfg, 8, "v08_hybrid")
    muts = r.index[r.mutation != ""].tolist()
    assert muts[:2] == [0, 2] and len(muts) <= 4
    assert r.hyb_n_front.iloc[-1] == 2
    assert r.theta_updates_total.iloc[-1] <= len(muts) - 2                 # only phase-2 moves can drive the threshold
    assert (r.configured_edges <= r.budget).all()


# ---- predictor constants ------------------------------------------------------------------------------------------
def test_predictor_constants_are_configurable_with_unchanged_defaults():
    pos, eu, ev, length, init_idx = make_network(BASE, 1)
    st = NetworkState(pos, eu, ev, length, init_idx)
    m = MutationPipeline(BASE, len(init_idx), len(eu))._ranked(st, 0, "lexicographic", None)[0][0][0]
    live = st.live_mask()
    d = Predictor(BASE, HazardEstimator()).evaluate(st, m, live)
    assert d["C"] in (0.25, 1.0)                                           # defaults equal the previously hard-coded 0.25 / 0.75
    c2 = replace(BASE, rcpr_c_rewire=0.4, rcpr_c_release=0.1)
    d2 = Predictor(c2, HazardEstimator()).evaluate(st, m, live)
    assert d2["C"] in (0.4, 0.5) and d2["E"] == d["E"] and d2["R"] == d["R"]
    assert HazardEstimator().rates() == (0.02, 0.1)                        # old default priors
    hz = RCPRArm(replace(BASE, hz_prior_h=0.05, hz_prior_r=0.3), StubPipeline(), np.random.default_rng(0)).hz
    assert hz.rates() == (0.05, 0.3)                                       # arm builds its estimator from cfg


@pytest.mark.parametrize("bad", [dict(hz_window=0), dict(hz_prior_h=0.0), dict(hz_prior_r=1.0), dict(rcpr_c_rewire=-1.0),
                                 dict(hz_prior_w=-1.0)])
def test_invalid_predictor_constants_rejected(bad):
    with pytest.raises(ValueError):
        replace(BASE, **bad)
