"""Revision 2 / TRDE: causality-aware debt ledger. Semantics tests on a hand-built 6-node ring with chords (no simulation
randomness), plus wiring tests for the C1 arm. Small runs only."""
import numpy as np
import pandas as pd
import pytest

from tccer.config import replace
from tccer.core.causal_debt import CausalDebtLedger
from tccer.network.state import NetworkState
from tccer.policies import POLICIES
from tccer.sim.engine import simulate
from test_v08_smoke import BASE

N = 6
EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (0, 5), (0, 3)]


def make_state():
    eu = np.array([a for a, b in EDGES]); ev = np.array([b for a, b in EDGES])
    pos = np.zeros((N, 2))
    return NetworkState(pos, eu, ev, np.ones(len(eu)), np.arange(len(eu)))


def ledger(**kw):
    s = make_state()
    return s, CausalDebtLedger(replace(BASE, **kw), N, s.eu, s.ev)


def step(s, L, down_edges=(), E=0.5, hazard=None):
    s.down[:] = False
    for e in down_edges:
        s.down[e] = True
    return L.update(s, E, hazard)


def test_criticality_sums_to_one_and_nonnegative():
    s, L = ledger()
    c = L.criticality(s.configured)
    assert abs(c.sum() - 1.0) < 1e-9 and (c >= 0).all()


def test_no_failure_means_no_debt_whatever_the_error():
    s, L = ledger()
    for _ in range(10):
        assert step(s, L, (), E=1.0) == 0.0          # error with no open damage creates no debt


def test_temporary_episode_is_charged_little_and_written_off():
    s, L = ledger(cd_tau=3)
    d1 = step(s, L, (0,))
    assert L.acc[0] > 0 and L.age[0] == 1
    step(s, L, ())                                    # repaired after 1 epoch (< tau)
    assert L.D == 0.0 and L.scar == 0.0 and L.n_temporary == 1


def test_persistent_failure_accrues_at_full_weight_and_leaves_scar():
    s, L = ledger(cd_tau=2, cd_rho_t=0.25, cd_w_prop=1.0, cd_lam_E=0.0)
    c0 = L.criticality(s.configured)[0]
    step(s, L, (0,)); a1 = L.acc[0]
    step(s, L, (0,)); a2 = L.acc[0]
    step(s, L, (0,)); a3 = L.acc[0]
    assert a1 == pytest.approx(0.25 * c0)             # temporary weight at age 1
    assert a2 - a1 == pytest.approx(c0) and a3 - a2 == pytest.approx(c0)   # persistent weight 1 from age tau
    acc = L.acc[0]
    step(s, L, (), E=1.0)                             # repaired, but consensus has not recovered: scar stays
    assert L.scar == pytest.approx(L.sigma * acc) and L.n_recovered == 1


def test_scar_decays_only_when_consensus_recovered():
    s, L = ledger(cd_tau=1, cd_w_prop=1.0)
    for _ in range(3):
        step(s, L, (0,))
    step(s, L, (), E=1.0); sc = L.scar
    assert sc > 0
    step(s, L, (), E=1.0); assert L.scar == pytest.approx(sc)             # no visible recovery: no decay
    step(s, L, (), E=0.0); assert L.scar == pytest.approx(sc * L.gamma)   # visible recovery: decays


def test_propagated_failure_is_charged_more_and_only_by_strictly_earlier_causes():
    s, L = ledger(cd_tau=1, cd_lam_E=0.0, cd_w_prop=2.0)
    step(s, L, (0,))                                  # edge 0 = (0,1) down; nothing earlier -> not cascaded
    assert not L.cascaded[0]
    step(s, L, (0, 1))                                # edge 1 = (1,2) shares node 1 with earlier failure -> cascaded
    assert L.cascaded[1] and not L.cascaded[0]
    c = L.criticality(s.configured)
    assert L.acc[1] == pytest.approx(2.0 * c[1])
    s2, L2 = ledger(cd_tau=1, cd_lam_E=0.0, cd_w_prop=2.0)
    step(s2, L2, (0, 4))                              # simultaneous (0,1) and (4,5): same-epoch events are not causes
    assert not L2.cascaded.any()


def test_mutation_removing_a_failed_link_settles_exactly_that_item():
    s, L = ledger(cd_tau=1, cd_w_prop=1.0)
    for _ in range(3):
        step(s, L, (0, 2))
    a2 = L.acc[2]
    s.configured[0] = False                           # a mutation removed the failed link 0
    step(s, L, (2,))
    assert L.acc[0] == 0.0 and L.n_compensated == 1
    assert L.acc[2] > a2                              # the other open item is untouched and still accruing
    assert L.D > 0                                    # no blanket reset


def test_forward_liability_is_instantaneous_and_off_by_default():
    s, L = ledger()
    assert step(s, L, (), hazard=(0.2, 0.1)) == 0.0   # cd_w_pred = 0
    s, L = ledger(cd_w_pred=1.0)
    d = step(s, L, (), hazard=(0.2, 0.1))
    assert d == pytest.approx(0.2)                    # sum c_e = 1, no failure so no propagation lift
    assert step(s, L, (), hazard=(0.0001, 0.1)) < 1e-3  # not accumulated


def test_causality_future_edits_cannot_change_past_debt():
    """Ledger is a causal filter: the debt at epoch k depends only on states up to k."""
    seq = [(0,), (0, 1), (1,), (), (2,), (2, 3)]
    out = []
    for cut in (len(seq), 4):
        s, L = ledger(cd_tau=1)
        out.append([step(s, L, d, E=0.4) for d in seq[:cut]])
    assert out[0][:4] == out[1]


@pytest.mark.parametrize("bad", [dict(cd_tau=0), dict(cd_w_prop=0.5), dict(cd_gamma=0.0), dict(cd_scar=1.5),
                                 dict(cd_w_pred=-1.0)])
def test_invalid_ledger_options_rejected(bad):
    with pytest.raises(ValueError):
        replace(BASE, **bad)


def test_c1_arm_runs_is_deterministic_and_logs_ledger_columns():
    cfg = replace(BASE, epochs=30, mutation_cap=3)
    a = pd.DataFrame(simulate(cfg, 8100, "r2_causal", log_rounds=False)[0])
    b = pd.DataFrame(simulate(cfg, 8100, "r2_causal", log_rounds=False)[0])
    pd.testing.assert_frame_equal(a, b)
    for col in ("debt", "cd_open", "cd_scar", "cd_recovered", "theta"):
        assert col in a
    assert a["n_mutations"].max() <= 3
    assert (a["debt"] >= 0).all()
    assert a["configured_edges"].max() <= a["configured_edges"].iloc[0] + 0     # strict edge budget


def test_c1_and_b8_share_everything_but_the_debt_statistic():
    cfg = replace(BASE, epochs=30, mutation_cap=3, v06_threshold=1e9, theta0=1e9, theta_min=2.5e8, theta_max=4e9)
    a = pd.DataFrame(simulate(cfg, 8101, "r2_causal", log_rounds=False)[0])
    b = pd.DataFrame(simulate(cfg, 8101, "v08_rcpr", log_rounds=False)[0])
    assert (a["n_mutations"] == 0).all() and (b["n_mutations"] == 0).all()    # unreachable threshold: both inert
    for col in ("E_hat", "lambda2", "live_edges", "configured_edges"):
        assert (a[col] == b[col]).all()                                        # same environment (common random numbers)


def test_registered_and_baseline_arms_untouched():
    assert "r2_causal" in POLICIES and "v08_rcpr" in POLICIES


# ---- retry rule (r2_retry) and setup-derived persistence age ---------------------------------------------------------
from types import SimpleNamespace  # noqa: E402

from tccer.core.causal_debt import setup_derived_tau  # noqa: E402
from tccer.policies.v08 import CausalDebtArm  # noqa: E402


def test_setup_derived_tau_follows_the_setup_delay():
    assert setup_derived_tau(replace(BASE, link_setup_epochs=2)) == 4
    assert setup_derived_tau(replace(BASE, link_setup_epochs=0)) == 2


def test_invalid_retry_mode_rejected():
    with pytest.raises(ValueError):
        replace(BASE, r2_retry="always")


def _arm(mode):
    s = make_state()
    arm = CausalDebtArm(replace(BASE, r2_retry=mode), None, np.random.default_rng(0))
    arm._state = s
    return s, arm


def test_suppressible_only_when_state_unchanged_and_within_hold():
    s, arm = _arm("state")
    assert not arm._suppressible(5)                           # nothing failed yet
    arm._fail_fp, arm._fail_k = arm._fp(5), 5
    hold = BASE.link_setup_epochs + BASE.pred_horizon_extra
    assert arm._suppressible(6) and arm._suppressible(5 + hold - 1)
    assert not arm._suppressible(5 + hold)                    # hold expired -> re-evaluate
    s.down[2] = True
    assert not arm._suppressible(6)                           # a link failed -> conditions changed
    s.down[2] = False
    s.configured[1] = False
    assert not arm._suppressible(6)                           # topology changed
    s.configured[1] = True
    s.ready_at[3] = 99
    assert not arm._suppressible(6)                           # a pending link's readiness changed


@pytest.mark.parametrize("cell_seed, needs_hit", [(8201, True), (8205, False)])
def test_audit_is_behaviour_neutral_and_state_never_suppresses_a_changed_state(cell_seed, needs_hit):
    cfg = replace(BASE, epochs=40, mutation_cap=4, v06_threshold=0.02, theta0=0.02, theta_min=0.005, theta_max=0.08)
    d = {m: pd.DataFrame(simulate(replace(cfg, r2_retry=m), cell_seed, "r2_causal", log_rounds=False)[0])
         for m in ("none", "audit", "state")}
    for col in ("E_hat", "n_mutations", "mutation", "debt", "v06_attempts_total"):
        assert d["none"][col].tolist() == d["audit"][col].tolist()
    assert d["none"].r2_suppressed.iloc[-1] == 0 and d["audit"].r2_suppressed.iloc[-1] == 0
    st = d["state"].iloc[-1]
    assert st.r2_suppressed == st.r2_suppressible == d["audit"].r2_suppressible.iloc[-1]   # audit predicts state exactly
    assert st.v06_attempts_total == d["none"].v06_attempts_total.iloc[-1] - st.r2_suppressed
    assert d["state"].n_mutations.iloc[-1] <= 4
    if needs_hit:
        assert st.r2_suppressed > 0            # the rule is actually exercised, not vacuous


def test_retry_mode_does_not_touch_other_arms():
    cfg = replace(BASE, epochs=30, mutation_cap=3)
    a = pd.DataFrame(simulate(cfg, 8210, "v08_rcpr", log_rounds=False)[0])
    b = pd.DataFrame(simulate(replace(cfg, r2_retry="state"), 8210, "v08_rcpr", log_rounds=False)[0])
    pd.testing.assert_frame_equal(a, b)


def test_calibration_script_fixes_c1_constants_and_guards_seeds():
    from experiments.calibrate_r2 import R2_SEEDS, make_cfg
    from experiments.v08_common import assert_seeds, scenario_config
    base = scenario_config("S1_rgg40_bursty")
    c1 = make_cfg(base, "C1", 1.0, {"kappa_s": 0.2}, 3)
    b8 = make_cfg(base, "B8", 1.0, {"kappa_s": 0.2}, 3)
    assert (c1.cd_tau, c1.r2_retry) == (base.link_setup_epochs + 2, "state")
    assert (b8.cd_tau, b8.r2_retry) == (2, "none") and b8.v06_kappa == 0.2 and c1.v06_kappa is None
    assert R2_SEEDS == tuple(range(8300, 8320))
    with pytest.raises(Exception):
        assert_seeds(tuple(range(9000, 9060)), range(8300, 8320), "R2 calibration")


def test_amendment_1_rule_and_seed_guards():
    import pandas as pd
    from experiments.calibrate_r2a import GRID_CAP, SEEDS, capped_means
    from experiments.run_r2 import AM_SEEDS, EVAL_SEEDS
    from experiments.v08_common import assert_seeds
    assert SEEDS == tuple(range(8400, 8420)) and AM_SEEDS == tuple(range(9200, 9260)) and GRID_CAP == 6
    assert not set(SEEDS) & set(range(8300, 8320)) and not set(AM_SEEDS) & set(EVAL_SEEDS)     # fresh seeds
    with pytest.raises(Exception):
        assert_seeds(tuple(range(9100, 9160)), range(9200, 9260), "amended")
    d = pd.DataFrame({"scenario": "s", "arm": "C1", "threshold": 1.0, "seed": range(4), "count": [0, 2, 5, 6]})
    assert capped_means(d, 3)["count"].iloc[0] == (0 + 2 + 3 + 3) / 4              # count under cap M = min(count, M)
    assert capped_means(d, 6)["count"].iloc[0] == (0 + 2 + 5 + 6) / 4
