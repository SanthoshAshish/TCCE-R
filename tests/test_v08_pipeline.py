"""v0.8 E1/E2 preparation: arm mappings, seed separation, output paths, job construction, predictor-validation analysis.
No large runs: tiny configs only."""
import numpy as np
import pandas as pd
import pytest

import experiments.v08_common as C
from experiments.run_v08 import build_jobs
from experiments.validate_predictor_v08 import PROBE_EPOCHS, ProbePolicy, analyze
from experiments.v06_common import IsolationError
from tccer.config import replace, save_config
from tccer.policies import POLICIES
from tccer.policies.v06 import V06Policy
from tccer.policies.v08 import RCPRArm, RCPRFixedArm
from tccer.sim.engine import simulate
from test_v08_smoke import BASE

LONG = replace(BASE, epochs=40)


def rows(cfg, seed, policy):
    return pd.DataFrame(simulate(cfg, seed, policy, log_rounds=False)[0])


# ---- ablation isolation: each B-step differs from its neighbour in exactly the intended component ---------------------
def test_b5_is_a4_and_differs_from_b6_only_by_the_selector():
    """B6 with its predictive selector replaced by the lexicographic one is A4 (= B5), row for row."""
    class B6Lex(RCPRFixedArm):
        name = "test_b6_lex"
        _select = V06Policy._select
    POLICIES[B6Lex.name] = B6Lex
    try:
        a4, b6lex = rows(LONG, 8, "v06_cusum_ecv"), rows(LONG, 8, B6Lex.name)
    finally:
        del POLICIES[B6Lex.name]
    assert a4.n_mutations.iloc[-1] > 0                                    # non-vacuous
    cols = ["E_hat", "final_error", "lambda2", "components", "C", "V", "mutation", "n_mutations", "v06_stat", "debt",
            "v06_attempt", "v06_attempt_ok", "configured_edges", "gate_rejections"]
    pd.testing.assert_frame_equal(a4[cols], b6lex[cols])


def test_b6_differs_from_b8_only_by_threshold_adaptation():
    """B8 with the threshold update disabled is B6, row for row (same trigger, selector, feedback bookkeeping aside)."""
    class B8Frozen(RCPRArm):
        name = "test_b8_frozen"

        def _apply_outcome(self, m, success):
            self.n_updates += 1                                              # outcome still evaluated, theta not changed
    POLICIES[B8Frozen.name] = B8Frozen
    try:
        b6, b8f = rows(LONG, 8, "v08_rcpr_fixed"), rows(LONG, 8, B8Frozen.name)
        b8 = rows(LONG, 8, "v08_rcpr")
    finally:
        del POLICIES[B8Frozen.name]
    cols = ["E_hat", "mutation", "n_mutations", "v06_stat", "debt", "theta", "rcpr_J_null", "rcpr_J_best"]
    pd.testing.assert_frame_equal(b6[cols], b8f[cols])
    assert b8.theta.nunique() > 1 and not b8[["mutation", "theta"]].equals(b6[["mutation", "theta"]])   # adaptation matters


def test_derived_arms_share_b8_threshold_and_differ_only_in_the_intended_field():
    b8 = replace(BASE, v06_threshold=1.7, v06_kappa=0.23, mutation_cap=6)
    d = C.derive_from_b8(b8, 6)
    assert d["B5"] == d["B6"] == d["B7"] == b8                               # policy class is the only difference
    assert d["H1"] == replace(b8, v08_front=3) and C.derive_from_b8(b8, 3)["H1"].v08_front == 2    # F = ceil(M / 2)
    assert {a: C.HYBRID_F[M] for a, M in (("a", 3), ("b", 6))} == {"a": 2, "b": 3}


def test_arm_tables_are_consistent_and_p1_is_dropped():
    assert set(C.EVAL_ARMS) <= set(C.ARM_POLICY) and "P1" not in C.ARM_POLICY
    assert all(p in POLICIES for p in C.ARM_POLICY.values())
    assert set(C.CALIBRATED_ARMS) | set(C.DERIVED_FROM_B8) | {"A7", "A7M"} == set(C.EVAL_ARMS)
    assert C.ARM_POLICY["B5"] == "v06_cusum_ecv" and C.ARM_POLICY["B1" if "B1" in C.ARM_POLICY else "A1"] == "v06_reactive"
    assert C.ARM_POLICY["A7"] == C.ARM_POLICY["A7M"] == "v06_front"


# ---- seeds and paths --------------------------------------------------------------------------------------------------
EARLIER = [range(0, 20), range(100, 120), range(200, 220), range(300, 320), range(400, 420), range(500, 560),
           range(1000, 1030), range(2000, 2030), range(3000, 3030), range(4000, 4030), range(6000, 6060),
           range(7000, 7060)]


def test_seed_sets_are_disjoint_from_each_other_and_from_every_earlier_range():
    sets = [set(C.TUNING_SEEDS), set(C.DEV_SEEDS), set(C.EVAL_SEEDS), set(C.SMOKE_CAL_SEEDS), set(C.SMOKE_EVAL_SEEDS)]
    assert (min(C.TUNING_SEEDS), max(C.TUNING_SEEDS), len(C.TUNING_SEEDS)) == (8000, 8019, 20)
    assert (min(C.DEV_SEEDS), max(C.DEV_SEEDS), len(C.DEV_SEEDS)) == (8100, 8119, 20)
    assert (min(C.EVAL_SEEDS), max(C.EVAL_SEEDS), len(C.EVAL_SEEDS)) == (9000, 9059, 60)
    assert set(C.SMOKE_CAL_SEEDS) | set(C.SMOKE_EVAL_SEEDS) <= set(C.DEV_SEEDS)          # smoke tests use development seeds only
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    for earlier in EARLIER:
        assert not (set(earlier) & (sets[0] | sets[1] | sets[2]))


def test_stage_guards_reject_foreign_seeds():
    with pytest.raises(IsolationError):
        C.assert_seeds(C.EVAL_SEEDS, range(8000, 8020), "calibration")           # held-out seeds in calibration
    with pytest.raises(IsolationError):
        C.assert_seeds(range(7000, 7003), range(9000, 9060), "evaluation")       # v0.7 held-out seeds in E2
    with pytest.raises(IsolationError):
        C.assert_seeds((8000,), range(8100, 8120), "E1")                         # calibration seeds in E1
    C.assert_seeds(C.DEV_SEEDS, range(8100, 8120), "E1")


def test_all_output_and_config_paths_are_v08_only():
    for p in (C.FROZEN_DIR, C.SMOKE_FROZEN_DIR, C.E2_OUT, C.CAL_OUT):
        assert "v0.8" in p and "v0.7" not in p and "v0.6" not in p
    import experiments.validate_predictor_v08 as E1
    assert E1.OUT.startswith("results/v0.8/") and E1.SMOKE_OUT.startswith("results/v0.8/")


# ---- job construction --------------------------------------------------------------------------------------------------
def test_build_jobs_uses_intended_arms_configs_policies_and_seeds(tmp_path):
    fd = str(tmp_path)
    for s in C.SCENARIOS:
        save_config(C.scenario_config(s), C.frozen_path(fd, "A0", s))
    for s, M in C.CELLS:
        for arm in C.EVAL_ARMS:
            if (s, M, arm) == ("S2_rgg40_background", 3, "B2"):
                continue                                                         # an uncalibratable arm-cell: no file
            cfg = replace(C.scenario_config(s), mutation_cap=M, v06_threshold=0.5)
            save_config(cfg, C.frozen_path(fd, arm, s, M))
    seeds = (9000, 9001)
    jobs = build_jobs(fd, seeds)
    assert len(jobs) == 3 * 2 + 6 * (len(C.EVAL_ARMS) * 2) - 2                  # statics + cells x arms x seeds - excluded
    assert {j[3] for j in jobs} == set(seeds)
    assert all(j[4] == C.ARM_POLICY[j[1]] for j in jobs)
    assert not any(j[0] == "S2_rgg40_background_M3" and j[1] == "B2" for j in jobs)
    assert {j[0] for j in jobs} >= {f"A0_{s}" for s in C.SCENARIOS} and "S3_rgg80_bursty_M6" in {j[0] for j in jobs}


# ---- E1 probe and analysis ---------------------------------------------------------------------------------------------
def test_probe_never_mutates_and_records_within_horizon():
    ProbePolicy.INSTANCES.clear()
    cfg = replace(C.scenario_config("S1_rgg40_bursty"), epochs=20)
    r = rows(cfg, 8100, ProbePolicy.name)
    assert (r.n_mutations == 0).all() and r.configured_edges.nunique() == 1 and (r.mutation == "").all()
    pol = ProbePolicy.INSTANCES[-1]
    assert pol.records and all(0 <= x["epoch"] <= 19 for x in pol.records)
    full = C.scenario_config("S1_rgg40_bursty")
    assert max(PROBE_EPOCHS) + full.link_setup_epochs + 3 <= full.epochs - 1       # replay window stays inside the run


def _synthetic(sign, n_units=12, per=6, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for u in range(n_units):
        for dec in range(4):
            for rank in range(per):
                x = rng.normal()
                y = sign * x + 0.3 * rng.normal()
                out.append({"scenario": "S1", "seed": u, "epoch": dec, "rank": rank, "n_cand": per, "pred_dE_win": x,
                            "pred_dE_1": x, "pred_dJ": x, "pred_dR": 0.0, "real_dE": y, "real_ddisc": 0,
                            "J_a": x, "J_null": 0.5, "allowed": True})
    return pd.DataFrame(out)


def test_validation_analysis_distinguishes_informative_from_uninformative_predictors():
    good, _ = analyze(_synthetic(+1))
    bad, _ = analyze(_synthetic(-1))
    rnd = _synthetic(+1)
    rnd["real_dE"] = np.random.default_rng(5).normal(size=len(rnd))
    null, _ = analyze(rnd)
    assert good["verdict"] == "informative" and good["spearman_dE_win"] > 0.8
    assert bad["verdict"] == "not demonstrated informative" and bad["spearman_dE_win"] < -0.8
    assert null["verdict"] == "not demonstrated informative"


# ---- calibration rule ------------------------------------------------------------------------------------------------
def test_choose_accepts_exact_limit_and_prefers_larger_threshold_on_ties():
    assert C.choose([(0.583, 2.55), (0.55, 4.5)], 3) == (0.583, 2.55, True)          # exactly -15%: accepted (was a float artefact)
    assert C.choose([(0.6, 2.549)], 3)[2] is False                                    # just outside the limit
    assert C.choose([(0.5, 2.0), (0.7, 4.0)], 3)[0] == 0.7                            # tie in distance -> larger threshold
    assert C.choose([(0.5, 3.4), (0.6, 2.9)], 3)[0] == 0.6


def test_amendment_bracket_picks_the_crossing_nearest_to_the_target():
    from experiments.amend_calibration_v08 import bracket
    pts = [(0.60, 9.0), (0.65, 4.7), (0.70, 1.85), (0.75, 0.4)]
    assert bracket(pts, 3) == (0.65, 0.70)
    assert bracket(pts, 6) == (0.60, 0.65)
    with pytest.raises(SystemExit):
        bracket(pts, 20)
